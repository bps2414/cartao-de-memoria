"""Projeção de espaço: repete o ritmo de cópias observado nos últimos dias e
aplica, dia a dia, as mesmas regras de retenção que o serviço usa de verdade
(`superseded_version` e `versions_to_keep`). Não é uma extrapolação linear.
"""
import datetime as dt
import re
import threading
import time
from collections import defaultdict

import ps5backup as core

WINDOW_DAYS = 7
HORIZONS = (30, 90, 365)
CACHE_SECONDS = 900
LINE_RE = re.compile(r"^(\d{4}-\d\d-\d\d) (\d\d):(\d\d):(\d\d) INFO NOVA VERSÃO (\S+)/(\S+)/(\S+) \(\S+, (\d+) bytes")

_cache = {"at": 0.0, "data": None, "busy": False}


def observed_activity(now):
    """Lê o log: para cada save, em que segundos de cada dia houve cópia."""
    activity = defaultdict(lambda: defaultdict(list))  # save -> data -> [segundo do dia]
    first = now.date()
    raw_bytes = copies = 0
    try:
        lines = core.LOG_FILE.read_text(errors="replace").splitlines()
    except FileNotFoundError:
        lines = []
    oldest = now.date() - dt.timedelta(days=WINDOW_DAYS - 1)
    for line in lines:
        m = LINE_RE.match(line)
        if not m:
            continue
        day = dt.date.fromisoformat(m[1])
        first = min(first, day)
        if day < oldest:
            continue
        activity[(m[5], m[6], m[7])][day].append(int(m[2]) * 3600 + int(m[3]) * 60 + int(m[4]))
        raw_bytes += int(m[8])
        copies += 1
    window = max(1, min(WINDOW_DAYS, (now.date() - first).days + 1))
    return activity, window, copies, raw_bytes


def simulate(cfg, now=None):
    now = now or dt.datetime.now()
    rules, state = cfg["retention"], core.load_state()
    activity, window, copies, raw_bytes = observed_activity(now)
    days = [now.date() - dt.timedelta(days=window - 1 - i) for i in range(window)]

    current = {}  # save -> (versões em ordem crescente, fixadas, tamanho)
    for vdir, meta in core.iter_versions():
        key = (meta["uid"], meta["title_id"], meta["file"])
        entry = current.setdefault(key, ([], set(), meta.get("size", 0)))
        entry[0].append(vdir.name)
        if (vdir / core.PIN_NAME).exists():
            entry[1].add(vdir.name)

    totals = dict.fromkeys(HORIZONS, 0)
    for key in set(current) | set(activity):
        kept, pinned, size = current.get(key, ([], set(), 0))
        kept = sorted(kept)
        size = size or 6 * 1048576
        uid, title, _ = key
        active = (core.profile_included(cfg, uid, state["profiles"].get(uid, ""))
                  and core.title_included(cfg, title))
        pattern = [sorted(activity[key].get(day, [])) if active else [] for day in days]
        trash = []
        for d in range(1, max(HORIZONS) + 1):
            midnight = dt.datetime.combine(now.date() + dt.timedelta(days=d), dt.time())
            for second in pattern[(d - 1) % window]:
                kept.append((midnight + dt.timedelta(seconds=second)).strftime(core.STAMP_FMT))
                old = core.superseded_version(kept, rules["min_gap_minutes"])
                if old and old not in pinned:
                    kept.remove(old)
            end = midnight + dt.timedelta(hours=23, minutes=59)
            if rules["thin_old_versions"]:
                keep = core.versions_to_keep(sorted(kept, reverse=True), pinned, rules, end)
                for stamp in [k for k in kept if k not in keep]:
                    age = (end - dt.datetime.strptime(stamp, core.STAMP_FMT)).total_seconds()
                    if age > rules["keep_hourly_days"] * 86400:
                        trash.append(d)
                kept = [k for k in kept if k in keep]
            trash = [x for x in trash if d - x < rules["trash_days"]]
            if d in totals:
                totals[d] += (len(kept) + len(trash)) * size

    stored = core.dir_bytes(core.SAVES_DIR) + core.dir_bytes(core.TRASH_DIR)
    per_day = raw_bytes / window
    return {
        "window_days": window, "copies_per_day": round(copies / window, 1), "raw_bytes_per_day": int(per_day),
        "now_bytes": stored, "free_bytes": core.shutil.disk_usage(core.DATA_DIR).free,
        "projected": {str(h): int(totals[h]) for h in HORIZONS},
        "without_cleanup_year": int(stored + per_day * 365),
        "computed_at": now.strftime("%Y-%m-%d %H:%M"),
    }


def cached(cfg):
    """Devolve a última projeção e recalcula em segundo plano quando envelhece."""
    def work():
        try:
            _cache["data"] = simulate(cfg)
        except Exception as e:
            core.log.warning("projeção de espaço falhou: %s", e)
        _cache["at"], _cache["busy"] = time.time(), False

    if not _cache["busy"] and time.time() - _cache["at"] > CACHE_SECONDS:
        _cache["busy"] = True
        threading.Thread(target=work, daemon=True).start()
    return _cache["data"]
