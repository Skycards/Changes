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


class RoutingKeyTest(unittest.TestCase):
    def test_source_when_not_misc(self):
        self.assertEqual(pl.routing_key("airports", is_misc=False), "airports")
        self.assertEqual(pl.routing_key("models", is_misc=False), "models")

    def test_misc_overrides_source(self):
        self.assertEqual(pl.routing_key("airports", is_misc=True), "misc")
        self.assertEqual(pl.routing_key("airlines", is_misc=True), "misc")


class FetchApiTest(unittest.TestCase):
    def test_fetches_text_with_timestamp_param(self):
        session = mock.Mock()
        session.get.return_value = mock.Mock(text='{"ok": 1}')
        text = pl.fetch_api("https://api/airports", "updatedAt", "123", session)
        session.get.assert_called_once_with(
            "https://api/airports", params={"updatedAt": "123"}, headers=pl.HEADERS)
        self.assertEqual(text, '{"ok": 1}')


class CliParseTest(unittest.TestCase):
    def test_fetch_args(self):
        ns = pl.build_parser().parse_args([
            "fetch", "--data-name", "airports", "--api-url", "https://a",
            "--output-file", "airports.json", "--compare-after"])
        self.assertEqual(ns.command, "fetch")
        self.assertEqual(ns.data_name, "airports")
        self.assertTrue(ns.compare_after)
        self.assertEqual(ns.timestamp_param, "updatedAt")
        self.assertFalse(hasattr(ns, "mention_everyone"))

    def test_fetch_timestamp_opts(self):
        ns = pl.build_parser().parse_args([
            "fetch", "--data-name", "airlines", "--api-url", "https://a",
            "--output-file", "airlines.json",
            "--timestamp-param", "timestamp",
            "--timestamp-url", "https://a/timestamp"])
        self.assertEqual(ns.timestamp_param, "timestamp")
        self.assertEqual(ns.timestamp_url, "https://a/timestamp")

    def test_compare_command(self):
        ns = pl.build_parser().parse_args(["compare"])
        self.assertEqual(ns.command, "compare")
