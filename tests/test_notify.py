"""Texto dos avisos da sessão no Discord."""
import time

from helpers import DataDirCase, core


class SessionEmbed(DataDirCase):
    def session(self, last_save_minutes_ago):
        now = int(time.time())
        return {"started": now - 7200, "updated": now, "entries": {"k": {
            "game": "Jogo", "profile": "Perfil", "save": "Slot 1", "count": 2, "bytes": 6 << 20,
            "last": now - last_save_minutes_ago * 60}}}

    def cfg(self, **notify):
        cfg = core.validate_config({})
        cfg["notify"].update(notify)
        return cfg

    def test_now_playing_window_is_configurable(self):
        sess = self.session(last_save_minutes_ago=20)
        self.assertIn("últimos 15 minutos", core.session_embed(self.cfg(), sess, False)["description"])
        wide = core.session_embed(self.cfg(now_playing_minutes=30), sess, False)["description"]
        self.assertIn("Agora: **Jogo** (Perfil)", wide)
        narrow = core.session_embed(self.cfg(now_playing_minutes=5), self.session(6), False)["description"]
        self.assertIn("últimos 5 minutos", narrow)

    def test_language_follows_config(self):
        sess = self.session(1)
        en = core.session_embed(self.cfg(language="en"), sess, False)
        self.assertIn("Playing now: **Jogo** (Perfil)", en["description"])
        self.assertEqual(en["fields"][0]["name"], "Backups made")
        closed = core.session_embed(self.cfg(language="en"), sess, True)
        self.assertIn("session ended", closed["title"])
        self.assertEqual(closed["fields"][0], {"name": "Duration", "value": "2 h 00 min", "inline": True})

    def test_empty_session(self):
        sess = {"started": int(time.time()), "updated": int(time.time()), "entries": {}}
        self.assertEqual(core.session_embed(self.cfg(), sess, False)["title"], "🟢  PS5 ligado")
        self.assertIn("Nenhum save mudou", core.session_embed(self.cfg(), sess, True)["description"])


class WeeklySummary(DataDirCase):
    MONDAY = __import__("datetime").date(2026, 9, 28)  # semana de 28/09 a 04/10

    def cfg(self, **notify):
        cfg = core.validate_config({})
        cfg["notify"].update(notify)
        return cfg

    def at(self, *args):
        import datetime as dt
        return dt.datetime(*args)

    def test_first_run_only_marks_the_week(self):
        meta = {}
        self.assertIsNone(core.weekly_due(meta, self.at(2026, 10, 7, 15)))
        self.assertEqual(meta["last_weekly"], "2026-10-05")

    def test_due_once_on_monday_morning(self):
        meta = {"last_weekly": "2026-09-28"}
        self.assertIsNone(core.weekly_due(meta, self.at(2026, 10, 4, 23, 59)))   # domingo à noite
        self.assertIsNone(core.weekly_due(meta, self.at(2026, 10, 5, 8, 59)))    # segunda cedo demais
        self.assertEqual(core.weekly_due(meta, self.at(2026, 10, 5, 9, 0)), self.MONDAY)
        self.assertIsNone(core.weekly_due(meta, self.at(2026, 10, 5, 9, 5)))     # já enviado
        self.assertIsNone(core.weekly_due(meta, self.at(2026, 10, 11, 20)))

    def test_service_down_on_monday_catches_up_with_the_latest_week_only(self):
        meta = {"last_weekly": "2026-09-07"}
        self.assertEqual(core.weekly_due(meta, self.at(2026, 10, 7, 12)), self.MONDAY)
        self.assertIsNone(core.weekly_due(meta, self.at(2026, 10, 7, 13)))

    def stats(self):
        return {"slots": {
            "2026-09-27": {"aaaaaaaa|PPSA00001": [1, 2, 3, 4, 5, 6, 7, 8, 9]},      # domingo anterior: fora
            "2026-09-28": {"aaaaaaaa|PPSA00001": [60, 61, 62], "bbbbbbbb|PPSA00002": [60, 61]},
            "2026-09-30": {"aaaaaaaa|PPSA00001": [100, 101], "aaaaaaaa|PPSA00002": [101, 102]},
            "2026-10-04": {"bbbbbbbb|PPSA00002": list(range(120, 132))},
            "2026-10-05": {"aaaaaaaa|PPSA00001": [1, 2, 3]},                        # segunda seguinte: fora
        }, "sizes": {"2026-09-27": 1 << 30, "2026-10-03": (1 << 30) + (50 << 20), "2026-10-06": 5 << 30}}

    STATE = {"profiles": {"aaaaaaaa": "Ana", "bbbbbbbb": ""}, "titles": {"PPSA00001": "Jogo Um"}}

    def test_numbers(self):
        embed = core.weekly_embed(self.cfg(), self.STATE, self.stats(), self.MONDAY)
        self.assertEqual(embed["title"], "📅  Resumo da semana · 28/09 a 04/10")
        lines = embed["description"].split("\n")
        self.assertEqual(lines[0], "**PPSA00002** · bbbbbbbb · 2 h 20 min")   # 14 intervalos
        self.assertEqual(lines[1], "**Jogo Um** · Ana · 50 min")               # 5 intervalos
        self.assertEqual(lines[2], "**PPSA00002** · Ana · 20 min")
        fields = {f["name"]: f["value"] for f in embed["fields"]}
        # Total sem contar duas vezes o mesmo intervalo: 3 (seg, dois perfis juntos) + 3 (qua) + 12 (dom).
        self.assertEqual(fields["Tempo de jogo"], "3 h 00 min")
        self.assertEqual(fields["Ana"], "1 h 00 min")   # 3 + 3 (o intervalo 101 conta uma vez)
        self.assertEqual(fields["bbbbbbbb"], "2 h 20 min")
        self.assertEqual(fields["Dia mais jogado"], "04/10 · 2 h 00 min")
        self.assertEqual(fields["Total guardado"], "1.05 GB (+50 MB na semana)")

    def test_english(self):
        embed = core.weekly_embed(self.cfg(language="en"), self.STATE, self.stats(), self.MONDAY)
        self.assertEqual(embed["title"], "📅  Weekly summary · Sep 28 – Oct 4")
        self.assertIn("Busiest day", [f["name"] for f in embed["fields"]])

    def test_week_without_play_sends_nothing(self):
        import datetime as dt
        self.assertIsNone(core.weekly_embed(self.cfg(), self.STATE, self.stats(), dt.date(2026, 8, 3)))

    def test_summary_is_sent_once_and_respects_the_switch(self):
        import datetime as dt
        from unittest import mock
        core.save_json(core.STATS_FILE, self.stats())
        core.save_json(core.STATE_FILE, {**self.STATE, "meta": {"last_weekly": "2026-09-28"}})

        class Clock(dt.datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 10, 5, 10, 0)

        with mock.patch.object(core.dt, "datetime", Clock), mock.patch.object(core, "webhook_url", lambda: "https://example.invalid/hook"):
            core.weekly_summary(self.cfg())
            core.weekly_summary(self.cfg())
            self.assertEqual(self.sent.call_count, 1)
            core.save_json(core.STATE_FILE, {**self.STATE, "meta": {"last_weekly": "2026-09-28"}})
            core.weekly_summary(self.cfg(weekly_summary=False))
            self.assertEqual(self.sent.call_count, 1)
            self.assertEqual(core.load_state()["meta"]["last_weekly"], "2026-10-05")
