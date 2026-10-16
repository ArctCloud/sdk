import { inspect } from 'node:util';

export class Secret {
  #value: string;
  constructor(value: string) { this.#value = value; }
  getSecretValue(): string { return this.#value; }
  toString(): string { return '[REDACTED]'; }
  toJSON(): string { return '[REDACTED]'; }
}

Object.defineProperty(Secret.prototype, inspect.custom, { value: () => 'Secret([REDACTED])' });

export function redact(value: unknown, token = ''): unknown {
  if (typeof value === 'string') return token ? value.split(token).join('[REDACTED]') : value;
  if (Array.isArray(value)) return value.map(item => redact(item, token));
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, /password|secret|authorization|access_token|api_key|^token$/i.test(key) ? '[REDACTED]' : redact(item, token)]));
  return value;
}

export class APIError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;
  readonly fields: unknown;
  constructor(message: string, status = 0, code = 'api_error', details: Record<string, unknown> = {}) {
    super(message);
    this.name = new.target.name;
    this.status = status;
    this.code = code;
    this.details = details;
    this.fields = details.fields;
  }
  toJSON(): object { return { error: { type: this.name, status: this.status, code: this.code, message: this.message, details: this.details } }; }
}
export class AuthenticationError extends APIError {}
export class PaymentRequiredError extends APIError {}
export class PermissionDeniedError extends APIError {}
export class NotFoundError extends APIError {}
export class ConflictError extends APIError {}
export class ValidationError extends APIError {}
export class RateLimitError extends APIError {}
export class ChargeUnknownError extends APIError {}
export class UncertainOperationError extends APIError {}
export class OperationFailedError extends APIError {}
export class WaitTimeoutError extends APIError {
  readonly lastState: unknown;
  constructor(lastState: unknown) {
    const preorder = (lastState as { status?: string })?.status === 'pre_order';
    super(preorder ? 'Pre-order is not ready; waiting timed out.' : 'Waiting timed out; operation completion is unverified.', 0, 'wait_timeout');
    this.lastState = lastState;
  }
}

export function errorFrom(status: number, body: unknown, token: string): APIError {
  const error = (body as { error?: { code?: unknown; message?: unknown; details?: unknown } })?.error;
  const code = typeof error?.code === 'string' ? String(redact(error.code, token)) : `http_${status}`;
  const rawDetails = error?.details && typeof error.details === 'object' ? error.details : {};
  const details = redact(rawDetails, token) as Record<string, unknown>;
  let message = typeof error?.message === 'string' ? String(redact(error.message, token)) : `API request failed (HTTP ${status}).`;
  if (code === 'insufficient_scope') message += ' Use a token with read_write scope for mutations.';
  if (code === 'api_access_disabled') message += ' Enable API access in the Arct dashboard.';
  const Type = Object.hasOwn(rawDetails, 'order_intent_id') || (status === 409 && code === 'payment_pending') ? ChargeUnknownError
    : ({ 401: AuthenticationError, 402: PaymentRequiredError, 403: PermissionDeniedError, 404: NotFoundError, 409: ConflictError, 422: ValidationError, 429: RateLimitError } as Record<number, typeof APIError>)[status] ?? APIError;
  return new Type(message, status, code, details);
}
