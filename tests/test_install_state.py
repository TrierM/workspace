import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'local-setup'))

from install_state import InstallState  # noqa: E402


def installed(data):
    return {'type': 'file', 'sha256': hashlib.sha256(data).hexdigest(), 'mode': 0o755}


class InstallStateReceiptTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.target = self.home / 'bin/tool'
        self.target.parent.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def install(self, data):
        def apply():
            self.target.write_bytes(data)
            self.target.chmod(0o755)
        with InstallState(self.home, namespace='personal') as state:
            state.workspace = str(self.home)
            state.change(self.target, installed(data), apply, [])

    def plan(self):
        with InstallState(self.home, namespace='personal') as state:
            return state.uninstall(self.home, dry_run=True)

    def test_ordinary_upgrade_keeps_original_baseline(self):
        self.install(b'v1')
        self.install(b'v2')
        self.assertEqual(self.target.read_bytes(), b'v2')
        self.assertEqual(self.plan(), [f'Would remove: {self.target}'])

    def test_hand_edit_matching_new_source_updates_receipt(self):
        self.install(b'v1')
        self.target.write_bytes(b'v2')
        self.target.chmod(0o755)
        self.install(b'v2')
        self.assertEqual(self.plan(), [f'Would remove: {self.target}'])

    def test_unrelated_hand_edit_is_still_reported(self):
        self.install(b'v1')
        self.target.write_bytes(b'edited')
        with self.assertRaisesRegex(ValueError, 'Modified since installation'):
            self.plan()

    def test_untracked_file_with_desired_content_is_not_claimed(self):
        self.target.write_bytes(b'v1')
        self.target.chmod(0o755)
        self.install(b'v1')
        with InstallState(self.home, namespace='personal') as state:
            self.assertEqual(state.entries, {})


if __name__ == '__main__':
    unittest.main()
