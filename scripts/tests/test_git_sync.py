import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import git_sync as gs  # noqa: E402


def _completed(returncode=0, stdout=""):
    m = mock.Mock()
    m.returncode = returncode
    m.stdout = stdout
    return m


class DetectChangesTest(unittest.TestCase):
    def test_no_changes(self):
        with mock.patch.object(gs, "_run", return_value=_completed(0)):
            self.assertEqual(gs.detect_changes("airports.json", cwd="/x"),
                             (False, False))

    def test_only_updatedat_changed(self):
        diff = ('+++ b/airports.json\n--- a/airports.json\n'
                '-  "updatedAt": 1\n+  "updatedAt": 2\n')
        calls = [_completed(1), _completed(1, diff)]
        with mock.patch.object(gs, "_run", side_effect=calls):
            self.assertEqual(gs.detect_changes("airports.json", cwd="/x"),
                             (True, True))

    def test_real_change(self):
        diff = ('+++ b/airports.json\n-  "name": "A"\n+  "name": "B"\n'
                '+  "updatedAt": 2\n')
        calls = [_completed(1), _completed(1, diff)]
        with mock.patch.object(gs, "_run", side_effect=calls):
            self.assertEqual(gs.detect_changes("airports.json", cwd="/x"),
                             (True, False))


class PushRetryTest(unittest.TestCase):
    def test_succeeds_first_try(self):
        with mock.patch.object(gs, "_run", return_value=_completed(0)) as run:
            gs.push_with_retry(cwd="/x")
        self.assertEqual(run.call_count, 1)

    def test_rebases_then_succeeds(self):
        # push fail, pull ok, push ok
        seq = [_completed(1), _completed(0), _completed(0)]
        with mock.patch.object(gs, "_run", side_effect=seq) as run:
            gs.push_with_retry(cwd="/x")
        self.assertEqual(run.call_count, 3)

    def test_raises_after_exhausting_attempts(self):
        # every push fails; pulls succeed
        def fake(args, cwd=None, check=False):
            return _completed(0 if args[0] == "pull" else 1)
        with mock.patch.object(gs, "_run", side_effect=fake):
            with self.assertRaises(RuntimeError):
                gs.push_with_retry(cwd="/x", attempts=3)


class CapturePreviousTest(unittest.TestCase):
    def test_writes_head_blob(self):
        with mock.patch.object(gs, "_run",
                               return_value=_completed(0, '{"a":1}')) as run:
            content = gs.show_file("HEAD", "airports.json", cwd="/x")
        run.assert_called_once()
        self.assertEqual(content, '{"a":1}')

    def test_missing_blob_returns_empty(self):
        with mock.patch.object(gs, "_run", return_value=_completed(128, "")):
            self.assertEqual(gs.show_file("HEAD", "missing.json", cwd="/x"), "")
