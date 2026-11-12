import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import shared_setup

SOURCE = Path(__file__).resolve().parents[1] / 'local-setup'


class PersonalInstructionsTest(unittest.TestCase):
    def test_shared_and_personal_updates_and_uninstall(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            home = root / 'developer home'
            home.mkdir()
            workspace = root / 'AIS workspace'
            workspace.mkdir()
            source = root / 'local sources'
            shutil.copytree(SOURCE, source, ignore=shutil.ignore_patterns('*.bak-*', '__pycache__'))
            self.assertFalse((source / 'AGENTS.template.md').exists())
            shared = shared_setup.install_shared_setup(workspace, '# Team instructions\nFirst shared rule.\n')
            personal = source / 'AGENTS.local.md'
            personal.write_text('## Personal additions\nFirst personal rule.\n')
            agents = workspace / 'AGENTS.md'
            agents.write_text('Original instructions\n')
            env = dict(os.environ, HOME=str(home))
            for key in ('CODEX_HOME', 'CLAUDE_CONFIG_DIR', 'COPILOT_HOME', 'ZDOTDIR'):
                env.pop(key, None)
            command = [sys.executable, str(source / 'install.py'), str(workspace)]

            def run(*args, success=True):
                result = subprocess.run(command + list(args), env=env, cwd=root,
                                        capture_output=True, text=True, timeout=15)
                if success:
                    self.assertEqual(result.returncode, 0, result.stderr)
                else:
                    self.assertNotEqual(result.returncode, 0)
                return result

            def instructions():
                # The shared installer stamps a generated header; the personal rules follow the team template.
                text = agents.read_text()
                self.assertTrue(text.startswith('<!-- AIS_GENERATED'))
                return text[text.index('-->\n') + len('-->\n'):].lstrip('\n')

            for _ in range(2):
                run()
                self.assertEqual(instructions(), shared.read_text().rstrip() +
                                 '\n\n' + personal.read_text().strip() + '\n')
            shared.write_text('# Team instructions\nUpdated shared rule.\n')
            personal.write_text('## Personal additions\nUpdated personal rule.\n')
            run()
            self.assertEqual(instructions().count('Updated shared rule.'), 1)
            self.assertEqual(instructions().count('Updated personal rule.'), 1)
            self.assertNotIn('First shared rule.', instructions())
            # The Kind wrapper is the shared installer's own file, not a personal copy.
            self.assertEqual((home / '.local/bin/iip-kind').read_bytes(),
                             (workspace / 'ais-greenshark/tools/workspace-setup/iip-kind').read_bytes())
            for name in ('.codex/AGENTS.md', '.claude/CLAUDE.md', '.copilot/copilot-instructions.md'):
                self.assertEqual((home / name).resolve(), agents)
            before = agents.read_bytes()
            shared.unlink()
            run(success=False)
            self.assertEqual(agents.read_bytes(), before)
            shared.write_text('# Team instructions\nUpdated shared rule.\n')
            run('--uninstall', '--dry-run')
            self.assertEqual(agents.read_bytes(), before)
            run('--uninstall')
            self.assertEqual(agents.read_text(), 'Original instructions\n')
            self.assertTrue(personal.exists())


if __name__ == '__main__':
    unittest.main()
