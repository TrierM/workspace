import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'local-setup'
sys.path.insert(0, str(SOURCE))
spec = importlib.util.spec_from_file_location('doctor', SOURCE / 'doctor.py')
doctor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(doctor)


class DoctorTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name).resolve() / 'home with spaces'
        self.home.mkdir()
        self.bin = self.home / 'bin'
        self.bin.mkdir()
        script = '''#!/bin/sh
name=${0##*/}
printf '%s %s\\n' "$name" "$*" >> "$HOME/commands"
case "$name:$1" in
  git:-C) printf '0\\n';;
  docker:context)
    if [ -f "$HOME/wrong-context" ]; then printf 'desktop-linux\\n'; else printf 'podman\\n'; fi;;
  podman:machine) printf '[{"Running":true}]\\n';;
  openssl:*) [ ! -f "$HOME/expired" ];;
  kubectl:version) printf '{"clientVersion":{"gitVersion":"v1.34"}}\\n';;
  *) printf '%s version 1.2.3\\n' "$name";;
esac
'''
        for name in (*doctor.TOOLS, 'openssl', 'ais-env', 'baldur', 'odin', 'mimir', 'heimdall'):
            tool = self.bin / name
            tool.write_text(script)
            tool.chmod(0o755)
        bundle = self.home / '.codegraph/versions/v1.6.2'
        (bundle / 'bin').mkdir(parents=True)
        (bundle / 'bin/codegraph').write_text(script)
        (bundle / 'bin/codegraph').chmod(0o755)
        (bundle / 'node').write_text("#!/bin/sh\nprintf 'v24.22.2\\n'\n")
        (bundle / 'node').chmod(0o755)
        (self.bin / 'codegraph').unlink()
        (self.bin / 'codegraph').symlink_to(bundle / 'bin/codegraph')
        # The fake tools use only shell builtins; no ambient credentials or services.
        self.env = {'HOME': str(self.home), 'PATH': str(self.bin)}
        config = self.home / '.config/ais'
        config.mkdir(parents=True)
        self.workspace = self.home / 'workspace'
        shared = self.workspace / 'ais-greenshark/tools/workspace-setup/AGENTS.template.md'
        shared.parent.mkdir(parents=True)
        shared.write_text('# Shared rules\n')
        local = config / 'local-setup/AGENTS.local.md'
        local.parent.mkdir()
        local.write_text('## Personal rules\n')
        (config / 'workspace').write_text(str(self.workspace) + '\n')
        installed = self.workspace / 'AGENTS.md'
        installed.write_text('# Shared rules\n\n## Personal rules\n')
        for relative in ('.codex/AGENTS.md', '.claude/CLAUDE.md', '.copilot/copilot-instructions.md'):
            path = self.home / relative
            path.parent.mkdir()
            path.symlink_to(installed)
        self.credentials = config / 'credentials.sh'
        self.credentials.write_text('SECRET_SENTINEL_DO_NOT_PRINT')
        self.credentials.chmod(0o600)
        certificate = self.home / 'certificate.crt'
        certificate.write_text('fake certificate for fake openssl')
        (config / 'zscaler-certificate').write_text(str(certificate) + '\n')

    def test_healthy_report_and_only_expected_read_commands(self):
        checks = doctor.collect(self.home, self.env)
        self.assertTrue(all(item['status'] == 'ok' for item in checks), checks)
        self.assertNotIn('SECRET_SENTINEL', json.dumps(checks))
        commands = (self.home / 'commands').read_text().splitlines()
        expected = {name + ' ' + ' '.join(flags) for name, flags in doctor.TOOLS.items()}
        for line in commands:
            self.assertTrue(line in expected or line.startswith('git -C ') or
                            line.startswith('openssl x509 -in ') or
                            line in ('docker context show', 'podman machine list --format json'), line)

    def test_actionable_warnings_without_secret_disclosure(self):
        (self.bin / 'node').unlink()
        (self.home / 'wrong-context').touch()
        (self.home / 'expired').touch()
        self.credentials.chmod(0o644)
        (self.workspace / 'AGENTS.md').write_text('Old instructions')
        checks = {item['check']: item for item in doctor.collect(self.home, self.env)}
        for name in ('node', 'Docker context', 'certificate validity', 'credentials permissions', 'instructions'):
            self.assertEqual(checks[name]['status'], 'warning', name)
        self.assertNotIn('SECRET_SENTINEL', json.dumps(checks))

    def test_unapproved_bundled_node_warns_even_when_path_node_works(self):
        node = self.home / '.codegraph/versions/v1.6.2/node'
        node.write_text("#!/bin/sh\nprintf 'v24.16.0\\n'\n")
        checks = {item['check']: item for item in doctor.collect(self.home, self.env)}
        self.assertEqual(checks['node']['status'], 'ok')
        self.assertEqual(checks['CodeGraph bundled Node']['status'], 'warning')
        self.assertIn('24.16.0', checks['CodeGraph bundled Node']['message'])

    def test_cli_json_and_exit_status(self):
        result = subprocess.run([sys.executable, str(SOURCE / 'doctor.py'), '--json'],
                                env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsInstance(json.loads(result.stdout), list)
        (self.bin / 'node').unlink()
        result = subprocess.run([sys.executable, str(SOURCE / 'doctor.py'), '--json'],
                                env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertTrue(any(item['status'] == 'warning' for item in json.loads(result.stdout)))


if __name__ == '__main__':
    unittest.main()
