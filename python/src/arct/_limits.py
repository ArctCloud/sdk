from collections import defaultdict, deque
import hashlib
import threading
import time

_LOCK = threading.Lock()
_EVENTS = defaultdict(deque)
_ACCOUNTS = {}


def token_key(token):
    return hashlib.sha256(token.encode()).hexdigest()


def account_for(key):
    with _LOCK:
        return _ACCOUNTS.get(key)


def bind(key, account):
    with _LOCK:
        _ACCOUNTS[key] = str(account)


def reserve(key, account, method, paid):
    now = time.monotonic()
    categories = [("read", 120, 60)] if method == "GET" else [("write", 30, 60)]
    if paid:
        categories += [("paid_minute", 5, 60), ("paid_hour", 20, 3600)]
    identities = [("token", key)] + ([("account", account)] if method != "GET" and account else [])
    buckets = [(identity + (category,), limit, window) for identity in identities for category, limit, window in categories]
    with _LOCK:
        delay = 0.0
        for bucket, limit, window in buckets:
            events = _EVENTS[bucket]
            while events and events[0] <= now - window:
                events.popleft()
            if len(events) >= limit:
                delay = max(delay, events[0] + window - now)
        if not delay:
            for bucket, _, _ in buckets:
                _EVENTS[bucket].append(now)
        return delay
