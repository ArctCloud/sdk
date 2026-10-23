import json
import os
import re
import urllib.error
import urllib.request

BASE_URL = "https://api.arct.cloud/v1"
PATHS = ("/account", "/servers?per_page=1", "/locations", "/plans", "/images", "/ssh-keys?per_page=1", "/invoices?per_page=1", "/datacenters", "/plans?datacenter=ams2", "/plans?location=ams")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


def main():
    token = os.environ.get("ARCT_READ_TOKEN")
    if not token:
        print("Skipped live smoke: ARCT_READ_TOKEN is not set.")
        return 0
    opener = urllib.request.build_opener(NoRedirect)

    def fetch(path):
        request = urllib.request.Request(BASE_URL + path, headers={"Authorization": f"Bearer {token}", "Accept": "application/json", "User-Agent": "arct-sdk-ci/0.1.0"}, method="GET")
        with opener.open(request, timeout=20) as response:
            return json.load(response)

    def catalog(path):
        rows, page, expected = [], 1, None
        while True:
            body = fetch(path + (("&" if "?" in path else "?") + f"page={page}" if page > 1 else ""))
            data, pagination = body["data"], body["pagination"]
            if not isinstance(data, list) or not all(isinstance(row, dict) for row in data):
                raise ValueError
            if any(type(pagination[key]) is not int for key in ("page", "per_page", "total", "total_pages")):
                raise ValueError
            total, pages, per_page = pagination["total"], pagination["total_pages"], pagination["per_page"]
            if pagination["page"] != page or total < 0 or per_page < 1 or pages != (total + per_page - 1) // per_page:
                raise ValueError
            if expected is None:
                expected = (total, pages, per_page)
            if expected != (total, pages, per_page) or len(data) != min(per_page, total - len(rows)):
                raise ValueError
            rows.extend(data)
            if page >= pages:
                return rows
            page += 1

    catalogs = {}
    for path in PATHS:
        try:
            if path == "/datacenters" or path.startswith("/plans"):
                catalogs[path] = catalog(path)
            else:
                fetch(path)
        except urllib.error.HTTPError as error:
            error.close()
            print(f"GET {path} failed: HTTP {error.code}")
            return 1
        except (urllib.error.URLError, TimeoutError, ValueError, OSError, KeyError, TypeError):
            print(f"GET {path} failed: transport, JSON or catalog error")
            return 1
        print(f"GET {path} passed.")
    try:
        datacenters = catalogs["/datacenters"]
        codes = [row["code"] for row in datacenters]
        if any(not isinstance(row["code"], str) or not isinstance(row["location"], str) for row in datacenters):
            raise ValueError
        if len(set(codes)) != len(codes) or "ams2" not in codes or any(not re.fullmatch(r"[a-z]{2,5}[0-9]{1,2}", row["code"]) or row["code"].rstrip("0123456789") != row["location"].casefold() for row in datacenters):
            raise ValueError
        scoped, legacy = catalogs["/plans?datacenter=ams2"], catalogs["/plans?location=ams"]
        if not scoped or not legacy or any(row["location"] != "ams" or row["tier"] != "high_performance" or "ams2" not in row["datacenters"] for row in scoped):
            raise ValueError
        all_ams = {row["slug"] for row in catalogs["/plans"] if row["location"] == "ams"}
        if any(row["location"] != "ams" for row in legacy) or {row["slug"] for row in legacy} != all_ams:
            raise ValueError
        expected = {row["slug"] for row in legacy if "ams2" in row["datacenters"]}
        if {row["slug"] for row in scoped} != expected:
            raise ValueError
    except (KeyError, TypeError, ValueError):
        print("Datacenter catalog assertions failed.")
        return 1
    print("Datacenter catalog assertions passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
