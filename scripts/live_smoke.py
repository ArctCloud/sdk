import json
import os
import urllib.error
import urllib.request

BASE_URL = "https://api.arct.cloud/v1"
PATHS = ("/account", "/servers?per_page=1", "/locations", "/plans", "/images", "/ssh-keys?per_page=1", "/invoices?per_page=1")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


def main():
    token = os.environ.get("ARCT_READ_TOKEN")
    if not token:
        print("Skipped live smoke: ARCT_READ_TOKEN is not set.")
        return 0
    opener = urllib.request.build_opener(NoRedirect)
    for path in PATHS:
        request = urllib.request.Request(BASE_URL + path, headers={"Authorization": f"Bearer {token}", "Accept": "application/json", "User-Agent": "arct-sdk-ci/0.1.0"}, method="GET")
        try:
            with opener.open(request, timeout=20) as response:
                json.load(response)
        except urllib.error.HTTPError as error:
            print(f"GET {path} failed: HTTP {error.code}")
            return 1
        except (urllib.error.URLError, TimeoutError, ValueError, OSError):
            print(f"GET {path} failed: transport or JSON error")
            return 1
        print(f"GET {path} passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
