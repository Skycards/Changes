import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import pipeline as pl  # noqa: E402

import shutil


class FormatJsonTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which("jq"), "jq not installed")
    def test_formats_via_jq_with_trailing_newline(self):
        path = os.path.join(tempfile.mkdtemp(), "out.json")
        pl.format_json('{"b":1,"a":[1,2]}', path)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        self.assertTrue(text.endswith("\n"))
        self.assertEqual(json.loads(text), {"b": 1, "a": [1, 2]})
        self.assertIn('  "a": [\n    1,\n    2\n  ]', text)


class TimestampTest(unittest.TestCase):
    def test_uses_millis_when_no_url(self):
        with mock.patch.object(pl.time, "time", return_value=2.0):
            self.assertEqual(pl.determine_timestamp(None, None), "2000")

    def test_fetches_and_validates_url(self):
        session = mock.Mock()
        session.get.return_value = mock.Mock(text="1700000000\n")
        self.assertEqual(
            pl.determine_timestamp("https://ts", session), "1700000000")

    def test_rejects_non_numeric(self):
        session = mock.Mock()
        session.get.return_value = mock.Mock(text="oops")
        with self.assertRaises(ValueError):
            pl.determine_timestamp("https://ts", session)


class MentionTest(unittest.TestCase):
    def test_everyone_when_enabled_and_not_misc(self):
        self.assertEqual(pl.resolve_mention(True, is_misc=False), "@everyone")

    def test_empty_when_misc(self):
        self.assertEqual(pl.resolve_mention(True, is_misc=True), "")

    def test_empty_when_disabled(self):
        self.assertEqual(pl.resolve_mention(False, is_misc=False), "")


class FetchApiTest(unittest.TestCase):
    def test_fetches_text_with_timestamp_param(self):
        session = mock.Mock()
        session.get.return_value = mock.Mock(text='{"ok": 1}')
        text = pl.fetch_api("https://api/airports", "updatedAt", "123", session)
        session.get.assert_called_once_with(
            "https://api/airports", params={"updatedAt": "123"}, headers=pl.HEADERS)
        self.assertEqual(text, '{"ok": 1}')
