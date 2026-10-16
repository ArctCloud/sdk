package arct

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"sync"
	"testing"
	"time"
)

func fixture(t *testing.T) map[string]json.RawMessage {
	t.Helper()
	raw, err := os.ReadFile("../api/test-cases.json")
	if err != nil {
		t.Fatal(err)
	}
	var f map[string]json.RawMessage
	if json.Unmarshal(raw, &f) != nil {
		t.Fatal("fixture")
	}
	return f
}
func TestSharedErrors(t *testing.T) {
	f := fixture(t)
	type scenario struct {
		Status int
		Body   json.RawMessage
	}
	var cases []scenario
	json.Unmarshal(f["documented_errors"], &cases)
	for _, key := range []string{"charge_unknown", "validation_error", "unknown_error"} {
		var tc scenario
		json.Unmarshal(f[key], &tc)
		cases = append(cases, tc)
	}
	for _, tc := range cases {
		var envelope map[string]map[string]any
		json.Unmarshal(tc.Body, &envelope)
		name := fmt.Sprint(envelope["error"]["code"])
		t.Run(name, func(t *testing.T) {
			c := testClient(t, func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(tc.Status); w.Write(tc.Body) })
			_, err := c.Account.Get(context.Background())
			var e *APIError
			if !errors.As(err, &e) || e.Status != tc.Status || e.Code != name {
				t.Fatalf("%T %v", err, err)
			}
			if name == "validation_error" && strings.Contains(string(tc.Body), "fields") && e.Fields == nil {
				t.Fatal("validation fields")
			}
		})
	}
}
func TestSharedMoneyAndSecrets(t *testing.T) {
	f := fixture(t)
	var money string
	json.Unmarshal(f["money_json"], &money)
	for _, key := range []string{"money_json", "create", "create_delayed", "server", "page_empty", "page_one"} {
		t.Run(key, func(t *testing.T) {
			raw := f[key]
			if key == "money_json" {
				raw = []byte(money)
			}
			var envelope map[string]any
			decoder := json.NewDecoder(strings.NewReader(string(raw)))
			decoder.UseNumber()
			if err := decoder.Decode(&envelope); err != nil {
				t.Fatal(err)
			}
			if _, ok := envelope["id"]; !ok {
				envelope["id"] = "fixture-account"
			}
			raw, err := json.Marshal(envelope)
			if err != nil {
				t.Fatal(err)
			}
			c := testClient(t, func(w http.ResponseWriter, r *http.Request) { w.Write(raw) })
			r, err := c.Account.Get(context.Background())
			if err != nil {
				t.Fatal(err)
			}
			if key == "money_json" && r["amount"] != json.Number("1234567890.123456789") {
				t.Fatal(r)
			}
			for _, repr := range []string{fmt.Sprint(r), fmt.Sprintf("%#v", r), fmt.Sprintf("%+v", r)} {
				if strings.Contains(repr, "fixture-password-only") {
					t.Fatal(repr)
				}
			}
		})
	}
}
func TestCreatePromoAndAmbiguity(t *testing.T) {
	for _, second := range []string{"promo_changed", "hostname_taken"} {
		t.Run(second, func(t *testing.T) {
			calls := 0
			c := testClient(t, func(w http.ResponseWriter, r *http.Request) {
				if r.Method == "GET" {
					fmt.Fprint(w, `{"data":[],"pagination":{"total_pages":0}}`)
					return
				}
				calls++
				code := "promo_changed"
				if calls > 1 {
					code = second
				}
				w.WriteHeader(409)
				fmt.Fprintf(w, `{"error":{"code":%q,"message":"try again"}}`, code)
			})
			_, err := c.Servers.Create(context.Background(), Params{"hostname": "web", "location": "fra", "plan": "small", "image_id": "00000000-0000-0000-0000-000000000001"})
			if calls != 2 || err == nil {
				t.Fatalf("%d %v", calls, err)
			}
			if second == "hostname_taken" {
				var uncertain *UncertainOperationError
				if !errors.As(err, &uncertain) {
					t.Fatalf("%T", err)
				}
			}
		})
	}
}
func TestResizeQuoteExactAndExplicitNull(t *testing.T) {
	for _, explicit := range []bool{false, true} {
		t.Run(fmt.Sprint(explicit), func(t *testing.T) {
			calls := 0
			c := testClient(t, func(w http.ResponseWriter, r *http.Request) {
				calls++
				if r.Method == "GET" {
					fmt.Fprint(w, `{"can_resize":true,"current_plan":"small","pending_resize":null,"plans":[{"slug":"medium","eligible":true,"amount_due_today":0.100000000000000001}]}`)
					return
				}
				var body map[string]json.RawMessage
				json.NewDecoder(r.Body).Decode(&body)
				want := "0.100000000000000001"
				if explicit {
					want = "null"
				}
				if string(body["expected_amount"]) != want {
					t.Fatalf("%s", body["expected_amount"])
				}
				fmt.Fprint(w, `{"status":"pending_payment","resize_id":"resize","to_plan":"medium"}`)
			})
			var err error
			if explicit {
				_, err = c.Servers.Resize(context.Background(), "id", "medium", nil)
			} else {
				_, err = c.Servers.Resize(context.Background(), "id", "medium")
			}
			want := 2
			if explicit {
				want = 1
			}
			if err != nil || calls != want {
				t.Fatalf("%v %d", err, calls)
			}
		})
	}
}
func TestRedirectAndNonJSON(t *testing.T) {
	calls := 0
	c := testClient(t, func(w http.ResponseWriter, r *http.Request) {
		calls++
		w.Header().Set("Location", "https://other.invalid/steal")
		w.WriteHeader(302)
		fmt.Fprint(w, "test-token raw secret")
	})
	_, err := c.Account.Get(context.Background())
	if err == nil || calls != 1 || strings.Contains(err.Error(), "test-token") {
		t.Fatalf("%v %d", err, calls)
	}
}
func TestWaitUnverifiedAndDelete(t *testing.T) {
	for _, action := range []string{"restart", "reinstall", "delete"} {
		t.Run(action, func(t *testing.T) {
			c := testClient(t, func(w http.ResponseWriter, r *http.Request) {
				if action == "delete" {
					w.WriteHeader(404)
					fmt.Fprint(w, `{"error":{"code":"not_found","message":"gone"}}`)
				} else {
					fmt.Fprint(w, `{"id":"id","status":"running"}`)
				}
			})
			out, err := c.Wait(context.Background(), "id", "running", action, Result{"password": Secret("one-time")}, 20*time.Millisecond)
			if action == "delete" {
				if err != nil || out["deleted"] != true {
					t.Fatal(err)
				}
			} else {
				var timeout *TimeoutError
				if !errors.As(err, &timeout) {
					t.Fatalf("%T %v", err, err)
				}
			}
		})
	}
}
func TestAccountBudgetsAndCancellation(t *testing.T) {
	budgets.Lock()
	budgets.events = map[string][]time.Time{}
	budgets.accounts = map[string]string{}
	budgets.Unlock()
	associate("a", "same")
	associate("b", "same")
	for i := 0; i < 5; i++ {
		if err := acquire(context.Background(), "a", false, true); err != nil {
			t.Fatal(err)
		}
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Millisecond)
	defer cancel()
	if err := acquire(ctx, "b", false, true); !errors.Is(err, context.DeadlineExceeded) {
		t.Fatal(err)
	}
	budgets.Lock()
	if len(budgets.events["account:same:write"]) != 5 || len(budgets.events["account:same:paid-hour"]) != 5 {
		t.Fatal("paid write budgets")
	}
	budgets.Unlock()
}
func TestSecretErrorValues(t *testing.T) {
	c := testClient(t, func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(400)
		fmt.Fprint(w, `{"error":{"code":"bad_request","message":"password one-time test-token","details":{"password":"one-time","nested":{"authorization":"Bearer private"},"trace":"one-time test-token Bearer private"}}}`)
	})
	_, err := c.Account.Get(context.Background())
	var e *APIError
	errors.As(err, &e)
	b, _ := json.Marshal(e)
	if strings.Contains(string(b), "one-time") || strings.Contains(string(b), "test-token") || strings.Contains(string(b), "Bearer private") {
		t.Fatal(string(b))
	}
}
func TestLazyListStopsEarly(t *testing.T) {
	calls := 0
	c := testClient(t, func(w http.ResponseWriter, r *http.Request) {
		calls++
		if r.URL.Query().Get("per_page") != "100" {
			t.Error("default page size")
		}
		fmt.Fprint(w, `{"data":[{"id":"one"},{"id":"two"}],"pagination":{"total_pages":10}}`)
	})
	iter := c.Servers.List(context.Background(), Params{})
	if calls != 0 {
		t.Fatal("not lazy")
	}
	for server, err := range iter {
		if err != nil || server["id"] != "one" {
			t.Fatal(err)
		}
		break
	}
	if calls != 1 {
		t.Fatal(calls)
	}
}
func TestWritesResolveSharedAccountAutomatically(t *testing.T) {
	budgets.Lock()
	budgets.events = map[string][]time.Time{}
	budgets.accounts = map[string]string{}
	budgets.Unlock()
	gets, writes := 0, 0
	var mu sync.Mutex
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		defer mu.Unlock()
		if r.URL.Path == "/account" {
			gets++
			fmt.Fprint(w, `{"id":"shared-auto-account"}`)
		} else {
			writes++
			fmt.Fprint(w, `{"status":"applied","resize_id":"resize","to_plan":"medium"}`)
		}
	}))
	defer s.Close()
	a, err := New(Options{Token: "auto-a", BaseURL: s.URL})
	if err != nil {
		t.Fatal(err)
	}
	b, err := New(Options{Token: "auto-b", BaseURL: s.URL})
	if err != nil {
		t.Fatal(err)
	}
	for i := 0; i < 5; i++ {
		if _, err = a.Servers.Resize(context.Background(), "id", "medium", nil); err != nil {
			t.Fatal(err)
		}
	}
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Millisecond)
	defer cancel()
	if _, err = b.Servers.Resize(ctx, "id", "medium", nil); !errors.Is(err, context.DeadlineExceeded) {
		t.Fatal(err)
	}
	mu.Lock()
	defer mu.Unlock()
	if gets != 2 || writes != 5 {
		t.Fatalf("account reads=%d paid writes=%d", gets, writes)
	}
}
func TestConcurrentIdentityResolution(t *testing.T) {
	budgets.Lock()
	budgets.events = map[string][]time.Time{}
	budgets.accounts = map[string]string{}
	budgets.Unlock()
	var mu sync.Mutex
	gets, writes := 0, 0
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		defer mu.Unlock()
		if r.URL.Path == "/account" {
			gets++
			fmt.Fprint(w, `{"id":"concurrent-account"}`)
		} else {
			writes++
			fmt.Fprint(w, `{"id":"id","status":"provisioning"}`)
		}
	}))
	defer s.Close()
	clients := make([]*Client, 10)
	for i := range clients {
		var err error
		clients[i], err = New(Options{Token: "concurrent-token", BaseURL: s.URL})
		if err != nil {
			t.Fatal(err)
		}
	}
	var wg sync.WaitGroup
	for _, c := range clients {
		wg.Add(1)
		go func(c *Client) {
			defer wg.Done()
			if _, err := c.Servers.Start(context.Background(), "id"); err != nil {
				t.Error(err)
			}
		}(c)
	}
	wg.Wait()
	mu.Lock()
	defer mu.Unlock()
	if gets != 1 || writes != 10 {
		t.Fatalf("%d %d", gets, writes)
	}
}
func TestAmbiguousCreateExposesCandidatesWithoutOrder(t *testing.T) {
	posts, gets := 0, 0
	c := testClient(t, func(w http.ResponseWriter, r *http.Request) {
		if r.Method == "GET" {
			gets++
			fmt.Fprint(w, `{"data":[{"id":"candidate","hostname":"web","location":"fra","plan":"small","created_at":"2026-10-17T00:00:00Z"}],"pagination":{"total_pages":1}}`)
			return
		}
		posts++
		if posts == 1 {
			w.WriteHeader(500)
			fmt.Fprint(w, `{"error":{"code":"internal","message":"lost"}}`)
		} else {
			w.WriteHeader(409)
			fmt.Fprint(w, `{"error":{"code":"hostname_taken","message":"reserved"}}`)
		}
	})
	result, err := c.Servers.Create(context.Background(), Params{"hostname": "web", "location": "fra", "plan": "small", "image_id": "00000000-0000-0000-0000-000000000001"})
	var uncertain *UncertainOperationError
	if !errors.As(err, &uncertain) || result != nil || posts != 2 || gets != 1 || uncertain.Details["candidates"] == nil {
		t.Fatalf("%v %v %d %d", result, err, posts, gets)
	}
}
func TestInvalidInputMakesNoRequests(t *testing.T) {
	for _, tc := range []struct {
		op   string
		q, b Params
	}{{"unknown", nil, nil}, {"servers_list", Params{"status": "running|stopped"}, nil}, {"servers_create", nil, Params{"hostname": "web", "location": 1, "plan": "small", "image_id": "00000000-0000-0000-0000-000000000001"}}, {"account_get", Params{"location": "fra"}, nil}, {"servers_create", nil, Params{"hostname": "web", "location": "fra", "plan": "small", "image_id": "00000000-0000-0000-0000-000000000001", "billing_period": "monthly|quarterly"}}} {
		t.Run(tc.op, func(t *testing.T) {
			calls := 0
			c := testClient(t, func(w http.ResponseWriter, r *http.Request) { calls++; fmt.Fprint(w, `{}`) })
			if _, err := c.Call(context.Background(), tc.op, "", tc.q, tc.b); err == nil || calls != 0 {
				t.Fatalf("%v %d", err, calls)
			}
		})
	}
}
