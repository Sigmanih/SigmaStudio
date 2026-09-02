import unittest
import json
import os
from pathlib import Path
from core.ssl_manager import ensure_ssl_certificates, get_lan_ip
from core.paths import certs_dir, provider_config_file, project_root

import sigma_server
from core.ai_providers import load_ai_config, save_ai_config


class TestNetworkSSLConfig(unittest.TestCase):
    def setUp(self):
        self.original_ai_cfg = load_ai_config()

    def tearDown(self):
        save_ai_config(self.original_ai_cfg)

    def test_ssl_certificate_generation(self):
        cert_p, key_p = ensure_ssl_certificates()
        self.assertIsNotNone(cert_p)
        self.assertIsNotNone(key_p)
        self.assertTrue(cert_p.exists())
        self.assertTrue(key_p.exists())
        self.assertGreater(cert_p.stat().st_size, 100)
        self.assertGreater(key_p.stat().st_size, 100)

    def test_lan_ip_detection(self):
        lan_ip = get_lan_ip()
        self.assertIsInstance(lan_ip, str)
        self.assertTrue(len(lan_ip) >= 7)

    def test_port_host_ssl_persistence(self):
        # 1. Update config with custom port and ssl enabled
        cfg = load_ai_config()
        cfg["provider_server_port"] = 8443
        cfg["provider_server_host"] = "0.0.0.0"
        cfg["server_port"] = 8443
        cfg["server_host"] = "0.0.0.0"
        cfg["ssl_enabled"] = True
        save_ai_config(cfg)

        # 2. Verify sigma_server._get_configured_host_port_ssl reads it
        host, port, ssl_on, cert, key = sigma_server._get_configured_host_port_ssl()
        self.assertEqual(port, 8443)
        self.assertEqual(host, "0.0.0.0")
        self.assertTrue(ssl_on)


if __name__ == "__main__":
    unittest.main()
