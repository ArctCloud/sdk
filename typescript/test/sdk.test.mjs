import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { inspect } from 'node:util';
import * as sdk from '../dist/index.js';
const f = JSON.parse(await readFile(new URL('../../api/test-cases.json', import.meta.url)));
const id = f.server.id;
const quoteBase = { can_resize: true, current_plan: 'vm.small', pending_resize: null, plans: [] };
const resizeResult = { status: 'applied', resize_id: id, to_plan: 'vm.medium', amount: 4.12, invoice_id: null, invoice_number: null, restart_required: true };
const body = { hostname: 'web-1', location: 'fra', plan: 'vm.small', image_id: id };
let serial = 0;
function client(replies, { autoAccount = true, ...options } = {}) {
  const calls = [];
  const accountCalls = [];
  const accountID = `fixture-account-${serial + 1}`;
  const fetch = async (url, init) => {
    if (autoAccount && new URL(url).pathname === '/v1/account') { accountCalls.push({ url: String(url), ...init }); return new Response(JSON.stringify({ id: accountID })); }
    calls.push({ url: String(url), ...init });
    const reply = typeof replies === 'function' ? await replies(calls.length, init) : replies[Math.min(calls.length - 1, replies.length - 1)];
    if (reply instanceof Error) throw reply;
    if (reply instanceof Response) return reply;
    return new Response(JSON.stringify(reply?.body ?? reply), { status: typeof reply?.status === 'number' ? reply.status : 200, headers: { 'Content-Type': 'application/json', ...reply?.headers } });
  };
  return { arct: new sdk.Arct({ token: `test-token-${++serial}`, fetch, ...options }), calls, accountCalls };
}
const operations = [
  ['account.get', 'GET', '/account', a => a.account.get(), { id }],
  ['servers.listPage', 'GET', '/servers', a => a.servers.listPage(), f.page_one],
  ['servers.create', 'POST', '/servers', a => a.servers.create(body), { status: 201, body: f.create }],
  ['servers.get', 'GET', `/servers/${id}`, a => a.servers.get(id), f.server],
  ['servers.update', 'PATCH', `/servers/${id}`, a => a.servers.update(id, { labels: [], delete_protection: false }), f.server],
  ['servers.delete', 'DELETE', `/servers/${id}`, a => a.servers.delete(id), new Response(null, { status: 204 })],
  ['servers.start', 'POST', `/servers/${id}/start`, a => a.servers.start(id), { status: 202, body: f.server }],
  ['servers.stop', 'POST', `/servers/${id}/stop`, a => a.servers.stop(id), { status: 202, body: f.server }],
  ['servers.restart', 'POST', `/servers/${id}/restart`, a => a.servers.restart(id), { status: 202, body: f.server }],
  ['servers.reinstall', 'POST', `/servers/${id}/reinstall`, a => a.servers.reinstall(id, { image_id: id, ssh_key_ids: [], hostname: 'new' }), { status: 202, body: { server: f.server, password: 'secret' } }],
  ['servers.resizeOptions', 'GET', `/servers/${id}/resize-options`, a => a.servers.resizeOptions(id), { current_plan: 'vm.small', pending_resize: null, plans: [], can_resize: true }],
  ['servers.resize', 'POST', `/servers/${id}/resize`, a => a.servers.resize(id, { plan: 'vm.medium', expected_amount: '4.120' }), { status: 202, body: { ...resizeResult, status: 'pending_payment' } }],
  ['servers.cancelDeletion', 'POST', `/servers/${id}/cancel-deletion`, a => a.servers.cancelDeletion(id), f.server],
  ['locations.listPage', 'GET', '/locations', a => a.locations.listPage(), f.page_empty],
  ['plans.listPage', 'GET', '/plans', a => a.plans.listPage(), f.page_empty],
  ['images.listPage', 'GET', '/images', a => a.images.listPage(), f.page_empty],
  ['invoices.listPage', 'GET', '/invoices', a => a.invoices.listPage(), f.page_empty],
  ['invoices.get', 'GET', `/invoices/${id}`, a => a.invoices.get(id), { id, status: 'paid' }],
  ['sshKeys.listPage', 'GET', '/ssh-keys', a => a.sshKeys.listPage(), f.page_empty],
  ['sshKeys.get', 'GET', `/ssh-keys/${id}`, a => a.sshKeys.get(id), { id }],
  ['sshKeys.create', 'POST', '/ssh-keys', a => a.sshKeys.create({ name: 'test', public_key: 'ssh-ed25519 test' }), { status: 201, body: { id } }],
  ['sshKeys.delete', 'DELETE', `/ssh-keys/${id}`, a => a.sshKeys.delete(id), new Response(null, { status: 204 })],
];
for (const [name, method, path, run, response] of operations) test(`operation: ${name}`, async () => {
  const { arct, calls } = client([response], { autoAccount: name !== 'account.get' });
  await run(arct);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].method, method);
  assert.equal(new URL(calls[0].url).pathname, `/v1${path}`);
  assert.equal(calls[0].redirect, 'manual');
  assert.match(new Headers(calls[0].headers).get('Authorization'), /^Bearer test-token-/);
});
test('preserves omitted, false, empty and explicit null request fields', async () => {
  const { arct, calls } = client([{ status: 201, body: f.create }, f.server]);
  await arct.servers.create({ ...body, enable_backups: false, ssh_key_ids: [], coupon_code: null });
  assert.deepEqual(JSON.parse(calls[0].body), { ...body, enable_backups: false, ssh_key_ids: [], coupon_code: null });
  await arct.servers.update(id, { delete_protection: false, labels: [] });
  assert.deepEqual(JSON.parse(calls[1].body), { delete_protection: false, labels: [] });
  const other = client([{ status: 201, body: f.create }]);
  await other.arct.servers.create(body);
  assert.equal(Object.hasOwn(JSON.parse(other.calls[0].body), 'ssh_key_ids'), false);
});
test('serializes queries and encodes paths', async () => {
  const { arct, calls } = client([f.page_one, f.server, f.server]);
  await arct.servers.listPage({ status: 'running', location: 'fra', page: 2, perPage: 7 });
  assert.equal(new URL(calls[0].url).search, '?status=running&location=fra&page=2&per_page=7');
  await arct.servers.delete('id/with space', { atPeriodEnd: false });
  assert.match(calls[1].url, /id%2Fwith%20space\?at_period_end=false$/);
  await arct.servers.delete(id, { atPeriodEnd: true });
  assert.match(calls[2].url, /at_period_end=true$/);
});
test('accepts unknown response enum values and fields', async () => {
  const { arct } = client([{ ...f.server, status: 'future_status', extra: { nested: 1 } }]);
  const server = await arct.servers.get(id);
  assert.equal(server.status, 'future_status');
  assert.deepEqual(server.extra, { nested: 1 });
});
for (const scenario of [...f.documented_errors, f.validation_error, f.unknown_error, f.charge_unknown]) test(`typed error: ${scenario.body.error.code} (${scenario.status})`, async () => {
  const { arct, calls } = client([scenario]);
  await assert.rejects(arct.servers.update(id, { labels: [] }), e => {
    const code = scenario.body.error.code;
    const charge = code === 'payment_pending' || scenario.body.error.details?.order_intent_id;
    const type = charge ? sdk.ChargeUnknownError : ({ 401: sdk.AuthenticationError, 402: sdk.PaymentRequiredError, 403: sdk.PermissionDeniedError, 404: sdk.NotFoundError, 409: sdk.ConflictError, 422: sdk.ValidationError, 429: sdk.RateLimitError, 500: sdk.UncertainOperationError, 503: sdk.UncertainOperationError }[scenario.status] ?? sdk.APIError);
    assert.ok(e instanceof type, `${e.constructor.name} should be ${type.name}`);
    assert.equal(e.code, code);
    assert.equal(e.status, scenario.status);
    if (scenario.body.error.details?.fields) assert.deepEqual(e.fields, scenario.body.error.details.fields);
    return true;
  });
  assert.equal(calls.length, scenario.status === 429 ? 3 : 1);
});
test('non-JSON and network failures are safe typed errors', async () => {
  const first = client([new Response('token and HTML <oops>', { status: 401 })], { autoAccount: false });
  await assert.rejects(first.arct.account.get(), sdk.AuthenticationError);
  const second = client([new TypeError('private network detail')]);
  await assert.rejects(second.arct.servers.restart(id), e => e instanceof sdk.UncertainOperationError && !inspect(e).includes('private network detail'));
  assert.equal(second.calls.length, 1);
});
test('retries safe reads and create at most three times with identical body', async () => {
  const r = client([new TypeError('lost'), { status: 503, body: { error: { code: 'service_unavailable' } } }, { status: 201, body: f.create }]);
  await r.arct.servers.create(body);
  assert.equal(r.calls.length, 3);
  assert.equal(r.calls[0].body, r.calls[1].body);
  assert.equal(r.calls[1].body, r.calls[2].body);
  const g = client([{ status: 500 }, { status: 503 }, f.server]);
  assert.equal((await g.arct.servers.get(id)).id, id);
  assert.equal(g.calls.length, 3);
});
test('charge uncertainty takes precedence over retryable statuses', async () => {
  for (const status of [429, 500, 503]) {
    const r = client([{ ...f.charge_unknown, status }]);
    await assert.rejects(r.arct.servers.create(body), sdk.ChargeUnknownError);
    assert.equal(r.calls.length, 1);
  }
});
test('promo_changed retries only once and respects total attempt budget', async () => {
  const error = { status: 409, body: { error: { code: 'promo_changed' } } };
  const r = client([error]);
  await assert.rejects(r.arct.servers.create(body), sdk.ConflictError);
  assert.equal(r.calls.length, 2);
  const exhausted = client([{ status: 500 }, error, { status: 500 }]);
  await assert.rejects(exhausted.arct.servers.create(body), sdk.UncertainOperationError);
  assert.equal(exhausted.calls.length, 3);
});
test('lost create followed by hostname conflict only returns uncertain candidates', async () => {
  const r = client([new TypeError('lost'), { status: 409, body: { error: { code: 'hostname_taken' } } }, { ...f.page_one, data: [{ ...f.server, created_at: '2000-01-01T00:00:00Z' }] }]);
  await assert.rejects(r.arct.servers.create(body), e => {
    assert.ok(e instanceof sdk.UncertainOperationError);
    assert.equal(e.details.candidates[0].id, id);
    assert.equal(e.details.candidates[0].matches_request, true);
    assert.equal(e.details.candidates[0].created_after_request, false);
    return true;
  });
  assert.equal(r.calls.filter(c => c.method === 'POST').length, 2);
});
test('Retry-After sleep and request cancellation stop promptly', async () => {
  const controller = new AbortController();
  const r = client([{ status: 429, headers: { 'Retry-After': '60' } }]);
  const promise = r.arct.servers.get(id, { signal: controller.signal });
  setTimeout(() => controller.abort(), 20);
  await assert.rejects(promise, { name: 'AbortError' });
  assert.equal(r.calls.length, 1);
  const p = client(async (_, init) => await new Promise((_, reject) => init.signal.addEventListener('abort', () => reject(init.signal.reason), { once: true })));
  const c = new AbortController();
  const pending = p.arct.servers.get(id, { signal: c.signal });
  setTimeout(() => c.abort(), 20);
  await assert.rejects(pending, { name: 'AbortError' });
});
test('lazy pagination retains filters and stops on an empty page', async () => {
  const r = client([{ ...f.page_one, pagination: { ...f.page_one.pagination, total_pages: 3 } }, f.page_empty]);
  const iterable = r.arct.servers.list({ location: 'fra' });
  assert.equal(r.calls.length, 0);
  const out = await Array.fromAsync(iterable);
  assert.equal(out.length, 1);
  assert.equal(r.calls.length, 2);
  for (const c of r.calls) assert.match(c.url, /location=fra.*per_page=100/);
});
test('resize submits the exact eligible quote without side effects', async () => {
  const r = client([{ ...quoteBase, can_resize: true, plans: [{ slug: 'vm.medium', eligible: true, amount_due_today: 4.12 }] }, { status: 202, body: { ...resizeResult, status: 'pending_payment' } }]);
  assert.equal((await r.arct.servers.resize(id, { plan: 'vm.medium' })).status, 'pending_payment');
  assert.deepEqual(JSON.parse(r.calls[1].body), { plan: 'vm.medium', expected_amount: '4.12' });
  assert.equal(r.calls.length, 2);
  const stale = client([{ status: 409, body: { error: { code: 'price_changed' } } }]);
  await assert.rejects(stale.arct.servers.resize(id, { plan: 'vm.medium', expected_amount: '4.1200' }), sdk.ConflictError);
  assert.equal(stale.calls.length, 1);
  assert.equal(JSON.parse(stale.calls[0].body).expected_amount, '4.1200');
});
test('secrets require deliberate unwrapping and survive create waiting', async () => {
  const r = client([{ status: 201, body: f.create }, f.server]);
  const result = await r.arct.servers.create(body);
  assert.equal(result.password.getSecretValue(), f.create.password);
  assert.equal(JSON.stringify(result).includes(f.create.password), false);
  assert.equal(inspect(result).includes(f.create.password), false);
  const final = await r.arct.servers.waitUntil(result, 'running');
  assert.equal(final.status, 'running');
  assert.equal(result.password.getSecretValue(), f.create.password);
  assert.equal(inspect(r.arct).includes('test-token'), false);
});
test('delayed create resolves known IDs or acknowledged hostname candidates', async () => {
  const known = client([f.server]);
  const result = { ...f.create_delayed, order: { ...f.create_delayed.order, server_id: id } };
  assert.equal((await known.arct.servers.waitUntil(result, 'running')).id, id);
  const discovery = client([f.page_one]);
  const acknowledged = client([{ status: 201, body: f.create_delayed }]);
  const created = await acknowledged.arct.servers.create(body);
  assert.equal((await discovery.arct.servers.waitUntil(created, 'running')).id, id);
});
test('restart and reinstall require a transition before reporting running', async () => {
  const r = client([{ status: 202, body: f.server }, f.server]);
  const result = await r.arct.servers.restart(id);
  await assert.rejects(r.arct.servers.waitUntil(result, 'running', { timeoutMs: 25 }), e => e instanceof sdk.WaitTimeoutError && e.lastState.status === 'running');
  const done = client([{ status: 202, body: { server: { ...f.server, status: 'reinstalling' }, password: 'keep' } }, f.server]);
  const accepted = await done.arct.servers.reinstall(id, { image_id: id });
  assert.equal((await done.arct.servers.waitUntil(accepted, 'running')).status, 'running');
  assert.equal(accepted.password.getSecretValue(), 'keep');
});
test('wait reports pre-orders, terminal failures, cancellation and resize status', async () => {
  const pre = client([{ ...f.server, status: 'pre_order' }]);
  await assert.rejects(pre.arct.servers.waitUntil(id, 'running', { timeoutMs: 20 }), e => e instanceof sdk.WaitTimeoutError && /pre.order/i.test(e.message));
  const failed = client([{ ...f.server, status: 'error' }]);
  await assert.rejects(failed.arct.servers.waitUntil(id, 'running'), sdk.OperationFailedError);
  const controller = new AbortController();
  const running = client([{ ...f.server, status: 'provisioning' }]);
  const wait = running.arct.servers.waitUntil(id, 'running', { signal: controller.signal });
  setTimeout(() => controller.abort(), 20);
  await assert.rejects(wait, { name: 'AbortError' });
  const resize = client([{ ...quoteBase, pending_resize: null, current_plan: 'vm.medium' }, { ...f.server, plan: 'vm.medium' }]);
  assert.equal((await resize.arct.servers.waitUntil(id, 'running', { plan: 'vm.medium' })).plan, 'vm.medium');
  const pending = client(n => n % 2 ? { ...quoteBase, pending_resize: { to_plan: 'vm.medium' }, current_plan: 'vm.medium' } : { ...f.server, plan: 'vm.medium' });
  await assert.rejects(pending.arct.servers.waitUntil(id, 'running', { plan: 'vm.medium', timeoutMs: 20 }), sdk.WaitTimeoutError);
});
test('token precedence and HTTPS validation happen locally', async () => {
  const previous = process.env.ARCT_TOKEN;
  process.env.ARCT_TOKEN = 'environment-token';
  try {
    let authorization;
    const fetch = async (_, init) => { authorization = new Headers(init.headers).get('Authorization'); return new Response(JSON.stringify({ id })); };
    await new sdk.Arct({ token: 'explicit-token', fetch }).account.get();
    assert.equal(authorization, 'Bearer explicit-token');
    await new sdk.Arct({ fetch }).account.get();
    assert.equal(authorization, 'Bearer environment-token');
    assert.throws(() => new sdk.Arct({ token: '', fetch }), sdk.AuthenticationError);
    assert.throws(() => new sdk.Arct({ token: 'x', baseURL: 'http://example.com' }), /HTTPS/);
    assert.throws(() => new sdk.Arct({ token: 'x', baseURL: 'http://localhost:9000' }), /HTTPS/);
    assert.doesNotThrow(() => new sdk.Arct({ token: 'x', baseURL: 'http://localhost:9000', allowInsecureLocalhost: true }));
  } finally { if (previous === undefined) delete process.env.ARCT_TOKEN; else process.env.ARCT_TOKEN = previous; }
});
test('redacts nested error secrets, token echoes, and redirect bodies', async () => {
  const token = 'explicit-secret-token';
  const r = client([{ status: 401, body: { error: { code: 'invalid_token', message: `Bearer ${token}`, details: { nested: { password: 'private', authorization: token }, support_id: 'safe' } } } }], { token, autoAccount: false });
  await assert.rejects(r.arct.account.get(), e => {
    assert.equal((inspect(e) + JSON.stringify(e)).includes(token), false);
    assert.equal((inspect(e) + JSON.stringify(e)).includes('private'), false);
    assert.equal(e.details.support_id, 'safe');
    return true;
  });
  const redirect = client([new Response('secret redirect', { status: 302, headers: { Location: 'https://evil.example' } })], { autoAccount: false });
  await assert.rejects(redirect.arct.account.get(), sdk.APIError);
  assert.equal(redirect.calls.length, 1);
});
test('account budgets are shared across tokens after account resolution', async () => {
  const account = { id: `shared-account-${++serial}` };
  const a = client([account, { status: 201, body: f.create }], { autoAccount: false });
  const b = client([account, { status: 201, body: f.create }], { autoAccount: false });
  await a.arct.account.get();
  await b.arct.account.get();
  for (let i = 0; i < 3; i++) await a.arct.servers.create(body);
  for (let i = 0; i < 2; i++) await b.arct.servers.create(body);
  const controller = new AbortController();
  const pending = b.arct.servers.create(body, { signal: controller.signal });
  setTimeout(() => controller.abort(), 20);
  await assert.rejects(pending, { name: 'AbortError' });
  assert.equal(b.calls.length, 3);
});
test('read, write and hourly paid limits count every attempted request', async () => {
  const reads = client([{ id }], { autoAccount: false });
  for (let i = 0; i < 120; i++) await reads.arct.account.get();
  await assert.rejects(reads.arct.account.get({ timeoutMs: 20 }), { name: 'AbortError' });
  assert.equal(reads.calls.length, 120);
  const writes = client([f.server]);
  for (let i = 0; i < 30; i++) await writes.arct.servers.update(id, { labels: [] });
  await assert.rejects(writes.arct.servers.update(id, { labels: [] }, { timeoutMs: 20 }), { name: 'AbortError' });
  assert.equal(writes.calls.length, 30);
  const now = Date.now;
  let simulated = now();
  Date.now = () => simulated;
  try {
    const paid = client([{ status: 201, body: f.create }]);
    for (let group = 0; group < 4; group++) {
      for (let i = 0; i < 5; i++) await paid.arct.servers.create(body);
      simulated += 60_001;
    }
    await assert.rejects(paid.arct.servers.create(body, { timeoutMs: 20 }), { name: 'AbortError' });
    assert.equal(paid.calls.length, 20);
  } finally { Date.now = now; }
});
test('a retry uses the same paid and write budgets as its initial attempt', async () => {
  const r = client(i => i % 3 ? { status: 503 } : { status: 201, body: f.create });
  await r.arct.servers.create(body);
  await assert.rejects(r.arct.servers.create(body, { timeoutMs: 1000 }), { name: 'AbortError' });
  assert.equal(r.calls.length, 5);
});
test('cancellation during uncertain-create discovery is propagated', async () => {
  const controller = new AbortController();
  const r = client((n, init) => n === 1 ? new TypeError('lost') : n === 2 ? { status: 409, body: { error: { code: 'hostname_taken' } } } : new Promise((_, reject) => init.signal.addEventListener('abort', () => reject(init.signal.reason), { once: true })));
  const pending = r.arct.servers.create(body, { signal: controller.signal });
  const timer = setInterval(() => { if (r.calls.length === 3) { controller.abort(); clearInterval(timer); } }, 5);
  try { await assert.rejects(pending, { name: 'AbortError' }); }
  finally { clearInterval(timer); }
});
test('resize waiting requires the requested plan and target state', async () => {
  const r = client(n => n % 2 ? { ...quoteBase, pending_resize: null, current_plan: 'vm.medium' } : { ...f.server, plan: 'vm.medium', status: 'provisioning' });
  await assert.rejects(r.arct.servers.waitUntil(id, 'running', { plan: 'vm.medium', timeoutMs: 20 }), sdk.WaitTimeoutError);
});
test('resize quoting shares one operation deadline with submission', async () => {
  const r = client(async n => {
    await new Promise(resolve => setTimeout(resolve, 15));
    return n === 1 ? { ...quoteBase, can_resize: true, plans: [{ slug: 'vm.medium', eligible: true, amount_due_today: 4.12 }] } : resizeResult;
  });
  await assert.rejects(r.arct.servers.resize(id, { plan: 'vm.medium' }, { timeoutMs: 20 }), { name: 'AbortError' });
});
test('automatic resize preserves the original numeric quote text', async () => {
  const r = client([new Response('{"can_resize":true,"current_plan":"vm.small","pending_resize":null,"plans":[{"slug":"vm.medium","eligible":true,"amount_due_today":1234567890.123456789}]}', { headers: { 'Content-Type': 'application/json' } }), resizeResult]);
  await r.arct.servers.resize(id, { plan: 'vm.medium' });
  assert.equal(JSON.parse(r.calls[1].body).expected_amount, '1234567890.123456789');
});
test('explicit nullable resize fields are preserved', async () => {
  const r = client([resizeResult]);
  await r.arct.servers.resize(id, { plan: 'vm.medium', expected_amount: null });
  assert.equal(r.calls.length, 1);
  assert.equal(JSON.parse(r.calls[0].body).expected_amount, null);
});
test('malformed successful JSON becomes a typed error without response text', async () => {
  const r = client([new Response('{"password":"private-value", malformed')], { autoAccount: false });
  await assert.rejects(r.arct.account.get(), e => e instanceof sdk.APIError && e.code === 'invalid_response' && !inspect(e).includes('private-value'));
});
test('cancellation during response body reading is propagated safely', async () => {
  const controller = new AbortController();
  const r = client([new Response(new ReadableStream({ start(stream) { setTimeout(() => { controller.abort('private-reason'); }, 10); } }))], { autoAccount: false });
  await assert.rejects(r.arct.account.get({ signal: controller.signal }), e => e.name === 'AbortError' && !inspect(e).includes('private-reason'));
});
test('mutations resolve their account automatically and share paid limits across tokens', async () => {
  const account = { id: `implicit-account-${++serial}` };
  const response = (_, init) => init.method === 'GET' ? account : { status: 201, body: f.create };
  const a = client(response, { autoAccount: false });
  const b = client(response, { autoAccount: false });
  for (let i = 0; i < 3; i++) await a.arct.servers.create(body);
  for (let i = 0; i < 2; i++) await b.arct.servers.create(body);
  await assert.rejects(b.arct.servers.create(body, { timeoutMs: 20 }), { name: 'AbortError' });
  assert.equal([...a.calls, ...b.calls].filter(c => new URL(c.url).pathname === '/v1/account').length, 2);
  assert.equal([...a.calls, ...b.calls].filter(c => c.method === 'POST').length, 5);
});
test('concurrent first mutations share one account lookup', async () => {
  const token = `singleflight-token-${++serial}`;
  let lookups = 0;
  let mutations = 0;
  const fetch = async (url) => {
    if (new URL(url).pathname.endsWith('/account')) {
      lookups++;
      await new Promise(resolve => setTimeout(resolve, 10));
      return new Response(JSON.stringify({ id: `singleflight-account-${serial}` }));
    }
    mutations++;
    return new Response(JSON.stringify(f.server));
  };
  const a = new sdk.Arct({ token, fetch });
  const b = new sdk.Arct({ token, fetch });
  await Promise.all([a.servers.update(id, { labels: [] }), b.servers.update(id, { labels: [] }), a.servers.stop(id)]);
  assert.equal(lookups, 1);
  assert.equal(mutations, 3);
});
test('account lookup failure and cancellation prevent mutation', async () => {
  let mutations = 0;
  const denied = new sdk.Arct({ token: `denied-${++serial}`, fetch: async (_, init) => {
    if (init.method !== 'GET') mutations++;
    return new Response(JSON.stringify({ error: { code: 'invalid_token' } }), { status: 401 });
  } });
  await assert.rejects(denied.servers.create(body), sdk.AuthenticationError);
  assert.equal(mutations, 0);
  const controller = new AbortController();
  const blocked = new sdk.Arct({ token: `blocked-${++serial}`, fetch: async (_, init) => {
    if (init.method !== 'GET') mutations++;
    return new Promise((_, reject) => init.signal.addEventListener('abort', () => reject(init.signal.reason), { once: true }));
  } });
  const pending = blocked.servers.create(body, { signal: controller.signal });
  setTimeout(() => controller.abort(), 10);
  await assert.rejects(pending, { name: 'AbortError' });
  assert.equal(mutations, 0);
});
for (const atPeriodEnd of [undefined, false, true]) test(`bodyless server deletion retains mode ${atPeriodEnd}`, async () => {
  const { arct, calls } = client([new Response(null, { status: 204 })]);
  if (atPeriodEnd === true) {
    await assert.rejects(arct.servers.delete(id, { atPeriodEnd }), error => error instanceof sdk.UncertainOperationError && error.status === 204 && error.code === 'invalid_response');
  } else {
    assert.equal(await arct.servers.delete(id, atPeriodEnd === undefined ? undefined : { atPeriodEnd }), null);
  }
  assert.equal(calls.length, 1);
  assert.equal(new URL(calls[0].url).searchParams.get('at_period_end'), atPeriodEnd === undefined ? null : String(atPeriodEnd));
});
test('bodyless SSH key deletion remains valid', async () => {
  const { arct, calls } = client([new Response(null, { status: 204 })]);
  assert.equal(await arct.sshKeys.delete(id), undefined);
  assert.equal(calls.length, 1);
});
