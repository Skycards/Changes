import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import discord_notify as dn  # noqa: E402


class WebhookUrlsTest(unittest.TestCase):
    def test_collects_only_webhook_prefixed_nonempty(self):
        env = {"WEBHOOK_A": "https://a", "WEBHOOK_B": "", "OTHER": "https://x",
               "WEBHOOK_C": "https://c"}
        self.assertEqual(dn.webhook_urls(env), ["https://a", "https://c"])


class StripArtifactsTest(unittest.TestCase):
    def test_unescapes_leading_dash_and_angle_links(self):
        src = "  \\- item\ntext [x](<https://u>) more"
        out = dn._strip_discord_artifacts(src)
        self.assertEqual(out, "  - item\ntext [x](https://u) more")
