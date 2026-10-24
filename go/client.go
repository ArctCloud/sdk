package arct

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math/rand"
	"net/http"
	"net/url"
	"os"
	"strconv"
	"strings"
	"time"

	"arct.cloud/sdk/go/internal/generated"
)

type Params map[string]any
type Result map[string]any
type Secret string

func (s Secret) Reveal() string               { return string(s) }
func (s Secret) String() string               { return "[REDACTED]" }
func (s Secret) GoString() string             { return s.String() }
func (s Secret) MarshalJSON() ([]byte, error) { return json.Marshal(s.String()) }
func (r Result) String() string               { b, _ := json.Marshal(Redact(map[string]any(r))); return string(b) }
func (r Result) GoString() string             { return r.String() }
func (r Result) MarshalJSON() ([]byte, error) { return json.Marshal(Redact(map[string]any(r))) }
func sensitive(k string) bool {
	k = strings.ToLower(k)
	return k == "password" || k == "authorization" || k == "access_token" || k == "api_token" || k == "secret" || k == "token"
}
func Redact(v any) any { return transform(v, false) }
func Reveal(v any) any { return transform(v, true) }
func transform(v any, reveal bool) any {
	switch x := v.(type) {
	case Result:
		return transform(map[string]any(x), reveal)
	case Params:
		return transform(map[string]any(x), reveal)
	case Secret:
		if reveal {
			return x.Reveal()
		}
		return x.String()
	case map[string]any:
		m := map[string]any{}
		for k, v := range x {
			if sensitive(k) && v != nil && !reveal {
				if k == "token" {
					if _, ok := v.(map[string]any); ok {
						m[k] = transform(v, reveal)
						continue
					}
				}
				m[k] = "[REDACTED]"
			} else {
				m[k] = transform(v, reveal)
			}
		}
		return m
	case []any:
		a := make([]any, len(x))
		for i, v := range x {
			a[i] = transform(v, reveal)
		}
		return a
	default:
		return v
	}
}
func secrets(v any) any {
	switch x := v.(type) {
	case map[string]any:
		for k, v := range x {
			if sensitive(k) {
				if s, ok := v.(string); ok {
					x[k] = Secret(s)
					continue
				}
			}
			x[k] = secrets(v)
		}
	case []any:
		for i, v := range x {
			x[i] = secrets(v)
		}
	}
	return v
}

type Options struct {
	Token           string
	BaseURL         string
	HTTPClient      *http.Client
	PollInterval    time.Duration
	DisableThrottle bool
}
type Client struct {
	Account     *AccountService
	Servers     *ServersService
	Locations   *CatalogService
	Datacenters *CatalogService
	Plans       *CatalogService
	Images      *CatalogService
	SSHKeys     *SSHKeysService
	Invoices    *InvoicesService

	api        *generated.APIClient
	token      string
	limiterKey string
	baseURL    string
	poll       time.Duration
	throttle   bool
}

func (c *Client) String() string   { return "Arct(" + c.baseURL + ", token=[REDACTED])" }
func (c *Client) GoString() string { return c.String() }
func New(o Options) (*Client, error) {
	if o.Token == "" {
		o.Token = os.Getenv("ARCT_TOKEN")
	}
	if strings.TrimSpace(o.Token) == "" {
		return nil, errors.New("authentication required: set ARCT_TOKEN or log in")
	}
	if strings.ContainsAny(o.Token, "\r\n") {
		return nil, errors.New("invalid token")
	}
	if o.BaseURL == "" {
		o.BaseURL = "https://api.arct.cloud/v1"
	}
	u, err := url.Parse(o.BaseURL)
	if err != nil || u.Host == "" || u.RawQuery != "" || u.Fragment != "" || u.User != nil {
		return nil, errors.New("invalid API base URL")
	}
	if u.Scheme != "https" && !(u.Scheme == "http" && (u.Hostname() == "localhost" || u.Hostname() == "127.0.0.1" || u.Hostname() == "::1")) {
		return nil, errors.New("HTTPS required except for localhost testing")
	}
	hc := http.Client{Timeout: 30 * time.Second}
	if o.HTTPClient != nil {
		hc = *o.HTTPClient
	}
	if hc.Timeout <= 0 {
		hc.Timeout = 30 * time.Second
	}
	hc.CheckRedirect = func(r *http.Request, via []*http.Request) error { return http.ErrUseLastResponse }
	cfg := generated.NewConfiguration()
	cfg.Servers = generated.ServerConfigurations{{URL: strings.TrimRight(o.BaseURL, "/")}}
	cfg.HTTPClient = &hc
	cfg.AddDefaultHeader("Authorization", "Bearer "+o.Token)
	if o.PollInterval <= 0 {
		o.PollInterval = 5 * time.Second
	}
	hash := sha256.Sum256([]byte(o.Token))
	c := &Client{api: generated.NewAPIClient(cfg), token: o.Token, limiterKey: fmt.Sprintf("token:%x", hash), baseURL: o.BaseURL, poll: o.PollInterval, throttle: !o.DisableThrottle}
	c.Account = &AccountService{c}
	c.Servers = &ServersService{c}
	c.Locations = &CatalogService{c, "locations_list"}
	c.Datacenters = &CatalogService{c, "datacenters_list"}
	c.Plans = &CatalogService{c, "plans_list"}
	c.Images = &CatalogService{c, "images_list"}
	c.SSHKeys = &SSHKeysService{c}
	c.Invoices = &InvoicesService{c}
	return c, nil
}

type APIError struct {
	Status  int            `json:"status"`
	Code    string         `json:"code"`
	Message string         `json:"message"`
	Details map[string]any `json:"details,omitempty"`
	Fields  any            `json:"fields,omitempty"`
	Kind    string         `json:"kind"`
}

func (e *APIError) Error() string    { return e.Kind + ": " + e.Code + ": " + e.Message }
func (e *APIError) GoString() string { return e.Error() }
func (e *APIError) String() string   { return e.Error() }

type AuthenticationError struct{ *APIError }

func (e *AuthenticationError) Unwrap() error { return e.APIError }

type PaymentRequiredError struct{ *APIError }

func (e *PaymentRequiredError) Unwrap() error { return e.APIError }

type PermissionDeniedError struct{ *APIError }

func (e *PermissionDeniedError) Unwrap() error { return e.APIError }

type NotFoundError struct{ *APIError }

func (e *NotFoundError) Unwrap() error { return e.APIError }

type ConflictError struct{ *APIError }

func (e *ConflictError) Unwrap() error { return e.APIError }

type ValidationError struct{ *APIError }

func (e *ValidationError) Unwrap() error { return e.APIError }

type RateLimitError struct{ *APIError }

func (e *RateLimitError) Unwrap() error { return e.APIError }

type ChargeUnknownError struct{ *APIError }

func (e *ChargeUnknownError) Unwrap() error { return e.APIError }

type UncertainOperationError struct{ *APIError }

func (e *UncertainOperationError) Unwrap() error { return e.APIError }

type TimeoutError struct{ *APIError }

func (e *TimeoutError) Unwrap() error { return e.APIError }
func typed(e *APIError) error {
	switch e.Kind {
	case "AuthenticationError":
		return &AuthenticationError{e}
	case "PaymentRequiredError":
		return &PaymentRequiredError{e}
	case "PermissionDeniedError":
		return &PermissionDeniedError{e}
	case "NotFoundError":
		return &NotFoundError{e}
	case "ConflictError":
		return &ConflictError{e}
	case "ValidationError":
		return &ValidationError{e}
	case "RateLimitError":
		return &RateLimitError{e}
	case "ChargeUnknownError":
		return &ChargeUnknownError{e}
	case "UncertainOperationError":
		return &UncertainOperationError{e}
	case "TimeoutError":
		return &TimeoutError{e}
	default:
		return e
	}
}
func (c *Client) clean(s string) string { return strings.ReplaceAll(s, c.token, "[REDACTED]") }
func (c *Client) apiError(status int, raw []byte) error {
	var envelope map[string]any
	d := json.NewDecoder(bytes.NewReader(raw))
	d.UseNumber()
	_ = d.Decode(&envelope)
	item, _ := envelope["error"].(map[string]any)
	code, _ := item["code"].(string)
	msg, _ := item["message"].(string)
	details, _ := item["details"].(map[string]any)
	if code == "" {
		code = "http_error"
	}
	if msg == "" {
		msg = http.StatusText(status)
	}
	if msg == "" {
		msg = "API request failed"
	}
	hidden := []string{c.token}
	collectSecrets(details, &hidden)
	scrub := func(s string) string {
		for _, secret := range hidden {
			if secret != "" {
				s = strings.ReplaceAll(s, secret, "[REDACTED]")
			}
		}
		return s
	}
	msg = scrub(msg)
	code = scrub(code)
	if details != nil {
		details = scrubStrings(Redact(details), scrub).(map[string]any)
	}
	kind := map[int]string{401: "AuthenticationError", 402: "PaymentRequiredError", 403: "PermissionDeniedError", 404: "NotFoundError", 409: "ConflictError", 422: "ValidationError", 429: "RateLimitError"}[status]
	if kind == "" {
		kind = "APIError"
	}
	_, hasIntent := details["order_intent_id"]
	if hasIntent || (status == 409 && code == "payment_pending") {
		kind = "ChargeUnknownError"
	}
	if code == "insufficient_scope" {
		msg += "; use a token with read_write scope"
	}
	if code == "api_access_disabled" {
		msg += "; enable API access in the dashboard"
	}
	return typed(&APIError{Status: status, Code: code, Message: c.clean(msg), Details: details, Fields: details["fields"], Kind: kind})
}
func wait(ctx context.Context, d time.Duration) error {
	if d <= 0 {
		select {
		case <-ctx.Done():
			return ctx.Err()
		default:
			return nil
		}
	}
	t := time.NewTimer(d)
	defer t.Stop()
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-t.C:
		return nil
	}
}
func retryDelay(h http.Header, n int) time.Duration {
	if value := h.Get("Retry-After"); value != "" {
		if seconds, err := strconv.ParseFloat(value, 64); err == nil && seconds >= 0 {
			if seconds > 86400*365 {
				seconds = 86400 * 365
			}
			return time.Duration(seconds * float64(time.Second))
		}
		if date, err := http.ParseTime(value); err == nil {
			return max(time.Duration(0), time.Until(date))
		}
	}
	return time.Duration(100*(1<<n)+rand.Intn(50)) * time.Millisecond
}
func (c *Client) Call(ctx context.Context, operation, id string, query, body Params) (Result, error) {
	if _, ok := ctx.Deadline(); !ok {
		var cancel context.CancelFunc
		ctx, cancel = context.WithTimeout(ctx, 600*time.Second)
		defer cancel()
	}
	if err := validate(operation, query, body); err != nil {
		return nil, err
	}
	raw, err := json.Marshal(body)
	if err != nil {
		return nil, errors.New("invalid JSON request")
	}
	var frozen map[string]any
	if body != nil {
		dec := json.NewDecoder(bytes.NewReader(raw))
		dec.UseNumber()
		if err = dec.Decode(&frozen); err != nil {
			return nil, err
		}
	}
	create := operation == "servers_create"
	read := strings.HasSuffix(operation, "_get") || strings.HasSuffix(operation, "_list") || operation == "servers_resize_options"
	paid := create || operation == "servers_resize"
	if c.throttle && !read {
		if err = c.ensureAccount(ctx); err != nil {
			return nil, err
		}
	}
	started := time.Now()
	promoRetried := false
	for attempt := 0; attempt < 3; attempt++ {
		if err = ctx.Err(); err != nil {
			return nil, err
		}
		if c.throttle {
			if err = acquire(ctx, c.limiterKey, read, paid); err != nil {
				return nil, err
			}
		}
		resp, dispatchErr := c.dispatch(ctx, operation, id, query, frozen)
		if resp == nil {
			if ctx.Err() != nil {
				return nil, ctx.Err()
			}
			if (read || create) && attempt < 2 {
				if err = wait(ctx, retryDelay(nil, attempt)); err != nil {
					return nil, err
				}
				continue
			}
			kind := "APIError"
			if !read {
				kind = "UncertainOperationError"
			}
			return nil, typed(&APIError{Kind: kind, Code: "network_error", Message: "request failed; operation outcome may be unverified"})
		}
		data, readErr := io.ReadAll(resp.Body)
		resp.Body.Close()
		if dispatchErr != nil {
			var generatedError *generated.GenericOpenAPIError
			if !errors.As(dispatchErr, &generatedError) {
				readErr = dispatchErr
			}
		}
		if resp.StatusCode >= 200 && resp.StatusCode < 300 {
			if ctx.Err() != nil {
				return nil, ctx.Err()
			}
			if readErr != nil {
				if (read || create) && attempt < 2 {
					if err = wait(ctx, retryDelay(nil, attempt)); err != nil {
						return nil, err
					}
					continue
				}
				kind := "APIError"
				if !read {
					kind = "UncertainOperationError"
				}
				return nil, typed(&APIError{Status: resp.StatusCode, Kind: kind, Code: "incomplete_response", Message: "response could not be read; completion unverified"})
			}
			bodyless := resp.StatusCode == 204 && (operation == "ssh_keys_delete" || operation == "servers_delete" && query["at_period_end"] != true)
			if bodyless && len(bytes.TrimSpace(data)) == 0 {
				return nil, nil
			}
			var value map[string]any
			decoder := json.NewDecoder(bytes.NewReader(data))
			decoder.UseNumber()
			parseErr := decoder.Decode(&value)
			if parseErr == nil {
				var extra any
				if decoder.Decode(&extra) != io.EOF {
					parseErr = errors.New("expected one complete JSON document")
				}
			}
			if parseErr == nil {
				parseErr = validateResponse(operation, value)
			}
			if parseErr != nil || resp.StatusCode == 204 {
				kind := "APIError"
				if !read {
					kind = "UncertainOperationError"
				}
				return nil, typed(&APIError{Status: resp.StatusCode, Kind: kind, Code: "invalid_response", Message: "invalid API response; operation completion unverified"})
			}
			if ctx.Err() != nil {
				return nil, ctx.Err()
			}
			result := Result(secrets(value).(map[string]any))
			if operation == "account_get" {
				if account, ok := value["id"].(string); ok {
					associate(c.limiterKey, account)
				}
			}
			return result, nil
		}
		apiErr := c.apiError(resp.StatusCode, data)
		var e *APIError
		errors.As(apiErr, &e)
		if e.Kind == "ChargeUnknownError" {
			return nil, apiErr
		}
		if ctx.Err() != nil {
			return nil, ctx.Err()
		}
		if create && attempt > 0 && e.Code == "hostname_taken" {
			return nil, c.uncertainCreate(ctx, e, body, started)
		}
		safeRetry := resp.StatusCode == 429 || ((read || create) && (resp.StatusCode == 500 || resp.StatusCode == 503))
		if create && e.Code == "promo_changed" && !promoRetried {
			safeRetry = true
			promoRetried = true
		}
		if safeRetry && attempt < 2 {
			if err = wait(ctx, retryDelay(resp.Header, attempt)); err != nil {
				return nil, err
			}
			continue
		}
		if !read && !create && (resp.StatusCode == 500 || resp.StatusCode == 503) {
			return nil, &UncertainOperationError{&APIError{Status: e.Status, Code: e.Code, Kind: "UncertainOperationError", Message: "operation completion unverified; inspect resource state before repeating", Details: e.Details}}
		}
		return nil, apiErr
	}
	return nil, errors.New("request attempts exhausted")
}
func (c *Client) All(ctx context.Context, op string, query Params) ([]any, error) {
	out := []any{}
	for item, err := range c.Iterate(ctx, op, query) {
		if err != nil {
			return nil, err
		}
		out = append(out, map[string]any(item))
	}
	return out, nil
}

func collectSecrets(v any, hidden *[]string) {
	switch x := v.(type) {
	case map[string]any:
		for k, v := range x {
			if sensitive(k) {
				if s, ok := v.(string); ok {
					*hidden = append(*hidden, s)
				}
			}
			collectSecrets(v, hidden)
		}
	case []any:
		for _, v := range x {
			collectSecrets(v, hidden)
		}
	}
}
func scrubStrings(v any, scrub func(string) string) any {
	switch x := v.(type) {
	case string:
		return scrub(x)
	case map[string]any:
		for k, v := range x {
			x[k] = scrubStrings(v, scrub)
		}
	case []any:
		for i, v := range x {
			x[i] = scrubStrings(v, scrub)
		}
	}
	return v
}
func RevealPasswords(v any) any {
	switch x := v.(type) {
	case Result:
		return RevealPasswords(map[string]any(x))
	case Params:
		return RevealPasswords(map[string]any(x))
	case map[string]any:
		m := map[string]any{}
		for k, v := range x {
			if k == "password" {
				switch s := v.(type) {
				case Secret:
					m[k] = s.Reveal()
				default:
					m[k] = v
				}
				continue
			}
			if sensitive(k) {
				if _, ok := v.(map[string]any); !ok && v != nil {
					m[k] = "[REDACTED]"
					continue
				}
			}
			m[k] = RevealPasswords(v)
		}
		return m
	case []any:
		a := make([]any, len(x))
		for i, v := range x {
			a[i] = RevealPasswords(v)
		}
		return a
	case Secret:
		return x.String()
	default:
		return v
	}
}
func (c *Client) Close() { c.api.GetConfig().HTTPClient.CloseIdleConnections() }
