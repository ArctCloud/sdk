package cli

import (
	"bufio"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sort"
	"strings"

	arct "arct.cloud/sdk/go"
	"golang.org/x/term"
)

type credential struct {
	Token   string `json:"token"`
	BaseURL string `json:"base_url,omitempty"`
}
type config struct {
	Active   string                `json:"active"`
	Contexts map[string]credential `json:"contexts"`
}

func (a *App) configFile() (string, error) {
	if a.ConfigPath != "" {
		return a.ConfigPath, nil
	}
	root := a.Getenv("XDG_CONFIG_HOME")
	if root == "" {
		var err error
		root, err = os.UserConfigDir()
		if err != nil {
			return "", errors.New("cannot locate configuration directory")
		}
	}
	return filepath.Join(root, "arct", "config.json"), nil
}
func (a *App) load() (config, error) {
	cfg := config{Contexts: map[string]credential{}}
	path, err := a.configFile()
	if err != nil {
		return cfg, err
	}
	info, err := os.Lstat(path)
	if errors.Is(err, os.ErrNotExist) {
		return cfg, nil
	}
	if err != nil || !info.Mode().IsRegular() {
		return cfg, errors.New("credential file must be a regular file")
	}
	if err = checkPrivate(path, info); err != nil {
		return cfg, err
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		return cfg, errors.New("cannot read credential file")
	}
	if json.Unmarshal(raw, &cfg) != nil {
		return cfg, errors.New("invalid credential configuration")
	}
	if cfg.Contexts == nil {
		cfg.Contexts = map[string]credential{}
	}
	return cfg, nil
}
func (a *App) save(cfg config) error {
	path, err := a.configFile()
	if err != nil {
		return err
	}
	directory := filepath.Dir(path)
	if err = os.MkdirAll(directory, 0700); err != nil {
		return errors.New("cannot create credential directory")
	}
	info, err := os.Lstat(directory)
	if err != nil || !info.IsDir() || info.Mode()&os.ModeSymlink != 0 {
		return errors.New("credential directory must be a real directory")
	}
	if err = makePrivate(directory, true); err != nil {
		return err
	}
	file, err := os.CreateTemp(directory, ".config-*")
	if err != nil {
		return errors.New("cannot create credential file")
	}
	temporary := file.Name()
	defer os.Remove(temporary)
	defer file.Close()
	if err = makePrivate(temporary, false); err != nil {
		return err
	}
	if err = json.NewEncoder(file).Encode(cfg); err != nil {
		return errors.New("cannot encode credential file")
	}
	if err = file.Sync(); err != nil {
		return errors.New("cannot save credential file")
	}
	if err = file.Close(); err != nil {
		return errors.New("cannot close credential file")
	}
	if err = os.Rename(temporary, path); err != nil {
		return errors.New("cannot replace credential file")
	}
	return nil
}
func (a *App) local(ctx context.Context, pos []string, f *flags) (any, error) {
	cfg, err := a.load()
	if err != nil {
		return nil, err
	}
	name := f.context
	if name == "" {
		name = cfg.Active
	}
	if name == "" {
		name = "default"
	}
	resource, action := pos[0], pos[1]
	if resource == "context" {
		switch action {
		case "list":
			if len(pos) != 2 {
				return nil, usageError("context list takes no identifier")
			}
			names := []string{}
			for name := range cfg.Contexts {
				names = append(names, name)
			}
			sort.Strings(names)
			out := []any{}
			for _, name := range names {
				out = append(out, map[string]any{"name": name, "active": cfg.Active == name, "base_url": cfg.Contexts[name].BaseURL})
			}
			return out, nil
		case "use", "delete":
			if len(pos) != 3 {
				return nil, usageError("context name required")
			}
			name = pos[2]
			if _, ok := cfg.Contexts[name]; !ok {
				return nil, usageError("unknown context " + name)
			}
			if action == "use" {
				cfg.Active = name
			} else {
				delete(cfg.Contexts, name)
				if cfg.Active == name {
					cfg.Active = ""
				}
			}
			if err = a.save(cfg); err != nil {
				return nil, err
			}
			return map[string]any{"context": name, "action": action}, nil
		}
	}
	if len(pos) != 2 {
		return nil, usageError("auth command takes no identifier")
	}
	switch action {
	case "status":
		source := "none"
		if cfg.Contexts[name].Token != "" {
			source = "context"
		}
		if a.Getenv("ARCT_TOKEN") != "" {
			source = "ARCT_TOKEN"
		}
		return map[string]any{"credential_source": source, "context": name, "configured": source != "none"}, nil
	case "logout":
		delete(cfg.Contexts, name)
		if cfg.Active == name {
			cfg.Active = ""
		}
		if err = a.save(cfg); err != nil {
			return nil, err
		}
		return map[string]any{"context": name, "logged_out": true}, nil
	case "login":
		if len(name) > 100 || strings.ContainsAny(name, "\r\n\t/") {
			return nil, usageError("invalid context name")
		}
		token := a.Getenv("ARCT_TOKEN")
		if token == "" {
			fmt.Fprint(a.Err, "Dashboard API token: ")
			if file, ok := a.In.(*os.File); ok && term.IsTerminal(int(file.Fd())) {
				var raw []byte
				raw, err = term.ReadPassword(int(file.Fd()))
				token = string(raw)
				fmt.Fprintln(a.Err)
			} else {
				var raw string
				raw, err = bufio.NewReader(io.LimitReader(a.In, 16385)).ReadString('\n')
				if errors.Is(err, io.EOF) {
					err = nil
				}
				token = strings.TrimSpace(raw)
			}
			if err != nil {
				return nil, usageError("cannot read token")
			}
		}
		if token == "" || len(token) > 16384 {
			return nil, usageError("token required")
		}
		base := f.baseURL
		if base == "" {
			base = a.Getenv("ARCT_BASE_URL")
		}
		c, err := a.NewClient(arct.Options{Token: token, BaseURL: base})
		if err != nil {
			return nil, err
		}
		defer c.Close()
		result, err := c.Call(ctx, "account_get", "", nil, nil)
		if err != nil {
			return nil, err
		}
		cfg.Contexts[name] = credential{Token: token, BaseURL: base}
		cfg.Active = name
		if err = a.save(cfg); err != nil {
			return nil, err
		}
		return map[string]any{"context": name, "account_id": result["id"], "validated": true}, nil
	}
	return nil, usageError("unknown local command")
}
