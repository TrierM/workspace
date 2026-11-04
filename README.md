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
| `ais-env`, `shell-env.sh`, `login-env.sh` | Common environment and Homebrew login initialization |
| `zsh-interactive.zsh`, `zsh-helpers.zsh` | Interactive NVM, aliases, and AWS profile shortcuts |
| `ais-doctor`, `doctor.py` | Local environment diagnostics, installed versions, and JSON output for agents |
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

## Shell startup

The installer preserves existing startup content and adds managed source blocks:

| Startup file | Loads |
|---|---|
| `.zshenv` | `shell-env.sh` for every normal Zsh invocation |
| `.zshrc` | `zsh-interactive.zsh` for interactive NVM, aliases, and AWS shortcuts |
| `.profile` | `login-env.sh` for Homebrew initialization and the common environment |
| `.zprofile` | `.profile` |
| `.bash_profile` | `.profile` followed by `.bashrc` |
| `.bashrc` | `shell-env.sh` |

Zsh startup files respect `ZDOTDIR`. Non-interactive Bash does not normally read `.bashrc`;
use `ais-env <command>` for those agent processes. The common environment owns PATH deduplication.
NVM respects an explicitly configured `NVM_DIR` and loads only in interactive Zsh.
Homebrew login initialization checks `HOMEBREW_PREFIX`, `/opt/homebrew`, and `/usr/local`.
The deprecated Desktop `devops` alias is removed during migration.

Edit the tracked shell fragments to change preferences; reinstall to deploy them. Known legacy
snippets are migrated while unrelated startup content stays in place. Uninstall restores the
recorded original files, including any original legacy settings. Credentials, certificates,
receipts, and timestamped backups stay outside Git.

## Diagnose the agent environment

```sh
ais-doctor
ais-doctor --json
```

The doctor loads the same environment as `ais-env`, then reports installed tool versions,
workspace and instruction setup, credential file permissions, certificate expiry, Docker context,
and Podman machine state. It runs no logins, deployments, package installations, or Git fetches.
The tool version commands and runtime inspection each have a five-second timeout. Normal tool
version commands may perform their own local cache initialization. Credential values are not
inspected or printed. JSON output uses `check`, `status`, and `message` for each diagnostic.

Exit code 0 means all checks passed; 1 means warnings need attention. Missing tools are warnings,
so the report remains useful on a machine that only needs a subset of the platform tools.
Instruction freshness compares with your current shared checkout; upstream comparison uses cached
`origin/main`. Fetch/update ais-greenshark explicitly when you want current upstream information.
No manually maintained list of installed tool versions is needed. `/opt/podman/bin` is included
when it exists, so Podman is available in clean non-interactive agent shells.

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
