import re


def safe(value, token=""):
    if isinstance(value, dict):
        return {k: "[REDACTED]" if any(s in k.lower() for s in ("password", "authorization", "token", "secret")) and k not in ("token_id",) else safe(v, token) for k, v in value.items()}
    if isinstance(value, list):
        return [safe(v, token) for v in value]
    if isinstance(value, str):
        value = value.replace(token, "[REDACTED]") if token else value
        return re.sub(r"arct_[A-Za-z0-9_-]+", "[REDACTED]", value)
    return value


class APIError(Exception):
    def __init__(self, message="API request failed", *, status=None, code="api_error", details=None, token=""):
        self.status = status
        self.code = safe(code)
        self.details = safe(details or {}, token)
        self.message = safe(message, token)
        super().__init__(self.message)

    def __repr__(self):
        return f"{type(self).__name__}(status={self.status!r}, code={self.code!r})"


class AuthenticationError(APIError): pass
class PaymentRequiredError(APIError): pass
class PermissionDeniedError(APIError): pass
class NotFoundError(APIError): pass
class ConflictError(APIError): pass
class ValidationError(APIError):
    @property
    def fields(self):
        return self.details.get("fields", [])
class RateLimitError(APIError): pass
class ChargeUnknownError(APIError): pass
class UncertainOperationError(APIError):
    def __init__(self, *args, candidates=None, **kwargs):
        self.candidates = candidates or []
        super().__init__(*args, **kwargs)
class WaitTimeoutError(APIError, TimeoutError):
    def __init__(self, message="Wait deadline exceeded", *, last_state=None):
        self.last_state = last_state
        super().__init__(message, code="wait_timeout")
class OperationFailedError(APIError):
    def __init__(self, last_state):
        self.last_state = last_state
        super().__init__("Server entered a terminal state", code="operation_failed")


def from_response(response, token):
    try:
        error = response.json().get("error", {})
        if not isinstance(error, dict):
            error = {}
    except (ValueError, AttributeError):
        error = {}
    code = error.get("code", "http_error")
    details = error.get("details")
    details = details if isinstance(details, dict) else {}
    charge = "order_intent_id" in details or (response.status_code == 409 and code == "payment_pending")
    kind = ChargeUnknownError if charge else {401: AuthenticationError, 402: PaymentRequiredError, 403: PermissionDeniedError, 404: NotFoundError, 409: ConflictError, 422: ValidationError, 429: RateLimitError}.get(response.status_code, APIError)
    message = error.get("message") or f"API request failed with HTTP {response.status_code}"
    if code == "insufficient_scope":
        message = "A read_write token is required for this operation"
    elif code == "api_access_disabled":
        message = "Enable API access in the Arct Cloud dashboard"
    return kind(message, status=response.status_code, code=code, details=details, token=token)
