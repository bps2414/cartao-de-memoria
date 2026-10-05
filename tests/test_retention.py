"""Regras que decidem quais versões ficam. Um erro aqui apaga saves guardados."""
import datetime as dt
import os
import time
import unittest

from helpers import RULES, DataDirCase, ago, core, stamp

NOW = dt.datetime(2026, 6, 15, 12, 0, 0)


def keep(whens, pinned=(), now=NOW, **overrides):
    stamps = sorted((w if isinstance(w, str) else stamp(w) for w in whens), reverse=True)
    return core.versions_to_keep(stamps, [stamp(p) for p in pinned], {**RULES, **overrides}, now)


class VersionsToKeep(unittest.TestCase):
    def test_newest_versions_always_stay(self):
        # Três cópias no mesmo mês, anos atrás: sem a regra, sobraria só uma.
        old = [dt.datetime(2020, 1, d) for d in (1, 2, 3)]
        self.assertEqual(keep(old), {stamp(w) for w in old})
        self.assertEqual(keep(old, keep_min_versions=1), {stamp(old[-1])})

    def test_keep_min_versions_zero_still_keeps_one(self):
        old = [dt.datetime(2020, 1, d) for d in (1, 2, 3)]
        self.assertEqual(keep(old, keep_min_versions=0), {stamp(old[-1])})

    def test_everything_inside_keep_all_hours_stays(self):
        recent = [ago(NOW, minutes=m) for m in range(0, 60, 5)]
        self.assertEqual(keep(recent, keep_min_versions=1), {stamp(w) for w in recent})

    def test_pinned_version_stays(self):
        whens = [dt.datetime(2020, 1, 1, h) for h in range(6)]
        kept = keep(whens, pinned=[whens[0]], keep_min_versions=1)
        self.assertEqual(kept, {stamp(whens[0]), stamp(whens[-1])})

    def test_hourly_bucket_keeps_last_of_each_hour(self):
        base = ago(NOW, hours=5).replace(minute=0)
        whens = [base + dt.timedelta(minutes=m) for m in (5, 25, 45, 65, 85)]  # duas horas diferentes
        kept = keep(whens, keep_min_versions=1)
        self.assertEqual(kept, {stamp(whens[2]), stamp(whens[4])})

    def test_daily_bucket_keeps_last_of_each_day(self):
        day = (NOW - dt.timedelta(days=5)).replace(hour=0)
        whens = [day + dt.timedelta(hours=h) for h in (-10, 9, 14, 20)]  # a primeira é do dia anterior
        self.assertEqual(keep(whens, keep_min_versions=1), {stamp(whens[0]), stamp(whens[-1])})

    def test_weekly_bucket_keeps_last_of_each_week(self):
        monday = dt.datetime(2026, 5, 4, 10)  # ~6 semanas antes de NOW; segunda-feira
        whens = [monday + dt.timedelta(days=d) for d in (0, 2, 6, 7)]  # 3 na mesma semana ISO, 1 na seguinte
        self.assertEqual(keep(whens, keep_min_versions=1), {stamp(whens[2]), stamp(whens[3])})

    def test_monthly_bucket_is_forever(self):
        whens = [dt.datetime(2019, 3, d) for d in (1, 15, 28)] + [dt.datetime(2019, 4, 2)]
        self.assertEqual(keep(whens, keep_min_versions=1), {stamp(whens[2]), stamp(whens[3])})

    def test_unparseable_names_are_never_dropped(self):
        whens = ["copia-manual", "20200101-000000", "20200102-000000"]
        self.assertIn("copia-manual", keep(whens, keep_min_versions=1))

    def test_no_period_with_copies_is_left_empty(self):
        # Uma cópia a cada 7 horas por dois anos: todo mês que tinha cópia continua com uma.
        whens = [NOW - dt.timedelta(hours=7 * i) for i in range(2500)]
        kept = keep(whens)
        self.assertLess(len(kept), len(whens) // 10)
        self.assertEqual({stamp(w)[:6] for w in whens}, {s[:6] for s in kept})
        self.assertIn(stamp(whens[0]), kept)

    def test_result_is_subset_and_never_empty(self):
        whens = [NOW - dt.timedelta(days=40 * i) for i in range(30)]
        kept = keep(whens)
        self.assertTrue(kept)
        self.assertLessEqual(kept, {stamp(w) for w in whens})


class SupersededVersion(unittest.TestCase):
    def stamps(self, *minutes):
        return [stamp(NOW + dt.timedelta(minutes=m)) for m in minutes]

    def test_needs_three_versions(self):
        self.assertIsNone(core.superseded_version(self.stamps(0, 1), 10))
        self.assertIsNone(core.superseded_version([], 10))

    def test_zero_gap_disables(self):
        self.assertIsNone(core.superseded_version(self.stamps(0, 1, 2), 0))

    def test_middle_copy_is_replaced_when_close_to_the_one_before(self):
        stamps = self.stamps(0, 4, 5)
        self.assertEqual(core.superseded_version(stamps, 10), stamps[1])

    def test_middle_copy_stays_when_gap_was_respected(self):
        self.assertIsNone(core.superseded_version(self.stamps(0, 10, 11), 10))
        self.assertIsNone(core.superseded_version(self.stamps(0, 30, 31), 10))

    def test_newest_and_oldest_are_never_the_answer(self):
        stamps = self.stamps(0, 1, 2, 3)
        self.assertEqual(core.superseded_version(stamps, 10), stamps[2])

    def test_unparseable_names_are_left_alone(self):
        self.assertIsNone(core.superseded_version(["a", "b", "c"], 10))

    def test_a_play_session_keeps_one_version_per_gap_plus_the_latest(self):
        # Um save por minuto durante uma hora, aplicando a regra a cada cópia como o backup faz.
        kept = []
        for minute in range(60):
            kept.append(stamp(NOW + dt.timedelta(minutes=minute)))
            old = core.superseded_version(kept, 10)
            if old:
                kept.remove(old)
        self.assertEqual(kept, self.stamps(0, 10, 20, 30, 40, 50, 59))


class Prune(DataDirCase):
    def cfg(self, **overrides):
        cfg = core.validate_config({})
        cfg["retention"].update(overrides)
        return cfg

    def test_recent_extras_are_deleted_and_old_extras_go_to_trash(self):
        now = dt.datetime.now()
        hour = ago(now, hours=6).replace(minute=0, second=0, microsecond=0)
        recent = [hour + dt.timedelta(minutes=m) for m in (5, 30, 55)]          # mesma hora, < 2 dias
        day = ago(now, days=6).replace(hour=0, minute=0, second=0, microsecond=0)
        old = [day + dt.timedelta(hours=h) for h in (8, 12, 20)]                # mesmo dia, > 2 dias
        newest = [ago(now, minutes=m) for m in (1, 2, 3)]
        for when in recent + old + newest:
            self.add_version(when)

        removed = core.prune(self.cfg())

        self.assertEqual(removed, 4)
        self.assertEqual(self.stored(), sorted(stamp(w) for w in [old[2], recent[2]] + newest))
        # Regra da lixeira: só o que tem mais de keep_hourly_days passa por ela.
        self.assertEqual(self.stored(root=core.TRASH_DIR), sorted(stamp(w) for w in old[:2]))
        trashed = core.TRASH_DIR / "1a2b3c4d" / "PPSA00001" / "sdimg_slot" / stamp(old[0])
        self.assertTrue((trashed / "sdimg_slot").exists() and (trashed / "meta.json").exists())

    def test_pinned_version_survives(self):
        now = dt.datetime.now()
        day = ago(now, days=30).replace(hour=0, minute=0, second=0, microsecond=0)
        whens = [day + dt.timedelta(hours=h) for h in (1, 2, 3)]
        self.add_version(whens[0], pinned=True)
        self.add_version(whens[1])
        self.add_version(whens[2])
        for m in (1, 2, 3):
            self.add_version(ago(now, minutes=m))
        core.prune(self.cfg())
        self.assertIn(stamp(whens[0]), self.stored())
        self.assertNotIn(stamp(whens[1]), self.stored())
        self.assertIn(stamp(whens[2]), self.stored())
        self.assertEqual(self.stored(root=core.TRASH_DIR), [stamp(whens[1])])

    def test_keep_min_versions_protects_a_save_no_longer_played(self):
        whens = [dt.datetime(2021, 5, 1, h) for h in range(5)]
        for when in whens:
            self.add_version(when)
        core.prune(self.cfg())
        self.assertEqual(self.stored(), [stamp(w) for w in whens[-3:]])

    def test_each_save_is_judged_on_its_own(self):
        other = ("1a2b3c4d", "PPSA00002", "sdimg_other")
        for h in range(5):
            self.add_version(dt.datetime(2021, 5, 1, h))
        self.add_version(dt.datetime(2021, 5, 1, 0), save=other)
        core.prune(self.cfg())
        self.assertEqual(len(self.stored()), 3)
        self.assertEqual(len(self.stored(save=other)), 1)

    def test_thinning_off_keeps_everything(self):
        whens = [dt.datetime(2021, 5, 1, h) for h in range(8)]
        for when in whens:
            self.add_version(when)
        self.assertEqual(core.prune(self.cfg(thin_old_versions=False)), 0)
        self.assertEqual(len(self.stored()), 8)
        self.assertFalse(core.TRASH_DIR.exists())

    def test_folders_that_are_not_versions_are_ignored(self):
        for h in range(5):
            self.add_version(dt.datetime(2021, 5, 1, h))
        stray = core.SAVES_DIR / "1a2b3c4d" / "PPSA00001" / "sdimg_slot" / "anotacoes"
        stray.mkdir()
        (stray / "leia.txt").write_text("não é uma versão", encoding="utf-8")
        odd = self.add_version("copia-manual")
        core.prune(self.cfg())
        self.assertTrue((stray / "leia.txt").exists())
        self.assertTrue(odd.exists())

    def test_trash_is_emptied_only_after_trash_days(self):
        expired = self.add_version(dt.datetime(2021, 1, 1), root=core.TRASH_DIR)
        fresh = self.add_version(dt.datetime(2021, 1, 2), root=core.TRASH_DIR)
        long_ago = time.time() - 8 * 86400
        os.utime(expired, (long_ago, long_ago))
        core.prune(self.cfg(trash_days=7))
        self.assertFalse(expired.exists())
        self.assertTrue(fresh.exists())

    def test_trash_entry_date_is_when_it_was_trashed_not_when_it_was_copied(self):
        whens = [dt.datetime(2021, 5, 1, h) for h in range(5)]
        for when in whens:
            vdir = self.add_version(when)
            os.utime(vdir, (0, 0))  # pasta com data antiga, como uma versão de anos atrás
        core.prune(self.cfg())
        self.assertEqual(len(self.stored(root=core.TRASH_DIR)), 2)  # não foram apagadas na mesma rodada
        core.prune(self.cfg())
        self.assertEqual(len(self.stored(root=core.TRASH_DIR)), 2)

    def test_running_twice_changes_nothing_more(self):
        now = dt.datetime.now()
        for i in range(60):
            self.add_version(ago(now, hours=5 * i))
        core.prune(self.cfg())
        after_first = self.stored()
        self.assertEqual(core.prune(self.cfg()), 0)
        self.assertEqual(self.stored(), after_first)


if __name__ == "__main__":
    unittest.main()
