## Environment and helper commands

- The installer loads `$HOME/.config/ais/shell-env.sh` from `.zshenv`. It provides tool paths, Podman settings, the configured certificate, and exports from the private `$HOME/.config/ais/credentials.sh` file in non-interactive Zsh sessions.
- For Bash, `sh`, or directly launched processes, use `ais-env <command> [arguments...]`, for example `ais-env ./gradlew build`. Kind wrappers load this environment automatically. Do not source interactive `.zshrc` to run agent commands.
- Keep credential values local in `credentials.sh` with mode `600`. Do not put them in shared templates or print them during checks. The installer preserves this file on updates. Loading the environment never triggers an AWS login.
- `aws-dev <command>`, `aws-staging <command>`, and `aws-prod <command>` explicitly log in with AWS SSO, mirror credentials to the default profile for Java tooling, then run the command with the selected `AWS_PROFILE`. An executable cannot change its parent shell. In interactive Zsh, the no-argument shortcuts also select the profile in the current shell.
- `jwt-decode <token>` (or token input on stdin) decodes the header and payload without verifying the signature.

- Use `ais-doctor` (or `ais-doctor --json`) to diagnose local tool availability, installed versions, instruction freshness, certificate validity, and Podman configuration. It does not log in or deploy; exit code 1 means a warning needs attention. Upstream comparison uses cached Git refs and does not fetch.
