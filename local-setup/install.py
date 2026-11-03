#!/usr/bin/env python3
"""Install AIS workspace instructions and platform commands for the current user."""
import argparse
import os
import re
from pathlib import Path
import hashlib

from install_state import InstallState


REFERENCE_START = '<!-- AIS_WORKSPACE_START -->'
REFERENCE_END = '<!-- AIS_WORKSPACE_END -->'


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


def reference_content(content, target):
    start_count = content.count(REFERENCE_START)
    end_count = content.count(REFERENCE_END)
    if start_count != end_count or start_count > 1:
        raise ValueError('Malformed AIS workspace reference markers; preserve and repair the instruction file first')
    block = (
        REFERENCE_START + '\n## AIS workspace instructions\n\n'
        'Before working on AIS repositories or their worktrees, read and follow the shared '
        f'instructions at `{target}`. Read `$HOME/.config/ais/workspace` to resolve the configured '
        'workspace root. The shared file is the source of team policies; keep personal instructions '
        'outside this managed block.\n' + REFERENCE_END
    )
    if start_count:
        pattern = re.escape(REFERENCE_START) + r'.*?' + re.escape(REFERENCE_END)
        if not re.search(pattern, content, re.DOTALL):
            raise ValueError('AIS workspace reference markers are out of order')
        return re.sub(pattern, lambda match: block, content, count=1, flags=re.DOTALL)
    return content + ('\n\n' if not content.endswith('\n') else '\n') + block + '\n'


def startup_content(content, source_name, marker):
    start, end = '# ' + marker + '_START', '# ' + marker + '_END'
    line = f'[ ! -r "$HOME/.config/ais/{source_name}" ] || . "$HOME/.config/ais/{source_name}"'
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


def install(workspace, home, source, environment=None, certificate=None):
    with InstallState(home, namespace='personal') as state:
        return _install(workspace, home, source, environment, certificate, state)


def _install(workspace, home, source, environment, certificate, state):
    workspace = workspace.expanduser().resolve(strict=True)
    if not workspace.is_dir():
        raise ValueError(f'Workspace is not a directory: {workspace}')
    if '\n' in str(workspace) or '\r' in str(workspace):
        raise ValueError('Workspace path must fit on one line')
    template = source / 'AGENTS.template.md'
    executable_names = ('iip-kind', 'ais-env', 'aws-session', 'jwt-decode')
    environment_names = ('shell-env.sh', 'zsh-helpers.zsh')
    for item in (template, *(source / name for name in executable_names + environment_names), source / 'credentials.example.sh'):
        if not item.is_file():
            raise ValueError(f'Missing setup file: {item}')
    bin_dir = home / '.local/bin'
    config = home / '.config/ais/workspace'
    credentials_file = home / '.config/ais/credentials.sh'
    certificate_file = home / '.config/ais/zscaler-certificate'
    if certificate is not None:
        certificate = certificate.expanduser().resolve(strict=True)
        if not certificate.is_file() or not os.access(certificate, os.R_OK) or '\n' in str(certificate) or '\r' in str(certificate):
            raise ValueError('Certificate must be a readable file with a path on one line')
    environment = environment or {}
    zsh_dir = Path(environment['ZDOTDIR']).expanduser().resolve() if environment.get('ZDOTDIR') else home
    startup_files = [(zsh_dir / '.zshenv', 'shell-env.sh', 'AIS_ENV'), (zsh_dir / '.zshrc', 'zsh-helpers.zsh', 'AIS_HELPERS')]
    destinations = [workspace / 'AGENTS.md', config, credentials_file]
    destinations += [bin_dir / name for name in executable_names + ('baldur', 'odin', 'mimir', 'heimdall', 'aws-dev', 'aws-staging', 'aws-prod')]
    destinations += [home / '.config/ais' / name for name in environment_names]
    destinations += [path for path, _, _ in startup_files]
    if certificate is not None:
        destinations.append(certificate_file)
    agent_paths = instruction_paths(home, environment)
    destinations += list(agent_paths.values())
    for path in destinations:
        if path.is_dir():
            raise ValueError(f'Refusing to replace a directory: {path}')
    startup_updates = [(path, startup_content(path.read_text() if path.exists() else '', name, marker).encode()) for path, name, marker in startup_files]
    target = workspace / 'AGENTS.md'
    previous_target = None
    if config.is_file():
        previous = config.read_text().rstrip('\n')
        if previous.startswith('/') and '\n' not in previous and '\r' not in previous:
            previous_target = Path(previous) / 'AGENTS.md'

    # Plan updates before writing anything. Never mutate a personal symlink's target.
    agent_updates = []
    for path in agent_paths.values():
        if path == target:
            continue
        existing_target = path.resolve() if path.is_symlink() else None
        if not path.exists() or (path.is_symlink() and existing_target in (target, previous_target)):
            agent_updates.append((path, None))
        else:
            content = path.read_text()
            if not content.strip() or content == template.read_text():
                agent_updates.append((path, None))
            else:
                agent_updates.append((path, reference_content(content, target).encode()))

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

    write(workspace / 'AGENTS.md', template.read_bytes(), 0o644)
    write(config, (str(workspace) + '\n').encode(), 0o600)
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
    for name in ('baldur', 'odin', 'mimir', 'heimdall'):
        path = bin_dir / name
        if path.is_symlink() and os.readlink(path) == 'iip-kind':
            continue
        link(path, 'iip-kind')
    for name in ('aws-dev', 'aws-staging', 'aws-prod'):
        path = bin_dir / name
        if path.is_symlink() and os.readlink(path) == 'aws-session':
            continue
        link(path, 'aws-session')
    for path, content in agent_updates:
        if content is not None:
            write(path, content, 0o644)
        elif not path.is_symlink() or path.resolve() != target:
            link(path, target)
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
            with InstallState(Path.home(), namespace='personal') as state:
                actions = state.uninstall(selected, dry_run=args.dry_run)
            for action in actions:
                print(action)
            if not actions:
                print('No recorded personal installation; existing files left unchanged.')
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
    print('Installed workspace instructions, shared environment, ais-env, AWS/JWT helpers, and Kind commands.')
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
