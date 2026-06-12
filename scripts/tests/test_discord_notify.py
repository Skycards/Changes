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


class PayloadTest(unittest.TestCase):
    def test_inline_payload_prefixes_mention_on_own_line(self):
        p = dn.build_inline_payload("## Heading\nbody", "Skycards", "@everyone")
        self.assertEqual(p["content"], "@everyone\n## Heading\nbody")
        self.assertEqual(p["username"], "Skycards")
        self.assertEqual(p["avatar_url"], dn.AVATAR)
        self.assertEqual(p["attachments"], [])

    def test_inline_payload_no_mention(self):
        p = dn.build_inline_payload("hi", "Skycards", "")
        self.assertEqual(p["content"], "hi")

    def test_attachment_content_uses_title_body_and_link(self):
        c = dn.build_attachment_content("## Title", "the body", "https://c/1", "")
        self.assertEqual(
            c, "## Title\nthe body\n\nSee [commit](<https://c/1>) for full changes")
