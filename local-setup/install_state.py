"""Record shared setup ownership and restore pre-install files without guessing."""
import fcntl
import hashlib
import json
import os
import re
from pathlib import Path
import stat
import tempfile
import time


def fingerprint(path):
    if path.is_symlink():
        return {'type': 'symlink', 'target': os.readlink(path)}
    if not path.exists():
        return None
    if not path.is_file():
        raise ValueError(f'Refusing to manage a non-file: {path}')
    return {'type': 'file', 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'mode': stat.S_IMODE(path.stat().st_mode)}


class InstallState:
    def __init__(self, home, namespace='shared'):
        if not re.fullmatch(r'[a-z][a-z0-9_-]*', namespace):
            raise ValueError('Invalid installer state namespace')
        self.namespace = namespace
        self.path = home / '.config/ais' / (namespace + '-install-state.json')
        self.entries = {}
        self.workspace = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock = self.path.with_name(self.namespace + '-install.lock')
        self.lock = os.fdopen(os.open(lock, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600), 'r+')
        try:
            try:
                fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ValueError('Another shared install or uninstall is running') from None
            if self.path.is_symlink():
                raise ValueError('Installation receipt must not be a symlink')
            if self.path.exists():
                data = json.loads(self.path.read_text())
                if not isinstance(data, dict) or data.get('version') != 1 or not isinstance(data.get('entries'), dict):
                    raise ValueError('Invalid shared installation receipt; preserve it for recovery')
                self.entries = data['entries']
                self.workspace = data.get('workspace')
                for name, entry in self.entries.items():
                    path = Path(name)
                    if not path.is_absolute() or not isinstance(entry, dict) or not isinstance(entry.get('installed'), dict) or not isinstance(entry.get('parent'), str):
                        raise ValueError('Invalid shared installation receipt entry')
                    before = entry.get('before')
                    if before is not None:
                        if not isinstance(before, dict) or not isinstance(before.get('snapshot'), dict) or not isinstance(before.get('backup'), str):
                            raise ValueError('Invalid original-file record')
                        backup = Path(before['backup'])
                        suffix = backup.name[len(path.name + '.bak-'):]
                        if backup.parent != path.parent or not backup.name.startswith(path.name + '.bak-') or not suffix.isdigit():
                            raise ValueError('Invalid backup path in receipt')
        except BaseException:
            self.lock.close()
            raise
        return self

    def __exit__(self, *args):
        self.lock.close()

    def save(self):
        if not self.entries:
            self.path.unlink(missing_ok=True)
            return
        fd, name = tempfile.mkstemp(prefix='.' + self.namespace + '-install-', dir=self.path.parent)
        temp = Path(name)
        try:
            with os.fdopen(fd, 'w') as stream:
                json.dump({'version': 1, 'workspace': self.workspace, 'entries': self.entries}, stream)
                stream.flush()
                os.fsync(stream.fileno())
            temp.replace(self.path)
        finally:
            temp.unlink(missing_ok=True)

    def change(self, path, installed, apply, backups):
        current = fingerprint(path)
        if current == installed:
            return
        previous = self.entries.get(str(path))
        backup = path.with_name(path.name + '.bak-' + str(time.time_ns())) if current is not None else None
        if backup is not None and (backup.exists() or backup.is_symlink()):
            raise ValueError(f'Backup already exists: {backup}')
        if previous and current == previous['installed']:
            # An ordinary upgrade retains the original uninstall baseline.
            before = previous['before']
        else:
            # Preserve edits made outside the installer as the new baseline.
            before = {'snapshot': current, 'backup': str(backup)} if backup is not None else None
        self.entries[str(path)] = {'before': before, 'installed': installed, 'parent': str(path.parent.resolve())}
        # Journal before mutation so interrupted installs can also be recovered.
        self.save()
        if backup is not None:
            path.rename(backup)
            backups.append(backup)
        apply()

    def uninstall(self, workspace=None, dry_run=False):
        if workspace is not None and self.entries and str(workspace) != self.workspace:
            raise ValueError(f'Receipt belongs to a different workspace: {self.workspace}')
        plan, problems = [], []
        for name, entry in self.entries.items():
            path = Path(name)
            if not path.parent.is_dir() or str(path.parent.resolve()) != entry['parent']:
                problems.append(f'Parent directory changed: {path}')
                continue
            current = fingerprint(path)
            before = entry['before']
            original = before['snapshot'] if before else None
            if current == original:
                plan.append((path, None, False, current))
                continue
            if current is not None and current != entry['installed']:
                problems.append(f'Modified since installation: {path}')
                continue
            backup = Path(before['backup']) if before else None
            if backup is not None and fingerprint(backup) != original:
                problems.append(f'Original backup missing or modified: {backup}')
                continue
            plan.append((path, backup, True, current))
        if problems:
            raise ValueError('Uninstall left files unchanged:\n' + '\n'.join(problems))
        if dry_run:
            return [f'Would {"restore" if backup is not None else "remove" if change else "leave unchanged"}: {path}' for path, backup, change, observed in plan]
        actions = []
        for path, backup, change, observed in plan:
            if fingerprint(path) != observed:
                raise ValueError(f'File changed during uninstall; remaining files preserved: {path}')
            if change:
                path.unlink(missing_ok=True)
                if backup is not None:
                    backup.rename(path)
                    actions.append(f'Restored: {path}')
                else:
                    actions.append(f'Removed: {path}')
            else:
                actions.append(f'Already restored or absent: {path}')
            del self.entries[str(path)]
            self.save()
        return actions
