package arct

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"testing"
)

func TestDatacenterRequests(t *testing.T) {
	for _, op := range []string{"datacenters_list", "servers_list", "plans_list", "images_list", "servers_create"} {
		t.Run(op, func(t *testing.T) {
			calls := 0
			c := testClient(t, func(w http.ResponseWriter, r *http.Request) {
				calls++
				if op == "datacenters_list" {
					if r.URL.Path != "/datacenters" || r.URL.Query().Get("page") != "2" || r.URL.Query().Get("per_page") != "10" {
						t.Error(r.URL)
					}
				} else if op == "servers_create" {
					var body Params
					if json.NewDecoder(r.Body).Decode(&body) != nil || body["datacenter"] != "aMs2" {
						t.Error(body)
					}
					if _, exists := body["location"]; exists {
						t.Error("location must remain omitted")
					}
					fmt.Fprint(w, `{"order":{"id":"order","server_id":null},"server":null,"future":true}`)
					return
				} else if r.URL.Query().Get("datacenter") != "aMs2" || r.URL.Query().Get("location") != "AMS" {
					t.Error(r.URL)
				}
				fmt.Fprint(w, `{"data":[{"code":"ams2","future":true}],"pagination":{"total_pages":2}}`)
			})
			q := Params{"datacenter": "aMs2", "location": "AMS"}
			var body Params
			if op == "datacenters_list" {
				q = Params{"page": 2, "per_page": 10}
			} else if op == "servers_create" {
				q = nil
				body = Params{"hostname": "web", "datacenter": "aMs2", "plan": "small", "image_id": "00000000-0000-0000-0000-000000000001"}
			}
			var result Result
			var err error
			if op == "datacenters_list" {
				result, err = c.Datacenters.ListPage(context.Background(), q)
			} else {
				result, err = c.Call(context.Background(), op, "", q, body)
			}
			if err != nil || calls != 1 || result == nil {
				t.Fatalf("%v %d %v", err, calls, result)
			}
			if op == "servers_create" && result["future"] != true {
				t.Fatal("unknown response field lost")
			}
		})
	}
	for _, missing := range []string{"hostname", "plan", "image_id"} {
		body := Params{"hostname": "web", "datacenter": "ams2", "plan": "small", "image_id": "00000000-0000-0000-0000-000000000001"}
		delete(body, missing)
		if err := Validate("servers_create", nil, body); err == nil {
			t.Fatalf("missing %s accepted", missing)
		}
	}
}

func TestDatacenterValidation(t *testing.T) {
	for _, code := range []any{"ams2", "AMS12", "ab1", "ABCDE99", "", "a1", "abcdef1", "ams", "ams123", "ams-2", " ams2", "ams2\n", nil, 2} {
		valid := code == "ams2" || code == "AMS12" || code == "ab1" || code == "ABCDE99"
		for _, op := range []string{"servers_list", "plans_list", "images_list", "servers_create"} {
			t.Run(fmt.Sprintf("%s/%v", op, code), func(t *testing.T) {
				q := Params{"datacenter": code}
				var body Params
				if op == "servers_create" {
					q = nil
					body = Params{"hostname": "web", "datacenter": code, "plan": "small", "image_id": "00000000-0000-0000-0000-000000000001"}
				}
				if err := Validate(op, q, body); (err == nil) != valid {
					t.Fatalf("valid=%v error=%v", valid, err)
				}
			})
		}
	}
	for _, selectors := range []Params{{}, {"location": nil}, {"datacenter": "ams2", "location": "invalid-location"}, {"datacenter": "ams2", "extra": true}} {
		body := Params{"hostname": "web", "plan": "small", "image_id": "00000000-0000-0000-0000-000000000001"}
		for k, v := range selectors {
			body[k] = v
		}
		calls := 0
		c := testClient(t, func(w http.ResponseWriter, r *http.Request) { calls++ })
		if _, err := c.Servers.Create(context.Background(), body); err == nil || calls != 0 {
			t.Fatalf("selectors=%v error=%v calls=%d", selectors, err, calls)
		}
	}
}

func TestCreateSelectorReconciliation(t *testing.T) {
	for _, tc := range []struct {
		name       string
		selectors  Params
		server     Params
		wantMatch  bool
		wantFilter string
	}{
		{"datacenter case", Params{"datacenter": "aMs2"}, Params{"datacenter": "AMS2", "location": "ams"}, true, "datacenter"},
		{"datacenter mismatch", Params{"datacenter": "ams2"}, Params{"datacenter": "ams1", "location": "ams"}, false, "datacenter"},
		{"datacenter absent", Params{"datacenter": "ams2"}, Params{"location": "ams"}, false, "datacenter"},
		{"datacenter null", Params{"datacenter": "ams2"}, Params{"datacenter": nil, "location": "ams"}, false, "datacenter"},
		{"datacenter invalid type", Params{"datacenter": "ams2"}, Params{"datacenter": 2, "location": "ams"}, false, "datacenter"},
		{"plan mismatch", Params{"datacenter": "ams2"}, Params{"datacenter": "ams2", "plan": "large"}, false, "datacenter"},
		{"location case", Params{"location": "LON"}, Params{"location": "lon"}, true, "location"},
		{"location mismatch", Params{"location": "LON"}, Params{"location": "ams"}, false, "location"},
		{"legacy alias", Params{"location": "lon1"}, Params{"datacenter": "LON1", "location": "LON"}, true, "location"},
		{"legacy alias absent", Params{"location": "lon1"}, Params{"location": "LON"}, false, "location"},
		{"legacy alias null", Params{"location": "lon1"}, Params{"datacenter": nil, "location": "LON"}, false, "location"},
		{"datacenter takes precedence", Params{"datacenter": "ams2", "location": "fra"}, Params{"datacenter": "AMS2", "location": "ams"}, true, "datacenter"},
		{"matching location insufficient", Params{"datacenter": "ams2", "location": "ams"}, Params{"datacenter": "ams1", "location": "ams"}, false, "datacenter"},
	} {
		t.Run(tc.name, func(t *testing.T) {
			body := Params{"hostname": "web", "plan": "small", "image_id": "00000000-0000-0000-0000-000000000001"}
			for k, v := range tc.selectors {
				body[k] = v
			}
			tc.server["hostname"], tc.server["id"] = "web", "candidate"
			if _, ok := tc.server["plan"]; !ok {
				tc.server["plan"] = "small"
			}
			posts, gets := 0, 0
			c := testClient(t, func(w http.ResponseWriter, r *http.Request) {
				if r.Method == "POST" {
					posts++
					var received Params
					json.NewDecoder(r.Body).Decode(&received)
					for key, value := range body {
						if received[key] != value {
							t.Error("create body changed", received)
						}
					}
					if posts == 1 {
						w.WriteHeader(500)
						fmt.Fprint(w, `{"error":{"code":"internal","message":"lost"}}`)
					} else {
						w.WriteHeader(409)
						fmt.Fprint(w, `{"error":{"code":"hostname_taken","message":"reserved"}}`)
					}
					return
				}
				gets++
				if r.Method != "GET" || r.URL.Query().Get(tc.wantFilter) != tc.selectors[tc.wantFilter] {
					t.Error(r.Method, r.URL)
				}
				if tc.wantFilter == "datacenter" && r.URL.Query().Get("location") != "" {
					t.Error("legacy selector must not hide a datacenter candidate")
				}
				json.NewEncoder(w).Encode(Params{"data": []any{tc.server}, "pagination": Params{"total_pages": 1}})
			})
			result, err := c.Servers.Create(context.Background(), body)
			var uncertain *UncertainOperationError
			if !errors.As(err, &uncertain) || result != nil || posts != 2 || gets != 1 || uncertain.Details["ownership_verified"] != false {
				t.Fatalf("%v posts=%d gets=%d", err, posts, gets)
			}
			candidates := uncertain.Details["candidates"].([]any)
			if len(candidates) != 1 || candidates[0].(map[string]any)["attributes_match"] != tc.wantMatch {
				t.Fatal(candidates)
			}
		})
	}
}

func TestDatacenterErrors(t *testing.T) {
	for _, tc := range []struct {
		code   string
		status int
	}{
		{"datacenter_not_found", 404}, {"datacenter_mismatch", 422}, {"datacenter_unavailable", 400},
	} {
		t.Run(tc.code, func(t *testing.T) {
			calls := 0
			c := testClient(t, func(w http.ResponseWriter, r *http.Request) {
				calls++
				w.WriteHeader(tc.status)
				fmt.Fprintf(w, `{"error":{"code":%q,"message":"placement rejected","details":{"fields":{"datacenter":"invalid"}}}}`, tc.code)
			})
			_, err := c.Servers.Create(context.Background(), Params{"hostname": "web", "datacenter": "ams2", "location": "fra", "plan": "small", "image_id": "00000000-0000-0000-0000-000000000001"})
			var apiErr *APIError
			if !errors.As(err, &apiErr) || apiErr.Code != tc.code || apiErr.Status != tc.status || apiErr.Fields == nil || calls != 1 {
				t.Fatalf("%v calls=%d", err, calls)
			}
		})
	}
}
