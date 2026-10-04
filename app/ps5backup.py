"""Backup versionado dos saves de um PS5 (jailbreak) para o servidor.

Somente leitura no PS5: usa apenas CWD/MLSD/RETR no ftpsrv. Nada é gravado,
apagado ou restaurado no console. Sem dependências além da biblioteca padrão.
"""
import argparse
import datetime as dt
import fcntl
import ftplib
import hashlib
import io
import json
import logging
import os
import re
import shutil
import socket
import sqlite3
import sys
import threading
import time
import tomllib
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path

CONFIG_PATH = Path(os.environ.get("PS5BACKUP_CONFIG", "/config/config.toml"))
DATA_DIR = Path(os.environ.get("PS5BACKUP_DATA", "/data"))
SAVES_DIR = DATA_DIR / "saves"
ART_DIR = DATA_DIR / "cache" / "art"
STATE_FILE = DATA_DIR / "state.json"
SECRETS_FILE = DATA_DIR / "secrets.json"
LOG_FILE = DATA_DIR / "backup.log"
TMP_DIR = DATA_DIR / ".tmp"
TRASH_DIR = DATA_DIR / "trash"
PIN_NAME = "PINNED"  # arquivo-marcador: versão fixada nunca é rareada
STAMP_FMT = "%Y%m%d-%H%M%S"
# savedata_prospero = saves de PS5; savedata = saves de PS4 (imagem + chave .bin)
SAVE_KINDS = ("savedata_prospero", "savedata")
UID_RE = re.compile(r"[0-9a-f]{8}")
TITLE_RE = re.compile(r"[A-Z]{4}\d{5}")
ART_FILES = ("icon0.png", "pic0.png")

DEFAULTS = {
    "ps5": {"host": "192.168.1.50", "ftp_port": 2121, "garlic_port": 8082},
    "filter": {"new_profiles": "include", "include_profiles": [], "exclude_profiles": [],
               "include_titles": [], "exclude_titles": []},
    "triggers": {"on_power_on": True, "power_on_delay_seconds": 20,
                 "on_save_change": True, "watch_interval_seconds": 60,
                 "schedule_interval_hours": 0, "schedule_daily_at": [],
                 "probe_interval_seconds": 15, "offline_after_failures": 3},
    "retention": {"thin_old_versions": True, "keep_all_hours": 1, "keep_hourly_days": 2,
                  "keep_daily_days": 14, "keep_weekly_weeks": 12, "keep_min_versions": 3,
                  "min_gap_minutes": 10, "trash_days": 7, "warn_total_gb": 20, "warn_free_gb": 10},
    "notify": {"on_backup": True, "on_error": True, "on_new_profile": True,
               "error_cooldown_minutes": 60, "session_gap_hours": 6},
}
MINIMUMS = {"watch_interval_seconds": 10, "probe_interval_seconds": 5, "offline_after_failures": 1, "keep_min_versions": 1,
            "ftp_port": 1, "garlic_port": 1}
# Avatar das mensagens no Discord (precisa ser uma URL pública; o Discord não lê SVG).
AVATAR_URL = "https://raw.githubusercontent.com/bps2414/cartao-de-memoria/main/docs/logo.png"
TRIGGER_LABEL = {"manual": "Manual", "power_on": "PS5 ligou", "save_changed": "Save alterado",
                 "schedule": "Agendamento"}

log = logging.getLogger("ps5backup")
# Estado em memória do daemon, lido pela interface web.
STATUS = {"online": None, "running": None}


# ------------------------------------------------------------------- config

def validate_config(user):
    """Mescla com os padrões e rejeita chaves desconhecidas ou tipos errados."""
    cfg = {}
    for section, defaults in DEFAULTS.items():
        given = user.get(section, {})
        if not isinstance(given, dict):
            raise ValueError(f"[{section}] precisa ser uma seção")
        unknown = set(given) - set(defaults)
        if unknown:
            raise ValueError(f"chave desconhecida em [{section}]: {sorted(unknown)}")
        cfg[section] = {}
        for key, default in defaults.items():
            value = given.get(key, default)
            if type(value) is not type(default):
                raise ValueError(f"[{section}] {key}: esperado {type(default).__name__}")
            if isinstance(value, list) and not all(isinstance(v, str) for v in value):
                raise ValueError(f"[{section}] {key}: a lista só aceita textos")
            if isinstance(value, int) and not isinstance(value, bool) and value < MINIMUMS.get(key, 0):
                raise ValueError(f"[{section}] {key}: mínimo {MINIMUMS.get(key, 0)}")
            cfg[section][key] = value
    if cfg["filter"]["new_profiles"] not in ("include", "exclude"):
        raise ValueError('[filter] new_profiles: use "include" ou "exclude"')
    for hhmm in cfg["triggers"]["schedule_daily_at"]:
        if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", hhmm):
            raise ValueError(f"[triggers] schedule_daily_at: horário inválido {hhmm!r} (use HH:MM)")
    return cfg


def load_config():
    try:
        with open(CONFIG_PATH, "rb") as f:
            user = tomllib.load(f)
    except FileNotFoundError:
        user = {}
    return validate_config(user)


def save_config(cfg):
    """Regrava o config.toml (os comentários do arquivo não são preservados)."""
    def val(v):
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, list):
            return "[" + ", ".join(json.dumps(x, ensure_ascii=False) for x in v) + "]"
        return json.dumps(v, ensure_ascii=False) if isinstance(v, str) else str(v)
    lines = ["# Gerado pela interface web. Pode ser editado à mão; veja config.example.toml.", ""]
    for section, values in validate_config(cfg).items():
        lines.append(f"[{section}]")
        lines += [f"{k} = {val(v)}" for k, v in values.items()]
        lines.append("")
    # Escrita no lugar: o arquivo é um bind mount e não pode ser trocado por rename.
    CONFIG_PATH.write_text("\n".join(lines))


def setup_logging():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
    for handler in (logging.StreamHandler(sys.stdout), logging.FileHandler(LOG_FILE)):
        handler.setFormatter(fmt)
        log.addHandler(handler)
    log.setLevel(logging.INFO)


@contextmanager
def locked():
    """Impede que duas rodadas (daemon, web, linha de comando) rodem juntas."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(DATA_DIR / ".lock", "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield


def load_json(path, default):
    try:
        return json.loads(Path(path).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path, data):
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False))
    tmp.replace(path)


def load_state():
    state = load_json(STATE_FILE, {})
    for key in ("files", "meta", "profiles", "profile_seen", "titles", "title_info", "savemeta", "console"):
        state.setdefault(key, {})
    state.setdefault("session", None)
    return state


# ------------------------------------------------------------ notificações

def webhook_url():
    return load_json(SECRETS_FILE, {}).get("notify_url") or os.environ.get("NOTIFY_URL", "")


def set_webhook_url(url):
    save_json(SECRETS_FILE, {"notify_url": url})
    os.chmod(SECRETS_FILE, 0o600)


def is_discord(url):
    return "discord.com/api/webhooks/" in url or "discordapp.com/api/webhooks/" in url


def _http(method, url, body, content_type):
    req = urllib.request.Request(url, data=body, method=method,
                                 headers={"Content-Type": content_type, "User-Agent": "ps5backup/1.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.read()


def send_embed(embed, message_id=None):
    """Envia um embed ao Discord. Com message_id, edita a mensagem existente em
    vez de criar outra. Devolve o id da mensagem. URL não-Discord recebe texto."""
    url = webhook_url()
    if not url:
        return None
    try:
        if not is_discord(url):
            text = "\n".join(x for x in (embed["title"], embed.get("description", "")) if x)
            _http("POST", url, text.encode(), "text/plain; charset=utf-8")
            return None
        body = json.dumps({"username": "Cartão de Memória", "avatar_url": AVATAR_URL,
                           "embeds": [embed]}).encode()
        base = url.split("?")[0]
        if message_id:
            try:
                _http("PATCH", f"{base}/messages/{message_id}", body, "application/json")
                return message_id
            except urllib.error.HTTPError as e:
                if e.code != 404:  # 404 = a mensagem foi apagada; cria outra
                    raise
        return json.loads(_http("POST", base + "?wait=true", body, "application/json"))["id"]
    except Exception as e:
        log.warning("notificação falhou: %s", e)
        return message_id


def make_embed(title, description, color, fields=()):
    return {"title": title, "description": description[:4000], "color": color,
            "fields": [{"name": n, "value": str(v)[:1000], "inline": True} for n, v in fields][:25],
            "timestamp": dt.datetime.now(dt.timezone.utc).isoformat()}


def session_embed(sess, closed):
    groups = {}
    for e in sess["entries"].values():
        mark = f"`{e['save']}`" + (f" ×{e['count']}" if e["count"] > 1 else "")
        groups.setdefault((e["game"], e["profile"]), []).append(mark)
    lines = [f"**{game}** · {profile}\n" + " · ".join(saves) for (game, profile), saves in groups.items()]
    more = f"\n… e mais {len(lines) - 12} jogos" if len(lines) > 12 else ""
    versions = sum(e["count"] for e in sess["entries"].values())
    size = sum(e["bytes"] for e in sess["entries"].values())
    title = "✅  Sessão encerrada, saves guardados" if closed else "💾  Guardando os saves desta sessão"
    return make_embed(title, "\n\n".join(lines[:12]) + more, 0x5BE3A0 if closed else 0xFFC53D, [
        ("Versões novas", versions), ("Saves", len(sess["entries"])), ("Tamanho", f"{size / 1048576:.1f} MB"),
        ("Início", f"<t:{sess['started']}:t>"), ("Última cópia", f"<t:{sess['updated']}:R>"),
        ("Gatilho", sess.get("trigger", "-"))])


def session_record(cfg, state, copied, trigger):
    """Uma única mensagem por sessão de jogo, editada a cada cópia (sem enxurrada)."""
    if not cfg["notify"]["on_backup"] or not webhook_url():
        return
    now, sess = int(time.time()), state["session"]
    if sess and now - sess["updated"] > cfg["notify"]["session_gap_hours"] * 3600:
        session_close(state)
        sess = None
    if not sess:
        sess = state["session"] = {"message_id": None, "started": now, "entries": {}}
    for c in copied:
        e = sess["entries"].setdefault(c["key"], {"game": c["game"], "profile": c["profile"],
                                                  "save": c["save"], "count": 0, "bytes": 0})
        e["count"] += 1
        e["bytes"] += c["bytes"]
    sess["updated"], sess["trigger"] = now, TRIGGER_LABEL.get(trigger, trigger)
    sess["message_id"] = send_embed(session_embed(sess, False), sess["message_id"])


def session_close(state):
    sess = state["session"]
    if sess and sess.get("message_id"):
        send_embed(session_embed(sess, True), sess["message_id"])
    state["session"] = None


def notify_error(cfg, title, description):
    """Erros iguais em sequência não viram uma mensagem por rodada."""
    if not cfg["notify"]["on_error"] or not webhook_url():
        return
    with locked():
        state = load_state()
        last = state["meta"].get("last_error_notified", 0)
        if time.time() - last < cfg["notify"]["error_cooldown_minutes"] * 60:
            return
        state["meta"]["last_error_notified"] = int(time.time())
        save_json(STATE_FILE, state)
    send_embed(make_embed("⚠️  " + title, description, 0xFF6B6B))


# ---------------------------------------------------------------- PS5 (leitura)

def ps5_online(cfg):
    try:
        socket.create_connection((cfg["ps5"]["host"], cfg["ps5"]["ftp_port"]), timeout=3).close()
        return True
    except OSError:
        return False


def ftp_connect(cfg):
    ftp = ftplib.FTP()
    ftp.connect(cfg["ps5"]["host"], cfg["ps5"]["ftp_port"], timeout=30)
    ftp.login()
    return ftp


def mlsd(ftp, path):
    """Lista um diretório. Diretório inexistente vira lista vazia.
    O ftpsrv ignora o argumento do MLSD e lista o diretório atual, por isso o CWD."""
    try:
        ftp.cwd(path)
        return [(n, f) for n, f in ftp.mlsd() if n not in (".", "..")]
    except ftplib.error_perm:
        return []


def ftp_bytes(ftp, path):
    buf = io.BytesIO()
    ftp.retrbinary(f"RETR {path}", buf.write)
    return buf.getvalue()


def read_profile_name(ftp, uid):
    try:
        raw = ftp_bytes(ftp, f"/user/home/{uid}/username.dat")
    except ftplib.all_errors:
        return ""
    return raw[:16].split(b"\0")[0].decode("utf-8", "replace")


def matches(values, *candidates):
    wanted = {str(v).lower() for v in values}
    return any(c and c.lower() in wanted for c in candidates)


def profile_included(cfg, uid, name):
    flt = cfg["filter"]
    if matches(flt["exclude_profiles"], uid, name):
        return False
    if matches(flt["include_profiles"], uid, name):
        return True
    return flt["new_profiles"] == "include"  # perfil sem decisão segue a regra dos novos


def title_included(cfg, title):
    flt = cfg["filter"]
    if flt["include_titles"] and not matches(flt["include_titles"], title):
        return False
    return not matches(flt["exclude_titles"], title)


def scan(ftp, cfg, state, refresh_names):
    """Lista os saves de todos os perfis. Os excluídos também são listados (para a
    interface mostrar), mas marcados com included=False e nunca baixados."""
    items, new_profiles, first_run = [], [], not state["profile_seen"]
    for uid, facts in mlsd(ftp, "/user/home"):
        if facts.get("type") != "dir" or not UID_RE.fullmatch(uid):
            continue
        if refresh_names or uid not in state["profiles"]:
            state["profiles"][uid] = read_profile_name(ftp, uid) or state["profiles"].get(uid, "")
        if uid not in state["profile_seen"]:
            # Na primeira rodada todos os perfis são conhecidos de partida, não "novos".
            state["profile_seen"][uid] = 0 if first_run else int(time.time())
            if not first_run:
                new_profiles.append(uid)
        profile_ok = profile_included(cfg, uid, state["profiles"][uid])
        for kind in SAVE_KINDS:
            for title, tfacts in mlsd(ftp, f"/user/home/{uid}/{kind}"):
                if tfacts.get("type") != "dir" or not TITLE_RE.fullmatch(title):
                    continue
                tdir = f"/user/home/{uid}/{kind}/{title}"
                for fname, ffacts in mlsd(ftp, tdir):
                    if ffacts.get("type") != "file":
                        continue
                    items.append({"uid": uid, "kind": kind, "title": title, "file": fname,
                                  "dir": tdir, "rpath": f"{tdir}/{fname}",
                                  "size": int(ffacts.get("size", -1)), "modify": ffacts.get("modify", ""),
                                  "included": profile_ok and title_included(cfg, title)})
    state["console"] = {i["rpath"]: {"uid": i["uid"], "title": i["title"], "file": i["file"],
                                     "size": i["size"], "included": i["included"]} for i in items}
    return items, new_profiles


def refresh_save_meta(ftp, state, uid, kind):
    """Lê o banco de saves do perfil para obter o nome e o subtítulo de cada save."""
    try:
        raw = ftp_bytes(ftp, f"/system_data/{kind}/{uid}/db/user/savedata.db")
    except ftplib.all_errors:
        return
    tmp = TMP_DIR / "savedata.db"
    tmp.write_bytes(raw)
    try:
        db = sqlite3.connect(f"file:{tmp}?mode=ro", uri=True)
        for title, dirname, main, sub, detail in db.execute(
                "SELECT title_id, dir_name, main_title, sub_title, detail FROM savedata"):
            state["savemeta"][f"{uid}/{title}/{dirname}"] = {
                "label": main or "", "sub": sub or "", "detail": detail or ""}
        db.close()
    except sqlite3.Error as e:
        log.info("banco de saves de %s ilegível (%s); sigo sem os nomes", uid, e)
    tmp.unlink(missing_ok=True)


def refresh_title_meta(ftp, state, title):
    """Nome, versão e arte do jogo, lidos de /user/appmeta. A arte fica em cache."""
    base = f"/user/appmeta/{title}"
    present = {name for name, _ in mlsd(ftp, base)}
    if "param.json" in present:
        try:
            param = json.loads(ftp_bytes(ftp, f"{base}/param.json"))
            loc = param.get("localizedParameters", {})
            name = loc.get(loc.get("defaultLanguage", ""), {}).get("titleName", "")
            state["titles"][title] = name or state["titles"].get(title, "")
            state["title_info"][title] = {"version": param.get("contentVersion", "")}
        except (json.JSONDecodeError, *ftplib.all_errors):
            pass
    state["titles"].setdefault(title, "")
    for art in ART_FILES:
        dest = ART_DIR / title / art
        if art in present and not dest.exists():
            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                tmp = dest.with_suffix(".part")
                with open(tmp, "wb") as f:
                    ftp.retrbinary(f"RETR {base}/{art}", f.write)
                tmp.replace(dest)
            except ftplib.all_errors as e:
                log.info("arte %s/%s indisponível: %s", title, art, e)


def save_info(state, item):
    """Nome amigável do save. Cópias de segurança do sistema (sce_bu_) usam o nome do original."""
    name = item["file"].removeprefix("sdimg_")
    base = f"{item['uid']}/{item['title']}/"
    return (state["savemeta"].get(base + name)
            or state["savemeta"].get(base + name.removeprefix("sce_bu_"))
            or {"label": "", "sub": "", "detail": ""})


def download(ftp, item, dest):
    """Baixa o arquivo e confirma que ele não mudou no PS5 durante a cópia."""
    for _ in range(3):
        h, n = hashlib.sha256(), 0
        with open(dest, "wb") as f:
            def chunk(b):
                nonlocal n
                f.write(b)
                h.update(b)
                n += len(b)
            ftp.retrbinary(f"RETR {item['rpath']}", chunk, blocksize=1 << 16)
        after = dict(mlsd(ftp, item["dir"])).get(item["file"])
        if after is None:
            raise RuntimeError("arquivo sumiu do PS5 durante a cópia")
        size, modify = int(after.get("size", -1)), after.get("modify", "")
        if (size, modify) == (item["size"], item["modify"]) and n == size:
            return h.hexdigest()
        log.info("%s mudou durante a cópia; tentando de novo", item["rpath"])
        item["size"], item["modify"] = size, modify
        time.sleep(5)
    raise RuntimeError("arquivo não estabilizou (jogo gravando?); fica para a próxima rodada")


# ------------------------------------------------------------------- backup

def version_root(item):
    return SAVES_DIR / item["uid"] / item["title"] / item["file"]


def superseded_version(stamps, gap_minutes):
    """Jogos que regravam o save a cada minuto gerariam dezenas de versões por hora.
    A cópia nova é sempre guardada; a anterior só é mantida se já estiver a pelo
    menos `gap_minutes` da que veio antes dela. Devolve a versão a descartar (a
    penúltima, depois que a nova entrou) ou None. `stamps` em ordem crescente."""
    if gap_minutes <= 0 or len(stamps) < 3:
        return None
    try:
        before, middle = (dt.datetime.strptime(x, STAMP_FMT) for x in stamps[-3:-1])
    except ValueError:
        return None
    return stamps[-2] if (middle - before).total_seconds() < gap_minutes * 60 else None


def run_backup(cfg, trigger, pending=None):
    """Uma rodada incremental. `pending` (modo vigia) exige que o arquivo apareça
    igual em duas varreduras seguidas antes de copiar. Devolve a lista de erros."""
    with locked():
        state = load_state()
        full = pending is None
        ftp = ftp_connect(cfg)
        errors, copied, same, waiting, nbytes = [], [], 0, 0, 0
        try:
            TMP_DIR.mkdir(parents=True, exist_ok=True)
            all_items, new_profiles = scan(ftp, cfg, state, refresh_names=full)
            items = [i for i in all_items if i["included"]]
            for title in {i["title"] for i in all_items}:
                if full or title not in state["titles"]:
                    refresh_title_meta(ftp, state, title)
            meta_done = set()
            if full:
                for uid, kind in {(i["uid"], i["kind"]) for i in all_items}:
                    refresh_save_meta(ftp, state, uid, kind)
                    meta_done.add((uid, kind))
            for item in items:
                key, sig = item["rpath"], [item["size"], item["modify"]]
                prev = state["files"].get(key)
                have = prev and (version_root(item) / prev["version"] / item["file"]).exists()
                if have and prev["sig"] == sig:
                    same += 1
                    continue
                if pending is not None and pending.get(key) != sig:
                    pending[key] = sig
                    waiting += 1
                    continue
                tmp = TMP_DIR / "download.part"
                try:
                    sha = download(ftp, item, tmp)
                except (RuntimeError, *ftplib.all_errors) as e:
                    log.warning("falha ao copiar %s: %s", key, e)
                    errors.append(f"`{item['title']}/{item['file']}`: {e}")
                    continue
                sig = [item["size"], item["modify"]]
                if have and prev["sha256"] == sha:
                    prev["sig"] = sig  # só a data mudou; conteúdo idêntico, sem nova versão
                    same += 1
                    continue
                if (item["uid"], item["kind"]) not in meta_done:
                    refresh_save_meta(ftp, state, item["uid"], item["kind"])
                    meta_done.add((item["uid"], item["kind"]))
                info = save_info(state, item)
                stamp = time.strftime(STAMP_FMT)
                vdir = version_root(item) / stamp
                vdir.mkdir(parents=True, exist_ok=True)
                shutil.move(tmp, vdir / item["file"])
                profile = state["profiles"].get(item["uid"]) or item["uid"]
                game = state["titles"].get(item["title"]) or item["title"]
                save_json(vdir / "meta.json", {
                    "uid": item["uid"], "profile": profile, "title_id": item["title"], "title_name": game,
                    "kind": item["kind"], "file": item["file"], "label": info["label"],
                    "sub_title": info["sub"], "detail": info["detail"], "remote_path": key,
                    "size": item["size"], "remote_mtime_utc": item["modify"],
                    "sha256": sha, "backed_up_at": stamp, "trigger": trigger})
                state["files"][key] = {"sig": sig, "sha256": sha, "version": stamp}
                nbytes += item["size"]
                copied.append({"key": key, "game": game, "profile": profile, "bytes": item["size"],
                               "save": info["label"] or item["file"].removeprefix("sdimg_")})
                log.info("NOVA VERSÃO %s/%s/%s (%s, %d bytes, sha256 %s…)", item["uid"],
                         item["title"], item["file"], stamp, item["size"], sha[:12])
                root = version_root(item)
                stamps = sorted(d.name for d in root.iterdir() if (d / "meta.json").exists())
                old = superseded_version(stamps, cfg["retention"]["min_gap_minutes"])
                if old and not (root / old / PIN_NAME).exists():
                    shutil.rmtree(root / old)
                    log.info("  substitui %s (intervalo menor que %d min)", old, cfg["retention"]["min_gap_minutes"])
            if pending is not None:
                live = {i["rpath"] for i in items}
                for key in [k for k in pending if k not in live]:
                    del pending[key]
        finally:
            try:
                ftp.quit()
            except ftplib.all_errors:
                pass
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        state["meta"].update({"last_run": now, "last_trigger": trigger})
        if not errors:
            state["meta"]["last_ok"] = now
        if copied:
            session_record(cfg, state, copied, trigger)
        save_json(STATE_FILE, state)
        if full or copied or errors:
            log.info("backup [%s]: %d arquivos em %d perfis; %d novas versões (%.1f MB), "
                     "%d inalterados, %d aguardando estabilizar, %d falhas; %d fora do backup",
                     trigger, len(items), len({i["uid"] for i in items}), len(copied), nbytes / 1048576,
                     same, waiting, len(errors), len(all_items) - len(items))
        if copied:
            prune(cfg)
    for uid in new_profiles:
        name = state["profiles"].get(uid) or uid
        included = profile_included(cfg, uid, name)
        log.info("PERFIL NOVO no PS5: %s (%s); %s", name, uid, "incluído" if included else "fora do backup")
        if cfg["notify"]["on_new_profile"]:
            send_embed(make_embed(f"👤  Perfil novo no PS5: {name}",
                                  "Os saves dele já entram no backup." if included else
                                  "Ele está fora do backup até você incluir na interface.", 0x7C8CFF))
    return errors


def versions_to_keep(stamps, pinned, rules, now):
    """Decide o que fica. `stamps` vem do mais novo para o mais velho.
    Fica: as N mais novas, as fixadas, tudo da última hora (configurável) e, dali
    para trás, a última versão de cada hora, depois de cada dia, de cada semana e,
    para sempre, de cada mês. Nenhum período com cópias fica sem representante."""
    keep = set(stamps[:max(rules["keep_min_versions"], 1)]) | set(pinned)
    seen = set()
    for stamp in stamps:
        try:
            when = dt.datetime.strptime(stamp, STAMP_FMT)
        except ValueError:
            keep.add(stamp)  # nome fora do padrão: não mexo
            continue
        age_hours = (now - when).total_seconds() / 3600
        if age_hours <= rules["keep_all_hours"]:
            keep.add(stamp)
            continue
        if age_hours <= rules["keep_hourly_days"] * 24:
            bucket = ("hora", stamp[:11])
        elif age_hours <= rules["keep_daily_days"] * 24:
            bucket = ("dia", stamp[:8])
        elif age_hours <= rules["keep_weekly_weeks"] * 168:
            bucket = ("semana", *when.isocalendar()[:2])
        else:
            bucket = ("mês", stamp[:6])
        if bucket not in seen:
            seen.add(bucket)
            keep.add(stamp)
    return keep


def prune(cfg):
    """Rareia versões antigas. Versões recentes (dentro de keep_hourly_days) saem
    direto, porque sempre sobra uma por hora. As mais velhas vão para a lixeira
    (trash/) e só são removidas de vez depois de trash_days."""
    rules, removed, now = cfg["retention"], 0, dt.datetime.now()
    if rules["thin_old_versions"]:
        for fdir in SAVES_DIR.glob("*/*/*"):
            stamps = sorted((d.name for d in fdir.iterdir() if (d / "meta.json").exists()), reverse=True)
            pinned = [st for st in stamps if (fdir / st / PIN_NAME).exists()]
            keep = versions_to_keep(stamps, pinned, rules, now)
            for stamp in stamps:
                if stamp in keep:
                    continue
                when = dt.datetime.strptime(stamp, STAMP_FMT)  # válido: nomes fora do padrão estão em keep
                if (now - when).total_seconds() <= rules["keep_hourly_days"] * 86400:
                    shutil.rmtree(fdir / stamp)
                    removed += 1
                    continue
                dest = TRASH_DIR / fdir.relative_to(SAVES_DIR) / stamp
                dest.parent.mkdir(parents=True, exist_ok=True)
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.move(fdir / stamp, dest)
                os.utime(dest)  # a data da pasta marca quando entrou na lixeira
                removed += 1
                log.info("retenção: %s foi para a lixeira", dest.relative_to(TRASH_DIR))
    cutoff = time.time() - rules["trash_days"] * 86400
    for vdir in TRASH_DIR.glob("*/*/*/*"):
        if vdir.stat().st_mtime < cutoff:
            shutil.rmtree(vdir)
            log.info("lixeira: %s removida de vez", vdir.relative_to(TRASH_DIR))
    return removed


def dir_bytes(path):
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) if path.exists() else 0


def check_size(cfg):
    """Passar dos limites nunca apaga nada: só avisa, no máximo uma vez por dia."""
    rules = cfg["retention"]
    used = dir_bytes(SAVES_DIR) + dir_bytes(TRASH_DIR)
    free = shutil.disk_usage(DATA_DIR).free
    over = rules["warn_total_gb"] and used > rules["warn_total_gb"] * 1024 ** 3
    low = rules["warn_free_gb"] and free < rules["warn_free_gb"] * 1024 ** 3
    if not over and not low:
        return
    limit = rules["warn_total_gb"]
    log.warning("espaço: backups ocupam %.1f GB (aviso em %d GB); %.1f GB livres no disco",
                used / 1024 ** 3, limit, free / 1024 ** 3)
    with locked():
        state = load_state()
        if time.time() - state["meta"].get("last_size_warned", 0) < 86400:
            return
        state["meta"]["last_size_warned"] = int(time.time())
        save_json(STATE_FILE, state)
    if cfg["notify"]["on_error"]:
        send_embed(make_embed("📦  Atenção ao espaço dos backups",
                              f"Os backups ocupam {used / 1024 ** 3:.1f} GB e restam {free / 1024 ** 3:.1f} GB livres "
                              "no disco. Nada foi apagado. Veja Ajustes › Quanto guardar.", 0xFFC53D))


def safe_run(cfg, trigger, pending=None):
    STATUS["running"] = trigger
    try:
        errors = run_backup(cfg, trigger, pending)
        if errors:
            notify_error(cfg, "Falha ao copiar saves", "\n".join(errors[:15]))
        if pending is None:
            check_size(cfg)
        return not errors
    except Exception as e:
        log.error("backup [%s] falhou: %s: %s", trigger, type(e).__name__, e)
        notify_error(cfg, "Backup falhou", f"`{type(e).__name__}: {e}`")
        return False
    finally:
        STATUS["running"] = None


# ------------------------------------------------------------------- daemon

def schedule_due(cfg, last_ts, now_ts):
    trig = cfg["triggers"]
    hours = trig["schedule_interval_hours"]
    if hours and now_ts - last_ts >= hours * 3600:
        return True
    today = dt.datetime.fromtimestamp(now_ts).date()
    for hhmm in trig["schedule_daily_at"]:
        h, m = map(int, hhmm.split(":"))
        slot = dt.datetime.combine(today, dt.time(h, m)).timestamp()
        if last_ts < slot <= now_ts:
            return True
    return False


def daemon(cfg):
    log.info("daemon iniciado; PS5 %s (ftp %d)", cfg["ps5"]["host"], cfg["ps5"]["ftp_port"])
    online, fails, next_watch, pending, warned_missed = False, 0, 0.0, {}, False
    # Agendamento conta a partir de agora; o que venceu com o daemon parado não é reexecutado.
    last_sched = time.time()
    while True:
        try:
            cfg = load_config()  # ajustes feitos na interface valem na hora
        except Exception as e:
            log.warning("config.toml inválido (%s); mantendo os ajustes anteriores", e)
        trig = cfg["triggers"]
        now = time.time()
        due = schedule_due(cfg, last_sched, now)
        if ps5_online(cfg):
            fails = 0
            if not online:
                online = STATUS["online"] = True
                log.info("PS5 ONLINE (ftpsrv respondeu)")
                if trig["on_power_on"] or due:
                    time.sleep(trig["power_on_delay_seconds"])
                    safe_run(cfg, "power_on" if trig["on_power_on"] else "schedule")
                    last_sched, warned_missed = time.time(), False
                next_watch = time.time() + trig["watch_interval_seconds"]
            elif due:
                safe_run(cfg, "schedule")
                last_sched, warned_missed = time.time(), False
            elif trig["on_save_change"] and now >= next_watch:
                safe_run(cfg, "save_changed", pending)
                next_watch = time.time() + trig["watch_interval_seconds"]
        else:
            fails += 1
            if STATUS["online"] is None:
                STATUS["online"] = False
            if online and fails >= trig["offline_after_failures"]:
                online = STATUS["online"] = False
                pending.clear()
                with locked():
                    state = load_state()
                    # Limitação: com o PS5 fora da rede não há como ler nada. O que foi
                    # gravado depois da última varredura só entra no próximo boot.
                    log.info("PS5 OFFLINE (desligado/repouso/fora da rede). Última rodada sem falhas: %s",
                             state["meta"].get("last_ok", "nunca"))
                    session_close(state)  # fecha a mensagem da sessão no Discord, sem criar outra
                    save_json(STATE_FILE, state)
            if due and not warned_missed:
                warned_missed = True
                log.info("agendamento vencido com o PS5 offline; roda quando ele voltar")
        time.sleep(trig["probe_interval_seconds"])


# ------------------------------------------------------------------ comandos

def iter_versions():
    for meta_path in sorted(SAVES_DIR.glob("*/*/*/*/meta.json")):
        yield meta_path.parent, load_json(meta_path, {})


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def verify_local():
    ok, bad = 0, []
    for vdir, meta in iter_versions():
        path = vdir / meta.get("file", "?")
        if path.exists() and path.stat().st_size == meta.get("size") and sha256_file(path) == meta.get("sha256"):
            ok += 1
        else:
            bad.append(str(path.relative_to(SAVES_DIR)))
    return {"ok": ok, "bad": bad}


def cmd_verify(cfg, remote):
    result = verify_local()
    for path in result["bad"]:
        print(f"CORROMPIDO/AUSENTE: {path}")
    print(f"local: {result['ok']} versões íntegras, {len(result['bad'])} com problema")
    problems = len(result["bad"])
    if remote:
        # Compara a versão mais nova de cada save com o que está no PS5 agora.
        with locked():
            state = load_state()
            ftp = ftp_connect(cfg)
            TMP_DIR.mkdir(parents=True, exist_ok=True)
            items = [i for i in scan(ftp, cfg, state, refresh_names=False)[0] if i["included"]]
            match = differ = missing = 0
            for item in items:
                prev = state["files"].get(item["rpath"])
                if not prev:
                    missing += 1
                    print(f"SEM BACKUP: {item['rpath']}")
                    continue
                sha = download(ftp, item, TMP_DIR / "verify.part")
                if sha == prev["sha256"]:
                    match += 1
                    print(f"IGUAL AO CONSOLE  {item['size']:>10} {sha[:16]}  {item['rpath']}")
                else:
                    differ += 1
                    print(f"MUDOU NO CONSOLE (ainda não copiado): {item['rpath']}")
            (TMP_DIR / "verify.part").unlink(missing_ok=True)
            ftp.quit()
        print(f"console: {match} idênticos ao backup, {differ} mudaram depois, {missing} sem backup "
              f"({len(items)} arquivos em {len({i['uid'] for i in items})} perfis)")
        problems += missing
    return 1 if problems else 0


def cmd_list():
    state = load_state()
    groups = {}
    for vdir, meta in iter_versions():
        groups.setdefault((meta.get("uid"), meta.get("title_id"), meta.get("file")), []).append((vdir, meta))
    for (uid, title, fname), versions in groups.items():
        vdir, meta = versions[-1]
        prof = state["profiles"].get(uid) or meta.get("profile", "")
        tname = state["titles"].get(title) or meta.get("title_name", "")
        print(f"{uid} ({prof})  {title} {tname!r}  {fname}  versões={len(versions)}  "
              f"última={vdir.name}\n    {vdir / fname}")
    return 0


def cmd_status(cfg):
    state = load_state()
    versions = list(iter_versions())
    size = sum((v / m.get("file", "")).stat().st_size for v, m in versions if (v / m.get("file", "")).exists())
    print(f"PS5 {cfg['ps5']['host']}: {'ONLINE' if ps5_online(cfg) else 'OFFLINE'}")
    print(f"última rodada: {state['meta'].get('last_run', 'nunca')} ({state['meta'].get('last_trigger', '-')})")
    print(f"última rodada sem falhas: {state['meta'].get('last_ok', 'nunca')}")
    for uid, name in state["profiles"].items():
        print(f"perfil {uid} {name!r}: {'no backup' if profile_included(cfg, uid, name) else 'FORA do backup'}")
    print(f"saves acompanhados: {len(state['files'])}; versões guardadas: {len(versions)}; {size / 1048576:.1f} MB")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("daemon", help="vigia o PS5, dispara backups e serve a interface web")
    sub.add_parser("backup", help="roda um backup agora (disparo manual)")
    sub.add_parser("status", help="estado do PS5 e do último backup")
    sub.add_parser("list", help="lista saves guardados e o caminho da versão mais nova")
    verify = sub.add_parser("verify", help="confere o checksum de todas as versões")
    verify.add_argument("--remote", action="store_true", help="também compara com o PS5 ao vivo")
    sub.add_parser("prune", help="aplica a retenção agora")
    args = parser.parse_args()
    cfg = load_config()
    setup_logging()
    if args.cmd == "daemon":
        import web
        threading.Thread(target=web.serve, daemon=True).start()
        daemon(cfg)
    elif args.cmd == "backup":
        return 0 if safe_run(cfg, "manual") else 1
    elif args.cmd == "status":
        return cmd_status(cfg)
    elif args.cmd == "list":
        return cmd_list()
    elif args.cmd == "verify":
        return cmd_verify(cfg, args.remote)
    elif args.cmd == "prune":
        with locked():
            print(f"{prune(cfg)} versões enviadas para a lixeira")
    return 0
