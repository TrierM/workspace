"""Update standalone CodeGraph only after its bundled Node passes AIS policy."""
import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


INSTALLER_URL = 'https://raw.githubusercontent.com/colbymchenry/codegraph/main/install.sh'
POLICY = 'Node 24.22.1+ or 26.12.1+ within those major versions'


def approved_node(version):
    match = re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)', version.strip())
    if not match:
        return False
    major, minor, patch = map(int, match.groups())
    minimum = {24: (22, 1), 26: (12, 1)}.get(major)
    return minimum is not None and (minor, patch) >= minimum


def bundle_for_launcher(launcher):
    bundle = Path(launcher).resolve(strict=True).parent.parent
    if not (bundle / 'node').is_file() or not (bundle / 'bin/codegraph').is_file():
        raise ValueError(f'Cannot locate standalone CodeGraph bundled Node from {launcher}')
    return bundle


def runtime_environment(environment):
    result = dict(environment)
    # Version probes must not load startup code from the caller's Node options.
    result.pop('NODE_OPTIONS', None)
    return result


def inspect_bundle(bundle, environment, timeout=5):
    node = Path(bundle) / 'node'
    try:
        result = subprocess.run([str(node), '--version'], env=runtime_environment(environment),
                                capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return False, f'{node}: runtime version check failed or timed out; required {POLICY}'
    version = result.stdout.strip()
    if result.returncode or not approved_node(version):
        return False, f'{node}: unapproved runtime {version!r}; required {POLICY}'
    return True, f'{version} at {node}'


def atomic_link(link, target):
    with tempfile.TemporaryDirectory(prefix='.ais-codegraph-', dir=link.parent) as temp:
        replacement = Path(temp) / 'link'
        replacement.symlink_to(target)
        os.replace(replacement, link)


def update(launcher, environment):
    launcher = Path(launcher).absolute()
    previous = bundle_for_launcher(launcher)
    if previous.parent.name != 'versions' or not launcher.is_symlink():
        raise ValueError('Use the standalone installation and its launcher symlink for AIS updates')
    install_dir = previous.parent.parent
    current = install_dir / 'current'
    if not current.is_symlink() or current.resolve() != previous:
        raise ValueError('CodeGraph on PATH differs from the current standalone installation')
    old_launcher, old_current = os.readlink(launcher), os.readlink(current)
    curl = shutil.which('curl', path=environment.get('PATH', ''))
    if curl is None:
        raise ValueError('curl is required to download the official CodeGraph installer')
    safe_env = runtime_environment(environment)
    with tempfile.TemporaryDirectory(prefix='.ais-update-', dir=install_dir) as temp:
        stage = Path(temp)
        script = stage / 'install.sh'
        subprocess.run([curl, '--fail', '--silent', '--show-error', '--location',
                        '--proto', '=https', '--output', str(script), INSTALLER_URL],
                       env=safe_env, check=True, timeout=60)
        staged_install = stage / 'install'
        staged_bin = stage / 'bin'
        stage_env = dict(safe_env, CODEGRAPH_INSTALL_DIR=str(staged_install),
                         CODEGRAPH_BIN_DIR=str(staged_bin))
        stage_env['PATH'] = str(staged_bin) + os.pathsep + stage_env.get('PATH', '')
        subprocess.run(['/bin/sh', str(script)], env=stage_env, check=True, timeout=180)
        candidate = (staged_install / 'current').resolve(strict=True)
        if candidate.parent != staged_install / 'versions' or not re.fullmatch(r'v\d+\.\d+\.\d+', candidate.name):
            raise ValueError('Unexpected CodeGraph bundle layout; current installation preserved')
        ok, message = inspect_bundle(candidate, safe_env)
        if not ok:
            raise ValueError(f'Rejected downloaded CodeGraph: {message}. Current installation preserved. '
                             'Upstream report: https://github.com/colbymchenry/codegraph/issues/2959')
        probe = subprocess.run([str(candidate / 'bin/codegraph'), '--version'], env=safe_env,
                               check=True, capture_output=True, text=True, timeout=15)
        if probe.stdout.strip() != candidate.name[1:]:
            raise ValueError('CodeGraph CLI version does not match its bundle; current installation preserved')
        if os.readlink(launcher) != old_launcher or os.readlink(current) != old_current:
            raise ValueError('CodeGraph changed during download; retry without another updater running')
        destination = install_dir / 'versions' / candidate.name
        if destination.exists():
            if destination == previous:
                ok, message = inspect_bundle(previous, safe_env)
                if ok:
                    return f'CodeGraph {candidate.name} is already installed with {message}'
            raise ValueError(f'Existing bundle at {destination}; preserving it without overwriting')
        candidate.rename(destination)
        try:
            atomic_link(current, destination)
            atomic_link(launcher, destination / 'bin/codegraph')
            probe = subprocess.run([str(launcher), '--version'], env=safe_env, check=True,
                                   capture_output=True, text=True, timeout=15)
            if probe.stdout.strip() != destination.name[1:]:
                raise ValueError('Activated CodeGraph returned an unexpected version')
        except Exception:
            atomic_link(current, old_current)
            atomic_link(launcher, old_launcher)
            shutil.rmtree(destination)
            raise
        shutil.rmtree(previous)
        return f'Installed CodeGraph {destination.name}; {inspect_bundle(destination, safe_env)[1]}. Restart CodeGraph clients.'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Check the installed bundled Node without network access or changes')
    args = parser.parse_args()
    environment = dict(os.environ)
    try:
        launcher = shutil.which('codegraph', path=environment.get('PATH', ''))
        if launcher is None:
            raise ValueError('codegraph is missing from PATH; install the standalone CLI first')
        if args.check:
            ok, message = inspect_bundle(bundle_for_launcher(launcher), environment)
            print(message)
            return 0 if ok else 1
        print(update(launcher, environment))
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f'CodeGraph update/check failed: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
