import http.cookiejar
import os
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PORTAL_DIR = ROOT / "services" / "xapi-portal"
sys.path.insert(0, str(PORTAL_DIR))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class PortalLogoutRegressionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.TemporaryDirectory()
        cls.db_path = Path(cls.tmpdir.name) / "portal.db"
        os.environ["XAPI_PORTAL_DB"] = str(cls.db_path)
        os.environ.setdefault("XAPI_BRAND", "NW-API")
        global xapi_portal
        import xapi_portal
        cls.portal = xapi_portal
        cls.portal.init_db()
        con = sqlite3.connect(cls.db_path)
        con.execute(
            "INSERT INTO users(email,pass_hash,sub2_user_id,role,status,created_at) VALUES(?,?,?,?,?,?)",
            ("logout-test@example.com", cls.portal.hash_pw("Password123!"), 1001, "user", "active", int(time.time())),
        )
        con.commit(); con.close()
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), cls.portal.H)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.tmpdir.cleanup()

    def url(self, path):
        return f"http://127.0.0.1:{self.port}{path}"

    def test_logout_clears_cookie_and_server_session(self):
        cj = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj), NoRedirect())
        data = b"email=logout-test%40example.com&password=Password123%21"
        try:
            opener.open(urllib.request.Request(self.url("/login"), data=data, method="POST"), timeout=5)
            self.fail("login should redirect")
        except urllib.error.HTTPError as exc:
            self.assertEqual(exc.code, 302)
            self.assertEqual(exc.headers.get("Location"), "/dashboard")
        sid_values = [c.value for c in cj if c.name == "sid" and c.value]
        self.assertTrue(sid_values)
        self.assertIn(sid_values[0], self.portal.SESS)

        try:
            opener.open(self.url("/login"), timeout=5)
            self.fail("logged-in /login should redirect to dashboard")
        except urllib.error.HTTPError as exc:
            self.assertEqual(exc.code, 302)
            self.assertEqual(exc.headers.get("Location"), "/dashboard")

        try:
            opener.open(self.url("/logout"), timeout=5)
            self.fail("logout should redirect")
        except urllib.error.HTTPError as exc:
            self.assertEqual(exc.code, 302)
            self.assertEqual(exc.headers.get("Location"), "/home")
        self.assertNotIn(sid_values[0], self.portal.SESS)

        try:
            opener.open(self.url("/keys"), timeout=5)
            self.fail("/keys after logout should redirect to login")
        except urllib.error.HTTPError as exc:
            self.assertEqual(exc.code, 302)
            self.assertEqual(exc.headers.get("Location"), "/login")


if __name__ == "__main__":
    unittest.main()
