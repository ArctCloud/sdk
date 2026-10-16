import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { inspect } from 'node:util';
import { Arct, APIError, UncertainOperationError, OperationFailedError } from '../dist/index.js';
const f = JSON.parse(await readFile(new URL('../../api/test-cases.json', import.meta.url)));
const id = f.server.id;
const body = { hostname: 'web-1', location: 'fra', plan: 'vm.small', image_id: id };
let serial = 0;
function make(reply, options = {}) {
  const calls = [];
  const token = `review-fix-${++serial}`;
  const client = new Arct({ token, ...options, fetch: async (url, init) => {
    if (new URL(url).pathname.endsWith('/account')) return new Response(JSON.stringify({ id: `account-${token}` }));
    calls.push({ url: String(url), ...init });
    return reply(url, init, calls.length);
  } });
  return { client, calls };
}
async function promptly(promise, ms = 100) {
  let timer;
  try { return await Promise.race([promise, new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('Operation did not settle promptly.')), ms); })]); }
  finally { clearTimeout(timer); }
}
for (const [name, status, raw, run] of [
  ['create object', 201, '{}', a => a.servers.create(body)],
  ['create missing server', 201, '{"order":{"id":"order"}}', a => a.servers.create(body)],
  ['create empty body', 201, '', a => a.servers.create(body)],
  ['reinstall null', 202, 'null', a => a.servers.reinstall(id, { image_id: id })],
  ['restart object', 202, '{}', a => a.servers.restart(id)],
]) test(`review: malformed ${name} reports received-status uncertainty`, async () => {
  const { client, calls } = make(() => new Response(raw, { status }));
  await assert.rejects(run(client), e => e instanceof UncertainOperationError && e.status === status && e.code === 'invalid_response');
  assert.equal(calls.length, 1);
});
test('review: null server and malformed pages are typed invalid responses', async () => {
  for (const [response, run] of [['null', a => a.servers.get(id)], ['{"data":null,"pagination":{}}', a => a.servers.listPage()]]) {
    const { client } = make(() => new Response(response));
    await assert.rejects(run(client), e => e instanceof APIError && e.code === 'invalid_response' && e.status === 200);
  }
});
for (const [name, status, run] of [
  ['successful body', 200, a => a.servers.get(id)],
  ['error body', 503, a => a.servers.get(id)],
  ['quote body', 200, a => a.servers.resize(id, { plan: 'vm.medium' })],
]) test(`review: injected stalled ${name} obeys absolute deadline`, async () => {
  let canceled = false;
  const { client, calls } = make(() => new Response(new ReadableStream({ cancel() { canceled = true; } }), { status }), { timeoutMs: 10 });
  await assert.rejects(promptly(run(client)), { name: 'AbortError' });
  assert.equal(calls.length, 1);
  assert.equal(canceled, true);
});
test('review: injected stalled fetch obeys absolute deadline', async () => {
  const { client } = make(() => new Promise(() => {}), { timeoutMs: 10 });
  await assert.rejects(promptly(client.servers.get(id)), { name: 'AbortError' });
});
for (const status of [201, 500, 503]) test(`review: create body failure (${status}) is sanitized uncertainty with no resend`, async () => {
  const { client, calls } = make(() => new Response(new ReadableStream({ start(stream) { stream.error(new Error('body-error-private-value')); } }), { status }));
  await assert.rejects(client.servers.create(body), e => e instanceof UncertainOperationError && e.status === status && !inspect(e).includes('body-error-private-value'));
  assert.equal(calls.length, 1);
});
test('review: read body failures become sanitized typed errors', async () => {
  const { client } = make(() => new Response(new ReadableStream({ start(stream) { stream.error(new Error('body-error-private-value')); } })));
  await assert.rejects(client.servers.get(id), e => e instanceof APIError && e.status === 200 && !inspect(e).includes('body-error-private-value'));
});
for (const pending of [null, { to_plan: 'vm.medium' }]) test(`review: resize wait reports terminal state with pending=${!!pending}`, async () => {
  const { client, calls } = make(url => new Response(JSON.stringify(new URL(url).pathname.endsWith('/resize-options') ? { can_resize: true, plans: [], pending_resize: pending, current_plan: 'vm.medium' } : { ...f.server, plan: 'vm.medium', status: 'error' })));
  await assert.rejects(client.servers.waitUntil(id, 'running', { plan: 'vm.medium', timeoutMs: 100 }), OperationFailedError);
  assert.equal(calls.length, 2);
});
test('review: shared account lookup survives another caller deadline', async () => {
  let lookups = 0;
  let mutations = 0;
  const fetch = async (url, init) => {
    if (new URL(url).pathname.endsWith('/account')) {
      lookups++;
      await new Promise((resolve, reject) => {
        const timer = setTimeout(resolve, 50);
        init.signal.addEventListener('abort', () => { clearTimeout(timer); reject(init.signal.reason); }, { once: true });
      });
      return new Response(JSON.stringify({ id: `isolated-account-${serial}` }));
    }
    mutations++;
    return new Response(JSON.stringify(f.server));
  };
  const token = `isolated-token-${++serial}`;
  const a = new Arct({ token, fetch });
  const b = new Arct({ token, fetch });
  const result = await Promise.allSettled([a.servers.update(id, { labels: [] }, { timeoutMs: 10 }), b.servers.update(id, { labels: [] }, { timeoutMs: 200 })]);
  assert.equal(result[0].status, 'rejected');
  assert.equal(result[0].reason.name, 'AbortError');
  assert.equal(result[1].status, 'fulfilled');
  assert.equal(lookups, 1);
  assert.equal(mutations, 1);
});
test('review: root base URL retains safe create retries and charge precedence', async () => {
  const { client, calls } = make((_, __, attempt) => new Response(JSON.stringify(attempt === 1 ? { error: { code: 'internal_error' } } : f.create), { status: attempt === 1 ? 500 : 201 }), { baseURL: 'https://api.example.test/' });
  await client.servers.create(body);
  assert.equal(calls.length, 2);
  assert.equal(calls[0].body, calls[1].body);
  const unknown = make(() => new Response(JSON.stringify(f.charge_unknown.body), { status: 500 }), { baseURL: 'https://api.example.test/' });
  await assert.rejects(unknown.client.servers.create(body), e => e.name === 'ChargeUnknownError');
  assert.equal(unknown.calls.length, 1);
});
for (const quote of [{ can_resize: true, plans: [null] }, { current_plan: 'vm.small' }, { can_resize: true, current_plan: 'vm.small', pending_resize: null, plans: [{ slug: 'vm.medium', eligible: true, amount_due_today: 'invalid' }] }]) test(`review: malformed resize quote is a received-status API error (${JSON.stringify(quote)})`, async () => {
  const { client, calls } = make(() => new Response(JSON.stringify(quote)));
  await assert.rejects(client.servers.resize(id, { plan: 'vm.medium' }), e => e instanceof APIError && !(e instanceof UncertainOperationError) && e.status === 200 && e.code === 'invalid_response');
  assert.equal(calls.length, 1);
});
test('review: delayed discovery rejects server entries missing policy fields', async () => {
  const { client } = make(() => new Response(JSON.stringify({ ...f.page_one, data: [{ id, status: 'running' }] })));
  await assert.rejects(client.servers.waitUntil(f.create_delayed, 'running', { hostname: 'web-1', timeoutMs: 100 }), e => e instanceof APIError && e.code === 'invalid_response' && e.status === 200);
});
test('review: malformed order correlation ID reports creation uncertainty', async () => {
  const { client, calls } = make(() => new Response(JSON.stringify({ ...f.create_delayed, order: { ...f.create_delayed.order, server_id: { invalid: true } } }), { status: 201 }));
  await assert.rejects(client.servers.create(body), e => e instanceof UncertainOperationError && e.status === 201 && e.code === 'invalid_response');
  assert.equal(calls.length, 1);
});
