"""Sintaxe do JavaScript da interface e paridade do dicionário (precisa do Node)."""
import shutil
import subprocess
import unittest

from helpers import ROOT


@unittest.skipUnless(shutil.which("node"), "node não instalado")
class Interface(unittest.TestCase):
    def test_script_parses_and_dictionary_is_complete(self):
        run = subprocess.run(["node", str(ROOT / "tests" / "check_ui.js"), str(ROOT / "app" / "ui" / "index.html")],
                             capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)


if __name__ == "__main__":
    unittest.main()
