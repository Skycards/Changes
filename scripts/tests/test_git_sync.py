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
