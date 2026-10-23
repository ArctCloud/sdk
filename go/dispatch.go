package arct

import (
	"context"
	"fmt"
	"net/http"
)

func number(q Params, k string) int32 {
	if x, ok := q[k].(int); ok {
		return int32(x)
	}
	return 0
}
func text(q Params, k string) string { x, _ := q[k].(string); return x }
func (c *Client) dispatch(ctx context.Context, op, id string, q, body map[string]any) (*http.Response, error) {
	var resp *http.Response
	var err error
	switch op {
	case "account_get":
		_, resp, err = c.api.AccountAPI.AccountGet(ctx).Execute()
	case "servers_list":
		r := c.api.ServersAPI.ServersList(ctx)
		if _, ok := q["page"]; ok {
			r = r.Page(number(q, "page"))
		}
		if _, ok := q["per_page"]; ok {
			r = r.PerPage(number(q, "per_page"))
		}
		if _, ok := q["status"]; ok {
			r = r.Status(text(q, "status"))
		}
		if _, ok := q["location"]; ok {
			r = r.Location(text(q, "location"))
		}
		if _, ok := q["datacenter"]; ok {
			r = r.Datacenter(text(q, "datacenter"))
		}
		_, resp, err = r.Execute()
	case "servers_get":
		_, resp, err = c.api.ServersAPI.ServersGet(ctx, id).Execute()
	case "servers_create":
		_, resp, err = c.api.ServersAPI.ServersCreate(ctx).RequestBody(body).Execute()
	case "servers_update":
		_, resp, err = c.api.ServersAPI.ServersUpdate(ctx, id).RequestBody(body).Execute()
	case "servers_delete":
		r := c.api.ServersAPI.ServersDelete(ctx, id)
		if b, ok := q["at_period_end"].(bool); ok {
			r = r.AtPeriodEnd(b)
		}
		_, resp, err = r.Execute()
	case "servers_start":
		_, resp, err = c.api.ServersAPI.ServersStart(ctx, id).Execute()
	case "servers_stop":
		_, resp, err = c.api.ServersAPI.ServersStop(ctx, id).Execute()
	case "servers_restart":
		_, resp, err = c.api.ServersAPI.ServersRestart(ctx, id).Execute()
	case "servers_reinstall":
		_, resp, err = c.api.ServersAPI.ServersReinstall(ctx, id).RequestBody(body).Execute()
	case "servers_resize_options":
		_, resp, err = c.api.ServersAPI.ServersResizeOptions(ctx, id).Execute()
	case "servers_resize":
		_, resp, err = c.api.ServersAPI.ServersResize(ctx, id).RequestBody(body).Execute()
	case "servers_cancel_deletion":
		_, resp, err = c.api.ServersAPI.ServersCancelDeletion(ctx, id).Execute()
	case "datacenters_list":
		r := c.api.CatalogAPI.DatacentersList(ctx)
		if _, ok := q["page"]; ok {
			r = r.Page(number(q, "page"))
		}
		if _, ok := q["per_page"]; ok {
			r = r.PerPage(number(q, "per_page"))
		}
		_, resp, err = r.Execute()
	case "locations_list":
		r := c.api.CatalogAPI.LocationsList(ctx)
		if _, ok := q["page"]; ok {
			r = r.Page(number(q, "page"))
		}
		if _, ok := q["per_page"]; ok {
			r = r.PerPage(number(q, "per_page"))
		}
		_, resp, err = r.Execute()
	case "plans_list":
		r := c.api.CatalogAPI.PlansList(ctx)
		if _, ok := q["page"]; ok {
			r = r.Page(number(q, "page"))
		}
		if _, ok := q["per_page"]; ok {
			r = r.PerPage(number(q, "per_page"))
		}
		if _, ok := q["location"]; ok {
			r = r.Location(text(q, "location"))
		}
		if _, ok := q["datacenter"]; ok {
			r = r.Datacenter(text(q, "datacenter"))
		}
		_, resp, err = r.Execute()
	case "images_list":
		r := c.api.CatalogAPI.ImagesList(ctx)
		if _, ok := q["page"]; ok {
			r = r.Page(number(q, "page"))
		}
		if _, ok := q["per_page"]; ok {
			r = r.PerPage(number(q, "per_page"))
		}
		if _, ok := q["location"]; ok {
			r = r.Location(text(q, "location"))
		}
		if _, ok := q["datacenter"]; ok {
			r = r.Datacenter(text(q, "datacenter"))
		}
		_, resp, err = r.Execute()
	case "invoices_list":
		r := c.api.InvoicesAPI.InvoicesList(ctx)
		if _, ok := q["page"]; ok {
			r = r.Page(number(q, "page"))
		}
		if _, ok := q["per_page"]; ok {
			r = r.PerPage(number(q, "per_page"))
		}
		_, resp, err = r.Execute()
	case "invoices_get":
		_, resp, err = c.api.InvoicesAPI.InvoicesGet(ctx, id).Execute()
	case "ssh_keys_list":
		r := c.api.SSHKeysAPI.SshKeysList(ctx)
		if _, ok := q["page"]; ok {
			r = r.Page(number(q, "page"))
		}
		if _, ok := q["per_page"]; ok {
			r = r.PerPage(number(q, "per_page"))
		}
		_, resp, err = r.Execute()
	case "ssh_keys_get":
		_, resp, err = c.api.SSHKeysAPI.SshKeysGet(ctx, id).Execute()
	case "ssh_keys_create":
		_, resp, err = c.api.SSHKeysAPI.SshKeysCreate(ctx).RequestBody(body).Execute()
	case "ssh_keys_delete":
		resp, err = c.api.SSHKeysAPI.SshKeysDelete(ctx, id).Execute()
	default:
		return nil, fmt.Errorf("unknown operation %q", op)
	}
	return resp, err
}
