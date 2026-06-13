import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import discord_notify as dn  # noqa: E402


class LoadRoutesTest(unittest.TestCase):
    def _env(self, config, urls):
        return {"WEBHOOKS_CONFIG": json.dumps(config),
                "WEBHOOK_URLS": json.dumps(urls)}

    def test_joins_config_and_urls(self):
        env = self._env(
            {"airports": [{"webhook": "main", "mention": "@everyone"}],
             "misc": [{"webhook": "main"}]},
            {"main": "https://a"})
        routes = dn.load_webhook_routes(env)
        self.assertEqual(routes["airports"], [("main", "https://a", "@everyone")])
        self.assertEqual(routes["misc"], [("main", "https://a", "")])

    def test_skips_unknown_type(self):
        env = self._env({"bogus": [{"webhook": "main"}]}, {"main": "https://a"})
        self.assertNotIn("bogus", dn.load_webhook_routes(env))

    def test_skips_subscription_without_url(self):
        env = self._env({"airports": [{"webhook": "ghost", "mention": "@here"}]},
                        {"main": "https://a"})
        self.assertEqual(dn.load_webhook_routes(env)["airports"], [])

    def test_empty_config_returns_empty(self):
        self.assertEqual(dn.load_webhook_routes({}), {})


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
        self.addCleanup(os.unlink, fh.name)
        return fh.name

    def test_short_message_posts_inline_per_subscriber_mention(self):
        path = self._write("## small\nbody")
        session = mock.Mock()
        session.post.return_value = _Resp()
        routes = {"airports": [("main", "https://a", "@everyone"),
                               ("staff", "https://s", "<@&1>")]}
        dn.send_discord(path, tldr="t", link="https://c/1", username="Skycards",
                        routing_key="airports", routes=routes, session=session)
        calls = session.post.call_args_list
        self.assertEqual(calls[0].args[0], "https://a")
        self.assertEqual(calls[0].kwargs["json"]["content"],
                         "@everyone\n## small\nbody")
        self.assertEqual(calls[1].args[0], "https://s")
        self.assertEqual(calls[1].kwargs["json"]["content"],
                         "<@&1>\n## small\nbody")

    def test_no_mention_subscriber_gets_bare_content(self):
        path = self._write("## small\nbody")
        session = mock.Mock()
        session.post.return_value = _Resp()
        routes = {"misc": [("main", "https://a", "")]}
        dn.send_discord(path, tldr="t", link="l", username="Skycards",
                        routing_key="misc", routes=routes, session=session)
        self.assertEqual(session.post.call_args.kwargs["json"]["content"],
                         "## small\nbody")

    def test_long_message_posts_multipart_attachment(self):
        path = self._write("## big\n" + ("x" * 2500))
        session = mock.Mock()
        session.post.return_value = _Resp()
        routes = {"airports": [("main", "https://a", "@here"),
                               ("staff", "https://s", "<@&1>")]}
        dn.send_discord(path, tldr="tldr", link="https://c/1", username="Skycards",
                        routing_key="airports", caption="cap", routes=routes,
                        session=session)
        calls = session.post.call_args_list
        self.assertEqual(len(calls), 2)
        # Each subscriber gets the attachment with its own mention prefix.
        self.assertEqual(calls[0].args[0], "https://a")
        self.assertIn("files", calls[0].kwargs)
        self.assertIn("cap", calls[0].kwargs["data"]["payload_json"])
        self.assertIn("@here", calls[0].kwargs["data"]["payload_json"])
        self.assertNotIn("\\-", calls[0].kwargs["files"]["files[0]"][1])
        self.assertEqual(calls[1].args[0], "https://s")
        self.assertIn("<@&1>", calls[1].kwargs["data"]["payload_json"])
        self.assertNotIn("\\-", calls[1].kwargs["files"]["files[0]"][1])

    def test_no_subscribers_sends_nothing(self):
        path = self._write("## small\nbody")
        session = mock.Mock()
        dn.send_discord(path, tldr="t", link="l", username="u",
                        routing_key="airlines", routes={"airports": [("m", "u", "")]},
                        session=session)
        session.post.assert_not_called()

    def test_empty_file_sends_nothing(self):
        path = self._write("")
        session = mock.Mock()
        dn.send_discord(path, tldr="t", link="l", username="u",
                        routing_key="airports",
                        routes={"airports": [("m", "https://u", "")]},
                        session=session)
        session.post.assert_not_called()
