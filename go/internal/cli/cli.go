package cli

import (
	"bufio"
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"sort"
	"strconv"
	"strings"
	"text/tabwriter"
	"time"

	arct "arct.cloud/sdk/go"
	"golang.org/x/term"
)

type App struct {
	In         io.Reader
	Out        io.Writer
	Err        io.Writer
	ConfigPath string
	Getenv     func(string) string
	NewClient  func(arct.Options) (*arct.Client, error)
}
type usageError string

func (e usageError) Error() string { return string(e) }

type stringsFlag []string

func (s *stringsFlag) String() string     { return strings.Join(*s, ",") }
func (s *stringsFlag) Set(v string) error { *s = append(*s, v); return nil }
func (s stringsFlag) values() []string {
	if len(s) == 1 && s[0] == "" {
		return []string{}
	}
	return []string(s)
}

type flags struct {
	context, baseURL, output, columns, timeout, hostname, location, plan, image, billing, coupon, status, name, key, keyFile, expected string
	noHeader, all, yes, wait, showPassword, backups, protection, periodEnd, couponNull                                                 bool
	page, perPage                                                                                                                      int
	keys, labels                                                                                                                       stringsFlag
	visited                                                                                                                            map[string]bool
}

var commands = map[string]string{"account": "get", "servers": "list get create update delete start stop restart reinstall resize-options resize cancel-deletion wait", "locations": "list", "plans": "list", "images": "list", "ssh-keys": "list get create delete", "invoices": "list get", "auth": "login logout status", "context": "list use delete"}

func (a *App) defaults() {
	if a.In == nil {
		a.In = os.Stdin
	}
	if a.Out == nil {
		a.Out = os.Stdout
	}
	if a.Err == nil {
		a.Err = os.Stderr
	}
	if a.Getenv == nil {
		a.Getenv = os.Getenv
	}
	if a.NewClient == nil {
		a.NewClient = arct.New
	}
}
func hasWord(words, word string) bool {
	for _, item := range strings.Fields(words) {
		if item == word {
			return true
		}
	}
	return false
}
func parse(args []string) (*flags, []string, *flag.FlagSet, error) {
	f := &flags{visited: map[string]bool{}}
	set := flag.NewFlagSet("arct", flag.ContinueOnError)
	set.SetOutput(io.Discard)
	set.StringVar(&f.context, "context", "", "Credential context")
	set.StringVar(&f.baseURL, "base-url", "", "API URL (HTTPS)")
	set.StringVar(&f.output, "output", "table", "table or json")
	set.StringVar(&f.columns, "columns", "", "Comma-separated table columns")
	set.BoolVar(&f.noHeader, "no-header", false, "Hide table headers")
	set.BoolVar(&f.yes, "yes", false, "Confirm mutation")
	resource, action := "", ""
	for i := 0; i < len(args); i++ {
		arg := args[i]
		if strings.HasPrefix(arg, "-") {
			name := strings.TrimLeft(strings.SplitN(arg, "=", 2)[0], "-")
			if !strings.Contains(arg, "=") && hasWord("context base-url output columns", name) {
				i++
			}
			continue
		}
		if resource == "" {
			resource = arg
		} else {
			action = arg
			break
		}
	}
	list := action == "list" && resource != "context"
	if list {
		set.BoolVar(&f.all, "all", false, "Retrieve all pages")
		set.IntVar(&f.page, "page", 1, "Page (1..100000)")
		set.IntVar(&f.perPage, "per-page", 20, "Items per page (1..100)")
	}
	if resource == "servers" {
		if hasWord("create start stop restart reinstall resize delete", action) {
			set.BoolVar(&f.wait, "wait", false, "Wait for completion")
		}
		if hasWord("create start stop restart reinstall resize delete wait", action) {
			set.StringVar(&f.timeout, "timeout", "600s", "Wait deadline (duration or seconds)")
		}
		if hasWord("list wait", action) {
			def := ""
			if action == "wait" {
				def = "running"
			}
			set.StringVar(&f.status, "status", def, "Server status")
		}
		if hasWord("create update reinstall", action) {
			set.StringVar(&f.hostname, "hostname", "", "Server hostname")
		}
		if hasWord("create reinstall", action) {
			set.StringVar(&f.image, "image", "", "Image UUID")
			set.Var(&f.keys, "ssh-key", "SSH key UUID, repeat; empty clears")
			set.BoolVar(&f.showPassword, "show-password", false, "Reveal one-time password")
		}
		if hasWord("create resize", action) {
			set.StringVar(&f.plan, "plan", "", "Plan slug")
		}
		if action == "create" {
			set.StringVar(&f.billing, "billing-period", "monthly", "monthly, quarterly, semi_annual, yearly")
			set.StringVar(&f.coupon, "coupon-code", "", "Coupon code")
			set.BoolVar(&f.couponNull, "coupon-code-null", false, "Send null coupon")
			set.BoolVar(&f.backups, "enable-backups", false, "Enable automatic backups")
		}
		if action == "update" {
			set.BoolVar(&f.protection, "delete-protection", false, "Delete protection")
			set.Var(&f.labels, "label", "Label, repeat; empty clears")
		}
		if action == "delete" {
			set.BoolVar(&f.periodEnd, "at-period-end", false, "Delete at paid period end")
		}
		if action == "resize" {
			set.StringVar(&f.expected, "expected-amount", "", "Exact nonnegative quoted amount")
		}
	}
	if (resource == "servers" && hasWord("create list", action)) || ((resource == "plans" || resource == "images") && list) {
		set.StringVar(&f.location, "location", "", "Location code")
	}
	if resource == "ssh-keys" && action == "create" {
		set.StringVar(&f.name, "name", "", "Key name")
		set.StringVar(&f.key, "public-key", "", "Public key line")
		set.StringVar(&f.keyFile, "public-key-file", "", "Public key file, or - for stdin")
	}
	var options, positions []string
	for i := 0; i < len(args); i++ {
		arg := args[i]
		if !strings.HasPrefix(arg, "-") || arg == "-" {
			positions = append(positions, arg)
			continue
		}
		if arg == "--" {
			positions = append(positions, args[i+1:]...)
			break
		}
		name := strings.TrimLeft(strings.SplitN(arg, "=", 2)[0], "-")
		opt := set.Lookup(name)
		if opt == nil {
			return f, positions, set, usageError("unknown flag --" + name)
		}
		options = append(options, arg)
		_, equal := strings.CutPrefix(arg, "--"+name+"=")
		if strings.Contains(arg, "=") {
			equal = true
		}
		isBool := false
		if b, ok := opt.Value.(interface{ IsBoolFlag() bool }); ok {
			isBool = b.IsBoolFlag()
		}
		if !equal && !isBool {
			if i+1 >= len(args) {
				return f, positions, set, usageError("value required for --" + name)
			}
			i++
			options = append(options, args[i])
		}
	}
	if err := set.Parse(options); err != nil {
		return f, positions, set, usageError(err.Error())
	}
	set.Visit(func(v *flag.Flag) { f.visited[v.Name] = true })
	return f, positions, set, nil
}
func (a *App) Run(ctx context.Context, args []string) int {
	a.defaults()
	jsonMode := false
	for i, v := range args {
		if v == "--output=json" || v == "--output" && i+1 < len(args) && args[i+1] == "json" {
			jsonMode = true
		}
	}
	if len(args) == 1 && args[0] == "--version" {
		fmt.Fprintln(a.Out, strings.TrimSpace(arct.Version))
		return 0
	}
	if len(args) == 0 || hasHelp(args) {
		a.help(args)
		return 0
	}
	f, pos, _, err := parse(args)
	if err != nil {
		return a.failure(err, jsonMode)
	}
	if len(pos) < 2 || commands[pos[0]] == "" || !hasWord(commands[pos[0]], pos[1]) {
		return a.failure(usageError("expected arct <resource> <action>; run arct --help"), jsonMode)
	}
	if f.output != "table" && f.output != "json" {
		return a.failure(usageError("--output must be table or json"), jsonMode)
	}
	if f.output == "json" && (f.columns != "" || f.noHeader) {
		return a.failure(usageError("--columns and --no-header apply to table output"), jsonMode)
	}
	var result any
	if pos[0] == "auth" || pos[0] == "context" {
		result, err = a.local(ctx, pos, f)
	} else {
		result, err = a.remote(ctx, pos, f)
	}
	if err != nil {
		if result != nil {
			if renderErr := a.render(result, f); renderErr != nil {
				return a.failure(renderErr, jsonMode)
			}
		}
		return a.failure(err, jsonMode)
	}
	if err = a.render(result, f); err != nil {
		return a.failure(err, jsonMode)
	}
	return 0
}
func hasHelp(args []string) bool {
	for _, arg := range args {
		if arg == "--help" || arg == "-h" || arg == "help" {
			return true
		}
	}
	return false
}
func (a *App) help(args []string) {
	fmt.Fprintln(a.Out, "Usage: arct <resource> <action> [ID] [flags]\n\nResources:")
	names := []string{}
	for k := range commands {
		names = append(names, k)
	}
	sort.Strings(names)
	for _, name := range names {
		fmt.Fprintf(a.Out, "  %-12s %s\n", name, commands[name])
	}
	clean := []string{}
	for _, s := range args {
		if s != "--help" && s != "-h" && s != "help" {
			clean = append(clean, s)
		}
	}
	_, _, set, _ := parse(clean)
	fmt.Fprintln(a.Out, "\nFlags:")
	set.SetOutput(a.Out)
	set.PrintDefaults()
	fmt.Fprintln(a.Out, "\nARCT_TOKEN overrides saved credentials. Tokens are never accepted as flags.\nConfirm paid/destructive actions with --yes in automation. JSON hides passwords unless --show-password is explicit.")
}
func (a *App) failure(err error, jsonMode bool) int {
	code := 1
	var usage usageError
	var api *arct.APIError
	switch {
	case errors.As(err, &usage):
		code = 2
	case errors.Is(err, context.Canceled):
		code = 130
	case errors.Is(err, context.DeadlineExceeded):
		code = 3
	case errors.As(err, &api):
		if api.Kind == "TimeoutError" || api.Kind == "UncertainOperationError" || api.Kind == "ChargeUnknownError" {
			code = 3
		}
	}
	if jsonMode {
		value := any(map[string]any{"code": "error", "message": err.Error()})
		if api != nil {
			value = api
		}
		_ = json.NewEncoder(a.Err).Encode(map[string]any{"error": arct.Redact(value)})
	} else {
		fmt.Fprintln(a.Err, err)
	}
	return code
}
func (a *App) confirm(f *flags, message string) error {
	fmt.Fprintln(a.Err, message)
	if f.yes {
		return nil
	}
	file, ok := a.In.(*os.File)
	if !ok || !term.IsTerminal(int(file.Fd())) {
		return usageError("confirmation required: pass --yes for noninteractive use")
	}
	fmt.Fprint(a.Err, "Continue? [y/N] ")
	line, _ := bufio.NewReader(a.In).ReadString('\n')
	if strings.ToLower(strings.TrimSpace(line)) != "y" {
		return usageError("operation not confirmed")
	}
	return nil
}
func duration(value string) (time.Duration, error) {
	if value == "" {
		return 600 * time.Second, nil
	}
	d, err := time.ParseDuration(value)
	if err != nil {
		seconds, parseErr := strconv.ParseFloat(value, 64)
		if parseErr != nil || seconds <= 0 || seconds > float64((1<<63-1)/int64(time.Second)) {
			return 0, usageError("invalid --timeout")
		}
		d = time.Duration(seconds * float64(time.Second))
	}
	if d <= 0 {
		return 0, usageError("--timeout must be positive")
	}
	return d, nil
}
func (a *App) client(f *flags) (*arct.Client, error) {
	cfg, err := a.load()
	if err != nil {
		return nil, err
	}
	token := a.Getenv("ARCT_TOKEN")
	base := f.baseURL
	name := f.context
	if name == "" {
		name = cfg.Active
	}
	stored, exists := cfg.Contexts[name]
	if f.context != "" && !exists && token == "" {
		return nil, usageError("unknown context " + name)
	}
	if token == "" {
		token = stored.Token
	}
	if base == "" {
		base = a.Getenv("ARCT_BASE_URL")
	}
	if base == "" {
		base = stored.BaseURL
	}
	if token == "" {
		return nil, usageError("authentication required: set ARCT_TOKEN or run arct auth login")
	}
	return a.NewClient(arct.Options{Token: token, BaseURL: base})
}
func (a *App) remote(ctx context.Context, pos []string, f *flags) (any, error) {
	resource, action := pos[0], pos[1]
	id := ""
	needsID := hasWord("get update delete start stop restart reinstall resize-options resize cancel-deletion wait", action) && resource != "account"
	want := 2
	if needsID {
		want = 3
	}
	if len(pos) != want {
		return nil, usageError("unexpected or missing identifier")
	}
	if needsID {
		id = pos[2]
		if !arct.ValidID(id) {
			return nil, usageError("identifier must be a UUID")
		}
	}
	timeout, err := duration(f.timeout)
	if err != nil {
		return nil, err
	}
	q, b := arct.Params{}, arct.Params{}
	if action == "list" {
		if f.page < 1 || f.page > 100000 || f.perPage < 1 || f.perPage > 100 {
			return nil, usageError("invalid page or per-page")
		}
		if f.visited["page"] {
			q["page"] = f.page
		}
		if f.visited["per-page"] {
			q["per_page"] = f.perPage
		}
		if f.visited["location"] {
			q["location"] = f.location
		}
		if f.visited["status"] {
			q["status"] = f.status
			if !hasWord("provisioning running stopped restarting reinstalling restoring deleting suspended pre_order", f.status) {
				return nil, usageError("unsupported status filter")
			}
		}
	}
	if resource == "servers" {
		switch action {
		case "create":
			b["hostname"] = f.hostname
			b["location"] = f.location
			b["plan"] = f.plan
			b["image_id"] = f.image
			if f.visited["billing-period"] {
				b["billing_period"] = f.billing
			}
			if f.visited["enable-backups"] {
				b["enable_backups"] = f.backups
			}
			if f.visited["coupon-code"] {
				b["coupon_code"] = f.coupon
			}
			if f.couponNull {
				if f.visited["coupon-code"] {
					return nil, usageError("coupon flags conflict")
				}
				b["coupon_code"] = nil
			}
		case "update":
			if f.visited["hostname"] {
				b["hostname"] = f.hostname
			}
			if f.visited["delete-protection"] {
				b["delete_protection"] = f.protection
			}
			if f.visited["label"] {
				b["labels"] = f.labels.values()
			}
		case "reinstall":
			b["image_id"] = f.image
			if f.visited["hostname"] {
				b["hostname"] = f.hostname
			}
		case "delete":
			if f.periodEnd && f.wait {
				return nil, usageError("scheduled deletion does not support --wait")
			}
			if f.visited["at-period-end"] {
				q["at_period_end"] = f.periodEnd
			}
		case "resize":
			if f.plan == "" {
				return nil, usageError("--plan required")
			}
			if f.visited["expected-amount"] && (!arct.ValidAmount(f.expected) || !json.Valid([]byte(f.expected))) {
				return nil, usageError("expected amount must be a nonnegative decimal")
			}
			b["plan"] = f.plan
		case "wait":
			if !hasWord("provisioning running stopped restarting reinstalling restoring error deleting suspended pre_order", f.status) {
				return nil, usageError("invalid target status")
			}
		}
		if f.visited["ssh-key"] {
			b["ssh_key_ids"] = f.keys.values()
		}
	}
	if resource == "ssh-keys" && action == "create" {
		if f.visited["public-key"] && f.visited["public-key-file"] {
			return nil, usageError("public key flags conflict")
		}
		if f.keyFile != "" {
			var raw []byte
			if f.keyFile == "-" {
				raw, err = io.ReadAll(io.LimitReader(a.In, 8194))
			} else {
				var file *os.File
				file, err = os.Open(f.keyFile)
				if err == nil {
					raw, err = io.ReadAll(io.LimitReader(file, 8194))
					file.Close()
				}
			}
			if err != nil {
				return nil, usageError("cannot read public key file")
			}
			f.key = strings.TrimSpace(string(raw))
		}
		if strings.Contains(f.key, "PRIVATE KEY") {
			return nil, usageError("a public key is required")
		}
		b["name"] = f.name
		b["public_key"] = f.key
	}
	op := strings.ReplaceAll(resource, "-", "_") + "_" + strings.ReplaceAll(action, "-", "_")
	if action != "wait" {
		err = arct.Validate(op, q, b)
	}
	if err != nil {
		return nil, usageError(err.Error())
	}
	if resource == "servers" && action == "create" {
		if err = a.confirm(f, fmt.Sprintf("Create %s: plan=%s location=%s billing=%s. A saved card is charged; final charges depend on promotions, backups and billing period.", f.hostname, f.plan, f.location, f.billing)); err != nil {
			return nil, err
		}
	}
	if action == "delete" || resource == "servers" && hasWord("reinstall cancel-deletion", action) {
		if err = a.confirm(f, fmt.Sprintf("Confirm %s %s %s; this may destroy data or change billing.", resource, action, id)); err != nil {
			return nil, err
		}
	}
	c, err := a.client(f)
	if err != nil {
		return nil, err
	}
	defer c.Close()
	if resource == "servers" && action == "wait" {
		return c.Wait(ctx, id, f.status, "wait", nil, timeout)
	}
	if resource == "servers" && action == "resize" {
		var amount any
		if f.visited["expected-amount"] {
			amount = json.Number(f.expected)
		} else {
			amount, err = c.Quote(ctx, id, f.plan)
			if err != nil {
				return nil, err
			}
		}
		if err = a.confirm(f, fmt.Sprintf("Resize %s to %s: quoted charge USD %v. This exact amount will be submitted; changed prices require a new decision.", id, f.plan, amount)); err != nil {
			return nil, err
		}
		b["expected_amount"] = amount
	}
	if action == "list" && f.all {
		return c.All(ctx, op, q)
	}
	result, err := c.Call(ctx, op, id, q, b)
	if err != nil {
		return nil, err
	}
	if f.wait {
		fmt.Fprintln(a.Err, "Waiting for completion; interruption stops polling only.")
		if action == "create" {
			out, err := c.WaitCreated(ctx, result, f.hostname, timeout)
			return keptResult(result, out, err)
		}
		target := "running"
		if action == "stop" {
			target = "stopped"
		}
		if action == "resize" {
			target = f.plan
		}
		out, err := c.Wait(ctx, id, target, action, result, timeout)
		return keptResult(result, out, err)
	}
	if resource == "servers" && hasWord("start stop restart reinstall", action) {
		fmt.Fprintln(a.Err, "Operation accepted; completion is asynchronous.")
	}
	if resource == "servers" && action == "resize" && result["status"] == "pending_payment" {
		fmt.Fprintln(a.Err, "Resize is pending payment; the plan has not been applied.")
	}
	return result, nil
}
func (a *App) render(result any, f *flags) error {
	if f.showPassword {
		result = arct.RevealPasswords(result)
	} else {
		result = arct.Redact(result)
	}
	if f.output == "json" {
		return json.NewEncoder(a.Out).Encode(result)
	}
	if result == nil {
		fmt.Fprintln(a.Out, "Done")
		return nil
	}
	var rows []any
	switch x := result.(type) {
	case []any:
		rows = x
	case map[string]any:
		if final, ok := x["final_server"].(map[string]any); ok {
			delete(x, "final_server")
			delete(x, "server")
			for key, value := range final {
				x[key] = value
			}
		}
		if data, ok := x["data"].([]any); ok {
			rows = data
		} else {
			keys := []string{}
			for k := range x {
				keys = append(keys, k)
			}
			sort.Strings(keys)
			w := tabwriter.NewWriter(a.Out, 0, 4, 2, ' ', 0)
			for _, k := range keys {
				fmt.Fprintf(w, "%s\t%s\n", k, display(x[k]))
			}
			return w.Flush()
		}
	default:
		fmt.Fprintln(a.Out, display(result))
		return nil
	}
	columns := strings.FieldsFunc(f.columns, func(r rune) bool { return r == ',' })
	if len(columns) == 0 {
		for _, name := range []string{"id", "code", "slug", "name", "hostname", "status", "location", "plan", "invoice_number", "total", "active", "base_url"} {
			for _, row := range rows {
				m, _ := row.(map[string]any)
				if _, ok := m[name]; ok {
					columns = append(columns, name)
					break
				}
			}
		}
	}
	w := tabwriter.NewWriter(a.Out, 0, 4, 2, ' ', 0)
	if !f.noHeader && len(columns) > 0 {
		fmt.Fprintln(w, strings.Join(columns, "\t"))
	}
	for _, row := range rows {
		m, _ := row.(map[string]any)
		values := []string{}
		for _, name := range columns {
			values = append(values, display(m[name]))
		}
		fmt.Fprintln(w, strings.Join(values, "\t"))
	}
	return w.Flush()
}
func display(value any) string {
	if value == nil {
		return "-"
	}
	switch x := value.(type) {
	case string:
		return strings.ReplaceAll(strings.ReplaceAll(x, "\n", " "), "\t", " ")
	default:
		b, _ := json.Marshal(x)
		return string(b)
	}
}

func keptResult(original, final arct.Result, err error) (any, error) {
	if err == nil {
		return final, nil
	}
	out := arct.Result{}
	for k, v := range original {
		out[k] = v
	}
	out["wait_error"] = err.Error()
	return out, err
}
