"""Diagnóstico FTP: leitura, falhas e relatório sem dados pessoais."""
import contextlib
import ftplib
import io
import json
import sys
from unittest import mock

from helpers import DataDirCase, core
from fake_ps5 import DB_PATH, OTHER_UID, SAVE_PATH, UID, FakePS5, example_tree
from test_web import WebCase


def config(fake):
    return core.validate_config({"ps5": {"host": fake.host, "ftp_port": fake.port}})


class Diagnose(DataDirCase):
    def test_both_mlsd_modes_and_read_only_commands(self):
        for respects in (False, True):
            with self.subTest(respects=respects), FakePS5(respect_mlsd_argument=respects) as fake:
                before = dict(fake.files)
                text, code = core.diagnose(config(fake))
                self.assertEqual(code, 0, text)
                self.assertIn("respeita o argumento" if respects else "lista o diretório atual", text)
                self.assertIn("Perfis em /user/home: 2", text)
                self.assertIn("Perfis com savedata_prospero: 2", text)
                self.assertIn("Perfis com savedata: 0", text)
                self.assertIn("savedata.db lido e aberto (um perfil; opcional): OK", text)
                self.assertIn("RETR do menor save: 31 bytes", text)
                self.assertEqual(fake.files, before)
                self.assertLessEqual({cmd for cmd, _ in fake.commands}, {
                    "USER", "PASS", "CWD", "PWD", "TYPE", "PASV", "MLSD", "RETR", "FEAT", "SYST", "QUIT"})
                self.assertFalse(any("username.dat" in arg for _, arg in fake.commands))
                self.assertFalse(core.STATE_FILE.exists())
                self.assertFalse(core.TMP_DIR.exists())

    def test_profile_and_save_names_ips_and_arbitrary_server_text_are_hidden(self):
        secret = f"João Maria {UID} {OTHER_UID} sdimg_slot 192.168.20.15 2001:db8::1"
        original = ftplib.FTP.sendcmd

        def reply(ftp, command):
            value = original(ftp, command)
            return value + " " + secret if command in ("SYST", "FEAT") else value

        with FakePS5() as fake, mock.patch.object(ftplib.FTP, "getwelcome", return_value="220 ftpsrv v0.21.1 " + secret), \
                mock.patch.object(ftplib.FTP, "sendcmd", reply):
            text, code = core.diagnose(config(fake))
        self.assertEqual(code, 0, text)
        self.assertIn("ftpsrv 0.21.1", text)
        for value in secret.split():
            self.assertNotIn(value, text)

    def test_syst_feat_refusals_do_not_prevent_backup(self):
        original = ftplib.FTP.sendcmd

        def refuse(ftp, command):
            if command in ("SYST", "FEAT"):
                raise ftplib.error_perm(f"502 João {UID} {SAVE_PATH} 127.0.0.1")
            return original(ftp, command)

        with FakePS5() as fake, mock.patch.object(ftplib.FTP, "sendcmd", refuse):
            text, code = core.diagnose(config(fake))
        self.assertEqual(code, 0, text)
        self.assertIn("SYST: recusado (502", text)
        self.assertIn("FEAT: recusado (502", text)
        for private in (UID, "João", "127.0.0.1", "sdimg_slot"):
            self.assertNotIn(private, text)

    def test_temporary_syst_feat_refusals_do_not_prevent_backup(self):
        original = ftplib.FTP.sendcmd

        def refuse(ftp, command):
            if command in ("SYST", "FEAT"):
                raise ftplib.error_temp("450 private " + UID)
            return original(ftp, command)

        with FakePS5() as fake, mock.patch.object(ftplib.FTP, "sendcmd", refuse):
            text, code = core.diagnose(config(fake))
        self.assertEqual(code, 0, text)
        self.assertIn("SYST: recusado (450", text)
        self.assertIn("FEAT: recusado (450", text)
        self.assertNotIn("private", text)
        self.assertNotIn(UID, text)

    def test_mlsd_argument_refusal_keeps_cwd_backup_available(self):
        original = ftplib.FTP.mlsd

        def refuse(ftp, path="", *args, **kwargs):
            if path:
                raise ftplib.error_perm("501 argument refused " + UID)
            return original(ftp, path, *args, **kwargs)

        with FakePS5() as fake, mock.patch.object(ftplib.FTP, "mlsd", refuse):
            text, code = core.diagnose(config(fake))
        self.assertEqual(code, 0, text)
        self.assertIn("MLSD com argumento: recusado (501", text)
        self.assertNotIn(UID, text)

    def test_root_permission_does_not_prevent_home_backup(self):
        original = ftplib.FTP.cwd

        def refuse(ftp, path):
            if path == "/":
                raise ftplib.error_perm("550 private " + UID)
            return original(ftp, path)

        with FakePS5() as fake, mock.patch.object(ftplib.FTP, "cwd", refuse):
            text, code = core.diagnose(config(fake))
        self.assertEqual(code, 0, text)
        self.assertIn("inconclusivo", text)
        self.assertNotIn(UID, text)

    def test_mlsd_unavailable_fails_without_list_fallback(self):
        with FakePS5() as fake, mock.patch.object(ftplib.FTP, "mlsd", side_effect=ftplib.error_perm("502 " + UID)):
            text, code = core.diagnose(config(fake))
        self.assertEqual(code, 1)
        self.assertIn("502", text)
        self.assertTrue(text.splitlines()[-1].startswith("Faltou:"))
        self.assertNotIn(UID, text)
        self.assertNotIn("LIST", {cmd for cmd, _ in fake.commands})

    def test_missing_or_invalid_mlsd_facts_fail(self):
        original = ftplib.FTP.mlsd
        for fact, bad in (("type", None), ("size", None), ("modify", None), ("size", "wrong"), ("modify", "wrong")):
            def incomplete(ftp, *args, **kwargs):
                for name, facts in original(ftp, *args, **kwargs):
                    if bad is None:
                        facts.pop(fact, None)
                    else:
                        facts[fact] = bad
                    yield name, facts

            with self.subTest(fact=fact, bad=bad), FakePS5() as fake, mock.patch.object(ftplib.FTP, "mlsd", incomplete):
                text, code = core.diagnose(config(fake))
            self.assertEqual(code, 1, text)
            self.assertIn("Faltou:", text)

    def test_retr_failure_is_private(self):
        original = ftplib.FTP.retrbinary

        def refuse(ftp, command, callback, *args, **kwargs):
            if "savedata.db" not in command:
                raise ftplib.error_perm("550 João " + SAVE_PATH + " 127.0.0.1")
            return original(ftp, command, callback, *args, **kwargs)

        with FakePS5() as fake, mock.patch.object(ftplib.FTP, "retrbinary", refuse):
            text, code = core.diagnose(config(fake))
        self.assertEqual(code, 1)
        self.assertIn("RETR de teste: falhou (550", text)
        self.assertNotIn(UID, text)
        self.assertNotIn("João", text)
        self.assertNotIn("127.0.0.1", text)

    def test_retr_size_mismatch_fails(self):
        original = ftplib.FTP.retrbinary

        def changed(ftp, command, callback, *args, **kwargs):
            if "savedata.db" not in command:
                callback(b"changed")
                return "226 Transfer complete"
            return original(ftp, command, callback, *args, **kwargs)

        with FakePS5() as fake, mock.patch.object(ftplib.FTP, "retrbinary", changed):
            text, code = core.diagnose(config(fake))
        self.assertEqual(code, 1)
        self.assertIn("tamanho do RETR igual ao MLSD", text)

    def test_connection_failure_and_empty_host_are_private(self):
        for host in ("", "invalid.example"):
            cfg = core.validate_config({"ps5": {"host": host}})
            with mock.patch.object(ftplib.FTP, "connect", side_effect=OSError("João 127.0.0.1 " + UID)):
                text, code = core.diagnose(cfg)
            self.assertEqual(code, 1)
            self.assertIn("Faltou: conexão e login FTP", text)
            for private in (host or "invalid.example", "João", "127.0.0.1", UID):
                self.assertNotIn(private, text)

    def test_metadata_optional_and_no_saves_inconclusive(self):
        files = {SAVE_PATH: b"tiny", f"/user/home/{UID}/savedata/PPSA00002/sdimg_ps4": b"longer"}
        with FakePS5(files) as fake:
            text, code = core.diagnose(config(fake))
        self.assertEqual(code, 0, text)
        self.assertIn("Perfis com savedata: 1", text)
        self.assertIn("/user/appmeta (opcional): ausente ou sem acesso", text)
        self.assertIn("RETR do menor save: 4 bytes", text)
        with FakePS5({f"/user/home/{UID}/username.dat": "João".encode()}) as fake:
            text, code = core.diagnose(config(fake))
        self.assertEqual(code, 1)
        self.assertIn("nenhum arquivo de save encontrado", text)

    def test_invalid_database_is_optional(self):
        files = example_tree()
        files[DB_PATH] = b"invalid database"
        files.pop(f"/system_data/savedata_prospero/{OTHER_UID}/db/user/savedata.db")
        with FakePS5(files) as fake:
            text, code = core.diagnose(config(fake))
        self.assertEqual(code, 0, text)
        self.assertIn("indisponível ou ilegível", text)

    def test_cli_portuguese_exit_code_and_frozen_dispatch(self):
        cfg = core.validate_config({"notify": {"language": "en"}})
        for frozen in (False, True):
            with mock.patch.object(core, "load_config", return_value=cfg), \
                    mock.patch.object(core, "diagnose", return_value=("Diagnóstico", 1)) as diagnose, \
                    mock.patch.object(core, "setup_logging") as logging, \
                    mock.patch.object(sys, "frozen", frozen, create=True), \
                    mock.patch.object(sys, "argv", ["memcard.exe", "diag"]), contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(core.main(), 1)
            self.assertEqual(output.getvalue(), "Diagnóstico\n")
            diagnose.assert_called_once_with(cfg)
            logging.assert_not_called()


class DiagAPI(WebCase):
    password = "secret"

    def test_login_and_configured_language(self):
        with mock.patch.object(core, "diagnose") as diagnose:
            self.assertEqual(self.call("/api/diag")[0], 401)
            diagnose.assert_not_called()
        _, cookie = self.login(self.password)
        with FakePS5() as fake:
            cfg = config(fake)
            cfg["notify"]["language"] = "en"
            with mock.patch.object(core, "load_config", return_value=cfg):
                status, body, _ = self.call("/api/diag", cookie=cookie)
        self.assertEqual(status, 200)
        result = json.loads(body)
        self.assertEqual(set(result), {"text"})
        self.assertIn("Compatibility diagnostics", result["text"])
        self.assertNotIn(UID, result["text"])

    def test_failed_diag_returns_text_for_issue(self):
        _, cookie = self.login(self.password)
        with mock.patch.object(ftplib.FTP, "connect", side_effect=OSError("private")):
            status, body, _ = self.call("/api/diag", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertIn("Faltou:", json.loads(body)["text"])
        self.assertNotIn("private", json.loads(body)["text"])

    def test_explicit_api_language_overrides_config(self):
        import urllib.request

        _, cookie = self.login(self.password)
        with FakePS5() as fake:
            cfg = config(fake)
            cfg["notify"]["language"] = "en"
            for lang, heading in (("pt-BR", "Diagnóstico"), ("en", "Compatibility diagnostics")):
                with self.subTest(lang=lang), mock.patch.object(core, "load_config", return_value=cfg):
                    request = urllib.request.Request(self.base + "/api/diag", headers={"Cookie": cookie, "X-Lang": lang})
                    with urllib.request.urlopen(request, timeout=10) as response:
                        result = json.loads(response.read())
                self.assertIn(heading, result["text"])
