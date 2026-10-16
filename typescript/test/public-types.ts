import { Arct, Secret, type Server, type VMStatus } from '../src/index.js';
const client = new Arct({ token: 'type-test' });
const unknown: VMStatus = 'future_status';
const create = await client.servers.create({ hostname: 'web-1', location: 'fra', plan: 'vm.small', image_id: 'image' });
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
void [unknown, orderId, server, status];
