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


import tempfile
from unittest import mock


class _Resp:
    status_code = 204

    def raise_for_status(self):
        pass


class SendTest(unittest.TestCase):
    def _write(self, text):
        fh = tempfile.NamedTemporaryFile("w", suffix=".md", delete=False,
                                         encoding="utf-8")
        fh.write(text)
        fh.close()
        return fh.name

    def test_short_message_posts_inline_json(self):
        path = self._write("## small\nbody")
        session = mock.Mock()
        session.post.return_value = _Resp()
        dn.send_discord(path, tldr="t", link="https://c/1", username="Skycards",
                        env={"WEBHOOK_A": "https://a"}, mention="@everyone",
                        session=session)
        _, kwargs = session.post.call_args
        self.assertEqual(kwargs["json"]["content"], "@everyone\n## small\nbody")
        self.assertNotIn("files", kwargs)

    def test_long_message_posts_multipart_attachment(self):
        path = self._write("## big\n" + ("x" * 2500))
        session = mock.Mock()
        session.post.return_value = _Resp()
        dn.send_discord(path, tldr="tldr", link="https://c/1",
                        username="Skycards", env={"WEBHOOK_A": "https://a"},
                        caption="cap", session=session)
        _, kwargs = session.post.call_args
        self.assertIn("files", kwargs)
        self.assertIn("cap", kwargs["data"]["payload_json"])

    def test_empty_file_sends_nothing(self):
        path = self._write("")
        session = mock.Mock()
        dn.send_discord(path, tldr="t", link="l", username="u",
                        env={"WEBHOOK_A": "https://a"}, session=session)
        session.post.assert_not_called()
