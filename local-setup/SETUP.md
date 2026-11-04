# Personal AIS workspace setup

This private installer owns personal shell preferences and helpers. Team instructions live in
`<workspace>/ais-greenshark/tools/workspace-setup/AGENTS.template.md`; the installer reads that
file on every run and appends only the personal rules in the sibling `AGENTS.local.md`.
Update the canonical ais-greenshark checkout before installing to receive new team rules.

## Install

Clone ais-greenshark and the AIS repositories into your workspace. Python 3 is required to run
the installer. Install the tools you use separately: Go Task, Podman, the compatible Docker CLI
and Compose plugin, AWS CLI, jq, and the relevant Java/Node build tools. For cluster prerequisites,
follow the Kind operations skill. The installer does not install packages or trigger logins.

Link this repository's `local-setup` directory to `$HOME/.config/ais/local-setup`, preserving any
existing local setup before changing the link. See the parent README for the clone/link commands.
Then run the shared entry point, supplying your workspace on first use:

```sh
python3 /absolute/path/to/ais-greenshark/tools/workspace-setup/install.py /absolute/path/to/workspace
```

It delegates to this extension. Subsequent direct runs can reuse the configured workspace:

```sh
python3 ~/.config/ais/local-setup/install.py
```

Edit `AGENTS.local.md` for personal agent rules and the tracked shell fragments for shell
preferences. Do not edit generated workspace instructions or deployed helper files.
The parent README documents the six managed shell startup files and their loading order.

## Machine-local configuration

- `~/.config/ais/workspace`: one absolute workspace path, written by the installer.
- `~/.config/ais/credentials.sh`: private exports, mode 600. A commented example is created
  if missing; an existing file is preserved. Never commit this file or put credentials in agent rules.
- `~/.config/ais/zscaler-certificate`: certificate path. Configure it with
  `python3 ~/.config/ais/local-setup/install.py --zscaler-certificate /absolute/path/to/certificate.crt`.
  Neither the certificate nor this machine-specific setting belongs in Git.

Start fresh agent sessions after installing so they load the updated instructions. The global
Codex, Claude Code, and Copilot CLI instructions point to the generated workspace `AGENTS.md`.

## Rollback

```sh
python3 ~/.config/ais/local-setup/install.py --uninstall --dry-run
python3 ~/.config/ais/local-setup/install.py --uninstall
```

The personal receipt records original files and installed checksums. Uninstall restores recorded
originals and removes recorded new files; later edits or missing backups stop it without forcing
removal. The restored originals may contain settings removed during migration. Existing machine
installations can have older, explicitly reviewed baselines. Use the dry-run to see the actual plan.

Credentials, certificate files, and installer sources are retained. Keep original backups until
rollback is no longer needed. Receipts and backups stay local and are not portable machine setup.
The shared entry point forwards `--uninstall`; use the direct private command for `--dry-run`.

## Validate

From the private workspace repository:

```sh
python3 -m unittest discover -s tests -v
```

Tests use temporary homes and workspaces. They check shared/personal instruction composition,
shell startup, legacy migration, and rollback without using real credentials or performing logins
or deployments. On a real machine, run `ais-doctor` or `ais-doctor --json` to inspect tools, versions, instructions,
certificate expiry, permissions, and Podman setup without logins or deployments. It exits 1 for
warnings and compares upstream using cached Git refs. Verify quiet startup; use `ais-env`
for directly launched tools or non-interactive Bash/sh sessions.
