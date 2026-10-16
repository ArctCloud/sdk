import { createHash } from 'node:crypto';
import { setTimeout as delay } from 'node:timers/promises';
import { AccountApi } from './generated/apis/AccountApi.js';
import { Configuration, FetchError } from './generated/runtime.js';
import { APIError, ChargeUnknownError, UncertainOperationError, errorFrom } from './errors.js';

export interface RequestOptions { signal?: AbortSignal; timeoutMs?: number }
export interface ClientOptions {
  token?: string;
  baseURL?: string;
  fetch?: typeof globalThis.fetch;
  timeoutMs?: number;
  allowInsecureLocalhost?: boolean;
}

const events = new Map<string, number[]>();
const accounts = new Map<string, string>();
const resolutions = new Map<string, { promise: Promise<void>; controller: AbortController; waiters: number }>();
const quoteAmounts = new WeakMap<object, string>();
export function quotedAmount(plan: { amount_due_today: number | null }): string | number | null { return quoteAmounts.get(plan) ?? plan.amount_due_today; }

function tokenKey(token: string, baseURL: string): string { return createHash('sha256').update(`${baseURL}\0${token}`).digest('hex'); }
function abortError(): DOMException { return new DOMException('Operation aborted.', 'AbortError'); }
export async function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  try { await delay(ms, undefined, { signal }); }
  catch { throw abortError(); }
}

function abortable<T>(promise: Promise<T>, signal: AbortSignal, onAbort?: () => void): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const aborted = () => { signal.removeEventListener('abort', aborted); onAbort?.(); reject(abortError()); };
    signal.addEventListener('abort', aborted, { once: true });
    promise.then(value => { signal.removeEventListener('abort', aborted); resolve(value); }, error => { signal.removeEventListener('abort', aborted); reject(error); });
    if (signal.aborted) aborted();
  });
}
async function responseText(response: Response, signal: AbortSignal): Promise<string> {
  if (!response.body) return '';
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let text = '';
  try {
    for (;;) {
      const chunk = await abortable(reader.read(), signal, () => { void reader.cancel().catch(() => {}); });
      if (chunk.done) return text + decoder.decode();
      text += decoder.decode(chunk.value, { stream: true });
    }
  } finally { reader.releaseLock(); }
}
function record(value: unknown): value is Record<string, unknown> { return value !== null && typeof value === 'object' && !Array.isArray(value); }
function identified(value: unknown, key = 'id'): value is Record<string, unknown> { return record(value) && typeof value[key] === 'string' && value[key].length > 0; }
function server(value: unknown): boolean { return identified(value) && ['status', 'hostname', 'location', 'plan', 'billing_period', 'created_at'].every(key => typeof value[key] === 'string'); }
function validResponse(path: string, method: string, value: unknown): boolean {
  if (!record(value)) return false;
  if (method === 'GET' && ['/servers', '/locations', '/plans', '/images', '/invoices', '/ssh-keys'].includes(path)) {
    if (!Array.isArray(value.data) || !record(value.pagination) || !['page', 'per_page', 'total', 'total_pages'].every(key => Number.isInteger(value.pagination && (value.pagination as Record<string, unknown>)[key]))) return false;
    return value.data.every(item => path === '/servers' ? server(item) : identified(item, path === '/locations' ? 'code' : path === '/plans' ? 'slug' : 'id'));
  }
  if (path === '/servers' && method === 'POST') return identified(value.order) && (value.order.server_id === null || typeof value.order.server_id === 'string') && Object.hasOwn(value, 'server') && (value.server === null || server(value.server)) && (value.password == null || typeof value.password === 'string');
  if (path.endsWith('/reinstall')) return server(value.server) && (value.password == null || typeof value.password === 'string');
  if (path.endsWith('/resize-options')) return typeof value.can_resize === 'boolean' && typeof value.current_plan === 'string' &&
    (value.pending_resize === null || record(value.pending_resize)) && Array.isArray(value.plans) && value.plans.every(plan =>
      identified(plan, 'slug') && typeof plan.eligible === 'boolean' &&
      (plan.amount_due_today === null || (typeof plan.amount_due_today === 'number' && Number.isFinite(plan.amount_due_today))));
  if (path.endsWith('/resize')) return identified(value, 'resize_id') && typeof value.status === 'string';
  if (path.startsWith('/servers/')) return server(value);
  return identified(value);
}
function invalidResponse(read: boolean, status: number, code = 'invalid_response'): APIError {
  return new (read ? APIError : UncertainOperationError)(read ? 'The API returned an invalid response.' : 'The mutation response is invalid; its outcome is unknown. Verify before repeating.', status, code);
}

export class Policy {
  readonly baseURL: string;
  #token: string;
  #key: string;
  #fetch: typeof globalThis.fetch;
  #timeoutMs: number;
  #pathPrefix: string;
  constructor(options: ClientOptions, token: string) {
    const url = new URL(options.baseURL ?? 'https://api.arct.cloud/v1');
    if (url.username || url.password || url.search || url.hash) throw new TypeError('Base URL must not contain credentials, query or fragment.');
    const local = ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname);
    if (url.protocol !== 'https:' && !(url.protocol === 'http:' && local && options.allowInsecureLocalhost)) throw new TypeError('HTTPS is required; localhost tests require allowInsecureLocalhost.');
    this.baseURL = url.href.replace(/\/+$/, '');
    this.#pathPrefix = url.pathname.replace(/\/+$/, '');
    this.#token = token;
    this.#key = tokenKey(token, this.baseURL);
    this.#fetch = options.fetch ?? globalThis.fetch;
    this.#timeoutMs = options.timeoutMs ?? 30_000;
    if (!Number.isFinite(this.#timeoutMs) || this.#timeoutMs <= 0) throw new TypeError('timeoutMs must be positive.');
  }
  setAccount(id: string): void { accounts.set(this.#key, id); }
  async #ensureAccount(signal: AbortSignal): Promise<void> {
    if (accounts.has(this.#key)) return;
    let pending = resolutions.get(this.#key);
    if (!pending || pending.controller.signal.aborted) {
      const controller = new AbortController();
      const promise = (async () => {
        try {
          const api = new AccountApi(new Configuration({ basePath: this.baseURL, accessToken: this.#token, fetchApi: this.fetch }));
          const account = await api.accountGet({ signal: controller.signal, redirect: 'manual' });
          this.setAccount(account.id);
        } catch (error) {
          if (error instanceof FetchError) throw error.cause;
          throw error;
        }
      })();
      pending = { promise, controller, waiters: 0 };
      const current = pending;
      resolutions.set(this.#key, current);
      const clear = () => { if (resolutions.get(this.#key) === current) resolutions.delete(this.#key); };
      promise.then(clear, clear);
    }
    pending.waiters++;
    try { await abortable(pending.promise, signal); }
    finally {
      if (--pending.waiters === 0) {
        pending.controller.abort();
        if (resolutions.get(this.#key) === pending) resolutions.delete(this.#key);
      }
    }
  }
  async #throttle(read: boolean, paid: boolean, signal: AbortSignal): Promise<void> {
    const keys = read ? [`token:${this.#key}`] : [`token:${this.#key}`, ...(accounts.has(this.#key) ? [`account:${this.baseURL}:${accounts.get(this.#key)}`] : [])];
    const limits: Array<[string, number, number]> = keys.flatMap(key => read ? [[`${key}:read`, 120, 60_000] as [string, number, number]] : [
      [`${key}:write`, 30, 60_000] as [string, number, number],
      ...(paid ? [[`${key}:paid-minute`, 5, 60_000], [`${key}:paid-hour`, 20, 3_600_000]] as Array<[string, number, number]> : []),
    ]);
    for (;;) {
      if (signal.aborted) throw abortError();
      const now = Date.now();
      let wait = 0;
      for (const [key, cap, window] of limits) {
        const recent = (events.get(key) ?? []).filter(time => time > now - window);
        events.set(key, recent);
        if (recent.length >= cap) wait = Math.max(wait, recent[recent.length - cap] + window - now);
      }
      if (wait <= 0) {
        for (const [key] of limits) events.get(key)!.push(now);
        return;
      }
      await sleep(wait, signal);
    }
  }
  options(options: RequestOptions): RequestInit {
    const timeoutMs = options.timeoutMs ?? this.#timeoutMs;
    if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) throw new TypeError('timeoutMs must be positive.');
    const deadline = AbortSignal.timeout(Math.ceil(timeoutMs));
    return { signal: options.signal ? AbortSignal.any([options.signal, deadline]) : deadline, redirect: 'manual' };
  }
  readonly fetch: typeof globalThis.fetch = async (input, init = {}) => {
    const url = String(input);
    const signal = init.signal ?? AbortSignal.timeout(this.#timeoutMs);
    const method = init.method ?? 'GET';
    const read = method === 'GET';
    const path = new URL(url).pathname.slice(this.#pathPrefix.length);
    const create = method === 'POST' && path === '/servers';
    const paid = create || (method === 'POST' && path.endsWith('/resize'));
    if (!read) await this.#ensureAccount(signal);
    let promoRetried = false;
    for (let attempt = 1; attempt <= 3; attempt++) {
      await this.#throttle(read, paid, signal);
      if (signal.aborted) throw abortError();
      let response: Response;
      try {
        response = await abortable(this.#fetch(input, { ...init, signal, redirect: 'manual' }), signal);
      } catch {
        if (signal.aborted) throw abortError();
        if ((read || create) && attempt < 3) { await sleep((2 ** (attempt - 1)) * 100 + Math.random() * 100, signal); continue; }
        throw new (read ? APIError : UncertainOperationError)(read ? 'Network request failed.' : 'The mutation outcome is unknown; verify before repeating.', 0, 'network_error');
      }
      if (signal.aborted) throw abortError();
      let text: string;
      try { text = await responseText(response, signal); }
      catch {
        if (signal.aborted) throw abortError();
        if (read && attempt < 3) { await sleep((2 ** (attempt - 1)) * 100 + Math.random() * 100, signal); continue; }
        throw invalidResponse(read, response.status, 'body_error');
      }
      if (signal.aborted) throw abortError();
      let body: unknown;
      try {
        body = JSON.parse(text, function (this: object, key: string, value: unknown, context?: { source?: string }) {
          if (path.endsWith('/resize-options') && key === 'amount_due_today' && typeof value === 'number') {
            if (context?.source === undefined) throw new APIError('The runtime cannot preserve the resize quote.', 0, 'unsupported_runtime');
            quoteAmounts.set(this, context.source);
          }
          return value;
        });
      } catch (error) {
        if (response.ok && !(response.status === 204 && method === 'DELETE')) throw invalidResponse(read, response.status);
      }
      if (response.ok) {
        if (!(response.status === 204 && method === 'DELETE') && !validResponse(path, method, body)) throw invalidResponse(read, response.status);
        response.json = async () => body;
        return response;
      }
      const error = errorFrom(response.status, body, this.#token);
      if (error instanceof ChargeUnknownError) throw error;
      if (create && attempt > 1 && error.code === 'hostname_taken') {
        throw new UncertainOperationError('Creation outcome is unknown; a matching hostname does not prove ownership.', error.status, error.code, error.details);
      }
      const retryable = response.status === 429 || ((read || create) && [500, 503].includes(response.status));
      const promo = create && error.code === 'promo_changed' && !promoRetried;
      if (attempt < 3 && (retryable || promo)) {
        if (promo) promoRetried = true;
        const retryAfter = response.headers.get('Retry-After');
        const seconds = retryAfter !== null && /^\d+(?:\.\d+)?$/.test(retryAfter) ? Number(retryAfter) : NaN;
        const at = retryAfter ? Date.parse(retryAfter) : NaN;
        const wait = Number.isFinite(seconds) ? seconds * 1000 : Number.isFinite(at) ? Math.max(0, at - Date.now()) : (2 ** (attempt - 1)) * 100 + Math.random() * 100;
        await sleep(wait, signal);
        continue;
      }
      if (!read && [500, 503].includes(response.status)) throw new UncertainOperationError('The mutation outcome is unknown; verify before repeating.', error.status, error.code, error.details);
      throw error;
    }
    throw new APIError('Attempt budget exhausted.');
  };
}
