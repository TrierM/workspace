import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


SOURCE = Path(__file__).resolve().parents[1] / 'local-setup'
spec = importlib.util.spec_from_file_location('codegraph_update', SOURCE / 'codegraph_update.py')
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class CodeGraphUpdateTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name).resolve() / 'home with spaces'
        self.install = self.home / '.codegraph'
        self.previous = self.install / 'versions/v1.6.2'
        self.bundle(self.previous, 'v24.22.2', '1.6.2')
        self.current = self.install / 'current'
        self.current.symlink_to(self.previous)
        self.launcher = self.home / '.local/bin/codegraph'
        self.launcher.parent.mkdir(parents=True)
        self.launcher.symlink_to(self.previous / 'bin/codegraph')
        self.env = {'HOME': str(self.home), 'PATH': str(self.launcher.parent) + os.pathsep + os.defpath,
                    'NODE_OPTIONS': '--caller-startup-option'}

    def bundle(self, path, node_version, cli_version):
        (path / 'bin').mkdir(parents=True)
        for name, version in [('node', node_version), ('bin/codegraph', cli_version)]:
            tool = path / name
            tool.write_text(f"#!/bin/sh\nprintf '%s\\n' '{version}'\n")
            tool.chmod(0o755)

    def installer(self, version='v24.22.2', fail_activation=False):
        real_run = subprocess.run

        def run(command, **kwargs):
            if command[0].endswith('/curl'):
                Path(command[command.index('--output') + 1]).write_text('# fake installer\n')
                return subprocess.CompletedProcess(command, 0)
            if command[0] == '/bin/sh':
                stage_install = Path(kwargs['env']['CODEGRAPH_INSTALL_DIR'])
                candidate = stage_install / 'versions/v1.6.3'
                self.bundle(candidate, version, '1.6.3')
                (stage_install / 'current').symlink_to(candidate)
                return subprocess.CompletedProcess(command, 0)
            self.assertNotIn('NODE_OPTIONS', kwargs['env'])
            if fail_activation and command[0] == str(self.launcher):
                raise subprocess.CalledProcessError(1, command)
            return real_run(command, **kwargs)

        return mock.patch.object(guard.subprocess, 'run', side_effect=run)

    def assert_preserved(self):
        self.assertEqual(self.current.resolve(), self.previous)
        self.assertEqual(self.launcher.resolve(), self.previous / 'bin/codegraph')
        self.assertTrue(self.previous.exists())
        self.assertFalse((self.install / 'versions/v1.6.3').exists())
        self.assertFalse(list(self.install.glob('.ais-update-*')))

    def test_policy_boundaries_and_unapproved_majors(self):
        for version in ['v24.22.1', '24.22.2', 'v24.23.0', 'v26.12.1', 'v26.13.0']:
            with self.subTest(version=version):
                self.assertTrue(guard.approved_node(version))
        for version in ['v24.22.0', 'v24.16.0', 'v26.12.0', 'v26.8.2', 'v22.23.4',
                        'v25.9.0', 'v27.0.0', 'v24.22.2-rc.1', 'unknown']:
            with self.subTest(version=version):
                self.assertFalse(guard.approved_node(version))

    def test_rejected_download_preserves_patched_install_and_deletes_staging(self):
        with self.installer('v24.16.0'):
            with self.assertRaisesRegex(ValueError, 'Rejected downloaded CodeGraph'):
                guard.update(self.launcher, self.env)
        self.assert_preserved()
        self.assertEqual(guard.inspect_bundle(self.previous, self.env)[0], True)

    def test_approved_download_activates_and_removes_previous_bundle(self):
        with self.installer():
            message = guard.update(self.launcher, self.env)
        destination = self.install / 'versions/v1.6.3'
        self.assertEqual(self.current.resolve(), destination)
        self.assertEqual(self.launcher.resolve(), destination / 'bin/codegraph')
        self.assertFalse(self.previous.exists())
        self.assertIn('Installed CodeGraph v1.6.3', message)
        self.assertTrue(guard.inspect_bundle(destination, self.env)[0])

    def test_activation_failure_restores_both_links_and_removes_failed_candidate(self):
        with self.installer(fail_activation=True):
            with self.assertRaises(subprocess.CalledProcessError):
                guard.update(self.launcher, self.env)
        self.assert_preserved()

    def test_mismatched_current_install_is_preserved(self):
        self.current.unlink()
        self.current.symlink_to(self.install / 'versions/another-install')
        with mock.patch.object(guard.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'differs from the current'):
                guard.update(self.launcher, self.env)
        run.assert_not_called()
        self.assertTrue(self.previous.exists())

    def test_failed_or_timed_out_runtime_probe_is_not_approved(self):
        for result in [subprocess.CompletedProcess([], 1, stdout='v24.22.2'),
                       subprocess.TimeoutExpired('node', 5)]:
            with self.subTest(result=result):
                if isinstance(result, Exception):
                    patch = mock.patch.object(guard.subprocess, 'run', side_effect=result)
                else:
                    patch = mock.patch.object(guard.subprocess, 'run', return_value=result)
                with patch:
                    self.assertFalse(guard.inspect_bundle(self.previous, self.env)[0])


if __name__ == '__main__':
    unittest.main()
