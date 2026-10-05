"""Rodadas reais contra o FTP de mentira e portabilidade dos arquivos locais."""
import ftplib
import io
import os
import sqlite3
import subprocess
import sys
import threading
import time
import unittest
from contextlib import closing
from pathlib import Path
from unittest import mock

from helpers import DataDirCase, ROOT, core
from fake_ps5 import DB_PATH, OTHER_SAVE_PATH, OTHER_UID, SAVE_LABEL, SAVE_PATH, TITLE, UID, FakePS5


class Backup(DataDirCase):
    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(core, "CONFIG_PATH", self.tmp / "config.toml")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.fake = FakePS5().start()
        self.addCleanup(self.fake.stop)
        self.cfg = core.validate_config({"ps5": {"host": self.fake.host, "ftp_port": self.fake.port}})
        core.save_config(self.cfg)

    def run_backup(self, stamp="20261005-120000"):
        # Rodadas rápidas ainda têm datas diferentes, sem esperar um segundo.
        strftime = time.strftime
        with mock.patch.object(core.time, "strftime", side_effect=lambda fmt, *args:
                               stamp if fmt == core.STAMP_FMT and not args else strftime(fmt, *args)):
            self.assertEqual(core.run_backup(self.cfg, "manual"), [])

    def test_first_backup_copies_saves_with_matching_sha256(self):
        self.run_backup()
        versions = list(core.iter_versions())
        self.assertEqual(len(versions), 2)
        for vdir, meta in versions:
            data = self.fake.files[meta["remote_path"]]
            self.assertEqual((vdir / meta["file"]).read_bytes(), data)
            self.assertEqual(meta["sha256"], core.hashlib.sha256(data).hexdigest())
            self.assertEqual(meta["size"], len(data))
        self.assertEqual(core.load_state()["profiles"][UID], "João")
        self.assertTrue(core.STATS_FILE.exists())
        allowed = {"USER", "PASS", "CWD", "PWD", "TYPE", "PASV", "MLSD", "RETR", "FEAT", "SYST", "QUIT"}
        self.assertLessEqual({command for command, _ in self.fake.commands}, allowed)

    def test_unchanged_second_backup_creates_no_version(self):
        self.run_backup()
        before = list(core.iter_versions())
        self.fake.commands.clear()
        self.run_backup("20261005-120100")
        self.assertEqual(list(core.iter_versions()), before)
        retrieved = [arg for command, arg in self.fake.commands if command == "RETR"]
        self.assertNotIn(SAVE_PATH, retrieved)
        self.assertNotIn(OTHER_SAVE_PATH, retrieved)

    def test_changed_console_file_creates_new_version(self):
        self.run_backup()
        changed = b"conteudo alterado no console de mentira"
        self.fake.set_file(SAVE_PATH, changed)
        self.run_backup("20261005-120100")
        self.assertEqual(self.stored(), ["20261005-120000", "20261005-120100"])
        versions = [(vdir, meta) for vdir, meta in core.iter_versions() if meta["uid"] == UID]
        self.assertEqual((versions[0][0] / "sdimg_slot").read_bytes(), b"save original do primeiro perfil")
        self.assertEqual((versions[1][0] / "sdimg_slot").read_bytes(), changed)
        self.assertEqual(versions[1][1]["sha256"], core.hashlib.sha256(changed).hexdigest())
        self.assertEqual(self.stored((OTHER_UID, TITLE, "sdimg_slot")), ["20261005-120000"])

    def test_excluded_profile_is_listed_but_its_save_is_not_downloaded(self):
        self.cfg["filter"]["exclude_profiles"] = ["Maria"]
        self.run_backup()
        state = core.load_state()
        self.assertEqual(state["profiles"][OTHER_UID], "Maria")
        self.assertFalse(state["console"][OTHER_SAVE_PATH]["included"])
        self.assertNotIn(OTHER_SAVE_PATH, state["files"])
        self.assertFalse((core.SAVES_DIR / OTHER_UID).exists())
        self.assertNotIn(("RETR", OTHER_SAVE_PATH), self.fake.commands)
        self.assertEqual(len(list(core.iter_versions())), 1)

    def test_save_name_comes_from_savedata_database(self):
        self.run_backup()
        meta = next(meta for _, meta in core.iter_versions() if meta["uid"] == UID)
        self.assertEqual(meta["label"], SAVE_LABEL)
        self.assertEqual(meta["sub_title"], "Capítulo 2")
        self.assertEqual(meta["detail"], "Antes do chefe")
        self.assertEqual(core.load_state()["savemeta"][f"{UID}/{TITLE}/slot"]["label"], SAVE_LABEL)
        self.assertFalse((core.TMP_DIR / "savedata.db").exists())

    def test_invalid_database_is_closed_before_temporary_file_is_deleted(self):
        with closing(sqlite3.connect(":memory:")) as db:
            db.execute("CREATE TABLE outra (id INTEGER)")
            self.fake.set_file(DB_PATH, db.serialize())
        core.TMP_DIR.mkdir()
        with core.ftp_connect(self.cfg) as ftp:
            state = core.load_state()
            core.refresh_save_meta(ftp, state, UID, "savedata_prospero")
        self.assertEqual(state["savemeta"], {})
        self.assertFalse((core.TMP_DIR / "savedata.db").exists())

    def test_unexpected_metadata_error_also_closes_and_deletes_database(self):
        core.TMP_DIR.mkdir()
        with core.ftp_connect(self.cfg) as ftp:
            with self.assertRaises(TypeError):
                core.refresh_save_meta(ftp, {"savemeta": None}, UID, "savedata_prospero")
        self.assertFalse((core.TMP_DIR / "savedata.db").exists())

    def test_accented_profile_name_round_trips_in_utf8_config(self):
        self.cfg["filter"]["include_profiles"] = ["João"]
        core.save_config(self.cfg)
        self.assertIn('"João"', core.CONFIG_PATH.read_bytes().decode("utf-8"))
        self.assertEqual(core.load_config(), self.cfg)

    def test_backup_also_works_when_mlsd_respects_its_argument(self):
        self.fake.respect_mlsd_argument = True
        self.run_backup()
        self.assertEqual(len(list(core.iter_versions())), 2)


class FTPFixture(unittest.TestCase):
    def test_mlsd_ignores_argument_by_default_and_can_respect_it(self):
        for respect in (False, True):
            with self.subTest(respect=respect), FakePS5(respect_mlsd_argument=respect) as fake:
                with ftplib.FTP() as ftp:
                    ftp.connect(fake.host, fake.port, timeout=5)
                    ftp.login()
                    self.assertIn("UNIX", ftp.sendcmd("SYST"))
                    self.assertIn("MLST", ftp.sendcmd("FEAT"))
                    ftp.cwd("/user/home")
                    self.assertEqual(ftp.pwd(), "/user/home")
                    listed = dict(ftp.mlsd(f"/user/appmeta/{TITLE}"))
                    self.assertEqual(set(listed), {"param.json"} if respect else {UID, OTHER_UID})
                    for facts in listed.values():
                        self.assertEqual(set(facts), {"type", "size", "modify"})
                        self.assertRegex(facts["modify"], r"^\d{14}$")


class Locking(DataDirCase):
    def test_two_threads_never_hold_lock_together(self):
        first_in, second_trying, second_in, release = (threading.Event() for _ in range(4))
        errors = []

        def first():
            try:
                with core.locked():
                    first_in.set()
                    if not release.wait(5):
                        raise RuntimeError("teste não liberou o primeiro lock")
            except Exception as e:
                errors.append(e)

        def second():
            try:
                second_trying.set()
                with core.locked():
                    second_in.set()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=first, daemon=True), threading.Thread(target=second, daemon=True)]
        try:
            threads[0].start()
            self.assertTrue(first_in.wait(5))
            threads[1].start()
            self.assertTrue(second_trying.wait(5))
            self.assertFalse(second_in.wait(0.15))
        finally:
            release.set()
            for thread in threads:
                if thread.ident is not None:
                    thread.join(timeout=5)
        self.assertEqual(errors, [])
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertTrue(second_in.is_set())

    def test_another_process_waits_for_the_same_lock(self):
        marker = self.tmp / "processo.txt"
        script = """from pathlib import Path
import ps5backup as core
print('esperando', flush=True)
with core.locked():
    (core.DATA_DIR / 'processo.txt').write_text('entrou', encoding='utf-8')
"""
        child = None
        try:
            with core.locked():
                child = subprocess.Popen([sys.executable, "-c", script], cwd=ROOT / "app",
                                         env={**os.environ, "PS5BACKUP_DATA": str(core.DATA_DIR)},
                                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8")
                self.assertEqual(child.stdout.readline(), "esperando\n")
                time.sleep(0.15)
                self.assertFalse(marker.exists())
            _, stderr = child.communicate(timeout=10)
            self.assertEqual(child.returncode, 0, stderr)
            self.assertEqual(marker.read_text(encoding="utf-8"), "entrou")
        finally:
            if child is not None:
                if child.poll() is None:
                    child.kill()
                child.communicate(timeout=5)

    def test_lock_is_released_after_exception(self):
        with self.assertRaisesRegex(RuntimeError, "falha de teste"):
            with core.locked():
                raise RuntimeError("falha de teste")
        with core.locked():
            pass


class LocalFiles(DataDirCase):
    def test_json_round_trips_in_utf8(self):
        data = {"perfil": "João", "nome": "日本語"}
        for path in (core.STATE_FILE, core.STATS_FILE, core.SECRETS_FILE, self.tmp / "meta.json"):
            with self.subTest(path=path.name):
                core.save_json(path, data)
                self.assertIn("João", path.read_bytes().decode("utf-8"))
                self.assertEqual(core.load_json(path, {}), data)

    def test_rotating_log_is_utf8(self):
        old_handlers, old_level = set(core.log.handlers), core.log.level
        try:
            with mock.patch.object(core.sys, "stdout", io.StringIO()):
                core.setup_logging()
                core.log.info("Cópia de João — 日本語")
            self.assertIn("Cópia de João — 日本語", core.LOG_FILE.read_text(encoding="utf-8"))
        finally:
            for handler in set(core.log.handlers) - old_handlers:
                core.log.removeHandler(handler)
                handler.close()
            core.log.setLevel(old_level)

    @unittest.skipUnless(os.name == "nt", "tentativas de replace são específicas do Windows")
    def test_json_replace_retries_transient_permission_error(self):
        core.save_json(core.STATE_FILE, {"versão": 1})
        replace, calls = Path.replace, []

        def busy_then_replace(path, target):
            calls.append(path)
            if len(calls) <= 2:
                raise PermissionError("arquivo em leitura")
            return replace(path, target)

        with mock.patch.object(Path, "replace", busy_then_replace):
            core.save_json(core.STATE_FILE, {"versão": 2})
        self.assertEqual(len(calls), 3)
        self.assertEqual(core.load_json(core.STATE_FILE, {}), {"versão": 2})
        self.assertFalse(Path(str(core.STATE_FILE) + ".tmp").exists())

    def test_json_replace_preserves_previous_file_when_permission_error_persists(self):
        core.save_json(core.STATE_FILE, {"versão": 1})
        with mock.patch.object(Path, "replace", side_effect=PermissionError("arquivo bloqueado")) as replace:
            with self.assertRaises(PermissionError):
                core.save_json(core.STATE_FILE, {"versão": 2})
        self.assertEqual(replace.call_count, 5 if os.name == "nt" else 1)
        self.assertEqual(core.load_json(core.STATE_FILE, {}), {"versão": 1})


if __name__ == "__main__":
    unittest.main()
