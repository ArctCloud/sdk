package arct

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"strings"
	"testing"
	"time"
)

type transportFunc func(*http.Request) (*http.Response, error)

func (f transportFunc) RoundTrip(r *http.Request) (*http.Response, error) { return f(r) }

type partialBody struct {
	data   string
	cancel context.CancelFunc
}

func (b *partialBody) Read(p []byte) (int, error) {
	n := copy(p, b.data)
	b.data = b.data[n:]
	if b.cancel != nil {
		b.cancel()
	}
	return n, io.ErrUnexpectedEOF
}
func (b *partialBody) Close() error { return nil }
func TestScheduledDeleteRejectsWrongTypesBeforeIdentity(t *testing.T) {
	for _, v := range []any{"true", "false", 1, nil} {
		t.Run(fmt.Sprint(v), func(t *testing.T) {
			calls := 0
			c, err := New(Options{Token: "invalid-delete", HTTPClient: &http.Client{Transport: transportFunc(func(r *http.Request) (*http.Response, error) {
				calls++
				return &http.Response{StatusCode: 204, Header: http.Header{}, Body: io.NopCloser(strings.NewReader(""))}, nil
			})}})
			if err != nil {
				t.Fatal(err)
			}
			if _, err = c.Call(context.Background(), "servers_delete", "id", Params{"at_period_end": v}, nil); err == nil || calls != 0 {
				t.Fatalf("calls=%d err=%v", calls, err)
			}
		})
	}
	for _, v := range []bool{true, false} {
		t.Run(fmt.Sprint(v), func(t *testing.T) {
			c := testClient(t, func(w http.ResponseWriter, r *http.Request) {
				if r.URL.Query().Get("at_period_end") != fmt.Sprint(v) {
					t.Fatal(r.URL.RawQuery)
				}
				fmt.Fprint(w, `{"id":"id","status":"deleting"}`)
			})
			if _, err := c.Call(context.Background(), "servers_delete", "id", Params{"at_period_end": v}, nil); err != nil {
				t.Fatal(err)
			}
		})
	}
}
func TestOriginalBodyReadErrorAndCancellation(t *testing.T) {
	for _, cancelRead := range []bool{false, true} {
		t.Run(fmt.Sprint(cancelRead), func(t *testing.T) {
			ctx, cancel := context.WithCancel(context.Background())
			defer cancel()
			calls := 0
			c, err := New(Options{Token: "partial", DisableThrottle: true, HTTPClient: &http.Client{Transport: transportFunc(func(r *http.Request) (*http.Response, error) {
				calls++
				var during context.CancelFunc
				if cancelRead {
					during = cancel
				}
				return &http.Response{StatusCode: 202, Header: http.Header{"Content-Type": []string{"application/json"}}, Body: &partialBody{data: `{"status":"restarting"}`, cancel: during}}, nil
			})}})
			if err != nil {
				t.Fatal(err)
			}
			out, err := c.Servers.Restart(ctx, "id")
			if out != nil || err == nil || calls != 1 {
				t.Fatalf("result=%v err=%v calls=%d", out, err, calls)
			}
			if cancelRead && !errors.Is(err, context.Canceled) {
				t.Fatal(err)
			}
			if !cancelRead {
				var uncertain *UncertainOperationError
				if !errors.As(err, &uncertain) {
					t.Fatalf("%T", err)
				}
			}
		})
	}
}
func TestChargeMarkerPrecedesBodyReadError(t *testing.T) {
	calls := 0
	c, err := New(Options{Token: "partial-charge", DisableThrottle: true, HTTPClient: &http.Client{Transport: transportFunc(func(r *http.Request) (*http.Response, error) {
		calls++
		return &http.Response{StatusCode: 500, Header: http.Header{"Content-Type": []string{"application/json"}}, Body: &partialBody{data: `{"error":{"code":"failure","message":"unknown","details":{"order_intent_id":"support"}}}`}}, nil
	})}})
	if err != nil {
		t.Fatal(err)
	}
	_, err = c.Servers.Create(context.Background(), Params{"hostname": "web", "location": "fra", "plan": "small", "image_id": "00000000-0000-0000-0000-000000000001"})
	var charge *ChargeUnknownError
	if !errors.As(err, &charge) || calls != 1 {
		t.Fatalf("%T %v %d", err, err, calls)
	}
}
func TestMalformedListResponseRejected(t *testing.T) {
	for _, body := range []string{"", "null", "{}", `{"data":"wrong","pagination":{"total_pages":1}}`, `{"data":[]} garbage`, `{"data":[],"pagination":{"total_pages":1}} {}`, `{"data":[null],"pagination":{"total_pages":1}}`, `{"data":[],"pagination":{}}`, `{"data":[],"pagination":{"total_pages":"1"}}`} {
		t.Run(body, func(t *testing.T) {
			c := testClient(t, func(w http.ResponseWriter, r *http.Request) { fmt.Fprint(w, body) })
			items, err := c.All(context.Background(), "servers_list", nil)
			if err == nil || items != nil {
				t.Fatalf("%v %v", items, err)
			}
			for _, err := range c.Servers.List(context.Background(), nil) {
				if err == nil {
					t.Fatal("iterator silently succeeded")
				}
				break
			}
		})
	}
}
func TestMalformedMutationResponseUncertain(t *testing.T) {
	for _, body := range []string{"", "null", "{}", `{"status":"restarting"} garbage`} {
		t.Run(body, func(t *testing.T) {
			calls := 0
			c := testClient(t, func(w http.ResponseWriter, r *http.Request) { calls++; fmt.Fprint(w, body) })
			out, err := c.Servers.Restart(context.Background(), "id")
			var uncertain *UncertainOperationError
			if out != nil || !errors.As(err, &uncertain) || calls != 1 {
				t.Fatalf("%v %T %v %d", out, err, err, calls)
			}
		})
	}
}
func TestUnsupportedBodylessSuccessRejected(t *testing.T) {
	c := testClient(t, func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(204) })
	_, err := c.Servers.Start(context.Background(), "id")
	var uncertain *UncertainOperationError
	if !errors.As(err, &uncertain) {
		t.Fatalf("%T %v", err, err)
	}
}
func TestWaitAcknowledgedTopLevelRestartAndRequiredState(t *testing.T) {
	for _, state := range []string{"running", "error", "suspended", "deleting"} {
		t.Run(state, func(t *testing.T) {
			c := testClient(t, func(w http.ResponseWriter, r *http.Request) { fmt.Fprintf(w, `{"id":"id","status":%q}`, state) })
			action := "wait"
			original := Result(nil)
			if state == "running" {
				action = "restart"
				original = Result{"status": "restarting"}
			}
			if _, err := c.Wait(context.Background(), "id", state, action, original, 20*time.Millisecond); err != nil {
				t.Fatal(err)
			}
		})
	}
	for _, body := range []string{`{"current_plan":"medium"}`, `{"pending_resize":null}`, `{"status":null}`} {
		t.Run(body, func(t *testing.T) {
			c := testClient(t, func(w http.ResponseWriter, r *http.Request) { fmt.Fprint(w, body) })
			action, target := "resize", "medium"
			if strings.Contains(body, "status") {
				action, target = "wait", "running"
			}
			if out, err := c.Wait(context.Background(), "id", target, action, nil, 20*time.Millisecond); err == nil || out != nil {
				t.Fatalf("%v %v", out, err)
			}
		})
	}
}
func TestBodyReadFailuresRetryOnlySafeOperations(t *testing.T) {
	for _, op := range []string{"account_get", "servers_create", "servers_reinstall"} {
		t.Run(op, func(t *testing.T) {
			calls := 0
			c, err := New(Options{Token: "partial-safe", DisableThrottle: true, HTTPClient: &http.Client{Transport: transportFunc(func(r *http.Request) (*http.Response, error) {
				calls++
				return &http.Response{StatusCode: 200, Header: http.Header{"Content-Type": []string{"application/json"}}, Body: &partialBody{data: `{"status":"accepted"}`}}, nil
			})}})
			if err != nil {
				t.Fatal(err)
			}
			body := Params(nil)
			if op == "servers_create" {
				body = Params{"hostname": "web", "location": "fra", "plan": "small", "image_id": "00000000-0000-0000-0000-000000000001"}
			}
			if op == "servers_reinstall" {
				body = Params{"image_id": "00000000-0000-0000-0000-000000000001"}
			}
			out, err := c.Call(context.Background(), op, "id", nil, body)
			want := 3
			if op == "servers_reinstall" {
				want = 1
			}
			if out != nil || err == nil || calls != want {
				t.Fatalf("%v %v %d", out, err, calls)
			}
		})
	}
}

type canceledBody struct {
	io.Reader
	cancel context.CancelFunc
}

func (b *canceledBody) Read(p []byte) (int, error) {
	n, err := b.Reader.Read(p)
	b.cancel()
	return n, err
}
func (b *canceledBody) Close() error { return nil }
func TestCanceledSuccessfulBodyNeverReturnsResult(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	c, err := New(Options{Token: "canceled-success", DisableThrottle: true, HTTPClient: &http.Client{Transport: transportFunc(func(r *http.Request) (*http.Response, error) {
		return &http.Response{StatusCode: 202, Header: http.Header{"Content-Type": []string{"application/json"}}, Body: &canceledBody{Reader: strings.NewReader(`{"status":"restarting"}`), cancel: cancel}}, nil
	})}})
	if err != nil {
		t.Fatal(err)
	}
	out, err := c.Servers.Restart(ctx, "id")
	if out != nil || !errors.Is(err, context.Canceled) {
		t.Fatalf("%v %v", out, err)
	}
}
func TestScheduledDeleteCannotAcceptBodylessResult(t *testing.T) {
	c := testClient(t, func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(204) })
	out, err := c.Servers.Delete(context.Background(), "id", true)
	var uncertain *UncertainOperationError
	if out != nil || !errors.As(err, &uncertain) {
		t.Fatalf("%v %v", out, err)
	}
}
func TestOperationSpecificSuccessEnvelopes(t *testing.T) {
	for _, op := range []string{"account_get", "servers_create", "servers_get", "servers_update", "servers_delete", "servers_start", "servers_stop", "servers_restart", "servers_reinstall", "servers_resize", "servers_resize_options", "servers_cancel_deletion", "ssh_keys_create", "ssh_keys_get", "invoices_get"} {
		t.Run(op, func(t *testing.T) {
			calls := 0
			c := testClient(t, func(w http.ResponseWriter, r *http.Request) {
				calls++
				w.WriteHeader(201)
				fmt.Fprint(w, `{"unexpected":"shape"}`)
			})
			body := Params(nil)
			switch op {
			case "servers_create":
				body = Params{"hostname": "web", "location": "fra", "plan": "small", "image_id": "00000000-0000-0000-0000-000000000001"}
			case "servers_update":
				body = Params{"labels": []string{}}
			case "servers_reinstall":
				body = Params{"image_id": "00000000-0000-0000-0000-000000000001"}
			case "servers_resize":
				body = Params{"plan": "medium", "expected_amount": nil}
			case "ssh_keys_create":
				body = Params{"name": "key", "public_key": "ssh-ed25519 AAAA"}
			}
			out, err := c.Call(context.Background(), op, "id", nil, body)
			var api *APIError
			mutation := !strings.HasSuffix(op, "_get") && op != "servers_resize_options"
			if out != nil || !errors.As(err, &api) || api.Code != "invalid_response" || api.Status != 201 || calls != 1 {
				t.Fatalf("%v %v calls=%d", out, err, calls)
			}
			if mutation {
				var uncertain *UncertainOperationError
				if !errors.As(err, &uncertain) {
					t.Fatalf("%T", err)
				}
			}
		})
	}
}
func TestCreateAcknowledgementRequiresTypedOrderAndServer(t *testing.T) {
	for _, body := range []string{`{"order":{},"server":null}`, `{"order":{"id":"order","server_id":null}}`, `{"order":{"id":"order","server_id":null},"server":"wrong"}`, `{"order":{"id":"order","server_id":null},"server":null,"password":123}`} {
		t.Run(body, func(t *testing.T) {
			calls := 0
			c := testClient(t, func(w http.ResponseWriter, r *http.Request) { calls++; w.WriteHeader(201); fmt.Fprint(w, body) })
			out, err := c.Servers.Create(context.Background(), Params{"hostname": "web", "location": "fra", "plan": "small", "image_id": "00000000-0000-0000-0000-000000000001"})
			var uncertain *UncertainOperationError
			if out != nil || !errors.As(err, &uncertain) || calls != 1 {
				t.Fatalf("%v %v %d", out, err, calls)
			}
		})
	}
}
func TestAcknowledgementOptionalFieldsAndUnknownValues(t *testing.T) {
	f := fixture(t)
	for _, tc := range []struct{ name, op, key string }{{"create", "servers_create", "create"}, {"delayed", "servers_create", "create_delayed"}, {"reinstall", "servers_reinstall", "server"}, {"resize", "servers_resize", ""}, {"server", "servers_get", "server"}} {
		t.Run(tc.name, func(t *testing.T) {
			var value map[string]any
			if tc.key != "" {
				decoder := json.NewDecoder(strings.NewReader(string(f[tc.key])))
				decoder.UseNumber()
				if err := decoder.Decode(&value); err != nil {
					t.Fatal(err)
				}
			}
			if tc.op == "servers_reinstall" {
				value = map[string]any{"server": value}
			}
			if tc.op == "servers_resize" {
				value = map[string]any{"resize_id": "resize", "status": "future_resize", "to_plan": "medium"}
			}
			delete(value, "password")
			value["extra"] = true
			if tc.op == "servers_get" {
				value["status"] = "future_server"
			}
			raw, err := json.Marshal(value)
			if err != nil {
				t.Fatal(err)
			}
			calls := 0
			c := testClient(t, func(w http.ResponseWriter, r *http.Request) { calls++; fmt.Fprint(w, string(raw)) })
			body := Params(nil)
			switch tc.op {
			case "servers_create":
				body = Params{"hostname": "web", "location": "fra", "plan": "small", "image_id": "00000000-0000-0000-0000-000000000001"}
			case "servers_reinstall":
				body = Params{"image_id": "00000000-0000-0000-0000-000000000001"}
			case "servers_resize":
				body = Params{"plan": "medium", "expected_amount": nil}
			}
			out, err := c.Call(context.Background(), tc.op, "id", nil, body)
			if err != nil || out["extra"] != true || calls != 1 {
				t.Fatalf("%v %v %d", out, err, calls)
			}
			if _, hasPassword := out["password"]; hasPassword {
				t.Fatal("optional password was fabricated")
			}
		})
	}
}
