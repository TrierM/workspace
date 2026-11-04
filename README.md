# My AIS workspace setup

This repository adds my personal settings and helper commands to the AIS team's shared setup. It helps my terminal and coding agents find the same tools, use the same environment, and follow the same team instructions.

The team setup lives in [`ais-greenshark/tools/workspace-setup`](https://github.com/elsevier-research/ais-greenshark/tree/main/tools/workspace-setup). That remains the source of the shared rules. This repository adds personal preferences around it.

## What each repository provides

| Area | Shared setup in `ais-greenshark` | What this repository adds |
|---|---|---|
| Agent instructions | Team rules for repositories, Jira, worktrees, deployments, and PR reviews | Personal instructions added after the current team rules |
| Agent connections | Connects Codex, Claude Code, and Copilot CLI to the workspace instructions | Keeps those connections while installing my personal setup |
| Local platform commands | `baldur`, `odin`, `mimir`, and `heimdall` commands | Loads my local environment and certificate settings before running them |
| Terminal and agent environment | Explains how to make commands available | Sets up tool paths, Podman availability, private credentials, and certificate settings for local commands |
| Personal helpers | Supports a developer-owned installer and optional personal rules | `ais-env`, AWS profile shortcuts, a JWT decoder, interactive Node setup, and terminal aliases |
| Troubleshooting and rollback | Shared installation and uninstall support | `ais-doctor` and rollback for the personal files this installer manages |

The shared starter example supports adding personal rules too. This repository is my working personal installer, with the additional shell setup and helpers listed above. Other developers can use the shared setup on its own or build their own personal layer from the [team's guide](https://github.com/elsevier-research/ais-greenshark/blob/main/docs/local-workspace-setup.md).

## How installation works

There is one set of installed agent instructions, combining shared and personal rules:

1. Run the shared installer from `ais-greenshark`.
2. It finds my personal installer at `~/.config/ais/local-setup/install.py` and hands the installation over to it.
3. My installer reads the **current shared template** from the local `ais-greenshark` checkout and appends only the personal rules in [`AGENTS.local.md`](local-setup/AGENTS.local.md).
4. It writes the combined instructions to `<workspace>/AGENTS.md` and connects the local agents to that file.
5. It also installs my shell settings and helper commands.

Here, `<workspace>` means the folder containing the AIS repository checkouts. Its location is saved in `~/.config/ais/workspace`.

**Shared rules are not copied into this repository.** Every install reads them from `<workspace>/ais-greenshark/tools/workspace-setup/AGENTS.template.md`. Update that checkout and rerun the installer to receive new team rules. Installation does not automatically download Git updates.

The shared installer hands over before changing installed files. My installer manages the personal installation and its rollback records; it does not run a second shared installation over the same files.

## Install on a machine

You need Python 3 and a local AIS workspace containing `ais-greenshark`. Development tools such as Podman and Go Task must be installed separately; this installer configures their environment.

First, clone this private repository and connect it to the shared installer:

```sh
git clone https://github.com/TrierM/workspace.git "$HOME/Projects/workspace"
mkdir -p "$HOME/.config/ais"
ln -s "$HOME/Projects/workspace/local-setup" "$HOME/.config/ais/local-setup"
```

If a local setup already exists at that location, preserve it before creating the link. The link lets future updates to this repository become available to the installer without copying its files.

Next, run the shared installer. Replace the two example paths below with your local paths:

```sh
python3 /absolute/path/to/ais-greenshark/tools/workspace-setup/install.py /absolute/path/to/ais-workspace
```

It detects this personal installer and follows the steps above. Fill in your private credentials and configure your certificate as described in the [personal setup guide](local-setup/SETUP.md). Start fresh terminal and agent sessions afterward.

Installation does not sign in to AWS or deploy services.

## Everyday use

| Command | What it does |
|---|---|
| `ais-env <command>` | Loads the local environment before running a command, for example `ais-env ./gradlew build` |
| `ais-doctor` | Checks tool availability and versions, instructions, certificate expiry, permissions, and Podman configuration |
| `ais-doctor --json` | Gives agents the same diagnostic results in a structured format |
| `aws-dev`, `aws-staging`, `aws-prod` | Selects an AWS environment and signs in when needed; can also run a command in that environment |
| `jwt-decode` | Makes a JWT's header and payload readable; it does not verify the signature |
| `baldur`, `odin`, `mimir`, `heimdall` | Runs the team's local Kind tasks with my environment settings loaded |

**For agent commands:** Zsh loads the environment automatically. In non-interactive Bash, `sh`, or directly launched processes, use `$HOME/.local/bin/ais-env <command>`. The absolute path works even when the agent cannot initially find the helper. Platform wrappers already load the environment themselves. Do not source the interactive `.zshrc` to run agent commands.

Interactive Zsh also loads my Node version manager and aliases. The installer maintains small source blocks in the Zsh, Bash, and login startup files, preserving unrelated settings. PATH cleanup and tool locations live in the common environment file.

`ais-doctor` does not sign in or deploy. It returns exit code 1 when it finds warnings. Its upstream check uses the last downloaded Git information, so update the shared checkout when you need to check against the latest team changes.

## Keep it up to date

Update both this repository and the local `ais-greenshark` checkout, then rerun:

```sh
python3 ~/.config/ais/local-setup/install.py
```

This direct command uses the same personal installer selected by the shared entry point. It reuses the saved workspace location and reads the updated shared template.

Make personal rule changes in [`AGENTS.local.md`](local-setup/AGENTS.local.md) and shell preference changes in the files under [`local-setup`](local-setup). Rerun the installer to apply them. The generated workspace `AGENTS.md` and installed helper files are outputs; edit their source files here instead.

## Undo an installation

Preview what would be restored or removed:

```sh
python3 ~/.config/ais/local-setup/install.py --uninstall --dry-run
```

Apply that rollback:

```sh
python3 ~/.config/ais/local-setup/install.py --uninstall
```

The installer records the original files and checks for later edits before undoing its changes. Keep its local backups while you may need rollback. Credentials, certificates, and this repository remain in place.

Private credential values, certificates, installation records, and backups stay outside Git. Only the commented credential example is stored here.

For detailed setup and rollback guidance, see [the personal setup guide](local-setup/SETUP.md). Maintainers can run the automated checks with:

```sh
python3 -m unittest discover -s tests -v
```
