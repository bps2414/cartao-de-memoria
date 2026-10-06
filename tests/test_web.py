"""Senha opcional da interface: sem login nada sai, nem API nem download."""
import datetime as dt
import json
import os
import shutil
import threading
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from unittest import mock

from helpers import DataDirCase, core, stamp

import web

WHEN = dt.datetime(2026, 1, 1)


class WebCase(DataDirCase):
    password = ""

    def setUp(self):
        super().setUp()
        patcher = mock.patch.dict(os.environ, {"WEB_PASSWORD": self.password})
        patcher.start()
        self.addCleanup(patcher.stop)
        web._failures.clear()
        cfg_patch = mock.patch.object(core, "CONFIG_PATH", self.tmp / "config.toml")
        cfg_patch.start()
        self.addCleanup(cfg_patch.stop)
        self.add_version(WHEN, content=b"conteudo do save")
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), web.Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.download = f"/download/1a2b3c4d/PPSA00001/sdimg_slot/{stamp(WHEN)}"

    def call(self, path, body=None, cookie=None, content_type="application/json"):
        """Devolve (status, corpo em bytes, cabeçalhos)."""
        headers = {"Cookie": cookie} if cookie else {}
        data = None
        if body is not None:
            data, headers["Content-Type"] = json.dumps(body).encode(), content_type
        req = urllib.request.Request(self.base + path, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, r.read(), r.headers
        except urllib.error.HTTPError as e:
            return e.code, e.read(), e.headers

    def login(self, password):
        status, body, headers = self.call("/api/login", {"password": password})
        cookie = (headers.get("Set-Cookie") or "").split(";")[0]
        return status, cookie


class NoPassword(WebCase):
    def test_everything_is_open_by_default(self):
        self.assertEqual(self.call("/api/overview")[0], 200)
        self.assertIn(b"i18n:start", self.call("/")[1])
        self.assertEqual(self.call(self.download)[1], b"conteudo do save")
        self.assertFalse(json.loads(self.call("/api/overview")[1])["auth"])

    def test_path_traversal_is_refused(self):
        self.assertIn(self.call("/download/1a2b3c4d/PPSA00001/..%2f..%2fstate.json/x")[0], (400, 404))
        self.assertEqual(self.call("/download/1a2b3c4d/PPSA00001/../../state.json")[0], 400)

    def test_posts_must_be_json(self):
        self.assertEqual(self.call("/api/pin", {}, content_type="text/plain")[0], 415)

    def test_bad_config_is_refused_and_not_written(self):
        status, body, _ = self.call("/api/config", {"retention": {"trash_days": -1}})
        self.assertEqual(status, 400)
        self.assertIn("trash_days", json.loads(body)["error"])
        self.assertFalse(core.CONFIG_PATH.exists())

    def test_pin_and_unpin(self):
        target = {"uid": "1a2b3c4d", "title": "PPSA00001", "file": "sdimg_slot", "stamp": stamp(WHEN)}
        pin = core.SAVES_DIR / "1a2b3c4d" / "PPSA00001" / "sdimg_slot" / stamp(WHEN) / core.PIN_NAME
        self.assertEqual(self.call("/api/pin", {**target, "pinned": True})[0], 200)
        self.assertTrue(pin.exists())
        self.assertEqual(self.call("/api/pin", {**target, "pinned": False})[0], 200)
        self.assertFalse(pin.exists())
        self.assertEqual(self.call("/api/pin", {**target, "stamp": "../x", "pinned": True})[0], 400)


class Setup(WebCase):
    def setUp(self):
        super().setUp()
        shutil.rmtree(core.SAVES_DIR / "1a2b3c4d")

    def test_empty_installation_needs_setup(self):
        status, body, _ = self.call("/api/overview")
        self.assertEqual(status, 200)
        self.assertIs(json.loads(body)["setup"], True)

    def test_known_profile_does_not_need_setup(self):
        state = core.load_state()
        state["profiles"]["1a2b3c4d"] = ""
        core.save_json(core.STATE_FILE, state)
        self.assertIs(json.loads(self.call("/api/overview")[1])["setup"], False)

    def test_stored_version_without_profile_does_not_need_setup(self):
        self.add_version(WHEN)
        self.assertFalse(core.load_state()["profiles"])
        self.assertIs(json.loads(self.call("/api/overview")[1])["setup"], False)

    def test_completion_is_persisted_and_hides_setup(self):
        status, body, _ = self.call("/api/setup", {"done": True})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"ok": True})
        self.assertIs(json.loads(core.STATE_FILE.read_text(encoding="utf-8"))["meta"]["setup_done"], True)
        self.assertIs(json.loads(self.call("/api/overview")[1])["setup"], False)

    def test_completion_preserves_state_updated_when_lock_is_acquired(self):
        state = core.load_state()
        state["meta"]["last_ok"] = "2026-01-01 00:00:00"
        state["profiles"]["1a2b3c4d"] = "João"
        state["files"]["save"] = {"version": stamp(WHEN)}
        state["titles"]["PPSA00001"] = "Jogo"
        state["session"] = {"started": 123}
        state["extra"] = {"keep": True}
        core.save_json(core.STATE_FILE, state)
        locked = core.locked

        @contextmanager
        def updated_locked():
            with locked():
                state["meta"]["last_run"] = "2026-01-01 00:01:00"
                core.save_json(core.STATE_FILE, state)
                yield

        with mock.patch.object(core, "locked", updated_locked):
            self.assertEqual(self.call("/api/setup", {"done": True})[0], 200)
        state["meta"]["setup_done"] = True
        self.assertEqual(json.loads(core.STATE_FILE.read_text(encoding="utf-8")), state)
        self.assertEqual(self.call("/api/setup", {"done": True})[0], 200)
        self.assertEqual(core.load_state(), state)

    def test_completion_requires_boolean_true(self):
        for body in ({}, {"done": False}, {"done": 1}, {"done": "true"}, {"done": None}):
            with self.subTest(body=body):
                status, response, _ = self.call("/api/setup", body)
                self.assertEqual(status, 400)
                self.assertEqual(json.loads(response), {"error": web.tr("pt-BR", "e_send_json")})
                self.assertFalse(core.STATE_FILE.exists())
        self.assertIs(json.loads(self.call("/api/overview")[1])["setup"], True)


class WithPassword(WebCase):
    password = "correta-cavalo-bateria"

    def test_nothing_is_served_without_login(self):
        for path in ("/api/overview", "/api/stats", "/api/log", self.download, "/art/PPSA00001/icon0.png"):
            self.assertEqual(self.call(path)[0], 401, path)
        for path in ("/api/config", "/api/backup", "/api/verify", "/api/pin", "/api/webhook", "/api/webhook/test"):
            self.assertEqual(self.call(path, {})[0], 401, path)
        self.assertFalse(core.CONFIG_PATH.exists())

    def test_root_shows_the_login_page_not_the_app(self):
        status, body, _ = self.call("/")
        self.assertEqual(status, 200)
        self.assertIn(b"/api/login", body)
        self.assertNotIn(b"i18n:start", body)

    def test_login_then_everything_works(self):
        status, cookie = self.login(self.password)
        self.assertEqual(status, 200)
        self.assertTrue(cookie.startswith("cm_session="))
        self.assertEqual(self.call("/api/overview", cookie=cookie)[0], 200)
        self.assertTrue(json.loads(self.call("/api/overview", cookie=cookie)[1])["auth"])
        self.assertEqual(self.call(self.download, cookie=cookie)[1], b"conteudo do save")
        self.assertIn(b"i18n:start", self.call("/", cookie=cookie)[1])

    def test_setup_requires_login(self):
        status, body, _ = self.call("/api/setup", {"done": True})
        self.assertEqual(status, 401)
        self.assertEqual(json.loads(body), {"error": web.tr("pt-BR", "e_auth")})
        self.assertFalse(core.STATE_FILE.exists())
        status, cookie = self.login(self.password)
        self.assertEqual(status, 200)
        status, body, _ = self.call("/api/setup", {"done": True}, cookie=cookie)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"ok": True})
        self.assertIs(core.load_state()["meta"]["setup_done"], True)

    def test_wrong_password_and_forged_cookies(self):
        self.assertEqual(self.login("errada")[0], 401)
        self.assertEqual(self.login("")[0], 401)
        far = int(time.time()) + 10 ** 6
        for forged in ("cm_session=", "cm_session=abc", f"cm_session={far}.{'0' * 64}", f"cm_session={far}."):
            self.assertEqual(self.call("/api/overview", cookie=forged)[0], 401, forged)

    def test_token_expires_and_dies_with_the_password(self):
        token = web.make_token()
        self.assertTrue(web.token_valid(token))
        self.assertFalse(web.token_valid(token, now=time.time() + (web.SESSION_DAYS + 1) * 86400))
        expiry, signature = token.split(".")
        self.assertFalse(web.token_valid(f"{int(expiry) + 1}.{signature}"))
        with mock.patch.dict(os.environ, {"WEB_PASSWORD": "outra"}):
            self.assertFalse(web.token_valid(token))

    def test_repeated_wrong_passwords_are_blocked_for_a_while(self):
        for _ in range(web.LOGIN_TRIES):
            self.assertEqual(self.login("errada")[0], 401)
        self.assertEqual(self.login("errada")[0], 429)
        self.assertEqual(self.login(self.password)[0], 429)  # nem a certa passa durante o bloqueio
        self.assertFalse(web.login_blocked("127.0.0.1", now=time.time() + web.LOGIN_WINDOW + 1))

    def test_logout_clears_the_cookie(self):
        status, _, headers = self.call("/api/logout", {})
        self.assertEqual(status, 200)
        self.assertIn("Max-Age=0", headers.get("Set-Cookie"))
