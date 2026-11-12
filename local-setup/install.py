#!/usr/bin/env python3
"""Install the personal AIS setup on top of the shared team installer.

The shared installer in ais-greenshark owns the team instructions (with the personal rules appended), the Kind
commands and the agent instruction files. This installer runs it first, so those files never drift from the checkout,
and then installs only what is personal: helpers, the shell environment, credentials and shell startup.
"""
import argparse
import hashlib
import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

SHARED_INSTALLER = Path('ais-greenshark/tools/workspace-setup/install.py')


def instruction_paths(home, environment=None):
    environment = environment or {}
    def directory(variable, default):
        value = environment.get(variable)
        return Path(value).expanduser().resolve() if value else home / default

    codex = directory('CODEX_HOME', '.codex')
    override = codex / 'AGENTS.override.md'
    # A nonempty override takes precedence over the standard global file.
    use_override = override.exists() and (override.is_dir() or override.stat().st_size > 0)
    return {
        'Codex': override if use_override else codex / 'AGENTS.md',
        'Claude Code': directory('CLAUDE_CONFIG_DIR', '.claude') / 'CLAUDE.md',
        'Copilot CLI': directory('COPILOT_HOME', '.copilot') / 'copilot-instructions.md',
    }


def startup_lines(content, line, marker):
    start, end = '# ' + marker + '_START', '# ' + marker + '_END'
    block = start + '\n' + line + '\n' + end
    if content.count(start) != content.count(end) or content.count(start) > 1:
        raise ValueError('Malformed AIS shell startup markers')
    if start in content:
        pattern = re.escape(start) + r'.*?' + re.escape(end)
        if not re.search(pattern, content, re.DOTALL):
            raise ValueError('AIS shell startup markers are out of order')
        return re.sub(pattern, lambda match: block, content, count=1, flags=re.DOTALL)
    if line in content:
        return content
    return content + ('\n\n' if content and not content.endswith('\n') else '\n' if content else '') + block + '\n'


def migrate_startup(name, content):
    """Remove only the exact legacy setup snippets previously installed here."""
    env_line = '[ ! -r "$HOME/.config/ais/shell-env.sh" ] || . "$HOME/.config/ais/shell-env.sh"'
    profile_line = '[ ! -r "$HOME/.profile" ] || . "$HOME/.profile"'
    bashrc_line = '[ ! -r "$HOME/.bashrc" ] || . "$HOME/.bashrc"'
    legacy = {
        '.zshenv': ['typeset -U path PATH\n'],
        '.zshrc': [
            'export NVM_DIR="$HOME/.nvm"\n'
            '[ -s "$NVM_DIR/nvm.sh" ] && \\. "$NVM_DIR/nvm.sh"\n'
            '[ -s "$NVM_DIR/bash_completion" ] && \\. "$NVM_DIR/bash_completion"\n',
            "alias ll='ls -alFG'\n", "alias la='ls -AG'\n", "alias l='ls -CFG'\n",
            "alias devops='/Users/trierm/Desktop/iip-devops-tool-darwin'\n",
            '# AIS_HELPERS_START\n'
            '[ ! -r "$HOME/.config/ais/zsh-helpers.zsh" ] || . "$HOME/.config/ais/zsh-helpers.zsh"\n'
            '# AIS_HELPERS_END\n',
        ],
        '.profile': ['if [ -x /opt/homebrew/bin/brew ]; then\n'
                     '    eval "$(/opt/homebrew/bin/brew shellenv)"\nfi\n', env_line + '\n'],
        '.zprofile': [profile_line + '\n'],
        '.bash_profile': [profile_line + '\n', bashrc_line + '\n'],
    }
    if name in ('.zshenv', '.bashrc') and '# AIS_ENV_START' not in content:
        content = content.replace(env_line + '\n', '')
    for snippet in legacy.get(name, []):
        # Do not remove text inside a managed block on subsequent installs.
        if snippet in content and not re.search(r'^# AIS_(?:LOGIN|PROFILE|BASH_LOGIN)_START$', content, re.M):
            content = content.replace(snippet, '')
    return content


def shared_installer(workspace):
    installer = workspace / SHARED_INSTALLER
    if not installer.is_file():
        raise ValueError(f'Shared installer missing: {installer}; update the canonical ais-greenshark checkout')
    return installer


def load_install_state(workspace):
    """Use the shared checkout's receipt module so the two installers cannot disagree about the receipt format."""
    module_path = shared_installer(workspace).with_name('install_state.py')
    spec = importlib.util.spec_from_file_location('ais_shared_install_state', module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.InstallState


def run_shared(workspace, source, uninstall=False):
    """Run the shared installer without its local-installer delegation. Returns its exit status."""
    command = [sys.executable, str(shared_installer(workspace)), str(workspace), '--shared-only']
    if uninstall:
        return subprocess.run(command + ['--uninstall']).returncode
    rules = source / 'AGENTS.local.md'
    if rules.is_file() and rules.read_text().strip():
        command += ['--local-rules', str(rules)]
    return subprocess.run(command).returncode


def release_shared_files(state, workspace, home, environment):
    """Forget receipt entries for files the shared installer owns now.

    Earlier versions of this installer wrote them. The files stay as they are; only the ownership record moves, so
    a personal uninstall does not report them as modified.
    """
    bin_dir = home / '.local/bin'
    owned = [workspace / 'AGENTS.md', home / '.config/ais/workspace', bin_dir / 'iip-kind']
    owned += [bin_dir / name for name in ('baldur', 'odin', 'mimir', 'heimdall')]
    owned += list(instruction_paths(home, environment).values())
    released = [str(path) for path in owned if str(path) in state.entries]
    for name in released:
        del state.entries[name]
    if released:
        state.save()


def install(workspace, home, source, environment=None, certificate=None):
    workspace = workspace.expanduser().resolve(strict=True)
    InstallState = load_install_state(workspace)
    with InstallState(home, namespace='personal') as state:
        return _install(workspace, home, source, environment, certificate, state)


def _install(workspace, home, source, environment, certificate, state):
    if not workspace.is_dir():
        raise ValueError(f'Workspace is not a directory: {workspace}')
    if '\n' in str(workspace) or '\r' in str(workspace):
        raise ValueError('Workspace path must fit on one line')
    executable_names = ('ais-env', 'ais-doctor', 'ais-codegraph-update', 'aws-session', 'jwt-decode')
    environment_names = ('shell-env.sh', 'zsh-helpers.zsh', 'zsh-interactive.zsh', 'login-env.sh', 'doctor.py', 'codegraph_update.py', 'aws-session.py')
    for item in (*(source / name for name in executable_names + environment_names), source / 'credentials.example.sh'):
        if not item.is_file():
            raise ValueError(f'Missing setup file: {item}')
    bin_dir = home / '.local/bin'
    credentials_file = home / '.config/ais/credentials.sh'
    certificate_file = home / '.config/ais/zscaler-certificate'
    if certificate is not None:
        certificate = certificate.expanduser().resolve(strict=True)
        if not certificate.is_file() or not os.access(certificate, os.R_OK) or '\n' in str(certificate) or '\r' in str(certificate):
            raise ValueError('Certificate must be a readable file with a path on one line')
    environment = environment or {}
    zsh_dir = Path(environment['ZDOTDIR']).expanduser().resolve() if environment.get('ZDOTDIR') else home
    def ais_source(name):
        return f'[ ! -r "$HOME/.config/ais/{name}" ] || . "$HOME/.config/ais/{name}"'
    profile_line = '[ ! -r "$HOME/.profile" ] || . "$HOME/.profile"'
    bashrc_line = '[ ! -r "$HOME/.bashrc" ] || . "$HOME/.bashrc"'
    startup_files = [
        (zsh_dir / '.zshenv', ais_source('shell-env.sh'), 'AIS_ENV'),
        (zsh_dir / '.zshrc', ais_source('zsh-interactive.zsh'), 'AIS_INTERACTIVE'),
        (home / '.profile', ais_source('login-env.sh'), 'AIS_LOGIN'),
        (zsh_dir / '.zprofile', profile_line, 'AIS_PROFILE'),
        (home / '.bash_profile', profile_line + '\n' + bashrc_line, 'AIS_BASH_LOGIN'),
        (home / '.bashrc', ais_source('shell-env.sh'), 'AIS_ENV'),
    ]
    destinations = [credentials_file]
    destinations += [bin_dir / name for name in executable_names + ('aws-dev', 'aws-staging', 'aws-prod')]
    destinations += [home / '.config/ais' / name for name in environment_names]
    destinations += [path for path, _, _ in startup_files]
    if certificate is not None:
        destinations.append(certificate_file)
    for path in destinations:
        if path.is_dir():
            raise ValueError(f'Refusing to replace a directory: {path}')
    startup_updates = [(path, startup_lines(migrate_startup(path.name, path.read_text() if path.exists() else ''), lines, marker).encode()) for path, lines, marker in startup_files]

    # The shared installer owns the team files. Run it before anything personal is written, since the personal
    # environment files and the Kind commands expect its workspace configuration.
    release_shared_files(state, workspace, home, environment)
    status = run_shared(workspace, source)
    if status:
        raise ValueError(f'The shared installer failed with status {status}; no personal files were changed')

    state.workspace = str(workspace)
    backups = []

    def write(path, data, mode):
        path.parent.mkdir(parents=True, exist_ok=True)
        installed = {'type': 'file', 'sha256': hashlib.sha256(data).hexdigest(), 'mode': mode}
        def apply():
            path.write_bytes(data)
            path.chmod(mode)
        state.change(path, installed, apply, backups)

    def link(path, target):
        path.parent.mkdir(parents=True, exist_ok=True)
        state.change(path, {'type':'symlink','target':str(target)}, lambda: path.symlink_to(target), backups)

    for name in executable_names:
        write(bin_dir / name, (source / name).read_bytes(), 0o755)
    for name in environment_names:
        write(home / '.config/ais' / name, (source / name).read_bytes(), 0o600)
    if not credentials_file.exists() and not credentials_file.is_symlink():
        fd = os.open(credentials_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write((source / 'credentials.example.sh').read_bytes())
    elif not credentials_file.is_symlink():
        credentials_file.chmod(0o600)
    if certificate is not None:
        write(certificate_file, (str(certificate) + '\n').encode(), 0o600)
    for path, content in startup_updates:
        write(path, content, 0o600)
    for name in ('aws-dev', 'aws-staging', 'aws-prod'):
        path = bin_dir / name
        if path.is_symlink() and os.readlink(path) == 'aws-session':
            continue
        link(path, 'aws-session')
    return workspace, backups


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workspace', nargs='?', type=Path, help='Directory containing AIS repositories; omit to reuse the configured workspace')
    parser.add_argument('--zscaler-certificate', type=Path, help='Optional certificate file; preserves an existing certificate setting when omitted')
    parser.add_argument('--uninstall', action='store_true', help='Restore the recorded pre-personal-setup files; keep credentials and certificate')
    parser.add_argument('--dry-run', action='store_true', help='Preview uninstall without changing installed files')
    args = parser.parse_args()
    if args.dry_run and not args.uninstall:
        parser.error('--dry-run requires --uninstall')
    try:
        if args.uninstall:
            selected = args.workspace.expanduser().resolve() if args.workspace is not None else None
            workspace_for_state = selected or Path(Path.home().joinpath('.config/ais/workspace').read_text().rstrip('\n'))
            InstallState = load_install_state(workspace_for_state)
            with InstallState(Path.home(), namespace='personal') as state:
                actions = state.uninstall(selected, dry_run=args.dry_run)
            for action in actions:
                print(action)
            if not actions:
                print('No recorded personal installation; existing files left unchanged.')
            if not args.dry_run:
                status = run_shared(workspace_for_state, Path(__file__).resolve().parent, uninstall=True)
                if status:
                    return status
            print('Private credentials, certificate, and local installer sources are retained.')
            return 0
        configured = args.workspace
        if configured is None:
            config = Path.home() / '.config/ais/workspace'
            value = config.read_text().rstrip('\n')
            if not value.startswith('/') or '\n' in value or '\r' in value:
                raise ValueError(f'Invalid workspace configuration: {config}')
            configured = Path(value)
        workspace, backups = install(configured, Path.home(), Path(__file__).resolve().parent, os.environ, args.zscaler_certificate)
    except (OSError, ValueError) as error:
        parser.exit(1, f'Setup failed: {error}\n')
    print(f'Workspace: {workspace}')
    print(f'Configuration: {Path.home() / ".config/ais/workspace"}')
    print('Installed through the shared installer: team instructions with personal rules, Kind commands and agent links.')
    print('Installed personally: shared environment, ais-env, AWS/JWT helpers and shell startup.')
    print('Private credentials: ' + str(Path.home() / '.config/ais/credentials.sh'))
    for agent, path in instruction_paths(Path.home(), os.environ).items():
        method = 'shared symlink' if path.is_symlink() else 'personal instructions with managed read reference'
        print(f'{agent}: {path} ({method})')
    print('Start fresh agent sessions to load updated instructions.')
    for backup in backups:
        print(f'Preserved existing file: {backup}')
    print('Ensure $HOME/.local/bin and the task executable are on PATH in interactive and agent shells.')
    print('Use baldur --help for usage. Installation does not run any cluster operations.')


if __name__ == '__main__':
    raise SystemExit(main())
