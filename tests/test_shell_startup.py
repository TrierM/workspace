import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'local-setup'


class ShellStartupTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.home = self.root / 'home with spaces'
        self.home.mkdir()
        self.workspace = self.root / 'workspace'
        shared = self.workspace / 'ais-greenshark/tools/workspace-setup/AGENTS.template.md'
        shared.parent.mkdir(parents=True)
        shared.write_text('# Team rules\n')
        self.env = {'HOME': str(self.home), 'PATH': '/usr/bin:/bin:/usr/bin', 'TERM': 'dumb'}
        self.command = [sys.executable, str(SOURCE / 'install.py'), str(self.workspace)]

    def install(self, *args):
        result = subprocess.run(self.command + list(args), env=self.env,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def shell(self, program, flags, command):
        result = subprocess.run([program, flags, command], env=self.env,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def test_legacy_migration_is_repeatable_and_reversible(self):
        env_line = '[ ! -r "$HOME/.config/ais/shell-env.sh" ] || . "$HOME/.config/ais/shell-env.sh"\n'
        profile_line = '[ ! -r "$HOME/.profile" ] || . "$HOME/.profile"\n'
        bashrc_line = '[ ! -r "$HOME/.bashrc" ] || . "$HOME/.bashrc"\n'
        originals = {
            '.zshenv': '# Keep my comment\ntypeset -U path PATH\n' + env_line,
            '.zshrc': 'export UNRELATED_SETTING=keep\n'
                      'export NVM_DIR="$HOME/.nvm"\n'
                      '[ -s "$NVM_DIR/nvm.sh" ] && \\. "$NVM_DIR/nvm.sh"\n'
                      '[ -s "$NVM_DIR/bash_completion" ] && \\. "$NVM_DIR/bash_completion"\n'
                      "alias ll='ls -alFG'\nalias la='ls -AG'\nalias l='ls -CFG'\n"
                      "alias devops='/Users/trierm/Desktop/iip-devops-tool-darwin'\n"
                      '# AIS_HELPERS_START\n'
                      '[ ! -r "$HOME/.config/ais/zsh-helpers.zsh" ] || . "$HOME/.config/ais/zsh-helpers.zsh"\n'
                      '# AIS_HELPERS_END\n',
            '.profile': 'if [ -x /opt/homebrew/bin/brew ]; then\n'
                        '    eval "$(/opt/homebrew/bin/brew shellenv)"\nfi\n' + env_line,
            '.zprofile': profile_line,
            '.bash_profile': profile_line + bashrc_line,
            '.bashrc': env_line,
        }
        for name, content in originals.items():
            (self.home / name).write_text(content)
        self.install()
        after = {name: (self.home / name).read_text() for name in originals}
        self.assertIn('UNRELATED_SETTING=keep', after['.zshrc'])
        self.assertNotIn('devops', after['.zshrc'])
        self.assertNotIn('NVM_DIR', after['.zshrc'])
        self.assertNotIn('typeset', after['.zshenv'])
        for content in after.values():
            self.assertEqual(content.count('_START'), 1)
        self.install()
        self.assertEqual(after, {name: (self.home / name).read_text() for name in originals})
        self.install('--uninstall')
        for name, content in originals.items():
            self.assertEqual((self.home / name).read_text(), content)
        self.assertFalse((self.home / '.config/ais/zsh-interactive.zsh').exists())

    def test_shell_modes_are_quiet_and_nvm_is_interactive_only(self):
        nvm = self.home / 'custom nvm'
        nvm.mkdir()
        (nvm / 'nvm.sh').write_text('export AIS_NVM_TEST=loaded\n')
        self.env['NVM_DIR'] = str(nvm)
        self.install()
        credentials = self.home / '.config/ais/credentials.sh'
        credentials.write_text('export AIS_STARTUP_TEST=ready\n')
        probe = 'test "$AIS_STARTUP_TEST" = ready && test "${AIS_NVM_TEST-unset}" = unset'
        for shell, flags in (('/bin/zsh', '-c'), ('/bin/zsh', '-lc'), ('/bin/bash', '-lc')):
            with self.subTest(shell=shell, flags=flags):
                result = self.shell(shell, flags, probe)
                self.assertEqual(result.stdout, '')
                self.assertEqual(result.stderr, '')
        result = self.shell('/bin/zsh', '-ic',
                            'test "$AIS_NVM_TEST" = loaded && '
                            'test "$NVM_DIR" = "$HOME/custom nvm" && '
                            'alias ll >/dev/null && ! alias devops >/dev/null 2>&1')
        self.assertEqual(result.stdout, '')
        self.assertEqual(result.stderr, '')
        result = self.shell('/bin/bash', '-c', '. "$HOME/.bashrc"; ' + probe)
        self.assertEqual(result.stdout, '')
        # Direct launch covers non-login, non-interactive Bash/sh agent processes.
        result = subprocess.run([str(self.home / '.local/bin/ais-env'), '/bin/sh', '-c', probe],
                                env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.shell('/bin/zsh', '-lc', 'printf "%s" "$PATH"')
        entries = result.stdout.split(':')
        self.assertEqual(len(entries), len(set(entries)))

    def test_homebrew_login_setup_uses_configured_prefix(self):
        prefix = self.home / 'brew prefix'
        brew = prefix / 'bin/brew'
        brew.parent.mkdir(parents=True)
        brew.write_text('#!/bin/sh\n[ "$1" = shellenv ] || exit 1\nprintf "%s\\n" "export AIS_BREW_TEST=ready"\n')
        brew.chmod(0o755)
        self.env['HOMEBREW_PREFIX'] = str(prefix)
        self.install()
        result = self.shell('/bin/zsh', '-lc', 'test "$AIS_BREW_TEST" = ready')
        self.assertEqual(result.stdout, '')
        self.assertEqual(result.stderr, '')


if __name__ == '__main__':
    unittest.main()
