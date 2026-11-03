# workspace

Personal installer for my AIS development environment. It installs the agent instructions, the
shell environment, the AWS/JWT helpers and the `baldur`, `odin`, `mimir` and `heimdall` commands
on this machine.

It is my **developer-owned local installer**, as described in the `ais-greenshark`
[local installer guide](https://github.com/elsevier-research/ais-greenshark/blob/main/docs/local-workspace-setup.md).
The team's setup lives in `ais-greenshark/tools/workspace-setup` and is documented in the
[workspace setup guide](https://github.com/elsevier-research/ais-greenshark/blob/main/docs/workspace-setup.md).

## How it relates to `ais-greenshark/tools/workspace-setup`

- The shared `install.py` looks for `~/.config/ais/local-setup/install.py`. When it exists, the shared
  entry point hands over to it, passes the workspace path and `--uninstall`, and uses its exit status.
- This repo owns the personal installation and its receipts. On every run, `local-setup/install.py` reads
  the current team template from `<workspace>/ais-greenshark/tools/workspace-setup/AGENTS.template.md`
  and appends only `local-setup/AGENTS.local.md`. It does not copy team policies into this repo.
  Update the canonical `ais-greenshark` checkout and rerun the installer to receive shared rule changes.
- The shared `tools/workspace-setup` currently has no copies of `aws-session`, `ais-env`, `jwt-decode`,
  `shell-env.sh` or `zsh-helpers.zsh`. They exist only here.
- Install receipts use the `personal` namespace (`~/.config/ais/personal-install-state.json`), separate
  from the shared receipts.

## Contents of `local-setup/`

| File | Purpose |
|---|---|
| `install.py`, `install_state.py` | Installer and its reversible install receipts (`--uninstall`, `--uninstall --dry-run`) |
| `AGENTS.local.md`, `SETUP.md` | Personal-only instruction additions and setup notes; the team template is read from ais-greenshark |
| `aws-session` | Behind `aws-dev`, `aws-staging` and `aws-prod`. Reuses a valid SSO session and logs in only when `aws sts get-caller-identity` fails. Mirrors credentials to the default profile |
| `ais-env`, `shell-env.sh`, `zsh-helpers.zsh` | Environment loader for non-interactive shells, and the interactive shortcuts |
| `jwt-decode`, `iip-kind` | JWT decoder and the Kind cluster entry point |
| `credentials.example.sh` | Template for `~/.config/ais/credentials.sh` |

## Install on a machine

1. Clone the `ais-greenshark` checkout and the AIS repositories into the workspace, and write the workspace
   path to `~/.config/ais/workspace`.
2. Clone this repo and link the installer:

   ```sh
   git clone https://github.com/TrierM/workspace.git ~/Projects/workspace
   ln -s ~/Projects/workspace/local-setup ~/.config/ais/local-setup
   python3 ~/.config/ais/local-setup/install.py
   ```

3. Fill in `~/.config/ais/credentials.sh` from `credentials.example.sh`. Start fresh agent sessions
   afterwards to load the updated instructions.

## Changing it

Edit `local-setup/AGENTS.local.md` for personal rules; do not edit the generated workspace `AGENTS.md`.
Edit other personal source files here and re-run `python3 ~/.config/ais/local-setup/install.py`. Do not edit the deployed
copies in `~/.local/bin` or `~/.config/ais`. The install receipt records their checksums, and a manual edit makes
a later uninstall report them as modified.

## Local patch to `install_state.py`

`local-setup/install_state.py` was a copy of the shared receipt helper. It is patched so that a file already holding
the content the installer would write, for example after a hand edit, updates its receipt checksum. The
unpatched helper returned early and left a stale checksum, so `--uninstall` reported the file as modified.
Only files the receipt already owns are updated; untracked files are never claimed. Run the tests with:

```sh
python3 -m unittest discover -s tests -v
```

Credentials stay in `~/.config/ais/credentials.sh` and are never committed. `.gitignore` also excludes
installer backups (`*.bak-*`), certificates and `__pycache__`.
