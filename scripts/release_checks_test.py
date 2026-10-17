import contextlib
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

        class Opener:
            def open(self, request, timeout):
                calls.append(request)
                self_token = request.get_header("Authorization")
                if self_token != "Bearer read-token" or timeout != 20 or request.get_header("User-agent") != "arct-sdk-ci/0.1.0":
                    raise AssertionError("Invalid authentication or timeout")
                return io.BytesIO(json.dumps({}).encode())

        with patch.dict(os.environ, {"ARCT_READ_TOKEN": "read-token"}), patch("urllib.request.build_opener", return_value=Opener()), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(live_smoke.main(), 0)
        self.assertEqual(len(calls), 7)
        self.assertTrue(all(request.get_method() == "GET" and request.full_url.startswith(live_smoke.BASE_URL + "/") for request in calls))
        self.assertNotIn("read-token", output.getvalue())
        self.assertIsNone(live_smoke.NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.example"))

    def test_live_smoke_errors_never_print_response_secrets(self):
        error = urllib.error.HTTPError(live_smoke.BASE_URL, 403, "secret-token", {}, None)
        with patch.dict(os.environ, {"ARCT_READ_TOKEN": "secret-token"}), patch("urllib.request.OpenerDirector.open", side_effect=error), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(live_smoke.main(), 1)
        self.assertNotIn("secret-token", output.getvalue())


if __name__ == "__main__":
    unittest.main()
