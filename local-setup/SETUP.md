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

## AWS profile isolation

Use `aws-dev <command>`, `aws-staging <command>`, or `aws-prod <command>` to choose the
profile explicitly. Each command receives its own temporary credentials. Inherited credential
overrides are cleared, and no helper writes credentials into the shared default profile or puts
credential values in command-line arguments. AWS login is reused when available.

For a verified legacy dependency on `[default]`, pass `--legacy-default` before the command.
This creates a private temporary credentials file for that process and removes it afterward;
it does not modify the machine's default profile. See the parent README for examples and limits.

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

## CodeGraph updates

Keep one standalone CodeGraph installation. Use the AIS command instead of a direct
`codegraph upgrade` so a release cannot silently restore an unapproved bundled Node:

```sh
ais-codegraph-update --check  # installed runtime only; no network or changes
ais-codegraph-update          # download, validate, then activate the latest release
```

The updater runs CodeGraph's official installer in a temporary directory, checks its bundled
Node against the Elsevier minimums (24.22.1 or later in 24.x, or 26.12.1 or later in 26.x),
then checks that the candidate CLI starts. A rejected download is deleted and the current
installation is preserved. Activation errors restore the previous launcher links. Successful
updates remove the previous bundle; restart coding-agent apps to unload its running processes.
`ais-doctor` also reports the bundled runtime separately from the Node selected by PATH.

CodeGraph 1.6.2 ships Node 24.16.0; the current Mac installation has a local 24.22.2 runtime
replacement. Until upstream publishes an approved bundle, the guarded updater will reject
that download and keep the patched installation. The upstream fix is tracked in
[CodeGraph #2959](https://github.com/colbymchenry/codegraph/issues/2959).
The check enforces the stated version policy; it is not a full vulnerability scan.
