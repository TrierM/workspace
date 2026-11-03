# AIS workspace instructions

Rules for work across the AIS repositories. Use the links below to find the relevant workflow; approval requirements apply throughout.

- [Workspace and repositories](#workspace-and-repositories)
- [Choose a checkout](#choose-a-checkout-before-editing)
- [CodeGraph](#codegraph)
- [Jira task management](#jira-task-management)
- [Branch, commit, and PR names](#branch-commit-and-pr-names)
- [Environment and helper commands](#environment-and-helper-commands)
- [Local Kind deployments](#local-kind-deployments)
- [Infrastructure and regions](#infrastructure-and-regions)
- [Review another developer's PR](#review-another-developers-pr)

## Workspace and repositories

### Configure the workspace once

Read `$HOME/.config/ais/workspace` before resolving repository paths. It must contain exactly one absolute directory path as plain text, with no quotes, shell expressions, or variable references. The directory is the developer's workspace root. If configuration is missing, invalid, or points to a missing directory, ask for the correct workspace location before repository work; do not guess a personal path.

In these instructions, `<workspace>` means that configured directory. Markdown does not expand variables. In each shell that uses `AIS_WORKSPACE_ROOT`, load it from the same file:

```sh
AIS_WORKSPACE_ROOT=$(cat "$HOME/.config/ais/workspace")
```

The platform commands read this file themselves. Set the path in this one file to change workspaces; do not edit the shared instructions or command scripts.

- The configured workspace contains multiple repositories; run repository Git commands in the relevant repository, rather than at the workspace root.
- Canonical checkouts normally live at `<workspace>/<repo>`.
- Create authorized worktrees at `<workspace>/worktrees/<repo>/<branch-slug>`, replacing `/` in the branch name with `__` and spaces with `-`. Reuse an existing worktree for the task when suitable.

### Products and repositories

Repository names below are relative to the workspace root. These are Elsevier Research repositories in the `elsevier-research` GitHub organization; confirm the target repository's remote before GitHub operations.

| Product / purpose | Repositories |
|---|---|
| Baldur | `iip-baldur` (monorepo) |
| Heimdall | `iip-heimdall` (monorepo) |
| Odin | `iip-odin` and `iip-odin-*` service, selector, UI, library, and test repositories |
| Mimir | `iip-mimir` (monorepo; primary checkout for current Mimir work). Separate `iip-mimir-*` repositories are legacy/migration references; use them only when the task explicitly requires them. |
| Shared libraries | `iip-commons`, `iip-datamodel`, `iip-spring-boot-starter`, `iip-spring-boot-opensearch-autoconfigure` |
| Delivery and tooling | `iip-ci-cd-workflows`, `iip-devops-tool`, `iip-configuration-automation`, `iip-tooling` |
| Templates | `iip-template-application`, `iip-template-library` |
| Infrastructure | `rdm-terraformcontrol` (Terraform/Terragrunt), `ipi-argocd-manifests` (ArgoCD deployments) |

## Choose a checkout before editing

**Default: use the canonical checkout when safe.** Use a worktree for isolation or when explicitly requested. Reuse a suitable task worktree when one already exists.

1. **Inspect the canonical checkout.** Check its branch, staged and unstaged changes, untracked files, and unpushed or unmerged commits. Check current remote refs and the PR state to establish whether its branch has already been merged into `main`. A branch name or `git branch --merged` alone is insufficient after a squash or rebase merge.
2. **Reuse it automatically when the previous work is finished.** If the checkout is clean, all branch work is pushed, and the corresponding PR is confirmed merged into `main`, check out `main`, update with fast-forward only, and create the task branch. Confirm there are no unpushed commits or unrelated changes first. If these conditions cannot be established, ask before switching or syncing.
3. **Resolve ongoing work before editing.** Determine whether an existing branch or changes belong to this task or separate active work. Ask if ownership or activity remains unclear. Do not edit a canonical checkout containing separate active work.
4. **Get agreement before creating a worktree.** Unless already requested or authorized, explain the specific need for isolation and ask whether the canonical checkout can be used safely or a task worktree should be created. Wait for the choice. A feature branch alone is not permission to create a worktree.
5. **Keep the task in the chosen checkout.** Create agreed worktrees using the path convention in [Workspace and repositories](#workspace-and-repositories). Initialize CodeGraph according to [CodeGraph](#codegraph). Read code and make changes in that checkout so context matches its revision.

**Preserve unrelated work.** Never force an update or discard work. Permission to reuse a checkout does not permit resetting, stashing, or moving existing changes; obtain specific authorization for those actions.

### Clean up after a PR is merged

After confirming the task's PR is merged, clean up its task worktree automatically when all checks below pass. No additional permission is needed for this routine cleanup.

1. **Verify the work is finished.** Confirm the PR's merged state and head commit against current remote information. Check that all task commits were pushed and the local branch contains no additional work beyond the merged PR. A squash or rebase merge may not appear in `git branch --merged`; do not rely on that command alone.
2. **Check the worktree.** Inspect staged and unstaged changes, untracked files, and any valuable ignored local files. If work remains, another task or agent is using the worktree, or ownership is unclear, preserve it and ask. Never reset, stash, or discard files to make cleanup possible.
3. **Leave the worktree before removing it.** If the current shell is inside it, move to the canonical checkout. Keep the canonical checkout intact.
4. **Use the mechanism that created it.** For a Codex-managed worktree, use Codex's `archive_worktree` tool. For a regular Git worktree, run `git worktree remove <absolute-worktree-path>` from outside it. Never force removal.
5. **Remove the local task branch when safe.** Only after confirming it contains no work beyond the merged PR and is not checked out elsewhere, attempt `git branch -d <branch>`. If Git refuses deletion, including after a squash merge, leave the branch and report it; do not use `-D` automatically.
6. **Report the outcome.** State which worktree was removed or archived, whether the local branch was deleted, and anything preserved or blocked. This rule does not authorize deleting remote branches or cleaning up unrelated worktrees.

### Identify the checkouts

Run these commands inside the relevant repository or worktree:

```sh
git rev-parse --show-toplevel
git rev-parse --path-format=absolute --git-common-dir
git branch --show-current
git worktree list
```

For this workspace's standard Git checkout layout, resolve the canonical checkout with:

```sh
canonical_checkout=$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")
```

Use the resolved canonical path; do not infer it from a worktree directory name. These inspection commands do not authorize branch switches or edits in another checkout.

<!-- CODEGRAPH_START -->
## CodeGraph

In repositories indexed by CodeGraph (a `.codegraph/` directory exists at the repo root), reach for it BEFORE grep/find or reading files when you need to understand or locate code:

- **MCP tool** (when available): `codegraph_explore` answers most code questions in one call — the relevant symbols' verbatim source plus the call paths between them, including dynamic-dispatch hops grep can't follow. Name a file or symbol in the query to read its current line-numbered source. If it's listed but deferred, load it by name via tool search.
- **Shell** (always works): `codegraph explore "<symbol names or question>"` prints the same output.

When creating a worktree for a repository whose canonical checkout contains `.codegraph/`, automatically run `codegraph init "<absolute-worktree-path>"` after creating the worktree and before exploring its code. No additional permission is needed to index that worktree. Run CodeGraph queries against the worktree being changed so the results match its source.

If an existing worktree lacks `.codegraph/` but its canonical checkout is indexed, automatically initialize that worktree before exploring its code as well. Resolve the canonical checkout from `git rev-parse --path-format=absolute --git-common-dir`, rather than inferring it from the worktree's directory name.

If neither the current checkout nor its canonical checkout contains `.codegraph/`, skip CodeGraph — indexing a previously unindexed repository remains the user's decision.
<!-- CODEGRAPH_END -->

## Jira task management

When starting implementation work that creates or updates a PR, establish the associated Jira ticket and mark it as active work.

1. **Identify the ticket.** Use the ticket supplied with the task or linked from the existing branch/PR. Otherwise search Jira for a matching ticket. Reuse a suitable existing ticket; if none exists, create one using the `create-jira-ticket` skill when available. If multiple tickets could match and the association is unclear, ask before choosing.
2. **Assign it to ourselves.** Resolve the authenticated Jira user's account ID and assign the task ticket to that user. Do not infer the assignee from a Git author name, email, or another developer's ticket.
3. **Move it to In Progress.** Inspect the ticket's available workflow transitions and select the project's `In Progress` status (or its equivalent for active implementation). Do not guess transition IDs. If it is already assigned to the current user and in the appropriate status, leave those fields as they are.
4. **Verify the update.** Read back the assignee and status. If assignment or transition fails, report the actual state and the reason; ask for any required access or workflow clarification. Do not claim the ticket was updated unless it succeeded.

Assignment and the transition to In Progress are authorized as part of starting the implementation; no separate confirmation is needed. Use the same ticket key for the branch, commits, and PR according to the naming rules below.

## Branch, commit, and PR names

Use the task's Jira key consistently. **If it is unknown, ask before creating a branch, committing, or creating a PR. Do not invent a key.**

| Item | Required format | Example |
|---|---|---|
| Branch | `<JIRA-KEY>_<short-description>` | `IIP-3213_fix-deployment-timeout` |
| Commit | `<JIRA-KEY>: <description>` | `IIP-3213: Fix deployment timeout` |
| PR title | `<JIRA-KEY>: <description>` | `IIP-3213: Fix deployment timeout` |

The commit rule also applies to merge commits and any squash commit message the agent supplies.


## Environment and helper commands

- The installer loads `$HOME/.config/ais/shell-env.sh` from `.zshenv`. It provides tool paths, Podman settings, the configured certificate, and exports from the private `$HOME/.config/ais/credentials.sh` file in non-interactive Zsh sessions.
- For Bash, `sh`, or directly launched processes, use `ais-env <command> [arguments...]`, for example `ais-env ./gradlew build`. Kind wrappers load this environment automatically. Do not source interactive `.zshrc` to run agent commands.
- Keep credential values local in `credentials.sh` with mode `600`. Do not put them in shared templates or print them during checks. The installer preserves this file on updates. Loading the environment never triggers an AWS login.
- `aws-dev <command>`, `aws-staging <command>`, and `aws-prod <command>` explicitly log in with AWS SSO, mirror credentials to the default profile for Java tooling, then run the command with the selected `AWS_PROFILE`. An executable cannot change its parent shell. In interactive Zsh, the no-argument shortcuts also select the profile in the current shell.
- `jwt-decode <token>` (or token input on stdin) decodes the header and payload without verifying the signature.

## Local Kind deployments

- **Podman is the only supported container runtime for local Kind operations.** Docker Engine and Docker Desktop are legacy variants; do not select them for new work. The tasks still use the Docker-compatible `docker` CLI and `docker compose`; both must target the `podman` context. Verify `podman machine list` and `docker context show` before lifecycle commands. If the context is different, select it with `docker context use podman`; follow the Kind skill for the remaining runtime checks.
- `iip-baldur`, `iip-heimdall`, `iip-mimir`, and `iip-odin-*` projects support deployment to the local Kind cluster running in Podman. Mimir Kind tasks support a source-mode switch between the monorepo and legacy repositories.
- For hands-on local Kind operations or deployments, invoke the `kind-cluster-operations` skill when available and follow its workflow; its tool is in `<workspace>/iip-tooling/iip-kind-cluster`.

### Select the source checkout

Deploy from the canonical checkout by default. For worktree builds, pass the override on **each applicable command**:

| Platform | Source selection |
|---|---|
| Baldur | `BALDUR_SOURCE_DIR=<absolute-worktree-path>` |
| Heimdall | `HEIMDALL_SOURCE_DIR=<absolute-worktree-path>` |
| Mimir | `MIMIR_SOURCE=monorepo MIMIR_SOURCE_DIR=<absolute-worktree-path>`; see [Mimir source selection](#mimir-source-selection) |
| Odin | Builds canonical sibling service checkouts; an app worktree is not selected automatically. |

### Run commands from any directory

- Use `baldur <task>`, `odin <task>`, `mimir <task>`, or `heimdall <task>` for local Kind tasks, for example `baldur start`, `odin stop`, `mimir check`, or `heimdall deploy:redeploy:manager`.
- When changing a single service, prefer `<platform> deploy:redeploy:<service>` to rebuild and redeploy that service, for example `baldur deploy:redeploy:data-fetcher` or `odin deploy:redeploy:search-controller`. Use `<platform> start` when the platform needs starting or updating as a whole. A service redeploy updates its deployment, including all replicas; it does not target one pod. Worktree source overrides still apply.
- These executables live in `$HOME/.local/bin` and dispatch to `task --dir "$AIS_WORKSPACE_ROOT/iip-tooling/iip-kind-cluster" <platform>:<task>`. They work in interactive and noninteractive shells without sourcing `.zshrc` and preserve the caller's working directory.
- Extra arguments pass through unchanged, including source overrides and Task flags such as `odin start --summary`. Use `<platform> --help` for usage.
- If an agent shell cannot find the commands, use the absolute executable path, for example `$HOME/.local/bin/baldur start`. The `task` executable must also be on PATH; use `command -v task` to locate it. Ensure `$HOME/.local/bin` is on PATH for interactive and agent shells. Keep using the Kind operations skill for runtime checks and deployment guidance.
- For tasks outside a platform namespace, use `task --dir "$AIS_WORKSPACE_ROOT/iip-tooling/iip-kind-cluster" <task>`, for example `cluster:stop` to sleep the entire cluster. A platform's `stop` only undeploys that platform; `destroy` deletes the shared cluster.

### Mimir source selection

- For current Mimir work, pass `MIMIR_SOURCE=monorepo` to each applicable start, build, deploy, or redeploy command. This selects `iip-mimir` for application builds and Helm values. The Kind Taskfile currently defaults to `MIMIR_SOURCE=legacy`, so explicitly select the monorepo even when using the canonical checkout. This switch applies to that invocation; it does not persist across commands.
- `MIMIR_SOURCE_DIR` defaults to the canonical `iip-mimir` checkout. When deploying code from a worktree, also pass `MIMIR_SOURCE_DIR=<absolute-worktree-path>` on each applicable command so builds and deployment values come from the same checkout.
- Use `MIMIR_SOURCE=legacy` only for an explicitly requested legacy-repository task. Check the local tooling implementation when migrating services: an older `iip-tooling` checkout may support fewer monorepo modules than current upstream code.

```sh
# Start Mimir from the canonical monorepo
mimir start MIMIR_SOURCE=monorepo

# Rebuild and redeploy a single monorepo service
mimir deploy:redeploy:manager MIMIR_SOURCE=monorepo

# Rebuild and redeploy that service from a monorepo worktree
mimir deploy:redeploy:manager MIMIR_SOURCE=monorepo MIMIR_SOURCE_DIR=/absolute/path/to/iip-mimir-worktree
```

## Infrastructure and regions

- Terraform/Terragrunt: `rdm-terraformcontrol/terraform/terragrunt/<account>/<env>/<region>/tenant-infra/institutional-integrations-platform/<product-or-service>/`.
- ArgoCD manifests: `ipi-argocd-manifests/institutional-integrations-platform/<env>/<region>/`.
- Terraform product directories are `baldur`, `heimdall`, and `mimir`; Odin services have separate directories named after their repositories (for example `iip-odin-manager`). Cross-region shared resources live under `global/.../shared-resources`.
- The following AWS region map was verified against `rdm-terraformcontrol` on GitHub `main` on 2026-11-02. Resolve effective region values from the product's Terragrunt configuration and inherited `region.yaml`; do not infer deployment regions solely from directory names or an outdated local checkout. Confirm current upstream configuration when the local checkout is behind.
- Heimdall production is in `us-east-2`: its [manager configuration](https://github.com/elsevier-research/rdm-terraformcontrol/blob/main/terraform/terragrunt/ipi-prod/prod/us-east-2/tenant-infra/institutional-integrations-platform/heimdall/manager/eks-iam-role/terragrunt.hcl) loads `region.yaml` and uses `local.region.aws_region`; the [production region configuration](https://github.com/elsevier-research/rdm-terraformcontrol/blob/main/terraform/terragrunt/ipi-prod/prod/us-east-2/region.yaml) sets `aws_region: "us-east-2"`.

| Product | dev (`ipi-dev/dev`) | staging (`ipi-staging/staging`) | prod (`ipi-prod/prod`) |
|---|---|---|---|
| Baldur | `eu-west-1` | `eu-west-1` | `us-east-2` |
| Heimdall | `eu-west-1` | `eu-west-1` | `us-east-2` |
| Odin | `eu-west-1` | `eu-west-1` | `eu-west-1` |
| Mimir | `eu-west-1` | `eu-west-1` | `eu-west-1`, `us-east-2`, `ap-southeast-1`, `ap-southeast-2` |

## Review another developer's PR

### Start and coordinate

1. Find the PR-link message in [#ais-greenshark-review](https://elsevier.enterprise.slack.com/archives/C0BCC81597W). If neither a PR URL nor a matching message is available, ask which PR to review.
2. Use the original PR-link message for coordination. Add `:eyes:` when the review begins.
3. If the user supplied a PR URL but no matching Slack post exists, review that PR without updating an unrelated message.

### Get approval before posting to GitHub

**Never submit GitHub review comments, inline comments, or verdicts without explicit user approval.** Present proposed findings in chat with the file, line, and exact comment text. Wait for a clear yes before submitting. Approval covers only the findings shown and does not carry over to later reviews or re-reviews.

### Update Slack after the GitHub action succeeds

| Completed GitHub action | Reaction on original message | Thread reply |
|---|---|---|
| Review comments submitted | Add `:review_comment:`; retain `:eyes:` during active review | Only `<@AUTHOR_SLACK_ID> Comments have been added.` |
| PR approved | Add `:github-approved:`; after that succeeds, remove the agent's `:eyes:` and `:review_comment:` | Mention the author with `<@AUTHOR_SLACK_ID>` and say the PR was approved. |

- The comments reply must contain only the author mention and the sentence shown: no findings, severity, status, test results, or links.
- Keep `:eyes:` while work or review remains active; it may coexist with `:review_comment:`. If review resumes, restore `:eyes:` and update superseded status reactions.
- Remove only reactions added by the agent for this review using the authenticated Slack identity. Preserve other reviewers' and unrelated reactions.
- Report only completed actions. Explicitly report any Slack reaction or reply that could not be completed.
