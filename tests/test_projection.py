"""A projeção repete o ritmo do log aplicando as regras reais de retenção."""
import datetime as dt
import json
import unittest

from helpers import DataDirCase, core, stamp

import projection

NOW = dt.datetime(2026, 6, 15, 12, 0, 0)
SAVE = ("1a2b3c4d", "PPSA00001", "sdimg_slot")
SIZE = 1000
UNSEEN = 6 * 1048576  # tamanho assumido para um save que ainda não tem versão guardada


class Simulate(DataDirCase):
    def cfg(self, **retention):
        cfg = core.validate_config({})
        cfg["retention"].update(retention)
        return cfg

    def log_copies(self, whens, save=SAVE, size=SIZE):
        """Linhas no formato que o backup grava de verdade no backup.log."""
        with open(core.LOG_FILE, "a") as f:
            f.write("2026-06-01 00:00:00 INFO daemon iniciado\n")
            for when in whens:
                f.write(f"{when:%Y-%m-%d %H:%M:%S} INFO NOVA VERSÃO {save[0]}/{save[1]}/{save[2]} "
                        f"({stamp(when)}, {size} bytes, sha256 0123456789ab…)\n")

    def daily(self, days, *times):
        return [dt.datetime.combine(NOW.date() - dt.timedelta(days=d), dt.time(*t)) for d in range(days) for t in times]

    def test_no_activity_no_growth(self):
        for h in (1, 2, 3):
            self.add_version(NOW - dt.timedelta(hours=h), size=SIZE)
        out = projection.simulate(self.cfg(thin_old_versions=False), NOW)
        self.assertEqual(out["projected"], {"30": 3 * SIZE, "90": 3 * SIZE, "365": 3 * SIZE})
        self.assertEqual(out["now_bytes"], core.dir_bytes(core.SAVES_DIR))
        self.assertEqual(out["copies_per_day"], 0)
        self.assertEqual(out["curve"][0], [0, out["now_bytes"]])

    def test_without_cleanup_every_copy_adds_up(self):
        self.add_version(NOW - dt.timedelta(hours=1), size=SIZE)
        self.log_copies(self.daily(7, (20, 0)))
        out = projection.simulate(self.cfg(thin_old_versions=False, min_gap_minutes=0), NOW)
        self.assertEqual(out["window_days"], 7)
        self.assertEqual(out["copies_per_day"], 1.0)
        self.assertEqual(out["raw_bytes_per_day"], SIZE)
        self.assertEqual(out["projected"], {"30": 31 * SIZE, "90": 91 * SIZE, "365": 366 * SIZE})

    def test_min_gap_replaces_in_between_copies(self):
        # Três cópias com um minuto de diferença por dia: fica uma por dia, mais a última de todas.
        self.log_copies(self.daily(7, (20, 0), (20, 1), (20, 2)))
        every = projection.simulate(self.cfg(thin_old_versions=False, min_gap_minutes=0), NOW)
        gapped = projection.simulate(self.cfg(thin_old_versions=False, min_gap_minutes=10), NOW)
        self.assertEqual(every["projected"]["30"], 90 * UNSEEN)
        self.assertEqual(gapped["projected"]["30"], 31 * UNSEEN)

    def test_cleanup_flattens_the_curve(self):
        self.log_copies(self.daily(7, (9, 0), (14, 0), (20, 0)))
        raw = projection.simulate(self.cfg(thin_old_versions=False), NOW)["projected"]
        thin = projection.simulate(self.cfg(), NOW)
        self.assertEqual(raw["365"], 3 * 365 * UNSEEN)
        self.assertLess(thin["projected"]["365"], raw["365"] // 10)
        self.assertGreaterEqual(thin["projected"]["365"], 12 * UNSEEN)  # pelo menos uma por mês continua lá
        self.assertLess(thin["projected"]["90"] - thin["projected"]["30"], raw["90"] - raw["30"])

    def test_same_rules_as_real_prune(self):
        """O que a simulação diz que sobra de um histórico tem de ser o que o prune deixa."""
        whens = [NOW - dt.timedelta(hours=5 * i) for i in range(1, 200)]
        stamps = sorted((stamp(w) for w in whens), reverse=True)
        kept = core.versions_to_keep(stamps, [], self.cfg()["retention"], NOW)
        for when in whens:
            self.add_version(when, size=SIZE)
        out = projection.simulate(self.cfg(trash_days=0), NOW)
        # Sem cópias novas, depois de um dia a simulação tem de ter rareado para (quase) o mesmo conjunto.
        day_7 = dict(map(tuple, out["curve"]))[7]
        self.assertLessEqual(day_7, len(kept) * SIZE)
        self.assertGreaterEqual(day_7, self.cfg()["retention"]["keep_min_versions"] * SIZE)

    def test_pinned_versions_are_never_dropped(self):
        for h in range(1, 40):
            self.add_version(NOW - dt.timedelta(days=400, hours=h), size=SIZE, pinned=True)
        out = projection.simulate(self.cfg(), NOW)
        self.assertEqual(out["projected"]["365"], 39 * SIZE)

    def test_excluded_profile_and_game_stop_growing(self):
        self.add_version(NOW - dt.timedelta(hours=1), size=SIZE)
        self.log_copies(self.daily(7, (20, 0)))
        for flt in ({"exclude_profiles": [SAVE[0]]}, {"exclude_titles": [SAVE[1]]}):
            cfg = self.cfg(thin_old_versions=False)
            cfg["filter"].update(flt)
            self.assertEqual(projection.simulate(cfg, NOW)["projected"]["365"], SIZE, flt)

    def test_window_shrinks_to_days_with_log(self):
        self.log_copies(self.daily(2, (20, 0)))
        with open(core.LOG_FILE) as f:
            lines = [line for line in f if "daemon iniciado" not in line]
        core.LOG_FILE.write_text("".join(lines))
        out = projection.simulate(self.cfg(thin_old_versions=False, min_gap_minutes=0), NOW)
        self.assertEqual(out["window_days"], 2)
        self.assertEqual(out["projected"]["30"], 30 * UNSEEN)

    def test_copies_older_than_the_window_are_ignored(self):
        self.log_copies([NOW - dt.timedelta(days=d) for d in (20, 21, 22)])
        out = projection.simulate(self.cfg(thin_old_versions=False), NOW)
        self.assertEqual(out["copies_per_day"], 0)
        self.assertEqual(out["projected"]["365"], 0)

    def test_output_is_json_and_has_the_marks_the_chart_needs(self):
        self.log_copies(self.daily(7, (20, 0)))
        out = projection.simulate(self.cfg(), NOW)
        json.dumps(out)
        days = [d for d, _ in out["curve"]]
        self.assertEqual(days, sorted(days))
        for mark in (0, 30, 90, 365):
            self.assertIn(mark, days)


if __name__ == "__main__":
    unittest.main()
