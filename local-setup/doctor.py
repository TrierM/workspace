"""Inspect the local agent environment without logins or deployment operations."""
import argparse
import json
import os
import re
from pathlib import Path
import shutil
import subprocess


TOOLS = {
    'git': ['--version'], 'gh': ['--version'], 'python3': ['--version'],
    'node': ['--version'], 'npm': ['--version'], 'java': ['-version'],
    'mvn': ['-version'], 'gradle': ['--version'], 'task': ['--version'],
    'podman': ['--version'], 'docker': ['--version'],
    'kubectl': ['version', '--client=true', '--output=json'], 'helm': ['version', '--short'],
    'aws': ['--version'], 'jq': ['--version'], 'codegraph': ['--version'],
}


def run(command, environment, timeout):
    try:
        return subprocess.run(command, env=environment, capture_output=True,
                              text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None


def collect(home, environment, timeout=5):
    checks = []

    def record(name, ok, message):
        checks.append({'check': name, 'status': 'ok' if ok else 'warning', 'message': message})

    executables = {}
    for name, flags in TOOLS.items():
        executable = shutil.which(name, path=environment.get('PATH', ''))
        if executable is None:
            record(name, False, 'Missing from this process PATH')
            continue
        executables[name] = executable
        result = run([executable, *flags], environment, timeout)
        if result is None or result.returncode:
            record(name, False, f'Found at {executable}; version check failed or timed out')
        else:
            output = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', result.stdout + '\n' + result.stderr)
            lines = [line.strip() for line in output.splitlines() if line.strip() and set(line.strip()) != {'-'}]
            version = next((line for line in lines if name.lower() in line.lower()),
                           lines[0] if lines else 'Version unavailable')
            if name == 'kubectl':
                try:
                    version = json.loads(result.stdout)['clientVersion']['gitVersion']
                except (ValueError, KeyError, TypeError):
                    version = 'Client version unavailable'
            record(name, True, version[:180])

    for name in ('ais-env', 'baldur', 'odin', 'mimir', 'heimdall'):
        executable = shutil.which(name, path=environment.get('PATH', ''))
        record(name, executable is not None, 'Available' if executable else 'Missing from this process PATH')

    workspace = None
    try:
        value = (home / '.config/ais/workspace').read_text().rstrip('\n')
        candidate = Path(value)
        if not value.startswith('/') or '\n' in value or '\r' in value or not candidate.is_dir():
            raise ValueError('Invalid workspace')
        workspace = candidate
        record('workspace', True, str(workspace))
    except (OSError, ValueError):
        record('workspace', False, 'Missing or invalid workspace configuration; rerun the installer')

    if workspace is not None:
        shared = workspace / 'ais-greenshark/tools/workspace-setup/AGENTS.template.md'
        personal = home / '.config/ais/local-setup/AGENTS.local.md'
        installed = workspace / 'AGENTS.md'
        try:
            expected = shared.read_text().rstrip() + '\n\n' + personal.read_text().strip() + '\n'
            text = installed.read_text()
            if text.startswith('<!-- AIS_GENERATED'):
                # The shared installer stamps a header with checksums; compare only the instructions after it.
                end = text.find('-->\n')
                text = text[end + len('-->\n'):].lstrip('\n') if end != -1 else text
            matches = text == expected
            record('instructions', matches, 'Current shared template plus personal rules' if matches else
                   'Installed instructions differ from current sources; rerun the installer')
        except OSError:
            record('instructions', False, 'Missing instruction source or installed AGENTS.md')
        if 'git' in executables:
            result = run([executables['git'], '-C', str(workspace / 'ais-greenshark'),
                          'rev-list', '--count', 'HEAD..origin/main'], environment, timeout)
            if result is not None and result.returncode == 0 and result.stdout.strip().isdigit():
                behind = int(result.stdout.strip())
                record('shared checkout', behind == 0,
                       'No missing commits against cached origin/main (no fetch performed)' if behind == 0 else
                       f'{behind} upstream commits missing against cached origin/main; update the checkout')
            else:
                record('shared checkout', False, 'Could not compare with cached origin/main')
        directories = {
            'Codex': Path(environment.get('CODEX_HOME') or home / '.codex'),
            'Claude Code': Path(environment.get('CLAUDE_CONFIG_DIR') or home / '.claude'),
            'Copilot CLI': Path(environment.get('COPILOT_HOME') or home / '.copilot'),
        }
        paths = {'Codex': directories['Codex'] / 'AGENTS.md',
                 'Claude Code': directories['Claude Code'] / 'CLAUDE.md',
                 'Copilot CLI': directories['Copilot CLI'] / 'copilot-instructions.md'}
        override = directories['Codex'] / 'AGENTS.override.md'
        if override.exists() and (override.is_dir() or override.stat().st_size):
            paths['Codex'] = override
        for name, path in paths.items():
            try:
                linked = path.is_symlink() and path.resolve() == installed.resolve()
                content = '' if linked else path.read_text()
                referenced = ('<!-- AIS_WORKSPACE_START -->' in content and
                              '<!-- AIS_WORKSPACE_END -->' in content and f'`{installed}`' in content)
                record(name + ' instructions', linked or referenced,
                       'Linked or referenced workspace instructions' if linked or referenced else
                       'Workspace instruction link/reference is missing')
            except OSError:
                record(name + ' instructions', False, 'Instruction file is missing or unreadable')

    credentials = home / '.config/ais/credentials.sh'
    try:
        mode = credentials.stat().st_mode & 0o777
        record('credentials permissions', mode == 0o600,
               'Mode 600; values not inspected' if mode == 0o600 else 'Expected mode 600; values not inspected')
    except OSError:
        record('credentials permissions', False, 'Private credentials file is missing or unreadable')

    certificate = environment.get('ZSCALER_CERTIFICATE_PATH')
    if not certificate:
        try:
            certificate = (home / '.config/ais/zscaler-certificate').read_text().rstrip('\n')
        except OSError:
            certificate = None
    valid_path = bool(certificate and certificate.startswith('/') and '\n' not in certificate and
                      '\r' not in certificate and Path(certificate).is_file() and os.access(certificate, os.R_OK))
    record('certificate path', valid_path, 'Readable certificate file' if valid_path else
           'Configure a readable absolute Zscaler certificate path')
    if valid_path:
        openssl = shutil.which('openssl', path=environment.get('PATH', ''))
        result = run([openssl, 'x509', '-in', certificate, '-checkend', '0', '-noout'],
                     environment, timeout) if openssl else None
        record('certificate validity', result is not None and result.returncode == 0,
               'Unexpired X.509 certificate' if result is not None and result.returncode == 0 else
               'Certificate expired, invalid, or could not be checked with openssl')

    if 'docker' in executables:
        result = run([executables['docker'], 'context', 'show'], environment, timeout)
        podman_context = result is not None and result.returncode == 0 and result.stdout.strip() == 'podman'
        record('Docker context', podman_context, 'podman' if podman_context else
               'Expected podman; inspect docker context show before Kind operations')
        record('Docker overrides', not environment.get('DOCKER_HOST'),
               'No DOCKER_HOST override' if not environment.get('DOCKER_HOST') else
               'DOCKER_HOST is set and may override the selected context; verify its target')
    if 'podman' in executables:
        result = run([executables['podman'], 'machine', 'list', '--format', 'json'], environment, timeout)
        try:
            machines = json.loads(result.stdout) if result is not None and result.returncode == 0 else []
            running = any(machine.get('Running') is True for machine in (machines or []))
            record('Podman machine', running, 'A machine is running' if running else
                   'No running machine found; inspect podman machine list before Kind operations')
        except (ValueError, TypeError, AttributeError):
            record('Podman machine', False, 'Could not inspect machine state')
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true', help='Emit structured diagnostics for agents')
    args = parser.parse_args()
    checks = collect(Path.home(), dict(os.environ))
    if args.json:
        print(json.dumps(checks, indent=2))
    else:
        for item in checks:
            print(f"[{item['status'].upper()}] {item['check']}: {item['message']}")
    return int(any(item['status'] != 'ok' for item in checks))


if __name__ == '__main__':
    raise SystemExit(main())
