"""Caminhos e inicialização do executável, sem precisar empacotar."""
import errno
import os
import socket
import sys
import threading
import unittest
from pathlib import Path
from unittest import mock

from helpers import DataDirCase, core

import web


class StoragePaths(unittest.TestCase):
    def test_source_keeps_docker_defaults(self):
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(sys, "frozen", False, create=True):
            self.assertEqual(core.storage_paths(), (Path("/config/config.toml"), Path("/data")))

    def test_frozen_defaults_are_next_to_executable(self):
        exe = str(Path("programas") / "Memcard" / "memcard.exe")
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(sys, "frozen", True, create=True), \
                mock.patch.object(sys, "executable", exe):
            self.assertEqual(core.storage_paths(), (Path(exe).parent / "config.toml", Path(exe).parent / "data"))

    def test_environment_overrides_each_path_independently(self):
        exe = str(Path("programas") / "memcard.exe")
        for frozen in (False, True):
            for env in ({"PS5BACKUP_CONFIG": "ajustes.toml"}, {"PS5BACKUP_DATA": "backups"},
                        {"PS5BACKUP_CONFIG": "ajustes.toml", "PS5BACKUP_DATA": "backups"}):
                with self.subTest(frozen=frozen, env=env), mock.patch.dict(os.environ, env, clear=True), \
                        mock.patch.object(sys, "frozen", frozen, create=True), mock.patch.object(sys, "executable", exe):
                    config, data = core.storage_paths()
                    self.assertEqual(config, Path(env.get("PS5BACKUP_CONFIG",
                                     Path(exe).parent / "config.toml" if frozen else "/config/config.toml")))
                    self.assertEqual(data, Path(env.get("PS5BACKUP_DATA",
                                     Path(exe).parent / "data" if frozen else "/data")))


class BindAddress(unittest.TestCase):
    def test_default_depends_on_frozen(self):
        for frozen, bind in ((False, "0.0.0.0"), (True, "127.0.0.1")):
            with self.subTest(frozen=frozen), mock.patch.dict(os.environ, {}, clear=True), \
                    mock.patch.object(sys, "frozen", frozen, create=True), mock.patch.object(web, "ThreadingHTTPServer") as factory:
                self.assertIs(web.create_server(), factory.return_value)
                kw = {"bind_and_activate": False} if frozen and os.name == "nt" else {}
                factory.assert_called_once_with((bind, web.PORT), web.Handler, **kw)

    def test_web_bind_overrides_both_defaults(self):
        for frozen in (False, True):
            with self.subTest(frozen=frozen), mock.patch.dict(os.environ, {"WEB_BIND": "192.0.2.1"}, clear=True), \
                    mock.patch.object(sys, "frozen", frozen, create=True), mock.patch.object(web, "ThreadingHTTPServer") as factory:
                web.create_server()
                kw = {"bind_and_activate": False} if frozen and os.name == "nt" else {}
                factory.assert_called_once_with(("192.0.2.1", web.PORT), web.Handler, **kw)


class Startup(DataDirCase):
    def setUp(self):
        super().setUp()
        patches = {
            "CONFIG_PATH": self.tmp / "config.toml",
            "setup_logging": mock.Mock(), "daemon": mock.Mock(), "cmd_list": mock.Mock(return_value=0),
        }
        for name, value in patches.items():
            patcher = mock.patch.object(core, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch.dict(os.environ, {"WEB_BIND": "127.0.0.1"})
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch.object(core.webbrowser, "open")
        self.browser = patcher.start()
        self.addCleanup(patcher.stop)

    def run_main(self, frozen, args):
        with mock.patch.object(sys, "frozen", frozen, create=True), mock.patch.object(sys, "argv", ["memcard", *args]):
            return core.main()

    def test_double_click_binds_before_browser_and_daemon(self):
        events = []
        create = web.create_server

        def bind():
            self.assertIs(__import__("ps5backup").STATUS, web.core.STATUS)
            server = create()
            self.addCleanup(server.server_close)
            self.server = server
            events.append("bind")
            return server

        def open_browser(url):
            with socket.create_connection(self.server.server_address, timeout=2):
                pass  # o socket já está escutando
            events.append("browser")

        self.browser.side_effect = open_browser
        core.daemon.side_effect = lambda cfg: events.append("daemon")
        with mock.patch.object(web, "PORT", 0), mock.patch.object(web, "create_server", side_effect=bind), \
                mock.patch.object(core.threading, "Thread") as thread:
            thread.return_value.start.side_effect = lambda: events.append("thread")
            self.assertEqual(self.run_main(True, []), 0)
            thread.assert_called_once_with(target=web.serve, args=(self.server,), daemon=True)
            self.browser.assert_called_once_with("http://127.0.0.1:0")
        self.assertEqual(events, ["bind", "thread", "browser", "daemon"])

    def test_occupied_port_opens_browser_and_returns_zero_without_daemon(self):
        with web.ThreadingHTTPServer(("127.0.0.1", 0), web.Handler) as occupied:
            port = occupied.server_address[1]
            with mock.patch.object(web, "PORT", port), mock.patch.object(core.threading, "Thread") as thread:
                self.assertEqual(self.run_main(True, []), 0)
                self.browser.assert_called_once_with(f"http://127.0.0.1:{port}")
                thread.assert_not_called()
        core.daemon.assert_not_called()

    def test_source_daemon_still_runs_if_web_thread_cannot_bind(self):
        failed, errors = threading.Event(), []

        def failure(args):
            errors.append(args.exc_value)
            failed.set()

        core.daemon.side_effect = lambda cfg: self.assertTrue(failed.wait(2))
        with mock.patch.object(web, "create_server", side_effect=OSError(errno.EADDRINUSE, "porta ocupada")), \
                mock.patch.object(threading, "excepthook", side_effect=failure):
            self.assertEqual(self.run_main(False, ["daemon"]), 0)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].errno, errno.EADDRINUSE)
        self.browser.assert_not_called()
        core.daemon.assert_called_once()

    def test_other_bind_errors_are_not_treated_as_another_copy(self):
        with mock.patch.object(web, "create_server", side_effect=OSError(errno.EACCES, "sem permissão")):
            with self.assertRaises(OSError):
                self.run_main(True, [])
        self.browser.assert_not_called()
        core.daemon.assert_not_called()

    def test_source_still_requires_a_subcommand(self):
        with mock.patch("sys.stderr"):
            with self.assertRaises(SystemExit) as caught:
                self.run_main(False, [])
        self.assertEqual(caught.exception.code, 2)
        core.setup_logging.assert_not_called()
        self.browser.assert_not_called()

    def test_explicit_frozen_command_does_not_start_daemon(self):
        self.assertEqual(self.run_main(True, ["list"]), 0)
        core.cmd_list.assert_called_once_with()
        core.daemon.assert_not_called()
        self.browser.assert_not_called()
