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
