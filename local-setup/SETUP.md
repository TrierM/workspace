# Shared agent workspace setup

Install the team's shared `AGENTS.md`, environment loader, AWS/JWT helpers, and the `baldur`, `odin`, `mimir`, and `heimdall` commands. Each developer configures one workspace root. Team policies and scripts are shared without editing personal paths into them.

## Prerequisites

- macOS or Linux, Python 3, and a POSIX shell.
- An AIS workspace directory containing your repository checkouts, including `ais-greenshark` and `iip-tooling`.
- Go Task for platform commands; AWS CLI and `jq` for AWS login helpers. The loader adds standard Homebrew tool directories to PATH when present.
- Podman is the only supported local container runtime. Docker Engine/Desktop are legacy. The Docker CLI and Compose plugin are still required for compatibility; `docker context show` must report `podman` before local Kind operations.
- The Kind operations skill and its runtime/build prerequisites for actual deployments.

The installer does not clone repositories, install dependencies, trigger AWS login, or run cluster operations. It adds managed source blocks to `.zshenv` and `.zshrc` (under `ZDOTDIR` when set) while preserving existing startup content.

## Install

From the `ais-greenshark` checkout:

```sh
python3 tools/workspace-setup/install.py /absolute/path/to/workspace
```

Pass the parent of the AIS repository checkouts, not the `ais-greenshark` repository itself. Quote paths that contain spaces.

The installer writes:

| Location | Purpose |
|---|---|
| `<workspace>/AGENTS.md` | Shared instructions for agents working under this workspace |
| `$HOME/.config/ais/workspace` | Your absolute workspace path as one plain-text line |
| `$HOME/.local/bin/iip-kind` | Dispatcher that reads the workspace configuration |
| `$HOME/.config/ais/shell-env.sh` | Quiet environment loader shared by shells and commands |
| `$HOME/.config/ais/credentials.sh` | Private exports, mode `600`; created as a commented example and never overwritten |
| `$HOME/.config/ais/zsh-helpers.zsh` | Thin interactive AWS profile shortcuts |
| `$HOME/.local/bin/ais-env` | Load the environment and execute any command |
| `$HOME/.local/bin/aws-session`, `aws-dev`, `aws-staging`, `aws-prod` | Explicit SSO login and command-scoped AWS profiles |
| `$HOME/.local/bin/jwt-decode` | Decode JWT headers/payloads without signature verification |
| `$HOME/.local/bin/baldur`, `odin`, `mimir`, `heimdall` | Symlinks to the dispatcher |
| `$HOME/.codex/AGENTS.md` | Codex user instructions linked to the shared file; an existing nonempty `AGENTS.override.md` is updated instead |
| `$HOME/.claude/CLAUDE.md` | Claude Code user instructions linked to the shared file |
| `$HOME/.copilot/copilot-instructions.md` | Copilot CLI user instructions linked to the shared file |

Different existing files are preserved next to their original locations as `<name>.bak-<timestamp>`. Identical files are reused. Existing directories at installation destinations cause installation to stop.

Ensure `$HOME/.local/bin` and Go Task's installation directory are on PATH in both terminal and agent processes. For example, add this to your shell startup configuration if needed, then restart the terminal or agent application:

```sh
export PATH="$HOME/.local/bin:$PATH"
```

The user instruction links also make the shared guidance available when a local agent starts in a worktree outside the workspace. Tool-specific loading rules still apply; verify the loaded instructions as described below.

## Configure credentials and the certificate

Populate `$HOME/.config/ais/credentials.sh` locally with the exports your tools require. The installed commented example shows the format. To keep an explicitly supplied environment value, use a default:

```sh
if [ -z "${ARTIFACTORY_USERNAME+x}" ]; then
    export ARTIFACTORY_USERNAME='your-user'
fi
```

Move existing literal credential exports from interactive shell configuration into this private file when needed. The installer does not extract credentials from arbitrary shell scripts. It never replaces an existing `credentials.sh` and enforces mode `600` on a regular credential file. A user-managed symlink is retained without modifying its target's permissions.

To save your certificate path, pass the optional installer setting once:

```sh
python3 tools/workspace-setup/install.py --zscaler-certificate /absolute/path/to/zscaler-root-ca.crt
```

The path is stored in `$HOME/.config/ais/zscaler-certificate`. Builds require a readable certificate. Ordinary status/stop commands do not. Precedence is Task command-line `ZSCALER_CERTIFICATE_PATH=...`, then the environment variable, then this config file. Certificate values are exported consistently to child build processes.

## Run tools without an interactive shell

Zsh loads the shared environment through `.zshenv`. Other shells and direct process launches can use:

```sh
ais-env ./gradlew build
aws-dev ./gradlew build
aws-prod aws sts get-caller-identity
jwt-decode '<token>'
```

`ais-env` loads private exports and common tool paths, then replaces itself with the supplied command, forwarding arguments and exit status. It does not load NVM or other interactive shell plugins. Add any extra tool locations you require through your private environment configuration.

AWS helpers explicitly perform SSO login, mirror resolved credentials to the default profile for existing Java tooling, and optionally execute a command under the selected `AWS_PROFILE`. They do not log in during shell startup. Login/mirroring messages go to stderr; stdout belongs to the supplied command. Mirroring failures are reported but retain the existing behavior of allowing the selected-profile command to proceed.

In interactive Zsh, `aws-dev`, `aws-staging`, or `aws-prod` without arguments also select the profile in the current shell. When passed a command, they leave the parent shell's profile unchanged. Bash and direct agent invocations should supply the command because executable programs cannot change the parent environment.

`jwt-decode` accepts a token argument or stdin, supports Base64URL padding, and outputs a JSON array containing the header and payload. Decoding does not verify a signature.

## Connect existing agent instructions

The installer checks the user instruction locations above. It honors `CODEX_HOME`, `CLAUDE_CONFIG_DIR`, and `COPILOT_HOME` when those variables are set in the installation process. Run updates with the same environment used to launch your agents.

- Missing or empty instruction files become symlinks to `<workspace>/AGENTS.md`.
- Existing symlinks to the shared file are reused. If the configured workspace changes through the installer, links pointing to the previous configured workspace are retargeted, with backups.
- A file containing personal instructions keeps that text and receives one managed `AIS_WORKSPACE_START` / `AIS_WORKSPACE_END` block. The block instructs the agent to read and follow the shared file before AIS work. Reinstalling updates that reference without duplicating it. This is an explicit instruction to read the file, not a native import mechanism.
- A symlink to a separate personal instruction file is backed up as a symlink. Its content is preserved in the active instruction file with the managed reference; the original target is not edited.
- Codex loads a nonempty global `AGENTS.override.md` ahead of `AGENTS.md`. The installer updates that override when present so the reference is in the file Codex actually reads.

Repository-specific instructions and IDE settings are not modified. This setup connects the local user instruction files used by Codex, Claude Code, and Copilot CLI. It does not configure remote/cloud agents or discover custom IDE profile files.

Start fresh agent sessions after installation. Ask Codex to list its instruction sources, use Claude Code's `/memory`, and use Copilot CLI's `/instructions` to inspect what each tool loaded. A filesystem link verifies the setup; it does not prove that an already-running session reloaded it.

Instruction-location references: [Codex](https://learn.chatgpt.com/docs/agent-configuration/agents-md), [Claude Code](https://code.claude.com/docs/en/memory), [Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-custom-instructions).

## Use

Commands work from any directory and preserve the caller's working directory:

```sh
baldur --help
odin start --summary
baldur deploy:redeploy:data-fetcher
heimdall deploy:redeploy:manager
mimir deploy:redeploy:manager MIMIR_SOURCE=monorepo
```

The last three examples rebuild and redeploy the named service. Follow the Kind operations skill before running deployment commands.

To select a Mimir worktree, pass the source switch and checkout together on each applicable command:

```sh
mimir deploy:redeploy:manager MIMIR_SOURCE=monorepo MIMIR_SOURCE_DIR=/absolute/path/to/iip-mimir-worktree
```

Baldur and Heimdall use `BALDUR_SOURCE_DIR` and `HEIMDALL_SOURCE_DIR`. Odin tasks use canonical sibling service checkouts.

The dispatcher maps `<platform> <task> [arguments...]` to the platform's Task namespace in `<workspace>/iip-tooling/iip-kind-cluster`. Additional arguments and Task exit codes are forwarded. The workspace configuration is read as data, never sourced or evaluated as shell code.

## Update or change workspace

After updating your `ais-greenshark` checkout, rerun the installer without an argument to reuse your configured workspace:

```sh
python3 tools/workspace-setup/install.py
```

To configure a different workspace, pass its absolute path. The previous configuration is backed up. The installer writes instructions in the new workspace and leaves the previous workspace's files intact.

The repository source of the instructions is [AGENTS.template.md](../tools/workspace-setup/AGENTS.template.md). Make shared policy changes there and rerun the installer to apply them locally. Personal changes to the installed `AGENTS.md` are backed up on updates; reconcile them with the shared template if needed.

## Check the setup

Read-only checks:

```sh
command -v baldur
command -v task
baldur --help
odin start --summary
mimir deploy:redeploy:manager MIMIR_SOURCE=monorepo --summary
```

Missing or malformed workspace configuration, a missing Kind Taskfile, or an unavailable Task executable produces an error before task execution.

Run the installer and command routing checks in temporary directories:

```sh
python3 -m unittest discover -s tools/workspace-setup/tests -v
```

These checks use a fake Task executable and do not start or modify the cluster.

## Personal rollback

The private installer now supports:

```sh
python3 ~/.config/ais/local-setup/install.py --uninstall --dry-run
python3 ~/.config/ais/local-setup/install.py --uninstall
```

The dry-run previews without removing installed files. The reviewed rollback restores the four pre-personal-helper files (workspace AGENTS.md, iip-kind, shell-env.sh, and .zshrc) and removes the seven personal executable/helper files created during this setup. Existing shared platform shortcuts and agent links remain. Credentials, the certificate, local installer sources, and the earlier shell cleanup remain local.

Rollback uses ~/.config/ais/personal-install-state.json and explicit verified backups from the setup session. Later edits or missing backups block uninstall; there is no force option. Do not delete the original backups while rollback is needed. The shared installer forwards --uninstall to this private installer; use the direct private command for --dry-run.

This standalone snapshot owns its full template. Reconcile team policy changes when updating it. For a generic shared-base-plus-overlay approach, see docs/local-workspace-setup.md and tools/workspace-setup/local-install.example.py in ais-greenshark.
