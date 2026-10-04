"""Apoio dos testes: coloca app/ no caminho e aponta o núcleo para um diretório temporário."""
import datetime as dt
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

import ps5backup as core  # noqa: E402

core.log.propagate = False  # o log do serviço não polui a saída dos testes
core.log.addHandler(__import__("logging").NullHandler())

RULES = dict(core.DEFAULTS["retention"])


def stamp(when):
    return when.strftime(core.STAMP_FMT)


class DataDirCase(unittest.TestCase):
    """Cada teste roda em uma pasta de backup vazia e descartável. Nada aqui
    enxerga a pasta real: todos os caminhos do núcleo são trocados no setUp."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ps5backup-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        paths = {"DATA_DIR": self.tmp, "SAVES_DIR": self.tmp / "saves", "TRASH_DIR": self.tmp / "trash",
                 "STATE_FILE": self.tmp / "state.json", "STATS_FILE": self.tmp / "stats.json",
                 "SECRETS_FILE": self.tmp / "secrets.json", "LOG_FILE": self.tmp / "backup.log",
                 "TMP_DIR": self.tmp / ".tmp", "ART_DIR": self.tmp / "cache" / "art"}
        for name, value in paths.items():
            patcher = mock.patch.object(core, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        # Nenhum teste fala com a rede: qualquer envio de aviso vira uma chamada registrada.
        patcher = mock.patch.object(core, "send_embed", mock.Mock(return_value=None))
        self.sent = patcher.start()
        self.addCleanup(patcher.stop)
        core.SAVES_DIR.mkdir()

    def add_version(self, when, save=("1a2b3c4d", "PPSA00001", "sdimg_slot"), pinned=False, size=1000,
                    content=None, root=None):
        """Cria uma versão como o backup criaria. `when` é datetime ou o nome da pasta."""
        uid, title, fname = save
        name = when if isinstance(when, str) else stamp(when)
        vdir = (root or core.SAVES_DIR) / uid / title / fname / name
        vdir.mkdir(parents=True)
        data = content if content is not None else b"x" * size
        (vdir / fname).write_bytes(data)
        (vdir / "meta.json").write_text(json.dumps({
            "uid": uid, "title_id": title, "file": fname, "size": len(data),
            "sha256": core.hashlib.sha256(data).hexdigest(), "remote_mtime_utc": "20260101000000"}))
        if pinned:
            (vdir / core.PIN_NAME).touch()
        return vdir

    def stored(self, save=("1a2b3c4d", "PPSA00001", "sdimg_slot"), root=None):
        fdir = (root or core.SAVES_DIR).joinpath(*save)
        return sorted(d.name for d in fdir.iterdir()) if fdir.exists() else []


def ago(now, **delta):
    return now - dt.timedelta(**delta)
