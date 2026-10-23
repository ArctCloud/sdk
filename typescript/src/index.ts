import { inspect } from 'node:util';
import { AccountApi, CatalogApi, InvoicesApi, SSHKeysApi, ServersApi } from './generated/apis/index.js';
import type { ServersListRequest } from './generated/apis/ServersApi.js';
import type { DatacentersListRequest, ImagesListRequest, PlansListRequest, LocationsListRequest } from './generated/apis/CatalogApi.js';
import type { InvoicesListRequest } from './generated/apis/InvoicesApi.js';
import type { SshKeysListRequest } from './generated/apis/SSHKeysApi.js';
import { Configuration, FetchError } from './generated/runtime.js';
import type * as M from './generated/models/index.js';
import { APIError, AuthenticationError, ConflictError, NotFoundError, OperationFailedError, Secret, UncertainOperationError, ValidationError, WaitTimeoutError } from './errors.js';
import { Policy, quotedAmount, sleep, type ClientOptions, type RequestOptions } from './policy.js';

export { APIError, AuthenticationError, PaymentRequiredError, PermissionDeniedError, NotFoundError, ConflictError, ValidationError, RateLimitError, ChargeUnknownError, UncertainOperationError, OperationFailedError, WaitTimeoutError, Secret } from './errors.js';
export type { ClientOptions, RequestOptions } from './policy.js';
export * from './generated/models/index.js';
type SecretResult<T> = { [K in keyof T]: K extends 'password' ? Secret | null | undefined : T[K] };
export type CreateResult = SecretResult<M.CreateServerResponse>;
export type ReinstallResult = SecretResult<M.ReinstallResponse>;
export interface WaitOptions extends RequestOptions { pollIntervalMs?: number; plan?: string; hostname?: string }
export type ServerListOptions = ServersListRequest;
export type PageOptions = LocationsListRequest;

const context = new WeakMap<object, { action: string; hostname?: string; request?: M.CreateServerRequest }>();
function protect<T extends { password?: string | null }>(result: T): SecretResult<T> {
  return { ...result, ...(typeof result.password === 'string' ? { password: new Secret(result.password) } : {}) } as SecretResult<T>;
}
async function unwrap<T>(call: Promise<T>): Promise<T> {
  try { return await call; } catch (error) { if (error instanceof FetchError) throw error.cause; throw error; }
}
async function* paginate<T>(load: (options: PageOptions, request: RequestOptions) => Promise<{ data: T[]; pagination: M.Pagination }>, options: PageOptions, request: RequestOptions): AsyncGenerator<T> {
  for (let page = options.page ?? 1; ; page++) {
    const result = await load({ ...options, perPage: options.perPage ?? 100, page }, request);
    if (result.data.length === 0) return;
    for (const item of result.data) { if (request.signal?.aborted) throw new DOMException('Operation aborted.', 'AbortError'); yield item; }
    if (page >= result.pagination.total_pages) return;
  }
}
function pageValidation(options: { page?: number; perPage?: number }): void {
  if (options.page !== undefined && (!Number.isInteger(options.page) || options.page < 1 || options.page > 100000)) throw new ValidationError('page must be an integer from 1 to 100000.', 0, 'validation_error');
  if (options.perPage !== undefined && (!Number.isInteger(options.perPage) || options.perPage < 1 || options.perPage > 100)) throw new ValidationError('perPage must be an integer from 1 to 100.', 0, 'validation_error');
}
function requestValidation(value: object, keys: string[]): void {
  if (!value || typeof value !== 'object' || Array.isArray(value) || Object.keys(value).some(key => !keys.includes(key))) throw new ValidationError('Unsupported request fields.', 0, 'validation_error');
}
function datacenterValidation(value: unknown): void {
  if (value !== undefined && (typeof value !== 'string' || !/^[A-Za-z]{2,5}[0-9]{1,2}$/.test(value) || value.trim() !== value)) throw new ValidationError('Invalid datacenter code.', 0, 'validation_error');
}
function catalogValidation(options: PlansListRequest | ImagesListRequest): void {
  requestValidation(options, ['location', 'datacenter', 'page', 'perPage']);
  pageValidation(options);
  datacenterValidation(options.datacenter);
}

export class Arct {
  #policy: Policy;
  readonly account;
  readonly servers;
  readonly sshKeys;
  readonly locations;
  readonly datacenters;
  readonly plans;
  readonly images;
  readonly invoices;
  constructor(options: ClientOptions = {}) {
    const token = options.token ?? process.env.ARCT_TOKEN;
    if (!token?.trim() || /[\r\n]/.test(token)) throw new AuthenticationError('Set ARCT_TOKEN or provide a non-empty token.', 0, 'missing_token');
    this.#policy = new Policy(options, token);
    const configuration = new Configuration({ basePath: this.#policy.baseURL, accessToken: token, fetchApi: this.#policy.fetch });
    const account = new AccountApi(configuration);
    const servers = new ServersApi(configuration);
    const catalog = new CatalogApi(configuration);
    const keys = new SSHKeysApi(configuration);
    const invoices = new InvoicesApi(configuration);
    const run = async <T>(fn: (init: RequestInit) => Promise<T>, request: RequestOptions = {}): Promise<T> => {
      const init = this.#policy.options(request);
      try {
        const result = await unwrap(fn(init));
        if (init.signal?.aborted) throw new DOMException('Operation aborted.', 'AbortError');
        return result;
      } catch (error) {
        if (init.signal?.aborted) throw new DOMException('Operation aborted.', 'AbortError');
        if (error instanceof SyntaxError) throw new APIError('The API returned invalid JSON.', 0, 'invalid_response');
        throw error;
      }
    };
    this.account = { get: async (request: RequestOptions = {}): Promise<M.Account> => {
      const result = await run(init => account.accountGet(init), request);
      if (result.id) this.#policy.setAccount(result.id);
      return result;
    } };
    const serverPage = async (options: ServersListRequest = {}, request: RequestOptions = {}) => {
      requestValidation(options, ['status', 'location', 'datacenter', 'page', 'perPage']);
      pageValidation(options);
      datacenterValidation(options.datacenter);
      if (options.status !== undefined && !['provisioning', 'running', 'stopped', 'restarting', 'reinstalling', 'restoring', 'deleting', 'suspended', 'pre_order'].includes(options.status)) throw new ValidationError('Unsupported server status filter.', 0, 'validation_error');
      return run(init => servers.serversList(options, init), request);
    };
    const serverGet = (id: string, request: RequestOptions = {}) => run(init => servers.serversGet({ serverId: id }, init), request);
    const resizeOptions = (id: string, request: RequestOptions = {}) => run(init => servers.serversResizeOptions({ serverId: id }, init), request);
    const state = async (action: 'start' | 'stop' | 'restart', id: string, request: RequestOptions = {}) => {
      const methods = { start: servers.serversStart.bind(servers), stop: servers.serversStop.bind(servers), restart: servers.serversRestart.bind(servers) };
      const result = await run(init => methods[action]({ serverId: id }, init), request);
      context.set(result, { action });
      return result;
    };
    this.servers = {
      listPage: serverPage,
      list: (options: ServersListRequest = {}, request: RequestOptions = {}) => paginate((page, req) => serverPage({ ...options, ...page }, req), options, request),
      get: serverGet,
      create: async (body: M.CreateServerRequest, request: RequestOptions = {}): Promise<CreateResult> => {
        requestValidation(body, ['hostname', 'plan', 'image_id', 'datacenter', 'location', 'billing_period', 'ssh_key_ids', 'coupon_code', 'enable_backups', 'payment_method']);
        datacenterValidation(body.datacenter);
        if (!['hostname', 'plan', 'image_id'].every(key => typeof body[key as keyof M.CreateServerRequest] === 'string' && (body[key as keyof M.CreateServerRequest] as string).length > 0) || (body.datacenter === undefined && body.location === undefined) || (body.location !== undefined && (typeof body.location !== 'string' || !/^[A-Za-z0-9-]{1,10}$/.test(body.location)))) throw new ValidationError('Provide hostname, plan, image_id and datacenter or location.', 0, 'validation_error');
        request = { ...request, signal: this.#policy.options(request).signal! };
        if (body.billing_period !== undefined && !['monthly', 'quarterly', 'semi_annual', 'yearly'].includes(body.billing_period)) throw new ValidationError('Unsupported billing period.', 0, 'validation_error');
        if (body.payment_method !== undefined && !['card', 'credit'].includes(body.payment_method)) throw new ValidationError('Unsupported payment method.', 0, 'validation_error');
        const payload = JSON.parse(JSON.stringify(body)) as M.CreateServerRequest;
        const started = Date.now();
        try {
          const result = protect(await run(init => servers.serversCreate({ createServerRequest: payload }, init), request));
          context.set(result, { action: 'create', hostname: body.hostname, request: payload });
          return result;
        } catch (error) {
          if (error instanceof UncertainOperationError && error.code === 'hostname_taken') {
            const candidates: unknown[] = [];
            try {
              for await (const server of this.servers.list({}, request)) {
                if (server.hostname.toLowerCase() !== payload.hostname.toLowerCase()) continue;
                const location = payload.location;
                const matches = (payload.datacenter === undefined || server.datacenter?.toLowerCase() === payload.datacenter.toLowerCase()) &&
                  (location === undefined || (/^[A-Za-z]{2,5}[0-9]{1,2}$/.test(location) ? server.datacenter?.toLowerCase() : server.location.toLowerCase()) === location.toLowerCase());
                candidates.push({ ...server, matches_request: matches && server.plan === payload.plan && server.billing_period === (payload.billing_period ?? 'monthly'), created_after_request: Date.parse(server.created_at) >= started });
              }
            } catch (discoveryError) { if (request.signal?.aborted) throw new DOMException('Operation aborted.', 'AbortError'); }
            throw new UncertainOperationError(error.message, error.status, error.code, { ...error.details, candidates });
          }
          throw error;
        }
      },
      update: (id: string, body: M.ServerUpdate, request: RequestOptions = {}) => run(init => servers.serversUpdate({ serverId: id, serverUpdate: body }, init), request),
      delete: (id: string, options: { atPeriodEnd?: boolean } = {}, request: RequestOptions = {}) => run(init => servers.serversDelete({ serverId: id, ...options }, init), request),
      start: (id: string, request: RequestOptions = {}) => state('start', id, request),
      stop: (id: string, request: RequestOptions = {}) => state('stop', id, request),
      restart: (id: string, request: RequestOptions = {}) => state('restart', id, request),
      reinstall: async (id: string, body: M.ServerReinstall, request: RequestOptions = {}): Promise<ReinstallResult> => {
        const result = protect(await run(init => servers.serversReinstall({ serverId: id, serverReinstall: body }, init), request));
        context.set(result, { action: 'reinstall' });
        return result;
      },
      cancelDeletion: (id: string, request: RequestOptions = {}) => run(init => servers.serversCancelDeletion({ serverId: id }, init), request),
      resizeOptions,
      resize: async (id: string, body: M.ResizeServerRequest, request: RequestOptions = {}): Promise<M.ResizeResponse> => {
        request = { ...request, signal: this.#policy.options(request).signal! };
        let payload = body;
        if (body.expected_amount === undefined) {
          const quote = await resizeOptions(id, request);
          const selected = quote.plans.find(plan => plan.slug === body.plan);
          if (!quote.can_resize || !selected?.eligible || selected.amount_due_today == null) throw new ConflictError('Selected resize plan is not eligible or has no quote.', 409, quote.blocked_code ?? 'ineligible');
          payload = { ...body, expected_amount: quotedAmount(selected) };
        }
        if (payload.expected_amount !== null && !/^(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(String(payload.expected_amount))) throw new ValidationError('expected_amount must be a non-negative amount.', 0, 'validation_error');
        return run(init => servers.serversResize({ serverId: id, resizeServerRequest: payload }, init), request);
      },
      waitUntil: (source: string | M.Server | CreateResult | ReinstallResult, targetStatus: M.VMStatus, options: WaitOptions = {}) => this.#wait(source, targetStatus, options),
    };
    const keyPage = async (options: SshKeysListRequest = {}, request: RequestOptions = {}) => { pageValidation(options); return run(init => keys.sshKeysList(options, init), request); };
    this.sshKeys = {
      listPage: keyPage, list: (options: SshKeysListRequest = {}, request: RequestOptions = {}) => paginate(keyPage, options, request),
      get: (id: string, request: RequestOptions = {}) => run(init => keys.sshKeysGet({ keyId: id }, init), request),
      create: (body: M.SshKeyCreate, request: RequestOptions = {}) => run(init => keys.sshKeysCreate({ sshKeyCreate: body }, init), request),
      delete: (id: string, request: RequestOptions = {}) => run(init => keys.sshKeysDelete({ keyId: id }, init), request),
    };
    const locationsPage = async (options: LocationsListRequest = {}, request: RequestOptions = {}) => { pageValidation(options); return run(init => catalog.locationsList(options, init), request); };
    const datacentersPage = async (options: DatacentersListRequest = {}, request: RequestOptions = {}) => { requestValidation(options, ['page', 'perPage']); pageValidation(options); return run(init => catalog.datacentersList(options, init), request); };
    const plansPage = async (options: PlansListRequest = {}, request: RequestOptions = {}) => { catalogValidation(options); return run(init => catalog.plansList(options, init), request); };
    const imagesPage = async (options: ImagesListRequest = {}, request: RequestOptions = {}) => { catalogValidation(options); return run(init => catalog.imagesList(options, init), request); };
    const invoicesPage = async (options: InvoicesListRequest = {}, request: RequestOptions = {}) => { pageValidation(options); return run(init => invoices.invoicesList(options, init), request); };
    this.locations = { listPage: locationsPage, list: (options: LocationsListRequest = {}, request: RequestOptions = {}) => paginate(locationsPage, options, request) };
    this.datacenters = { listPage: datacentersPage, list: (options: DatacentersListRequest = {}, request: RequestOptions = {}) => paginate(datacentersPage, options, request) };
    this.plans = { listPage: plansPage, list: (options: PlansListRequest = {}, request: RequestOptions = {}) => paginate((page, req) => plansPage({ ...options, ...page }, req), options, request) };
    this.images = { listPage: imagesPage, list: (options: ImagesListRequest = {}, request: RequestOptions = {}) => paginate((page, req) => imagesPage({ ...options, ...page }, req), options, request) };
    this.invoices = { listPage: invoicesPage, list: (options: InvoicesListRequest = {}, request: RequestOptions = {}) => paginate(invoicesPage, options, request), get: (id: string, request: RequestOptions = {}) => run(init => invoices.invoicesGet({ invoiceId: id }, init), request) };
  }
  async #wait(source: string | M.Server | CreateResult | ReinstallResult, target: M.VMStatus, options: WaitOptions): Promise<M.Server> {
    const timeout = options.timeoutMs ?? 600_000;
    const poll = options.pollIntervalMs ?? 5_000;
    if (!Number.isFinite(timeout) || timeout <= 0) throw new TypeError('timeoutMs must be positive.');
    if (poll < 5_000 || poll > 10_000 || !Number.isFinite(poll)) throw new TypeError('pollIntervalMs must be from 5000 to 10000.');
    const deadline = performance.now() + timeout;
    const timer = AbortSignal.timeout(Math.ceil(timeout));
    const signal = options.signal ? AbortSignal.any([options.signal, timer]) : timer;
    const request = { signal };
    const metadata = typeof source === 'object' ? context.get(source) : undefined;
    const initial = typeof source === 'object' ? ('server' in source ? source.server as M.Server | null : source as M.Server) : undefined;
    const order = typeof source === 'object' && 'order' in source ? source.order as M.Order : undefined;
    let id = typeof source === 'string' ? source : initial?.id ?? order?.server_id ?? undefined;
    const hostname = metadata?.hostname ?? options.hostname;
    const transitionRequired = ['restart', 'reinstall'].includes(metadata?.action ?? '') || (typeof source === 'object' && 'server' in source && !('order' in source));
    let transition = initial?.status !== undefined && initial.status !== target;
    let last: unknown = initial ?? source;
    try {
      for (;;) {
        if (signal.aborted || performance.now() >= deadline) throw new WaitTimeoutError(last);
        if (!id && hostname) {
          const found: M.Server[] = [];
          for await (const server of this.servers.list({}, request)) if (server.hostname.toLowerCase() === hostname.toLowerCase()) found.push(server);
          if (found.length > 1) throw new UncertainOperationError('Multiple hostname matches; server discovery is uncertain.', 0, 'ambiguous_discovery', { candidates: found });
          if (found.length === 1) id = found[0].id;
          last = found[0] ?? last;
          if (found[0] && found[0].status === target && !transitionRequired && !options.plan) return found[0];
        }
        if (id) {
          if (options.plan) {
            const resize = await this.servers.resizeOptions(id, request);
            const server = await this.servers.get(id, request);
            last = server;
            if (!resize.pending_resize && resize.current_plan === options.plan && server.plan === options.plan && server.status === target) return server;
            if (['error', 'deleting', 'suspended'].includes(server.status)) throw new OperationFailedError(`Server entered terminal state: ${server.status}.`, 0, 'terminal_state', { server });
          } else {
            try {
              const server = await this.servers.get(id, request);
              last = server;
              transition ||= server.status !== target;
              if (server.status === target && (!transitionRequired || transition)) return server;
              if (['error', 'deleting', 'suspended'].includes(server.status)) throw new OperationFailedError(`Server entered terminal state: ${server.status}.`, 0, 'terminal_state', { server });
            } catch (error) { if (!(error instanceof NotFoundError && order)) throw error; }
          }
        } else if (!hostname) throw new ValidationError('Provide the acknowledged creation result or a hostname for delayed discovery.', 0, 'missing_server');
        await sleep(Math.min(poll, Math.max(1, deadline - performance.now())), signal);
      }
    } catch (error) {
      if (options.signal?.aborted) throw new DOMException('Operation aborted.', 'AbortError');
      if (timer.aborted || performance.now() >= deadline) throw new WaitTimeoutError(last);
      throw error;
    }
  }
}

Object.defineProperty(Arct.prototype, inspect.custom, { value: () => 'Arct([REDACTED])' });
