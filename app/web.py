"""Interface web: painel, ajustes e download das versões guardadas.

Só lê e escreve no servidor (config.toml e pasta de backup). Nenhuma rota fala
com o PS5 além de disparar a mesma rodada de backup somente-leitura do daemon
e de procurar o console na rede (conexões de leitura, sem gravar nada).
Pensada para a rede local; não exponha na internet. Com WEB_PASSWORD definida
(no .env), tudo exige login: páginas, API, artes e downloads.
"""
import hashlib
import hmac
import json
import os
import re
import socket
import sys
import threading
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import ps5backup as core
import projection
from i18n import LANGS, Msg, tr

PORT = 8765
UI_DIR = Path(__file__).parent / "ui"
UI_FILE = UI_DIR / "index.html"
LOGIN_FILE = UI_DIR / "login.html"
COOKIE = "cm_session"
SESSION_DAYS = 30
LOGIN_TRIES, LOGIN_WINDOW = 5, 300  # tentativas erradas por endereço antes de bloquear, e por quantos segundos
_failures = {}  # endereço -> horários das tentativas erradas recentes
SEGMENT_RE = re.compile(r"[A-Za-z0-9_.\-]+")


def overview():
    cfg, state = core.load_config(), core.load_state()
    saves = {}  # (uid, title, file) -> dict

    def entry(uid, title, fname):
        key = (uid, title, fname)
        if key not in saves:
            info = core.save_info(state, {"uid": uid, "title": title, "file": fname})
            saves[key] = {"uid": uid, "title": title, "file": fname,
                          "name": fname.removeprefix("sdimg_"), "label": info["label"],
                          "sub": info["sub"], "detail": info["detail"],
                          "is_system_copy": fname.startswith("sdimg_sce_bu_"),
                          "on_console": False, "size": 0, "versions": []}
        return saves[key]

    total_bytes = total_versions = 0
    title_bytes = {}
    for vdir, meta in core.iter_versions():
        e = entry(meta["uid"], meta["title_id"], meta["file"])
        e["versions"].append({"stamp": vdir.name, "size": meta.get("size", 0), "sha256": meta.get("sha256", ""),
                              "trigger": meta.get("trigger", ""),
                              "label": meta.get("label", ""), "sub": meta.get("sub_title", ""),
                              "pinned": (vdir / core.PIN_NAME).exists()})
        total_bytes += meta.get("size", 0)
        title_bytes[meta["title_id"]] = title_bytes.get(meta["title_id"], 0) + meta.get("size", 0)
        total_versions += 1
    for c in state["console"].values():
        e = entry(c["uid"], c["title"], c["file"])
        e["on_console"], e["size"] = True, c["size"]
    for e in saves.values():
        e["versions"].sort(key=lambda v: v["stamp"], reverse=True)

    flt = cfg["filter"]
    profiles = []
    for uid, name in state["profiles"].items():
        decided = ("exclude" if core.matches(flt["exclude_profiles"], uid, name) else
                   "include" if core.matches(flt["include_profiles"], uid, name) else None)
        seen = state["profile_seen"].get(uid, 0)
        mine = sorted((s for s in saves.values() if s["uid"] == uid),
                      key=lambda s: (s["title"], s["is_system_copy"], s["name"]))
        profiles.append({"uid": uid, "name": name or uid, "decided": decided,
                         "included": core.profile_included(cfg, uid, name),
                         "is_new": decided is None and time.time() - seen < 7 * 86400,
                         "saves": mine})
    profiles.sort(key=lambda p: (not p["included"], p["name"].lower()))

    titles = {}
    for tid in {s["title"] for s in saves.values()} | set(flt["exclude_titles"]):
        titles[tid] = {"name": state["titles"].get(tid, ""),
                       "version": state["title_info"].get(tid, {}).get("version", ""),
                       "icon": (core.ART_DIR / tid / "icon0.png").exists(),
                       "pic": (core.ART_DIR / tid / "pic0.png").exists(),
                       "bytes": title_bytes.get(tid, 0),
                       "excluded": not core.title_included(cfg, tid)}

    protected = [s for s in saves.values() if s["versions"]]
    url = core.webhook_url()
    return {
        "status": {"online": core.STATUS["online"], "running": core.STATUS["running"],
                   "host": cfg["ps5"]["host"],
                   "garlic_url": f"http://{cfg['ps5']['host']}:{cfg['ps5']['garlic_port']}",
                   "last_run": state["meta"].get("last_run"), "last_ok": state["meta"].get("last_ok"),
                   "last_trigger": state["meta"].get("last_trigger", "")},
        "totals": {"saves": len(protected), "versions": total_versions, "bytes": total_bytes,
                   "trash_bytes": core.dir_bytes(core.TRASH_DIR),
                   "free_bytes": core.shutil.disk_usage(core.DATA_DIR).free,
                   "over_limit": bool(cfg["retention"]["warn_total_gb"])
                   and total_bytes > cfg["retention"]["warn_total_gb"] * 1024 ** 3},
        "profiles": profiles, "titles": titles, "config": cfg,
        "setup": "setup_done" not in state["meta"],  # instalação antiga também vê o assistente uma vez
        "webhook": {"set": bool(url), "discord": core.is_discord(url)},
        "session_open": bool(state["session"]), "auth": bool(password()),
        "verify": {"at": state["meta"].get("last_verify"), "ok": state["meta"].get("last_verify_ok", 0),
                   "bad": state["meta"].get("last_verify_bad", [])},
        "projection": projection.cached(cfg),
    }


def password():
    return os.environ.get("WEB_PASSWORD", "")


def _sign(expiry):
    # A chave sai da senha: trocar a senha derruba todas as sessões, e o login
    # sobrevive a reinícios do container sem guardar nada em disco.
    key = hashlib.sha256(b"ps5backup-session:" + password().encode()).digest()
    return hmac.new(key, str(expiry).encode(), "sha256").hexdigest()


def make_token(now=None):
    expiry = int(now or time.time()) + SESSION_DAYS * 86400
    return f"{expiry}.{_sign(expiry)}"


def token_valid(token, now=None):
    expiry, _, signature = (token or "").partition(".")
    return (expiry.isdigit() and int(expiry) > (now or time.time())
            and hmac.compare_digest(signature, _sign(expiry)))


def login_blocked(addr, now=None):
    now = now or time.time()
    recent = [t for t in _failures.get(addr, []) if now - t < LOGIN_WINDOW]
    _failures[addr] = recent
    return len(recent) >= LOGIN_TRIES


def set_membership(values, uid, name, present):
    """Tira o perfil da lista (por ID ou nome) e, se pedido, recoloca pelo ID."""
    kept = [v for v in values if v.lower() not in (uid.lower(), (name or "").lower())]
    return kept + [uid] if present else kept


class Handler(BaseHTTPRequestHandler):
    server_version = "ps5backup"

    def log_message(self, *args):
        pass

    @property
    def lang(self):
        """Idioma da interface (cabeçalho X-Lang), usado nas mensagens de erro."""
        lang = self.headers.get("X-Lang", "")
        return lang if lang in LANGS else core.DEFAULTS["notify"]["language"]

    def t(self, key, **kw):
        return tr(self.lang, key, **kw)

    def authed(self):
        if not password():
            return True
        cookie = SimpleCookie(self.headers.get("Cookie", "")).get(COOKIE)
        return bool(cookie) and token_valid(cookie.value)

    def session_cookie(self, token, max_age):
        return ("Set-Cookie", f"{COOKIE}={token}; Path=/; Max-Age={max_age}; HttpOnly; SameSite=Strict")

    def login(self, body):
        addr = self.client_address[0]
        if not password():
            return self.send_json({"ok": True})
        if login_blocked(addr):
            return self.send_json({"error": self.t("e_login_blocked", minutes=LOGIN_WINDOW // 60)}, 429)
        given = str(body.get("password", ""))
        if not hmac.compare_digest(given.encode(), password().encode()):
            _failures.setdefault(addr, []).append(time.time())
            core.log.warning("interface: senha errada vinda de %s", addr)
            return self.send_json({"error": self.t("e_login")}, 401)
        _failures.pop(addr, None)
        self.send_json({"ok": True}, headers=[self.session_cookie(make_token(), SESSION_DAYS * 86400)])

    def send_json(self, obj, code=200, headers=()):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for name, value in headers:
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path, content_type, download_name=None, cache=False):
        if not path.is_file():
            return self.send_json({"error": self.t("e_not_found")}, 404)
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(path.stat().st_size))
        self.send_header("Cache-Control", "max-age=86400" if cache else "no-store")
        if download_name:
            self.send_header("Content-Disposition", f'attachment; filename="{download_name}"')
        self.end_headers()
        with open(path, "rb") as f:
            while chunk := f.read(1 << 16):
                self.wfile.write(chunk)

    def do_GET(self):
        path = self.path.split("?")[0]
        parts = [p for p in path.split("/") if p]
        if any(not SEGMENT_RE.fullmatch(p) or ".." in p for p in parts):
            return self.send_json({"error": self.t("e_bad_path")}, 400)
        if path in ("/logo.svg", "/mark.svg"):  # só a marca, usada também na tela de login
            return self.send_file(UI_DIR / path[1:], "image/svg+xml", cache=True)
        if not self.authed():
            if not parts:
                return self.send_file(LOGIN_FILE, "text/html; charset=utf-8")
            return self.send_json({"error": self.t("e_auth")}, 401)
        if not parts:
            return self.send_file(UI_FILE, "text/html; charset=utf-8")
        if path == "/api/overview":
            return self.send_json(overview())
        if path == "/api/diag":
            cfg = core.load_config()
            lang = self.headers.get("X-Lang", "")
            text, _ = core.diagnose(cfg, lang if lang in LANGS else cfg["notify"]["language"])
            return self.send_json({"text": text})
        if path == "/api/stats":
            stats = core.load_stats()
            return self.send_json({"slots": stats["slots"], "sizes": stats["sizes"]})
        if path == "/api/log":
            try:
                lines = core.LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()[-400:]
            except FileNotFoundError:
                lines = []
            return self.send_json({"lines": lines})
        if parts[0] == "art" and len(parts) == 3 and parts[2] in core.ART_FILES:
            return self.send_file(core.ART_DIR / parts[1] / parts[2], "image/png", cache=True)
        if parts[0] == "download" and len(parts) == 5:
            uid, title, fname, stamp = parts[1:]
            return self.send_file(core.SAVES_DIR / uid / title / fname / stamp / fname,
                                  "application/octet-stream", download_name=fname)
        self.send_json({"error": self.t("e_not_found")}, 404)

    def do_POST(self):
        # Exigir JSON bloqueia formulários de outros sites (não respondemos CORS).
        if "application/json" not in self.headers.get("Content-Type", ""):
            return self.send_json({"error": self.t("e_send_json")}, 415)
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(min(length, 1 << 16)) or b"{}")
            if not isinstance(body, dict):
                raise Msg("e_send_json")
            if self.path == "/api/login":
                return self.login(body)
            if self.path == "/api/logout":
                return self.send_json({"ok": True}, headers=[self.session_cookie("", 0)])
            if not self.authed():
                return self.send_json({"error": self.t("e_auth")}, 401)
            self.send_json(self.route_post(self.path, body))
        except Msg as e:
            self.send_json({"error": e.text(self.lang)}, 400)
        except ValueError as e:
            self.send_json({"error": str(e)}, 400)
        except Exception as e:
            self.send_json({"error": f"{type(e).__name__}: {e}"}, 500)

    def route_post(self, path, body):
        cfg = core.load_config()
        if path == "/api/setup":
            if body.get("done") is not True:
                raise Msg("e_send_json")
            with core.locked():
                state = core.load_state()
                state["meta"]["setup_done"] = True
                core.save_json(core.STATE_FILE, state)
            return {"ok": True}
        if path == "/api/backup":
            if core.STATUS["running"]:
                raise Msg("e_busy")
            if not core.ps5_online(cfg):
                raise Msg("e_offline")
            threading.Thread(target=core.safe_run, args=(cfg, "manual"), daemon=True).start()
            return {"ok": True}
        if path == "/api/discover":
            # O botão manda o que está digitado em Ajustes (ainda não salvo) como ponto de partida.
            search = {**cfg, "ps5": {**cfg["ps5"], **{k: str(body[k]).strip() for k in ("host", "subnet") if k in body}}}
            core.validate_config(search)
            found = core.apply_discovery(cfg, search)
            if not found:
                raise Msg("e_discover")
            return {"host": found[0], "port": found[1]}
        if path == "/api/config":
            core.save_config(body)
            return {"ok": True}
        if path == "/api/profile":
            uid, mode = body.get("uid", ""), body.get("mode")
            name = core.load_state()["profiles"].get(uid)
            if name is None or mode not in ("include", "exclude"):
                raise Msg("e_profile")
            flt = cfg["filter"]
            flt["include_profiles"] = set_membership(flt["include_profiles"], uid, name, mode == "include")
            flt["exclude_profiles"] = set_membership(flt["exclude_profiles"], uid, name, mode == "exclude")
            core.save_config(cfg)
            core.log.info("perfil %s (%s): %s", name, uid, "no backup" if mode == "include" else "fora do backup")
            return {"ok": True}
        if path == "/api/title":
            tid = body.get("id", "")
            if not core.TITLE_RE.fullmatch(tid):
                raise Msg("e_title")
            flt = cfg["filter"]
            flt["exclude_titles"] = [t for t in flt["exclude_titles"] if t != tid]
            if body.get("excluded"):
                flt["exclude_titles"].append(tid)
            core.save_config(cfg)
            return {"ok": True}
        if path == "/api/webhook":
            url = str(body.get("url", "")).strip()
            if url and not url.startswith(("https://", "http://")):
                raise Msg("e_url")
            core.set_webhook_url(url)
            return {"ok": True}
        if path == "/api/webhook/test":
            if not core.webhook_url():
                raise Msg("e_no_webhook")
            lang = cfg["notify"]["language"]
            sent = core.send_embed(core.make_embed(tr(lang, "test_title"), tr(lang, "test_body"),
                                                   0x7C8CFF, [("PS5", cfg["ps5"]["host"])]))
            if core.is_discord(core.webhook_url()) and not sent:
                raise Msg("e_discord")
            return {"ok": True}
        if path == "/api/pin":
            parts = [str(body.get(k, "")) for k in ("uid", "title", "file", "stamp")]
            if any(not SEGMENT_RE.fullmatch(p) or ".." in p for p in parts):
                raise Msg("e_version")
            vdir = core.SAVES_DIR.joinpath(*parts)
            if not (vdir / "meta.json").exists():
                raise Msg("e_version_missing")
            if body.get("pinned"):
                (vdir / core.PIN_NAME).touch()
            else:
                (vdir / core.PIN_NAME).unlink(missing_ok=True)
            return {"ok": True}
        if path == "/api/verify":
            return core.verify_and_record(cfg, notify=False)
        raise Msg("e_unknown_route")


def create_server():
    frozen = getattr(sys, "frozen", False)
    bind = os.environ.get("WEB_BIND", "127.0.0.1" if frozen else "0.0.0.0")
    if not frozen or os.name != "nt":
        return ThreadingHTTPServer((bind, PORT), Handler)
    server = ThreadingHTTPServer((bind, PORT), Handler, bind_and_activate=False)
    try:
        # SO_REUSEADDR no Windows deixaria a segunda cópia ocupar a mesma porta.
        server.allow_reuse_address = False
        server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        server.server_bind()
        server.server_activate()
    except OSError:
        server.server_close()
        raise
    return server


def serve(server=None):
    (server or create_server()).serve_forever()
