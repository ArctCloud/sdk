import contextlib
import copy
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

import live_smoke
from release_check import check


class ReleaseChecks(unittest.TestCase):
    def smoke_bodies(self):
        def page(rows):
            return {"data": rows, "pagination": {"page": 1, "per_page": 20, "total": len(rows), "total_pages": 1 if rows else 0}}

        plans = [{"slug": "vm.nano", "location": "ams", "datacenters": ["ams1"], "tier": "standard"},
                 {"slug": "hvm.nano", "location": "ams", "datacenters": ["ams2"], "tier": "high_performance"}]
        return {**{path: {} for path in live_smoke.PATHS},
                "/datacenters": page([{"code": "ams1", "location": "ams", "tiers": ["standard"]}, {"code": "ams2", "location": "ams", "tiers": ["high_performance"]}]),
                "/plans": page(plans), "/plans?datacenter=ams2": page(plans[1:]), "/plans?location=ams": page(plans)}

    def test_tags_match_package_versions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for package, filename, content, version in (
                ("python", "python/pyproject.toml", '[project]\nversion = "0.1.0rc1"\n', "0.1.0rc1"),
                ("typescript", "typescript/package.json", '{"version":"0.1.0-rc.1"}', "0.1.0-rc.1"),
            ):
                path = root / filename
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
                with self.subTest(package=package):
                    self.assertEqual(check(package, f"{package}-v{version}", root), version)
                    for tag in ("", "v" + version, package + "-v9.0.0"):
                        with self.assertRaises(ValueError):
                            check(package, tag, root)

    def test_live_smoke_without_token_makes_no_requests(self):
        with patch.dict(os.environ, {}, clear=True), patch("urllib.request.build_opener") as build, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(live_smoke.main(), 0)
            build.assert_not_called()

    def test_live_smoke_only_gets_fixed_origin(self):
        calls = []
        bodies = self.smoke_bodies()

        class Opener:
            def open(self, request, timeout):
                calls.append(request)
                self_token = request.get_header("Authorization")
                if self_token != "Bearer read-token" or timeout != 20 or request.get_header("User-agent") != "arct-sdk-ci/0.1.0":
                    raise AssertionError("Invalid authentication or timeout")
                return io.BytesIO(json.dumps(bodies[request.full_url.removeprefix(live_smoke.BASE_URL)]).encode())

        with patch.dict(os.environ, {"ARCT_READ_TOKEN": "read-token"}), patch("urllib.request.build_opener", return_value=Opener()), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(live_smoke.main(), 0)
        self.assertEqual(len(calls), 10)
        self.assertTrue(all(request.get_method() == "GET" and request.full_url.startswith(live_smoke.BASE_URL + "/") for request in calls))
        self.assertNotIn("read-token", output.getvalue())
        self.assertIsNone(live_smoke.NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.example"))

    def test_live_smoke_rejects_empty_or_wrong_catalogs(self):
        bodies = self.smoke_bodies()
        cases = [('/datacenters', {}), ('/datacenters', {"data": [], "pagination": {"page": 1, "per_page": 20, "total": 0, "total_pages": 0}}),
                 ('/datacenters', {"data": [{"code": "secret-response", "location": "ams"}], "pagination": {"page": 1, "per_page": 20, "total": 1, "total_pages": 1}}),
                 ('/plans?datacenter=ams2', {**bodies['/plans?datacenter=ams2'], 'data': [bodies['/plans']['data'][0]]}),
                 ('/plans?location=ams', bodies['/plans?datacenter=ams2']),
                 ('/plans?datacenter=ams2', {"data": [], "pagination": {"page": 1, "per_page": 20, "total": 0, "total_pages": 0}})]
        for path, response in cases:
            with self.subTest(path=path, response=response):
                responses = {**bodies, path: response}
                with patch.dict(os.environ, {"ARCT_READ_TOKEN": "read-token"}), patch("urllib.request.OpenerDirector.open", side_effect=lambda request, timeout: io.BytesIO(json.dumps(responses[request.full_url.removeprefix(live_smoke.BASE_URL)]).encode())), contextlib.redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(live_smoke.main(), 1)
                self.assertNotIn('secret-response', output.getvalue())

    def test_live_smoke_accepts_uppercase_legacy_location(self):
        bodies = self.smoke_bodies()
        bodies['/datacenters']['data'].append({"code": "lon1", "location": "LON", "tiers": ["standard"]})
        bodies['/datacenters']['pagination']['total'] = 3
        with patch.dict(os.environ, {"ARCT_READ_TOKEN": "read-token"}), patch("urllib.request.OpenerDirector.open", side_effect=lambda request, timeout: io.BytesIO(json.dumps(bodies[request.full_url.removeprefix(live_smoke.BASE_URL)]).encode())), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(live_smoke.main(), 0)

    def test_live_smoke_accepts_legacy_catalog_mappings_and_case(self):
        for legacy_mapping, uppercase_plans in ((True, False), (False, True), (True, True)):
            bodies = self.smoke_bodies()
            if legacy_mapping:
                bodies['/datacenters']['data'].append({"code": "tyo1", "location": "jp", "tiers": ["standard"]})
                bodies['/datacenters']['pagination']['total'] = 3
            if uppercase_plans:
                for path in ('/plans', '/plans?datacenter=ams2', '/plans?location=ams'):
                    for row in bodies[path]['data']:
                        row['location'] = 'AMS'
            with self.subTest(legacy_mapping=legacy_mapping, uppercase_plans=uppercase_plans), patch.dict(os.environ, {"ARCT_READ_TOKEN": "read-token"}), patch("urllib.request.OpenerDirector.open", side_effect=lambda request, timeout: io.BytesIO(json.dumps(bodies[request.full_url.removeprefix(live_smoke.BASE_URL)]).encode())), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(live_smoke.main(), 0)

    def test_live_smoke_checks_every_catalog_page(self):
        for bad_second_page in (False, True):
            bodies = copy.deepcopy(self.smoke_bodies())
            plans = bodies['/plans']['data']
            bodies['/plans'] = {"data": plans[:1], "pagination": {"page": 1, "per_page": 1, "total": 2, "total_pages": 2}}
            bodies['/plans?page=2'] = {"data": plans[1:] if not bad_second_page else [], "pagination": {"page": 2, "per_page": 1, "total": 2, "total_pages": 2}}
            calls = []

            def response(request, timeout):
                path = request.full_url.removeprefix(live_smoke.BASE_URL)
                calls.append(path)
                return io.BytesIO(json.dumps(bodies[path]).encode())

            with self.subTest(bad_second_page=bad_second_page), patch.dict(os.environ, {"ARCT_READ_TOKEN": "read-token"}), patch("urllib.request.OpenerDirector.open", side_effect=response), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(live_smoke.main(), int(bad_second_page))
            self.assertIn('/plans?page=2', calls)

    def test_live_smoke_refuses_redirects(self):
        error = urllib.error.HTTPError(live_smoke.BASE_URL, 302, 'redirect', {'Location': 'https://other.example'}, None)
        with patch.dict(os.environ, {"ARCT_READ_TOKEN": "read-token"}), patch("urllib.request.OpenerDirector.open", side_effect=error) as opened, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(live_smoke.main(), 1)
        self.assertEqual(opened.call_count, 1)

    def test_live_smoke_errors_never_print_response_secrets(self):
        error = urllib.error.HTTPError(live_smoke.BASE_URL, 403, "secret-token", {}, None)
        with patch.dict(os.environ, {"ARCT_READ_TOKEN": "secret-token"}), patch("urllib.request.OpenerDirector.open", side_effect=error), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(live_smoke.main(), 1)
        self.assertNotIn("secret-token", output.getvalue())


if __name__ == "__main__":
    unittest.main()
