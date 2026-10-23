import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { Arct, ValidationError, UncertainOperationError } from '../dist/index.js';

const fixtures = JSON.parse(await readFile(new URL('../../api/test-cases.json', import.meta.url)));
const body = { hostname: 'web-1', datacenter: 'ams2', plan: 'vm.small', image_id: fixtures.server.id };
const pagination = { page: 1, per_page: 100, total: 1, total_pages: 1 };
let serial = 0;
function client(reply) {
  const calls = [];
  const token = `datacenters-${++serial}`;
  const arct = new Arct({ token, fetch: async (url, init) => {
    if (new URL(url).pathname.endsWith('/account')) return Response.json({ id: token });
    calls.push({ url: new URL(url), ...init });
    const result = await reply(calls.length, init);
    if (result instanceof Error) throw result;
    return result instanceof Response ? result : Response.json(result);
  } });
  return { arct, calls };
}

test('datacenters list paginates and preserves unknown fields', async () => {
  const datacenter = { code: 'ams2', location: 'ams', name: 'Amsterdam', region: null, status: 'online', is_preorder: false, tiers: ['hvm'], future: true };
  const { arct, calls } = client(n => ({ data: [{ ...datacenter, code: `ams${n}` }], pagination: { ...pagination, page: n, total_pages: 2 } }));
  const result = await Array.fromAsync(arct.datacenters.list({ perPage: 1 }));
  assert.deepEqual(result.map(dc => dc.code), ['ams1', 'ams2']);
  assert.equal(result[0].future, true);
  assert.deepEqual(calls.map(call => call.url.search), ['?page=1&per_page=1', '?page=2&per_page=1']);
  assert.ok(calls.every(call => call.url.pathname === '/v1/datacenters'));
  const page = await arct.datacenters.listPage();
  assert.equal(page.data[0].location, 'ams');
});

for (const resource of ['servers', 'plans', 'images']) test(`${resource} keeps datacenter filters across pages`, async () => {
  const item = resource === 'servers' ? fixtures.server : resource === 'plans' ? { slug: 'vm.small' } : { id: 'image' };
  const { arct, calls } = client(n => ({ data: [item], pagination: { ...pagination, page: n, total_pages: 2 } }));
  await Array.fromAsync(arct[resource].list({ datacenter: 'AMS2', location: 'ams', perPage: 1 }));
  assert.equal(calls.length, 2);
  for (const call of calls) {
    assert.equal(call.url.searchParams.get('datacenter'), 'AMS2');
    assert.equal(call.url.searchParams.get('location'), 'ams');
  }
});

test('create accepts new, legacy and combined selectors unchanged', async () => {
  for (const selectors of [{ datacenter: 'ams2' }, { location: 'AMS' }, { location: 'AMS2' }, { datacenter: 'ams2', location: 'ams' }]) {
    const request = { ...body, ...selectors };
    if (!Object.hasOwn(selectors, 'datacenter')) delete request.datacenter;
    const { arct, calls } = client(() => fixtures.create);
    await arct.servers.create(request);
    assert.deepEqual(JSON.parse(calls[0].body), request);
    assert.equal(calls.length, 1);
  }
});

test('invalid creates fail before account lookup or mutation', async () => {
  for (const invalid of [
    { hostname: body.hostname, plan: body.plan, image_id: body.image_id },
    ...['ams', 'a1', 'abcdef1', 'ams123', 'ams2\n', '', null, 2].map(datacenter => ({ ...body, datacenter })),
    ...['hostname', 'plan', 'image_id'].map(key => ({ ...body, [key]: undefined })),
    { ...body, extra: true },
    { ...body, location: null },
  ]) {
    const { arct, calls } = client(() => { throw new Error('Unexpected request.'); });
    await assert.rejects(arct.servers.create(invalid), ValidationError);
    assert.equal(calls.length, 0);
  }
});

test('invalid and unknown query fields fail locally', async () => {
  const { arct, calls } = client(() => { throw new Error('Unexpected request.'); });
  for (const resource of ['servers', 'plans', 'images']) {
    for (const options of [{ datacenter: 'ams' }, { datacenter: 'ams2\n' }, { datacenter: null }, { typo: 'ams2' }]) await assert.rejects(arct[resource].listPage(options), ValidationError);
  }
  await assert.rejects(arct.datacenters.listPage({ location: 'ams' }), ValidationError);
  assert.equal(calls.length, 0);
});

test('new response fields may be absent or null and extras survive', async () => {
  for (const value of [undefined, null, 'ams2']) {
    const server = { ...fixtures.server, future: true };
    delete server.datacenter;
    if (value !== undefined) server.datacenter = value;
    const { arct } = client(() => server);
    const result = await arct.servers.get(server.id);
    assert.equal(result.datacenter, value);
    assert.equal(Object.hasOwn(result, 'datacenter'), value !== undefined);
    assert.equal(result.future, true);
  }
  for (const resource of ['locations', 'plans']) {
    for (const datacenters of [undefined, null, ['ams2']]) {
      const item = resource === 'locations' ? { code: 'ams' } : { slug: 'vm.small' };
      if (datacenters !== undefined) item.datacenters = datacenters;
      const { arct } = client(() => ({ data: [{ ...item, future: true }], pagination }));
      const page = await arct[resource].listPage();
      assert.deepEqual(page.data[0].datacenters, datacenters);
      assert.equal(page.data[0].future, true);
    }
  }
});

for (const [selectors, actual, matches] of [
  [{ datacenter: 'AMS2' }, { datacenter: 'ams2', location: 'ams' }, true],
  [{ datacenter: 'ams2' }, { datacenter: 'ams1', location: 'ams' }, false],
  [{ datacenter: 'ams2' }, { datacenter: null, location: 'ams' }, false],
  [{ datacenter: 'ams2' }, { location: 'ams' }, false],
  [{ location: 'AMS' }, { datacenter: 'ams2', location: 'ams' }, true],
  [{ location: 'AMS2' }, { datacenter: 'ams2', location: 'ams' }, true],
  [{ datacenter: 'ams2', location: 'fra' }, { datacenter: 'ams2', location: 'ams' }, false],
]) test(`retry reconciliation checks selectors ${JSON.stringify(selectors)} against ${JSON.stringify(actual)}`, async () => {
  const request = { ...body, ...selectors };
  if (!Object.hasOwn(selectors, 'datacenter')) delete request.datacenter;
  const server = { ...fixtures.server, ...actual };
  delete server.datacenter;
  Object.assign(server, actual);
  const { arct, calls } = client(n => n === 1 ? new TypeError('lost') : n === 2 ? Response.json({ error: { code: 'hostname_taken' } }, { status: 409 }) : { data: [server], pagination });
  await assert.rejects(arct.servers.create(request), error => {
    assert.ok(error instanceof UncertainOperationError);
    assert.equal(error.details.candidates[0].matches_request, matches);
    return true;
  });
  assert.equal(calls.filter(call => call.method === 'POST').length, 2);
  assert.equal(calls[0].body, calls[1].body);
  assert.equal(calls.length, 3);
});
