"""Give a test workspace the real shared installer, which the personal installer runs first."""
import os
from pathlib import Path
import shutil
import unittest

DEFAULT = Path(__file__).resolve().parents[2] / 'ais/ais-greenshark/tools/workspace-setup'
SHARED_SETUP = Path(os.environ.get('AIS_SHARED_SETUP', DEFAULT))
FILES = ('install.py', 'install_state.py', 'iip-kind')


def require_shared_setup():
    if not all((SHARED_SETUP / name).is_file() for name in FILES):
        raise unittest.SkipTest(f'The shared installer is not available at {SHARED_SETUP}; set AIS_SHARED_SETUP')


def install_shared_setup(workspace, template):
    """Copy the shared installer into `workspace` with a test template and return the template path."""
    require_shared_setup()
    target = workspace / 'ais-greenshark/tools/workspace-setup'
    target.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        shutil.copy2(SHARED_SETUP / name, target / name)
    path = target / 'AGENTS.template.md'
    path.write_text(template)
    return path
