"""Busca do PS5 na rede: escolha das sub-redes, porta preferida e validação do `subnet`."""
import ipaddress
import unittest
from unittest import mock

from helpers import core


def cfg(**ps5):
    return core.validate_config({"ps5": ps5})


class Subnet(unittest.TestCase):
    def test_validation(self):
        core.validate_config({"ps5": {"subnet": "192.168.1.0/24"}})
        for bad in ("lixo", "10.0.0.0/8", "192.168.1.0/19"):
            with self.assertRaises(ValueError):
                core.validate_config({"ps5": {"subnet": bad}})

    def test_candidates_prefer_configured_host_then_local_network(self):
        with mock.patch.object(core, "local_ip", return_value="172.18.0.2"):
            nets = core.scan_candidates(cfg(host="192.168.0.77"))
        self.assertEqual([str(n) for n in nets], ["192.168.0.0/24", "172.18.0.0/24"])

    def test_explicit_subnet_wins(self):
        with mock.patch.object(core, "local_ip", return_value="172.18.0.2"):
            nets = core.scan_candidates(cfg(subnet="10.1.2.0/23"))
        self.assertEqual(nets, [ipaddress.ip_network("10.1.2.0/23")])


class Discover(unittest.TestCase):
    def run_discover(self, config, open_pairs, ps5_pairs):
        with mock.patch.object(core, "local_ip", return_value=None), \
             mock.patch.object(core, "port_open", side_effect=lambda h, p: (h, p) in open_pairs), \
             mock.patch.object(core, "is_ps5_ftp", side_effect=lambda h, p: (h, p) in ps5_pairs):
            return core.discover(config)

    def test_finds_new_ip_and_port(self):
        pair = ("192.168.1.80", 1337)
        self.assertEqual(self.run_discover(cfg(), {pair}, {pair}), pair)

    def test_ignores_open_port_that_is_not_a_ps5(self):
        pair = ("192.168.1.9", 21)  # roteador ou NAS com FTP
        self.assertIsNone(self.run_discover(cfg(), {pair}, set()))

    def test_none_when_nothing_answers(self):
        self.assertIsNone(self.run_discover(cfg(), set(), set()))


if __name__ == "__main__":
    unittest.main()
