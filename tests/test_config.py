"""Validação do config.toml e os três lugares em que cada chave precisa existir."""
import re
import tomllib
import unittest

from helpers import ROOT, core

from i18n import LANGS, TEXT


class ValidateConfig(unittest.TestCase):
    def test_empty_config_gives_defaults(self):
        self.assertEqual(core.validate_config({}), core.DEFAULTS)

    def test_result_does_not_alias_defaults_sections(self):
        cfg = core.validate_config({})
        cfg["retention"]["trash_days"] = 999
        self.assertNotEqual(core.DEFAULTS["retention"]["trash_days"], 999)

    def test_partial_config_is_merged(self):
        cfg = core.validate_config({"retention": {"keep_daily_days": 30}})
        self.assertEqual(cfg["retention"]["keep_daily_days"], 30)
        self.assertEqual(cfg["retention"]["trash_days"], core.DEFAULTS["retention"]["trash_days"])

    def assert_rejected(self, user):
        with self.assertRaises(ValueError):
            core.validate_config(user)

    def test_unknown_key_is_rejected(self):
        self.assert_rejected({"retention": {"keep_dayly_days": 30}})

    def test_unknown_section_is_ignored(self):
        self.assertEqual(core.validate_config({"extra": {"a": 1}}), core.DEFAULTS)

    def test_section_must_be_a_table(self):
        self.assert_rejected({"retention": 5})

    def test_wrong_types_are_rejected(self):
        self.assert_rejected({"retention": {"keep_daily_days": "14"}})
        self.assert_rejected({"retention": {"keep_daily_days": 1.5}})
        self.assert_rejected({"retention": {"keep_daily_days": True}})   # bool não passa por int
        self.assert_rejected({"retention": {"thin_old_versions": 1}})    # nem int por bool
        self.assert_rejected({"filter": {"exclude_titles": "PPSA00001"}})
        self.assert_rejected({"filter": {"exclude_titles": ["PPSA00001", 5]}})

    def test_negative_numbers_and_minimums(self):
        self.assert_rejected({"retention": {"trash_days": -1}})
        self.assert_rejected({"retention": {"keep_min_versions": 0}})
        self.assert_rejected({"triggers": {"watch_interval_seconds": 9}})
        self.assert_rejected({"ps5": {"ftp_port": 0}})
        core.validate_config({"retention": {"trash_days": 0, "keep_min_versions": 1}})

    def test_enumerations(self):
        self.assert_rejected({"filter": {"new_profiles": "maybe"}})
        self.assert_rejected({"notify": {"language": "fr"}})
        for lang in LANGS:
            core.validate_config({"notify": {"language": lang}})

    def test_daily_times(self):
        core.validate_config({"triggers": {"schedule_daily_at": ["04:00", "23:59"]}})
        for bad in ("4:00", "24:00", "12:60", "noon"):
            self.assert_rejected({"triggers": {"schedule_daily_at": [bad]}})

    def test_error_text_is_available_in_every_language(self):
        with self.assertRaises(core.Msg) as caught:
            core.validate_config({"retention": {"trash_days": -1}})
        self.assertIn("trash_days", caught.exception.text("en"))
        self.assertNotEqual(caught.exception.text("en"), caught.exception.text("pt-BR"))


class KeysEverywhere(unittest.TestCase):
    """A interface regrava o config.toml e o daemon rejeita chave desconhecida: uma
    chave nova tem de estar em DEFAULTS, no config.example.toml e no formulário."""

    def test_example_config_is_valid_and_complete(self):
        with open(ROOT / "config.example.toml", "rb") as f:
            example = tomllib.load(f)
        core.validate_config(example)
        for section, defaults in core.DEFAULTS.items():
            self.assertEqual(set(example.get(section, {})), set(defaults), f"[{section}] no config.example.toml")

    def test_every_key_has_a_field_in_settings(self):
        html = (ROOT / "app" / "ui" / "index.html").read_text()
        on_cards = {"filter.include_profiles", "filter.exclude_profiles",  # interruptor de cada cartão
                    "filter.include_titles", "filter.exclude_titles"}      # interruptor de cada jogo
        for section, defaults in core.DEFAULTS.items():
            for key in defaults:
                path = f"{section}.{key}"
                if path not in on_cards:
                    self.assertRegex(html, rf'\b(num|tog|txt|pick)\("{re.escape(path)}"', f"{path} sem campo em Ajustes")

    def test_saved_config_round_trips(self):
        import tempfile
        from pathlib import Path
        from unittest import mock
        cfg = core.validate_config({"filter": {"exclude_titles": ["PPSA01650"], "include_profiles": ["João \"J\""]},
                                    "triggers": {"schedule_daily_at": ["04:00"]}})
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(core, "CONFIG_PATH", Path(tmp) / "config.toml"):
            core.save_config(cfg)
            self.assertEqual(core.load_config(), cfg)


class Changelog(unittest.TestCase):
    def test_top_release_matches_version_in_every_language(self):
        for name in ("CHANGELOG.md", "CHANGELOG.en.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertEqual(re.search(r"^## \[(\d+\.\d+\.\d+)\]", text, re.M).group(1), core.VERSION, name)


class Dictionary(unittest.TestCase):
    def test_languages_have_the_same_keys_and_placeholders(self):
        base = TEXT["pt-BR"]
        for lang in LANGS:
            self.assertEqual(set(TEXT[lang]), set(base), lang)
            for key, text in TEXT[lang].items():
                if key == "date_short":  # formato de data: cada idioma usa as partes que quiser
                    continue
                self.assertEqual(set(re.findall(r"\{(\w+)\}", text)), set(re.findall(r"\{(\w+)\}", base[key])), key)


if __name__ == "__main__":
    unittest.main()
