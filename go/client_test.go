package arct

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"reflect"
	"strings"
	"testing"
	"time"
)

func testClient(t *testing.T, handler http.HandlerFunc) *Client {
	t.Helper()
	s := httptest.NewServer(handler)
	t.Cleanup(s.Close)
	c, err := New(Options{Token: "test-token", BaseURL: s.URL, HTTPClient: s.Client(), PollInterval: time.Millisecond, DisableThrottle: true})
	if err != nil {
		t.Fatal(err)
	}
	return c
}
func TestOperationMatrix(t *testing.T) {
	cases := []struct {
		op, method, path string
		body             Params
	}{
		{"account_get", "GET", "/account", nil}, {"servers_list", "GET", "/servers", nil}, {"servers_get", "GET", "/servers/id", nil},
		{"servers_create", "POST", "/servers", Params{"hostname": "web", "location": "fra", "plan": "small", "image_id": "00000000-0000-0000-0000-000000000001"}},
		{"servers_update", "PATCH", "/servers/id", Params{"delete_protection": false, "labels": []string{}}}, {"servers_delete", "DELETE", "/servers/id", nil},
		{"servers_start", "POST", "/servers/id/start", nil}, {"servers_stop", "POST", "/servers/id/stop", nil}, {"servers_restart", "POST", "/servers/id/restart", nil},
		{"servers_reinstall", "POST", "/servers/id/reinstall", Params{"image_id": "00000000-0000-0000-0000-000000000001", "ssh_key_ids": []string{}}},
		{"servers_resize_options", "GET", "/servers/id/resize-options", nil}, {"servers_resize", "POST", "/servers/id/resize", Params{"plan": "medium", "expected_amount": json.Number("4.120000000000001")}},
		{"servers_cancel_deletion", "POST", "/servers/id/cancel-deletion", nil}, {"locations_list", "GET", "/locations", nil}, {"plans_list", "GET", "/plans", nil}, {"images_list", "GET", "/images", nil},
		{"ssh_keys_list", "GET", "/ssh-keys", nil}, {"ssh_keys_get", "GET", "/ssh-keys/id", nil}, {"ssh_keys_create", "POST", "/ssh-keys", Params{"name": "key", "public_key": "ssh-ed25519 AAAA"}}, {"ssh_keys_delete", "DELETE", "/ssh-keys/id", nil},
		{"invoices_list", "GET", "/invoices", nil}, {"invoices_get", "GET", "/invoices/id", nil}}
	for _, tc := range cases {
		t.Run(tc.op, func(t *testing.T) {
			calls := 0
			c := testClient(t, func(w http.ResponseWriter, r *http.Request) {
				calls++
				if r.Method != tc.method || r.URL.Path != tc.path {
					t.Errorf("%s %s", r.Method, r.URL.Path)
				}
				if r.Header.Get("Authorization") != "Bearer test-token" {
					t.Error("auth")
				}
				if tc.body != nil {
					var body Params
					d := json.NewDecoder(r.Body)
					d.UseNumber()
					if err := d.Decode(&body); err != nil {
						t.Fatal(err)
					}
					a, _ := json.Marshal(body)
					b, _ := json.Marshal(tc.body)
					if string(a) != string(b) {
						t.Errorf("body %s != %s", a, b)
					}
				}
				w.Header().Set("Content-Type", "application/json")
				if tc.op == "ssh_keys_delete" {
					w.WriteHeader(204)
				} else {
					fmt.Fprint(w, `{"status":"future_state","amount":0.100000000000000001,"new":true,"data":[],"pagination":{"total_pages":0}}`)
				}
			})
			result, err := c.Call(context.Background(), tc.op, "id", Params{}, tc.body)
			if err != nil {
				t.Fatal(err)
			}
			if calls != 1 {
				t.Fatalf("calls %d", calls)
			}
			if result != nil && result["amount"] != json.Number("0.100000000000000001") {
				t.Fatalf("precision %v", result)
			}
		})
	}
}
func TestChargeUnknownNeverRetries(t *testing.T) {
	for _, status := range []int{409, 429, 500, 503} {
		t.Run(fmt.Sprint(status), func(t *testing.T) {
			calls := 0
			c := testClient(t, func(w http.ResponseWriter, r *http.Request) {
				calls++
				w.WriteHeader(status)
				fmt.Fprint(w, `{"error":{"code":"payment_pending","message":"test-token","details":{"order_intent_id":"support-1","password":"secret"}}}`)
			})
			_, err := c.Call(context.Background(), "servers_create", "", nil, Params{"hostname": "web", "location": "fra", "plan": "small", "image_id": "00000000-0000-0000-0000-000000000001"})
			if err == nil || calls != 1 {
				t.Fatalf("calls=%d err=%v", calls, err)
			}
			if !strings.Contains(fmt.Sprintf("%T", err), "ChargeUnknownError") || strings.Contains(err.Error(), "test-token") {
				t.Fatalf("%T %v", err, err)
			}
		})
	}
}
func TestRetrySafety(t *testing.T) {
	for _, op := range []string{"account_get", "servers_create", "servers_restart"} {
		t.Run(op, func(t *testing.T) {
			calls := 0
			var bodies []string
			c := testClient(t, func(w http.ResponseWriter, r *http.Request) {
				calls++
				var b Params
				json.NewDecoder(r.Body).Decode(&b)
				raw, _ := json.Marshal(b)
				bodies = append(bodies, string(raw))
				w.WriteHeader(500)
				fmt.Fprint(w, `{"error":{"code":"internal","message":"failure"}}`)
			})
			_, err := c.Call(context.Background(), op, "id", nil, Params{"hostname": "web", "location": "fra", "plan": "small", "image_id": "00000000-0000-0000-0000-000000000001"})
			want := 3
			if op == "servers_restart" {
				want = 1
			}
			if err == nil || calls != want {
				t.Fatalf("calls=%d err=%v", calls, err)
			}
			for _, b := range bodies {
				if b != bodies[0] {
					t.Fatal("body changed")
				}
			}
		})
	}
}
func TestCancellation(t *testing.T) {
	c := testClient(t, func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Retry-After", "100")
		w.WriteHeader(429)
		fmt.Fprint(w, `{"error":{"code":"rate_limited","message":"wait"}}`)
	})
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Millisecond)
	defer cancel()
	start := time.Now()
	_, err := c.Call(ctx, "account_get", "", nil, nil)
	if err == nil || time.Since(start) > time.Second {
		t.Fatalf("%v", err)
	}
}
func TestWaitPreservesSecretsAndTransition(t *testing.T) {
	n := 0
	c := testClient(t, func(w http.ResponseWriter, r *http.Request) {
		n++
		state := "running"
		if n == 2 {
			state = "reinstalling"
		}
		fmt.Fprintf(w, `{"id":"id","status":%q}`, state)
	})
	original := Result{"server": map[string]any{"id": "id", "status": "running"}, "password": Secret("one-time")}
	out, err := c.Wait(context.Background(), "id", "running", "reinstall", original, time.Second)
	if err != nil {
		t.Fatal(err)
	}
	if n != 3 || out["password"].(Secret).Reveal() != "one-time" || out["final_server"] == nil {
		t.Fatal(out)
	}
	b, _ := json.Marshal(out)
	if strings.Contains(string(b), "one-time") {
		t.Fatal(string(b))
	}
}
func TestPageAndOmission(t *testing.T) {
	n := 0
	c := testClient(t, func(w http.ResponseWriter, r *http.Request) {
		n++
		if r.URL.Query().Get("location") != "fra" {
			t.Error("filter")
		}
		if n == 1 {
			fmt.Fprint(w, `{"data":[{"id":"a"}],"pagination":{"total_pages":2}}`)
		} else {
			fmt.Fprint(w, `{"data":[],"pagination":{"total_pages":2}}`)
		}
	})
	items, err := c.All(context.Background(), "servers_list", Params{"location": "fra"})
	if err != nil || len(items) != 1 || n != 2 {
		t.Fatalf("%v %v %d", items, err, n)
	}
	if !reflect.DeepEqual(Redact(Params{"password": "secret"}), map[string]any{"password": "[REDACTED]"}) {
		t.Fatal("redaction")
	}
}
