"""Conferência de integridade: detectar versão que não bate e avisar só nesse caso."""
import datetime as dt
import os
import shutil
import time

from helpers import DataDirCase, core


class Verify(DataDirCase):
    def setUp(self):
        super().setUp()
        self.good = [self.add_version(dt.datetime(2026, 1, d), content=b"save %d" % d) for d in (1, 2, 3)]
        self.cfg = core.validate_config({})

    def test_intact_versions(self):
        self.assertEqual(core.verify_local(), {"ok": 3, "bad": []})

    def test_flipped_byte_same_size_is_caught(self):
        (self.good[1] / "sdimg_slot").write_bytes(b"sAve 2")
        result = core.verify_local()
        self.assertEqual(result["ok"], 2)
        self.assertEqual(result["bad"], [os.path.join("1a2b3c4d", "PPSA00001", "sdimg_slot",
                                                    "20260102-000000", "sdimg_slot")])

    def test_truncated_and_missing_files_are_caught(self):
        (self.good[0] / "sdimg_slot").write_bytes(b"sav")
        (self.good[2] / "sdimg_slot").unlink()
        self.assertEqual(len(core.verify_local()["bad"]), 2)

    def test_unreadable_meta_counts_as_bad(self):
        (self.good[0] / "meta.json").write_text("{", encoding="utf-8")
        self.assertEqual(len(core.verify_local()["bad"]), 1)

    def test_version_removed_by_cleanup_during_the_check_is_not_reported(self):
        versions = list(core.iter_versions())
        shutil.rmtree(self.good[0])
        with self.subTest():
            original = core.iter_versions
            core.iter_versions = lambda: iter(versions)
            try:
                self.assertEqual(core.verify_local(), {"ok": 2, "bad": []})
            finally:
                core.iter_versions = original

    def test_scheduled_check_is_silent_when_all_is_well(self):
        core.verify_and_record(self.cfg, notify=True)
        self.sent.assert_not_called()
        meta = core.load_state()["meta"]
        self.assertEqual((meta["last_verify_ok"], meta["last_verify_bad"]), (3, []))
        self.assertAlmostEqual(meta["last_verify"], time.time(), delta=5)

    def test_scheduled_check_notifies_when_something_is_wrong(self):
        (self.good[1] / "sdimg_slot").write_bytes(b"sAve 2")
        core.verify_and_record(self.cfg, notify=True)
        self.sent.assert_called_once()
        embed = self.sent.call_args.args[0]
        self.assertIn("1 com problema", embed["title"])
        self.assertIn("20260102-000000", embed["description"])
        self.assertEqual(len(core.load_state()["meta"]["last_verify_bad"]), 1)

    def test_no_notification_from_the_button_or_with_errors_muted(self):
        (self.good[1] / "sdimg_slot").write_bytes(b"sAve 2")
        core.verify_and_record(self.cfg, notify=False)
        self.cfg["notify"]["on_error"] = False
        core.verify_and_record(self.cfg, notify=True)
        self.sent.assert_not_called()

    def test_when_it_is_due(self):
        now = time.time()
        self.assertTrue(core.verify_due(self.cfg, {}, now))
        self.assertFalse(core.verify_due(self.cfg, {"last_verify": now - 6 * 86400}, now))
        self.assertTrue(core.verify_due(self.cfg, {"last_verify": now - 7 * 86400}, now))
        self.cfg["triggers"]["verify_interval_days"] = 0
        self.assertFalse(core.verify_due(self.cfg, {}, now))
