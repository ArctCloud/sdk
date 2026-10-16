package arct

import (
	"context"
	"errors"
	"fmt"
	"sync"
	"time"
)

var budgets = struct {
	sync.Mutex
	events    map[string][]time.Time
	accounts  map[string]string
	resolving map[string]chan struct{}
}{events: map[string][]time.Time{}, accounts: map[string]string{}, resolving: map[string]chan struct{}{}}

func associate(token, account string) {
	budgets.Lock()
	defer budgets.Unlock()
	budgets.accounts[token] = "account:" + account
}
func acquire(ctx context.Context, token string, read, paid bool) error {
	for {
		budgets.Lock()
		now := time.Now()
		type rule struct {
			key    string
			limit  int
			window time.Duration
		}
		rules := []rule{}
		keys := []string{token}
		if account := budgets.accounts[token]; account != "" && !read {
			keys = append(keys, account)
		}
		for _, key := range keys {
			if read {
				rules = append(rules, rule{key + ":read", 120, time.Minute})
			} else {
				rules = append(rules, rule{key + ":write", 30, time.Minute})
				if paid {
					rules = append(rules, rule{key + ":paid-minute", 5, time.Minute}, rule{key + ":paid-hour", 20, time.Hour})
				}
			}
		}
		delay := time.Duration(0)
		for _, r := range rules {
			events := budgets.events[r.key]
			start := 0
			for start < len(events) && !events[start].After(now.Add(-r.window)) {
				start++
			}
			events = events[start:]
			budgets.events[r.key] = events
			if len(events) >= r.limit {
				delay = max(delay, events[len(events)-r.limit].Add(r.window).Sub(now))
			}
		}
		if delay <= 0 {
			for _, r := range rules {
				budgets.events[r.key] = append(budgets.events[r.key], now)
			}
			budgets.Unlock()
			return nil
		}
		budgets.Unlock()
		if err := wait(ctx, delay); err != nil {
			return err
		}
	}
}
func (c *Client) Quote(ctx context.Context, id, plan string) (any, error) {
	r, err := c.Call(ctx, "servers_resize_options", id, nil, nil)
	if err != nil {
		return nil, err
	}
	if r["can_resize"] != true {
		return nil, fmt.Errorf("resize unavailable: %v", r["blocked_reason"])
	}
	plans, _ := r["plans"].([]any)
	for _, v := range plans {
		p, _ := v.(map[string]any)
		if p["slug"] == plan && p["eligible"] == true && p["amount_due_today"] != nil {
			return p["amount_due_today"], nil
		}
	}
	return nil, errors.New("selected plan has no eligible resize quote")
}
func (c *Client) Resize(ctx context.Context, id, plan string, expected ...any) (Result, error) {
	if len(expected) > 1 {
		return nil, errors.New("only one expected amount is allowed")
	}
	var amount any
	if len(expected) == 0 {
		var err error
		amount, err = c.Quote(ctx, id, plan)
		if err != nil {
			return nil, err
		}
	} else {
		amount = expected[0]
	}
	return c.Call(ctx, "servers_resize", id, nil, Params{"plan": plan, "expected_amount": amount})
}
func (c *Client) Wait(ctx context.Context, id, target, action string, original Result, timeout time.Duration) (Result, error) {
	if timeout <= 0 {
		timeout = 600 * time.Second
	}
	ctx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()
	transition := action != "restart" && action != "reinstall"
	var last Result
	if action == "restart" && original["status"] == "restarting" {
		transition = true
	}
	if s, ok := original["server"].(map[string]any); ok {
		state, _ := s["status"].(string)
		if state == "restarting" && action == "restart" || state == "reinstalling" && action == "reinstall" {
			transition = true
		}
	}
	for {
		var r Result
		var err error
		if action == "resize" {
			r, err = c.Call(ctx, "servers_resize_options", id, nil, nil)
			if err == nil {
				_, hasPending := r["pending_resize"]
				plan, hasPlan := r["current_plan"].(string)
				if !hasPending || !hasPlan || plan == "" {
					return nil, &APIError{Kind: "APIError", Code: "invalid_response", Message: "resize observation requires current_plan and pending_resize"}
				}
				if pending := r["pending_resize"]; pending != nil {
					if _, ok := pending.(map[string]any); !ok {
						return nil, &APIError{Kind: "APIError", Code: "invalid_response", Message: "pending_resize must be an object or null"}
					}
				}
			}
			if err == nil && r["pending_resize"] == nil && r["current_plan"] == target {
				out := copyResult(original)
				out["final_resize_options"] = map[string]any(r)
				return out, nil
			}
		} else {
			r, err = c.Call(ctx, "servers_get", id, nil, nil)
			var apiErr *APIError
			if action == "delete" && errors.As(err, &apiErr) && apiErr.Status == 404 {
				out := copyResult(original)
				out["deleted"] = true
				return out, nil
			}
			if err == nil {
				state, ok := r["status"].(string)
				if !ok || state == "" {
					return nil, &APIError{Kind: "APIError", Code: "invalid_response", Message: "server observation requires a status"}
				}
				if state == "restarting" && action == "restart" || state == "reinstalling" && action == "reinstall" {
					transition = true
				}
				if action != "delete" && state == target && transition {
					out := copyResult(original)
					out["final_server"] = map[string]any(r)
					return out, nil
				}
				if state == "error" || state == "suspended" || state == "deleting" && action != "delete" {
					return nil, &APIError{Kind: "APIError", Code: "terminal_state", Message: "server reached terminal state " + state, Details: map[string]any{"last_server": Redact(r)}}
				}
			}
		}
		if r != nil {
			last = r
		}
		if err != nil && ctx.Err() == nil {
			return nil, err
		}
		if err = wait(ctx, c.poll); err != nil {
			if errors.Is(err, context.Canceled) {
				return nil, err
			}
			return nil, &TimeoutError{&APIError{Kind: "TimeoutError", Code: "wait_timeout", Message: "completion unverified; operation continues on the server", Details: map[string]any{"last_state": Redact(last), "original": Redact(original)}}}
		}
	}
}
func copyResult(r Result) Result {
	out := Result{}
	for k, v := range r {
		out[k] = v
	}
	return out
}
func (c *Client) WaitCreated(ctx context.Context, result Result, hostname string, timeout time.Duration) (Result, error) {
	if timeout <= 0 {
		timeout = 600 * time.Second
	}
	ctx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()
	id := ""
	if s, ok := result["server"].(map[string]any); ok {
		id, _ = s["id"].(string)
	}
	if id == "" {
		if order, ok := result["order"].(map[string]any); ok {
			id, _ = order["server_id"].(string)
		}
	}
	for id == "" {
		items, err := c.All(ctx, "servers_list", nil)
		if err != nil {
			return nil, err
		}
		for _, v := range items {
			server, _ := v.(map[string]any)
			if server["hostname"] == hostname {
				candidate, _ := server["id"].(string)
				if id != "" && id != candidate {
					return nil, &UncertainOperationError{&APIError{Kind: "UncertainOperationError", Code: "ambiguous_server", Message: "multiple servers match the acknowledged creation"}}
				}
				id = candidate
			}
		}
		if id != "" {
			break
		}
		if err = wait(ctx, c.poll); err != nil {
			if errors.Is(err, context.Canceled) {
				return nil, err
			}
			return nil, &TimeoutError{&APIError{Kind: "TimeoutError", Code: "wait_timeout", Message: "acknowledged creation has no server yet; pre-orders may exceed the deadline", Details: map[string]any{"original": Redact(result)}}}
		}
	}
	return c.Wait(ctx, id, "running", "create", result, timeout)
}

func (c *Client) ensureAccount(ctx context.Context) error {
	for {
		budgets.Lock()
		if budgets.accounts[c.limiterKey] != "" {
			budgets.Unlock()
			return nil
		}
		if done := budgets.resolving[c.limiterKey]; done != nil {
			budgets.Unlock()
			select {
			case <-ctx.Done():
				return ctx.Err()
			case <-done:
				continue
			}
		}
		done := make(chan struct{})
		budgets.resolving[c.limiterKey] = done
		budgets.Unlock()
		_, err := c.Call(ctx, "account_get", "", nil, nil)
		budgets.Lock()
		known := budgets.accounts[c.limiterKey] != ""
		delete(budgets.resolving, c.limiterKey)
		close(done)
		budgets.Unlock()
		if err != nil {
			return err
		}
		if !known {
			return errors.New("account identity is required before mutations")
		}
		return nil
	}
}

func (c *Client) uncertainCreate(ctx context.Context, e *APIError, body Params, started time.Time) error {
	details := map[string]any{"requested_at": started.UTC().Format(time.RFC3339Nano), "ownership_verified": false, "support_details": e.Details}
	candidates := []any{}
	q := Params{}
	if location, ok := body["location"].(string); ok {
		q["location"] = location
	}
	items, err := c.All(ctx, "servers_list", q)
	if err == nil {
		for _, v := range items {
			server, _ := v.(map[string]any)
			if server["hostname"] != body["hostname"] {
				continue
			}
			candidate := map[string]any{"server": Redact(server), "attributes_match": server["location"] == body["location"] && server["plan"] == body["plan"]}
			if created, parseErr := time.Parse(time.RFC3339Nano, fmt.Sprint(server["created_at"])); parseErr == nil {
				candidate["timestamp_near_request"] = !created.Before(started.Add(-5*time.Minute)) && created.Before(time.Now().Add(5*time.Minute))
			}
			candidates = append(candidates, candidate)
		}
	} else {
		details["discovery_failed"] = true
	}
	details["candidates"] = candidates
	return &UncertainOperationError{&APIError{Status: e.Status, Code: "create_outcome_uncertain", Kind: "UncertainOperationError", Message: "hostname is reserved; candidates cannot prove ownership or recover a password; contact support before creating another server", Details: details}}
}
