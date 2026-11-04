import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'local-setup'


class AWSSessionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name).resolve() / 'home with spaces'
        config = self.home / '.config/ais'
        config.mkdir(parents=True)
        shutil.copy2(SOURCE / 'aws-session.py', config / 'aws-session.py')
        # Even credentials reintroduced by the environment loader must be isolated.
        (config / 'shell-env.sh').write_text('export AWS_ACCESS_KEY_ID=STALE_ACCESS\nexport AWS_SECRET_ACCESS_KEY=STALE_SECRET\n')
        self.bin = self.home / '.local/bin'
        self.bin.mkdir(parents=True)
        shutil.copy2(SOURCE / 'aws-session', self.bin / 'aws-session')
        (self.bin / 'aws-session').chmod(0o755)
        for profile in ('dev', 'staging', 'prod'):
            (self.bin / f'aws-{profile}').symlink_to('aws-session')
        aws = self.bin / 'aws'
        aws.write_text(f'#!{sys.executable}\n' + '''import json, os, sys
from pathlib import Path
args = sys.argv[1:]
profile = args[args.index('--profile') + 1]
with (Path.home() / 'aws-calls').open('a') as stream:
    stream.write(json.dumps({'args': args, 'access': os.environ.get('AWS_ACCESS_KEY_ID'),
                             'secret': os.environ.get('AWS_SECRET_ACCESS_KEY'),
                             'role': os.environ.get('AWS_ROLE_ARN')}) + '\\n')
if args[:2] == ['sts', 'get-caller-identity']:
    sys.exit(1 if os.environ.get('NEEDS_LOGIN') else 0)
if args[:2] == ['sso', 'login']:
    sys.exit(1 if os.environ.get('LOGIN_FAIL') else 0)
if args[:2] == ['configure', 'export-credentials']:
    if os.environ.get('EXPORT_FAIL'):
        print('SENSITIVE_AWS_ERROR', file=sys.stderr)
        sys.exit(1)
    print(json.dumps({'AccessKeyId': profile + '_ACCESS', 'SecretAccessKey': profile + '_SECRET',
                      'SessionToken': profile + '_TOKEN'}))
    sys.exit(0)
sys.exit(99)
''')
        aws.chmod(0o755)
        shared = self.home / '.aws/credentials'
        shared.parent.mkdir()
        shared.write_text('[default]\naws_access_key_id=ORIGINAL\n')
        self.shared = shared
        self.env = dict(os.environ, HOME=str(self.home), PATH=str(self.bin) + os.pathsep + os.defpath,
                        AWS_SESSION_TOKEN='STALE_TOKEN', AWS_ROLE_ARN='STALE_ROLE',
                        AWS_DEFAULT_PROFILE='wrong', AWS_CONTAINER_CREDENTIALS_FULL_URI='http://invalid')
        self.probe = self.home / 'probe.py'
        self.probe.write_text('''import configparser, json, os, pathlib, sys, time
value = {name: os.environ.get(name) for name in ('AWS_PROFILE', 'AWS_DEFAULT_PROFILE',
         'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN', 'AWS_ROLE_ARN',
         'AWS_CONTAINER_CREDENTIALS_FULL_URI')}
path = os.environ.get('AWS_SHARED_CREDENTIALS_FILE')
if path:
    p = pathlib.Path(path)
    c = configparser.RawConfigParser(); c.read(path)
    value['legacy'] = {'path': path, 'mode': p.stat().st_mode & 0o777,
                       'dir_mode': p.parent.stat().st_mode & 0o777,
                       'access': c['default']['aws_access_key_id']}
value['args'] = sys.argv[1:]
time.sleep(0.1)
print(json.dumps(value))
''')

    def run_helper(self, profile='dev', extra=(), **env):
        return subprocess.run([str(self.bin / f'aws-{profile}'), *extra],
                              env=dict(self.env, **env), capture_output=True, text=True)

    def assert_calls_are_safe(self):
        calls = [json.loads(line) for line in (self.home / 'aws-calls').read_text().splitlines()]
        for call in calls:
            self.assertIsNone(call['access'])
            self.assertIsNone(call['secret'])
            self.assertIsNone(call['role'])
            self.assertNotIn('configure set', ' '.join(call['args']))
            self.assertFalse(any('_ACCESS' in arg or '_SECRET' in arg or '_TOKEN' in arg
                                 for arg in call['args']))
        self.assertEqual(self.shared.read_text(), '[default]\naws_access_key_id=ORIGINAL\n')
        return calls

    def test_process_credentials_and_arguments_are_isolated(self):
        result = self.run_helper(extra=(sys.executable, str(self.probe), '--flag', 'argument with spaces'))
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data['AWS_PROFILE'], 'dev')
        self.assertEqual(data['AWS_DEFAULT_PROFILE'], 'dev')
        self.assertEqual(data['AWS_ACCESS_KEY_ID'], 'dev_ACCESS')
        self.assertEqual(data['AWS_SECRET_ACCESS_KEY'], 'dev_SECRET')
        self.assertEqual(data['AWS_SESSION_TOKEN'], 'dev_TOKEN')
        self.assertIsNone(data['AWS_ROLE_ARN'])
        self.assertIsNone(data['AWS_CONTAINER_CREDENTIALS_FULL_URI'])
        self.assertEqual(data['args'], ['--flag', 'argument with spaces'])
        self.assert_calls_are_safe()

    def test_parallel_legacy_commands_have_separate_private_files(self):
        children = [subprocess.Popen([str(self.bin / f'aws-{profile}'), '--legacy-default',
                                     sys.executable, str(self.probe)], env=self.env,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    for profile in ('dev', 'prod')]
        paths = []
        for profile, child in zip(('dev', 'prod'), children):
            stdout, stderr = child.communicate(timeout=15)
            self.assertEqual(child.returncode, 0, stderr)
            data = json.loads(stdout)
            legacy = data['legacy']
            self.assertEqual(legacy['access'], profile + '_ACCESS')
            self.assertEqual(legacy['mode'], 0o600)
            self.assertEqual(legacy['dir_mode'], 0o700)
            self.assertFalse(Path(legacy['path']).exists())
            paths.append(legacy['path'])
        self.assertNotEqual(*paths)
        self.assert_calls_are_safe()

    def test_parallel_normal_commands_keep_their_selected_profile(self):
        children = [subprocess.Popen([str(self.bin / f'aws-{profile}'),
                                     sys.executable, str(self.probe)], env=self.env,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    for profile in ('dev', 'prod')]
        for profile, child in zip(('dev', 'prod'), children):
            stdout, stderr = child.communicate(timeout=15)
            self.assertEqual(child.returncode, 0, stderr)
            data = json.loads(stdout)
            self.assertEqual(data['AWS_PROFILE'], profile)
            self.assertEqual(data['AWS_ACCESS_KEY_ID'], profile + '_ACCESS')
            self.assertNotIn('legacy', data)
        self.assert_calls_are_safe()

    def test_failure_never_starts_command_or_leaks_captured_error(self):
        result = self.run_helper(extra=(sys.executable, str(self.probe)), EXPORT_FAIL='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')
        self.assertNotIn('SENSITIVE_AWS_ERROR', result.stderr)
        self.assert_calls_are_safe()

    def test_login_only_when_needed_and_preserve_exit_status(self):
        result = self.run_helper(extra=('/bin/sh', '-c', 'exit 17'), NEEDS_LOGIN='1')
        self.assertEqual(result.returncode, 17, result.stderr)
        self.assertTrue(any(call['args'][:2] == ['sso', 'login'] for call in self.assert_calls_are_safe()))

    def test_legacy_failure_cleans_up_and_preserves_status(self):
        code = 'import os,pathlib; pathlib.Path(os.environ["HOME"],"legacy-path").write_text(os.environ["AWS_SHARED_CREDENTIALS_FILE"]); raise SystemExit(23)'
        result = self.run_helper(extra=('--legacy-default', sys.executable, '-c', code))
        self.assertEqual(result.returncode, 23, result.stderr)
        self.assertFalse(Path((self.home / 'legacy-path').read_text()).exists())

    def test_interactive_selection_clears_parent_overrides(self):
        script = f'. "{SOURCE / "zsh-helpers.zsh"}"; aws-dev; test "$AWS_PROFILE" = dev && test "$AWS_DEFAULT_PROFILE" = dev && test -z "${{AWS_ACCESS_KEY_ID+x}}" && test -z "${{AWS_SESSION_TOKEN+x}}" && test -z "${{AWS_ROLE_ARN+x}}"'
        result = subprocess.run(['/bin/zsh', '-f', '-c', script], env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_calls_are_safe()


if __name__ == '__main__':
    unittest.main()
