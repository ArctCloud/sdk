import { Arct, Secret, type Server, type VMStatus, type CreateServerRequest, type Location, type Plan, type Account, type ResizeOptions } from '../src/index.js';
const client = new Arct({ token: 'type-test' });
const unknown: VMStatus = 'future_status';
const create = await client.servers.create({ hostname: 'web-1', location: 'fra', plan: 'vm.small', image_id: 'image' });
const datacenterRequest: CreateServerRequest = { hostname: 'web-1', datacenter: 'ams2', plan: 'vm.small', image_id: 'image' };
interface LegacyRequest extends CreateServerRequest { location: string }
const legacyRequest: LegacyRequest = { hostname: 'web-1', location: 'ams', plan: 'vm.small', image_id: 'image' };
await client.servers.create(legacyRequest);
await client.servers.create(datacenterRequest);
await client.datacenters.listPage();
for await (const datacenter of client.datacenters.list()) { const code: string = datacenter.code; void code; }
await client.servers.listPage({ datacenter: 'ams2' });
await client.plans.listPage({ datacenter: 'ams2' });
await client.images.listPage({ datacenter: 'ams2' });
const oldLocation: Location = { code: 'ams', name: 'Amsterdam', region: null, status: 'online', is_preorder: false };
const compatibleServer: Pick<Server, 'datacenter'> = {};
const compatiblePlan: Pick<Plan, 'datacenters'> = {};
const compatibleAccount: Pick<Account, 'credit_balance' | 'credit_autopay'> = {};
const compatibleResize: Pick<ResizeOptions, 'credit_balance' | 'payment_methods'> = {};
// @ts-expect-error
client.servers.create({ ...datacenterRequest, unknown: true });
const orderId: string = create.order.id;
const server: Server | null = create.server;
const secret: Secret | null | undefined = create.password;
if (secret) secret.getSecretValue();
const request = await client.servers.resize('id', { plan: 'vm.medium', expected_amount: '4.1200' });
const status: string = request.status;
// @ts-expect-error
client.servers.create({ hostname: 'web-1', location: 'fra', plan: 'vm.small', image_id: 'image', billing_period: 'future' });
// @ts-expect-error
client.servers.listPage({ status: 'error' });
// @ts-expect-error
const password: string = create.password;
void [unknown, orderId, server, status, oldLocation, compatibleServer, compatiblePlan, compatibleAccount, compatibleResize];
