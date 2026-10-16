package cli

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"testing"
	"time"

	arct "arct.cloud/sdk/go"
)

const id = "00000000-0000-0000-0000-000000000001"

func appTest(t *testing.T, h http.HandlerFunc) (*App, *bytes.Buffer, *bytes.Buffer) {
	t.Helper()
	s := httptest.NewServer(h)
	t.Cleanup(s.Close)
	out, errOut := new(bytes.Buffer), new(bytes.Buffer)
	a := &App{In: strings.NewReader(""), Out: out, Err: errOut, ConfigPath: filepath.Join(t.TempDir(), "arct", "config.json"), Getenv: func(k string) string {
		if k == "ARCT_TOKEN" {
			return "secret-token"
		}
		if k == "ARCT_BASE_URL" {
			return s.URL
		}
		return ""
	}, NewClient: func(o arct.Options) (*arct.Client, error) {
		o.DisableThrottle = true
		o.PollInterval = time.Millisecond
		return arct.New(o)
	}}
	return a, out, errOut
}
func TestCommands(t *testing.T) {
	cases := []struct {
		args         []string
		method, path string
	}{
		{[]string{"account", "get"}, "GET", "/account"}, {[]string{"servers", "list", "--status", "running", "--location", "fra", "--page", "2", "--per-page", "7"}, "GET", "/servers"}, {[]string{"servers", "get", id}, "GET", "/servers/" + id},
		{[]string{"servers", "create", "--hostname", "web", "--location", "fra", "--plan", "small", "--image", id, "--billing-period", "yearly", "--ssh-key", "", "--coupon-code", "SAVE", "--enable-backups=false", "--yes"}, "POST", "/servers"},
		{[]string{"servers", "update", id, "--hostname", "web", "--delete-protection=false", "--label", ""}, "PATCH", "/servers/" + id},
		{[]string{"servers", "delete", id, "--at-period-end", "--yes"}, "DELETE", "/servers/" + id},
		{[]string{"servers", "start", id}, "POST", "/servers/" + id + "/start"}, {[]string{"servers", "stop", id}, "POST", "/servers/" + id + "/stop"}, {[]string{"servers", "restart", id}, "POST", "/servers/" + id + "/restart"},
		{[]string{"servers", "reinstall", id, "--image", id, "--hostname", "new", "--ssh-key", "", "--yes"}, "POST", "/servers/" + id + "/reinstall"},
		{[]string{"servers", "resize-options", id}, "GET", "/servers/" + id + "/resize-options"}, {[]string{"servers", "resize", id, "--plan", "medium", "--expected-amount", "4.120000000000001", "--yes"}, "POST", "/servers/" + id + "/resize"},
		{[]string{"servers", "cancel-deletion", id, "--yes"}, "POST", "/servers/" + id + "/cancel-deletion"},
		{[]string{"locations", "list"}, "GET", "/locations"}, {[]string{"plans", "list", "--location", "fra"}, "GET", "/plans"}, {[]string{"images", "list", "--location", "fra"}, "GET", "/images"},
		{[]string{"ssh-keys", "list"}, "GET", "/ssh-keys"}, {[]string{"ssh-keys", "get", id}, "GET", "/ssh-keys/" + id}, {[]string{"ssh-keys", "create", "--name", "laptop", "--public-key", "ssh-ed25519 AAAA"}, "POST", "/ssh-keys"}, {[]string{"ssh-keys", "delete", id, "--yes"}, "DELETE", "/ssh-keys/" + id},
		{[]string{"invoices", "list"}, "GET", "/invoices"}, {[]string{"invoices", "get", id}, "GET", "/invoices/" + id}}
	for _, tc := range cases {
		t.Run(strings.Join(tc.args[:2], " "), func(t *testing.T) {
			calls := 0
			a, out, errOut := appTest(t, func(w http.ResponseWriter, r *http.Request) {
				calls++
				if r.Method != tc.method || r.URL.Path != tc.path {
					t.Errorf("%s %s", r.Method, r.URL.Path)
				}
				if tc.args[0] == "servers" && tc.args[1] == "create" {
					var b map[string]any
					json.NewDecoder(r.Body).Decode(&b)
					if b["enable_backups"] != false || len(b["ssh_key_ids"].([]any)) != 0 || b["coupon_code"] != "SAVE" || b["billing_period"] != "yearly" {
						t.Fatal(b)
					}
				}
				if tc.args[1] == "resize" {
					var b map[string]json.RawMessage
					json.NewDecoder(r.Body).Decode(&b)
					if string(b["expected_amount"]) != "4.120000000000001" {
						t.Fatal(string(b["expected_amount"]))
					}
				}
				w.Header().Set("Content-Type", "application/json")
				fmt.Fprint(w, `{"id":"`+id+`","password":"one-time","status":"accepted","order":{"id":"order","server_id":"`+id+`"},"server":{"id":"`+id+`","status":"provisioning"},"resize_id":"resize","to_plan":"medium","can_resize":true,"current_plan":"small","pending_resize":null,"plans":[],"data":[],"pagination":{"total_pages":1}}`)
			})
			args := append(append([]string{}, tc.args...), "--output", "json")
			code := a.Run(context.Background(), args)
			if code != 0 || calls != 1 {
				t.Fatalf("exit=%d calls=%d stderr=%s", code, calls, errOut)
			}
			if strings.Contains(out.String(), "one-time") || strings.Contains(out.String(), "secret-token") {
				t.Fatal(out)
			}
		})
	}
}
func TestUsageBeforeMutation(t *testing.T) {
	cases := [][]string{{"servers", "create", "--hostname", "web", "--location", "fra", "--plan", "small", "--image", id}, {"servers", "delete", id}, {"servers", "reinstall", id, "--image", id}, {"servers", "delete", id, "--at-period-end", "--wait", "--yes"}, {"servers", "resize", id, "--plan", "medium", "--expected-amount", "NaN", "--yes"}, {"servers", "get"}, {"servers", "get", id, "--wat"}, {"servers", "list", "--status", "error"}}
	for _, args := range cases {
		t.Run(strings.Join(args, " "), func(t *testing.T) {
			calls := 0
			a, _, errOut := appTest(t, func(w http.ResponseWriter, r *http.Request) { calls++; fmt.Fprint(w, `{}`) })
			if code := a.Run(context.Background(), args); code != 2 || calls != 0 {
				t.Fatalf("exit=%d calls=%d %s", code, calls, errOut)
			}
		})
	}
}
func TestWaitOutputAndColumns(t *testing.T) {
	calls := 0
	a, out, errOut := appTest(t, func(w http.ResponseWriter, r *http.Request) {
		calls++
		w.Header().Set("Content-Type", "application/json")
		if r.Method == "POST" {
			w.WriteHeader(201)
			fmt.Fprint(w, `{"order":{"id":"order","server_id":"`+id+`"},"server":null,"password":"one-time"}`)
		} else {
			fmt.Fprint(w, `{"id":"`+id+`","status":"running"}`)
		}
	})
	code := a.Run(context.Background(), []string{"servers", "create", "--hostname", "web", "--location", "fra", "--plan", "small", "--image", id, "--yes", "--wait", "--show-password", "--output", "json"})
	if code != 0 || calls != 2 || !strings.Contains(out.String(), "one-time") || !strings.Contains(out.String(), "final_server") {
		t.Fatalf("%d %d %s %s", code, calls, out, errOut)
	}
}
func TestLocalContexts(t *testing.T) {
	a, out, errOut := appTest(t, func(w http.ResponseWriter, r *http.Request) { fmt.Fprint(w, `{"id":"account"}`) })
	for _, args := range [][]string{{"auth", "login", "--context", "work"}, {"context", "list"}, {"context", "use", "work"}, {"auth", "status"}, {"auth", "logout", "--context", "work"}} {
		out.Reset()
		errOut.Reset()
		if code := a.Run(context.Background(), args); code != 0 {
			t.Fatalf("%v %d %s", args, code, errOut)
		}
		if strings.Contains(out.String(), "secret-token") {
			t.Fatal(out)
		}
	}
}
func TestAllPagesAndTable(t *testing.T) {
	for _, all := range []bool{false, true} {
		t.Run(fmt.Sprint(all), func(t *testing.T) {
			calls := 0
			a, out, errOut := appTest(t, func(w http.ResponseWriter, r *http.Request) {
				calls++
				if r.URL.Query().Get("location") != "fra" {
					t.Error("lost filter")
				}
				fmt.Fprintf(w, `{"data":[{"id":"%d","hostname":"web"}],"pagination":{"total_pages":2}}`, calls)
			})
			args := []string{"servers", "list", "--location", "fra", "--columns", "hostname,id", "--no-header"}
			want := 1
			if all {
				args = append(args, "--all")
				want = 2
			}
			if code := a.Run(context.Background(), args); code != 0 || calls != want || strings.Contains(out.String(), "hostname") || !strings.Contains(out.String(), "web") {
				t.Fatalf("%d calls=%d out=%s err=%s", code, calls, out, errOut)
			}
		})
	}
}
func TestFlagAndBodyDistinctions(t *testing.T) {
	for _, test := range []struct {
		name     string
		args     []string
		expected string
	}{
		{"empty update", []string{"servers", "update", id, "--delete-protection=false", "--label", ""}, `{"delete_protection":false,"labels":[]}`},
		{"reinstall", []string{"servers", "reinstall", id, "--image", id, "--hostname", "new", "--ssh-key", id, "--yes"}, `{"hostname":"new","image_id":"` + id + `","ssh_key_ids":["` + id + `"]}`},
		{"omitted create", []string{"servers", "create", "--hostname", "web", "--location", "fra", "--plan", "small", "--image", id, "--yes"}, `{"hostname":"web","image_id":"` + id + `","location":"fra","plan":"small"}`},
		{"null coupon", []string{"servers", "create", "--hostname", "web", "--location", "fra", "--plan", "small", "--image", id, "--coupon-code-null", "--yes"}, `{"coupon_code":null,"hostname":"web","image_id":"` + id + `","location":"fra","plan":"small"}`},
	} {
		t.Run(test.name, func(t *testing.T) {
			a, _, errOut := appTest(t, func(w http.ResponseWriter, r *http.Request) {
				var body map[string]any
				json.NewDecoder(r.Body).Decode(&body)
				raw, _ := json.Marshal(body)
				if string(raw) != test.expected {
					t.Errorf("%s != %s", raw, test.expected)
				}
				fmt.Fprint(w, `{"id":"`+id+`","status":"accepted","order":{"id":"order","server_id":null},"server":{"id":"`+id+`","status":"provisioning"}}`)
			})
			if code := a.Run(context.Background(), test.args); code != 0 {
				t.Fatalf("%d %s", code, errOut)
			}
		})
	}
}
func TestExitAndJSONErrors(t *testing.T) {
	for _, tc := range []struct {
		status int
		body   string
		exit   int
	}{{401, `{"error":{"code":"invalid_token","message":"secret-token"}}`, 1}, {409, `{"error":{"code":"payment_pending","message":"pending","details":{"order_intent_id":"support"}}}`, 3}} {
		t.Run(fmt.Sprint(tc.status), func(t *testing.T) {
			a, out, errOut := appTest(t, func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(tc.status); fmt.Fprint(w, tc.body) })
			if code := a.Run(context.Background(), []string{"account", "get", "--output", "json"}); code != tc.exit || out.Len() != 0 || !json.Valid(errOut.Bytes()) || strings.Contains(errOut.String(), "secret-token") {
				t.Fatalf("%d out=%s err=%s", code, out, errOut)
			}
		})
	}
	a, _, errOut := appTest(t, func(w http.ResponseWriter, r *http.Request) { fmt.Fprint(w, `{}`) })
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if code := a.Run(ctx, []string{"account", "get"}); code != 130 {
		t.Fatalf("%d %s", code, errOut)
	}
}
func TestPublicKeyStdinAndLoginStdin(t *testing.T) {
	a, _, errOut := appTest(t, func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/ssh-keys" {
			var b map[string]string
			json.NewDecoder(r.Body).Decode(&b)
			if b["public_key"] != "ssh-ed25519 AAAA" {
				t.Error(b)
			}
		}
		fmt.Fprint(w, `{"id":"account"}`)
	})
	a.In = strings.NewReader("ssh-ed25519 AAAA\n")
	if code := a.Run(context.Background(), []string{"ssh-keys", "create", "--name", "key", "--public-key-file", "-"}); code != 0 {
		t.Fatalf("%d %s", code, errOut)
	}
	getenv := a.Getenv
	a.Getenv = func(k string) string {
		if k == "ARCT_TOKEN" {
			return ""
		}
		return getenv(k)
	}
	a.In = strings.NewReader("secret-token\n")
	if code := a.Run(context.Background(), []string{"auth", "login", "--context", "work"}); code != 0 {
		t.Fatalf("%d %s", code, errOut)
	}
	if code := a.Run(context.Background(), []string{"context", "delete", "work"}); code != 0 {
		t.Fatalf("%d %s", code, errOut)
	}
}
func TestPasswordFlagDoesNotRevealTokens(t *testing.T) {
	a, out, errOut := appTest(t, func(w http.ResponseWriter, r *http.Request) {
		fmt.Fprint(w, `{"order":{"id":"order","server_id":null},"server":null,"password":"one-time","access_token":"should-hide"}`)
	})
	code := a.Run(context.Background(), []string{"servers", "create", "--hostname", "web", "--location", "fra", "--plan", "small", "--image", id, "--yes", "--show-password", "--output", "json"})
	if code != 0 || !strings.Contains(out.String(), "one-time") || strings.Contains(out.String(), "should-hide") {
		t.Fatalf("%d %s %s", code, out, errOut)
	}
}
func TestWaitTimeoutKeepsOneTimeResult(t *testing.T) {
	a, out, errOut := appTest(t, func(w http.ResponseWriter, r *http.Request) {
		if r.Method == "POST" {
			fmt.Fprint(w, `{"server":{"id":"`+id+`","status":"provisioning"},"order":{"id":"order","server_id":"`+id+`"},"password":"one-time"}`)
		} else {
			fmt.Fprint(w, `{"id":"`+id+`","status":"provisioning"}`)
		}
	})
	code := a.Run(context.Background(), []string{"servers", "create", "--hostname", "web", "--location", "fra", "--plan", "small", "--image", id, "--yes", "--wait", "--timeout", "10ms", "--show-password", "--output", "json"})
	if code != 3 || !strings.Contains(out.String(), "one-time") || !strings.Contains(out.String(), "order") {
		t.Fatalf("%d out=%s err=%s", code, out, errOut)
	}
}
func TestReinstall202WaitAndDeleteModes(t *testing.T) {
	for _, action := range []string{"reinstall", "delete"} {
		t.Run(action, func(t *testing.T) {
			calls := 0
			a, out, errOut := appTest(t, func(w http.ResponseWriter, r *http.Request) {
				calls++
				if action == "delete" {
					if r.Method == "DELETE" {
						w.WriteHeader(204)
					} else {
						w.WriteHeader(404)
						fmt.Fprint(w, `{"error":{"code":"not_found","message":"deleted"}}`)
					}
					return
				}
				if r.Method == "POST" {
					w.WriteHeader(202)
					fmt.Fprint(w, `{"server":{"id":"`+id+`","status":"reinstalling"},"password":"one-time"}`)
				} else {
					fmt.Fprint(w, `{"id":"`+id+`","status":"running"}`)
				}
			})
			args := []string{"servers", action, id, "--yes", "--wait", "--output", "json"}
			if action == "reinstall" {
				args = append(args, "--image", id, "--show-password")
			}
			if code := a.Run(context.Background(), args); code != 0 || calls != 2 {
				t.Fatalf("%d %d %s %s", code, calls, out, errOut)
			}
			if action == "reinstall" && !strings.Contains(out.String(), "one-time") {
				t.Fatal(out)
			}
			if action == "delete" && !strings.Contains(out.String(), `"deleted":true`) {
				t.Fatal(out)
			}
		})
	}
}
