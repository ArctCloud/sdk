package arct

import (
	"context"
	"iter"
)

type AccountService struct{ client *Client }
type ServersService struct{ client *Client }
type CatalogService struct {
	client    *Client
	operation string
}
type SSHKeysService struct{ client *Client }
type InvoicesService struct{ client *Client }

func (r *AccountService) Get(ctx context.Context) (Result, error) {
	return r.client.Call(ctx, "account_get", "", nil, nil)
}
func (r *ServersService) ListPage(ctx context.Context, q Params) (Result, error) {
	return r.client.Call(ctx, "servers_list", "", q, nil)
}
func (r *ServersService) List(ctx context.Context, q Params) iter.Seq2[Result, error] {
	return r.client.Iterate(ctx, "servers_list", q)
}
func (r *ServersService) Get(ctx context.Context, id string) (Result, error) {
	return r.client.Call(ctx, "servers_get", id, nil, nil)
}
func (r *ServersService) Create(ctx context.Context, body Params) (Result, error) {
	return r.client.Call(ctx, "servers_create", "", nil, body)
}
func (r *ServersService) Update(ctx context.Context, id string, body Params) (Result, error) {
	return r.client.Call(ctx, "servers_update", id, nil, body)
}
func (r *ServersService) Delete(ctx context.Context, id string, atPeriodEnd bool) (Result, error) {
	return r.client.Call(ctx, "servers_delete", id, Params{"at_period_end": atPeriodEnd}, nil)
}
func (r *ServersService) Start(ctx context.Context, id string) (Result, error) {
	return r.client.Call(ctx, "servers_start", id, nil, nil)
}
func (r *ServersService) Stop(ctx context.Context, id string) (Result, error) {
	return r.client.Call(ctx, "servers_stop", id, nil, nil)
}
func (r *ServersService) Restart(ctx context.Context, id string) (Result, error) {
	return r.client.Call(ctx, "servers_restart", id, nil, nil)
}
func (r *ServersService) Reinstall(ctx context.Context, id string, body Params) (Result, error) {
	return r.client.Call(ctx, "servers_reinstall", id, nil, body)
}
func (r *ServersService) ResizeOptions(ctx context.Context, id string) (Result, error) {
	return r.client.Call(ctx, "servers_resize_options", id, nil, nil)
}
func (r *ServersService) Resize(ctx context.Context, id, plan string, expected ...any) (Result, error) {
	return r.client.Resize(ctx, id, plan, expected...)
}
func (r *ServersService) CancelDeletion(ctx context.Context, id string) (Result, error) {
	return r.client.Call(ctx, "servers_cancel_deletion", id, nil, nil)
}
func (r *CatalogService) ListPage(ctx context.Context, q Params) (Result, error) {
	return r.client.Call(ctx, r.operation, "", q, nil)
}
func (r *CatalogService) List(ctx context.Context, q Params) iter.Seq2[Result, error] {
	return r.client.Iterate(ctx, r.operation, q)
}
func (r *SSHKeysService) ListPage(ctx context.Context, q Params) (Result, error) {
	return r.client.Call(ctx, "ssh_keys_list", "", q, nil)
}
func (r *SSHKeysService) List(ctx context.Context, q Params) iter.Seq2[Result, error] {
	return r.client.Iterate(ctx, "ssh_keys_list", q)
}
func (r *SSHKeysService) Get(ctx context.Context, id string) (Result, error) {
	return r.client.Call(ctx, "ssh_keys_get", id, nil, nil)
}
func (r *SSHKeysService) Create(ctx context.Context, body Params) (Result, error) {
	return r.client.Call(ctx, "ssh_keys_create", "", nil, body)
}
func (r *SSHKeysService) Delete(ctx context.Context, id string) (Result, error) {
	return r.client.Call(ctx, "ssh_keys_delete", id, nil, nil)
}
func (r *InvoicesService) ListPage(ctx context.Context, q Params) (Result, error) {
	return r.client.Call(ctx, "invoices_list", "", q, nil)
}
func (r *InvoicesService) List(ctx context.Context, q Params) iter.Seq2[Result, error] {
	return r.client.Iterate(ctx, "invoices_list", q)
}
func (r *InvoicesService) Get(ctx context.Context, id string) (Result, error) {
	return r.client.Call(ctx, "invoices_get", id, nil, nil)
}
