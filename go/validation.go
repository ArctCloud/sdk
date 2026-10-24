package arct

import (
	"encoding/json"
	"fmt"
	"math/big"
	"regexp"
	"slices"
	"strings"
	"unicode/utf8"
)

var hostnamePattern = regexp.MustCompile(`^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?$`)
var labelPattern = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9-]{0,62}$`)
var locationPattern = regexp.MustCompile(`^[A-Za-z0-9-]{1,10}$`)
var datacenterPattern = regexp.MustCompile(`^[A-Za-z]{2,5}[0-9]{1,2}$`)
var planPattern = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9_.-]{0,49}$`)
var uuidPattern = regexp.MustCompile(`^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$`)
var decimalPattern = regexp.MustCompile(`^[+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$`)

func ValidID(id string) bool { return uuidPattern.MatchString(id) }
func ValidAmount(v any) bool {
	s := fmt.Sprint(v)
	if !decimalPattern.MatchString(s) {
		return false
	}
	n, ok := new(big.Rat).SetString(s)
	return ok && n.Sign() >= 0
}
func validate(op string, q, b Params) error {
	switch op {
	case "account_get", "servers_list", "servers_get", "servers_create", "servers_update", "servers_delete", "servers_start", "servers_stop", "servers_restart", "servers_reinstall", "servers_resize_options", "servers_resize", "servers_cancel_deletion", "locations_list", "datacenters_list", "plans_list", "images_list", "ssh_keys_list", "ssh_keys_get", "ssh_keys_create", "ssh_keys_delete", "invoices_list", "invoices_get":
	default:
		return fmt.Errorf("unknown operation")
	}
	queries := ""
	switch op {
	case "servers_list":
		queries = "page per_page status location datacenter"
	case "plans_list", "images_list":
		queries = "page per_page location datacenter"
	case "locations_list", "datacenters_list", "ssh_keys_list", "invoices_list":
		queries = "page per_page"
	case "servers_delete":
		queries = "at_period_end"
	}
	for k, v := range q {
		if !slices.Contains(strings.Fields(queries), k) {
			return fmt.Errorf("unsupported query field %s", k)
		}
		switch k {
		case "at_period_end":
			if _, ok := v.(bool); !ok {
				return fmt.Errorf("at_period_end must be boolean")
			}
		case "page", "per_page":
			n, ok := v.(int)
			limit := 100000
			if k == "per_page" {
				limit = 100
			}
			if !ok || n < 1 || n > limit {
				return fmt.Errorf("%s must be 1..%d", k, limit)
			}
		case "status":
			if _, ok := v.(string); !ok {
				return fmt.Errorf("status must be a string")
			}
			if !slices.Contains(strings.Fields("provisioning running stopped restarting reinstalling restoring deleting suspended pre_order"), fmt.Sprint(v)) {
				return fmt.Errorf("unsupported status filter")
			}
		case "location":
			value, ok := v.(string)
			if !ok || !locationPattern.MatchString(value) {
				return fmt.Errorf("invalid location")
			}
		case "datacenter":
			value, ok := v.(string)
			if !ok || !datacenterPattern.MatchString(value) {
				return fmt.Errorf("invalid datacenter")
			}
		}
	}
	allowed := map[string]string{"servers_create": "hostname location datacenter plan image_id billing_period ssh_key_ids coupon_code enable_backups", "servers_update": "hostname delete_protection labels", "servers_reinstall": "image_id ssh_key_ids hostname", "servers_resize": "plan expected_amount", "ssh_keys_create": "name public_key"}
	fields, hasBody := allowed[op]
	if !hasBody {
		return nil
	}
	if b == nil {
		return fmt.Errorf("request body required")
	}
	for k, v := range b {
		if !slices.Contains(strings.Fields(fields), k) {
			return fmt.Errorf("unknown request field %s", k)
		}
		switch k {
		case "hostname":
			s, ok := v.(string)
			if !ok || !hostnamePattern.MatchString(s) {
				return fmt.Errorf("invalid hostname")
			}
		case "location":
			value, ok := v.(string)
			if !ok || !locationPattern.MatchString(value) {
				return fmt.Errorf("invalid location")
			}
		case "datacenter":
			value, ok := v.(string)
			if !ok || !datacenterPattern.MatchString(value) {
				return fmt.Errorf("invalid datacenter")
			}
		case "plan":
			value, ok := v.(string)
			if !ok || !planPattern.MatchString(value) {
				return fmt.Errorf("invalid plan")
			}
		case "image_id":
			value, ok := v.(string)
			if !ok || !ValidID(value) {
				return fmt.Errorf("invalid image ID")
			}
		case "billing_period":
			if _, ok := v.(string); !ok {
				return fmt.Errorf("billing_period must be a string")
			}
			if !slices.Contains(strings.Fields("monthly quarterly semi_annual yearly"), fmt.Sprint(v)) {
				return fmt.Errorf("invalid billing period")
			}
		case "enable_backups", "delete_protection":
			if _, ok := v.(bool); !ok {
				return fmt.Errorf("%s must be boolean", k)
			}
		case "coupon_code":
			if v == nil {
				continue
			}
			s, ok := v.(string)
			if !ok || utf8.RuneCountInString(s) < 1 || utf8.RuneCountInString(s) > 64 {
				return fmt.Errorf("invalid coupon code")
			}
		case "expected_amount":
			if v != nil && !ValidAmount(v) {
				return fmt.Errorf("expected amount must be a nonnegative decimal")
			}
		case "ssh_key_ids", "labels":
			raw, _ := json.Marshal(v)
			var values []string
			if len(raw) == 0 || raw[0] != '[' || json.Unmarshal(raw, &values) != nil {
				return fmt.Errorf("%s must be an array of strings", k)
			}
			limit := 100
			if k == "ssh_key_ids" {
				limit = 20
			}
			if len(values) > limit {
				return fmt.Errorf("too many %s", k)
			}
			for _, s := range values {
				if k == "ssh_key_ids" && !ValidID(s) {
					return fmt.Errorf("invalid SSH key ID")
				}
				if k == "labels" && (len(s) == 0 || len(s) > 63 || !labelPattern.MatchString(s)) {
					return fmt.Errorf("invalid label")
				}
			}
		case "name", "public_key":
			s, ok := v.(string)
			limit := 255
			if k == "public_key" {
				limit = 8192
			}
			if !ok || utf8.RuneCountInString(s) < 1 || utf8.RuneCountInString(s) > limit {
				return fmt.Errorf("invalid %s", k)
			}
		}
	}
	required := map[string]string{"servers_create": "hostname plan image_id", "servers_reinstall": "image_id", "servers_resize": "plan", "ssh_keys_create": "name public_key"}
	for _, k := range strings.Fields(required[op]) {
		if _, ok := b[k]; !ok {
			return fmt.Errorf("%s required", k)
		}
	}
	if op == "servers_create" && b["datacenter"] == nil && b["location"] == nil {
		return fmt.Errorf("datacenter or location required")
	}
	if op == "servers_update" && len(b) == 0 {
		return fmt.Errorf("at least one update field required")
	}
	return nil
}
func Validate(operation string, query, body Params) error { return validate(operation, query, body) }

func validateResponse(operation string, value map[string]any) error {
	if len(value) == 0 {
		return fmt.Errorf("expected a nonempty JSON object")
	}
	if strings.HasSuffix(operation, "_list") {
		items, ok := value["data"].([]any)
		if !ok {
			return fmt.Errorf("expected a data array")
		}
		for _, v := range items {
			if item, ok := v.(map[string]any); !ok || item == nil {
				return fmt.Errorf("expected object list items")
			}
		}
		pagination, ok := value["pagination"].(map[string]any)
		if !ok {
			return fmt.Errorf("expected pagination metadata")
		}
		total, ok := pagination["total_pages"].(json.Number)
		if !ok {
			return fmt.Errorf("expected integer total_pages")
		}
		n, err := total.Int64()
		if err != nil || n < 0 {
			return fmt.Errorf("expected nonnegative integer total_pages")
		}
	}

	switch operation {
	case "servers_create":
		order, ok := value["order"].(map[string]any)
		if !ok || !responseString(order, "id") {
			return fmt.Errorf("expected order acknowledgement")
		}
		serverID, hasID := order["server_id"]
		if !hasID {
			return fmt.Errorf("expected nullable order server_id")
		}
		if serverID != nil {
			if id, ok := serverID.(string); !ok || id == "" {
				return fmt.Errorf("expected order server_id")
			}
		}
		server, hasServer := value["server"]
		if !hasServer || server != nil && !responseServer(server) {
			return fmt.Errorf("expected nullable server acknowledgement")
		}
		if password := value["password"]; password != nil {
			if _, ok := password.(string); !ok {
				return fmt.Errorf("expected nullable password")
			}
		}
	case "servers_reinstall":
		if !responseServer(value["server"]) {
			return fmt.Errorf("expected reinstalled server")
		}
		if password := value["password"]; password != nil {
			if _, ok := password.(string); !ok {
				return fmt.Errorf("expected nullable password")
			}
		}
	case "servers_resize":
		if !responseString(value, "resize_id") || !responseString(value, "status") || !responseString(value, "to_plan") {
			return fmt.Errorf("expected resize acknowledgement")
		}
	case "servers_resize_options":
		if _, ok := value["can_resize"].(bool); !ok {
			return fmt.Errorf("expected can_resize")
		}
		if !responseString(value, "current_plan") {
			return fmt.Errorf("expected current_plan")
		}
		pending, hasPending := value["pending_resize"]
		if !hasPending {
			return fmt.Errorf("expected nullable pending_resize")
		}
		if pending != nil {
			if _, ok := pending.(map[string]any); !ok {
				return fmt.Errorf("expected pending_resize object")
			}
		}
		plans, ok := value["plans"].([]any)
		if !ok {
			return fmt.Errorf("expected resize plans")
		}
		for _, item := range plans {
			plan, ok := item.(map[string]any)
			if !ok || !responseString(plan, "slug") {
				return fmt.Errorf("expected resize plan")
			}
			if _, ok := plan["eligible"].(bool); !ok {
				return fmt.Errorf("expected plan eligibility")
			}
			amount, hasAmount := plan["amount_due_today"]
			if !hasAmount {
				return fmt.Errorf("expected nullable resize amount")
			}
			if amount != nil {
				if _, ok := amount.(json.Number); !ok {
					return fmt.Errorf("expected numeric resize amount")
				}
			}
		}
	case "servers_get", "servers_update", "servers_delete", "servers_start", "servers_stop", "servers_restart", "servers_cancel_deletion":
		if !responseServer(value) {
			return fmt.Errorf("expected server acknowledgement")
		}
	case "account_get", "ssh_keys_get", "ssh_keys_create", "invoices_get":
		if !responseString(value, "id") {
			return fmt.Errorf("expected resource identifier")
		}
		if operation == "invoices_get" && !responseString(value, "status") {
			return fmt.Errorf("expected invoice status")
		}
	}
	return nil
}

func responseString(value map[string]any, key string) bool {
	v, ok := value[key].(string)
	return ok && v != ""
}
func responseServer(value any) bool {
	server, ok := value.(map[string]any)
	return ok && responseString(server, "id") && responseString(server, "status")
}
