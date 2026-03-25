# lint-gha-reviewdog

GitHub Action for linting GitHub Actions files with `actionlint`, `zizmor`, and `ghalint`.

This repository provides a step-level composite action as the public entry point. The main goal is to let another repository add one step and get:

- pull request feedback via `reviewdog`
- normal CI failures on `push`
- centrally managed tool versions
- optional per-tool execution

## Current behavior

- `actionlint` posts findings through `reviewdog`
- `zizmor` runs as CI and writes results to the job summary
- `ghalint` runs as CI and writes results to the job summary

`zizmor` and `ghalint` do not currently emit `reviewdog` comments. They fail the job when findings are detected.

## Usage

Action metadata:

[`/action.yaml`](./action.yaml)

Use it from another repository like this:

```yaml
name: lint github actions

"on":
  pull_request:
    paths:
      - ".github/actions/**"
      - ".github/workflows/**"
  push:
    paths:
      - ".github/actions/**"
      - ".github/workflows/**"

jobs:
  gha-lint:
    runs-on: ubuntu-latest
    permissions:
      checks: write
      contents: read
      pull-requests: write
    steps:
      - uses: actions/checkout@v6
        with:
          persist-credentials: false

      - uses: ne-sachirou/lint-gha-reviewdog@v1
        with:
          github_token: ${{ github.token }}
```

If you only need one tool, set `toolset` to `actionlint`, `zizmor`, or `ghalint`.

`runs-on` and `actions/checkout` are required because this action runs inside a normal job and lints the checked out workspace.

## Inputs

| Name            | Default            | Description                                                                           |
| --------------- | ------------------ | ------------------------------------------------------------------------------------- |
| `toolset`       | `all`              | Which tools to run. Supported values: `all`, `actionlint`, `zizmor`, `ghalint`.       |
| `reporter`      | `github-pr-review` | `reviewdog` reporter used by `actionlint`.                                            |
| `filter_mode`   | `added`            | `reviewdog` filter mode used by `actionlint`.                                         |
| `workdir`       | `.`                | Directory to lint.                                                                    |
| `fail_on_error` | `true`             | Fail the step when findings are detected.                                             |
| `github_token`  | `""`               | GitHub token used by `reviewdog`. Pass `${{ github.token }}` in the calling workflow. |

## Output

| Name           | Description                                   |
| -------------- | --------------------------------------------- |
| `has_findings` | `true` if any enabled tool reported findings. |

## Permissions

Recommended job permissions:

- `checks: write`
- `contents: read`
- `pull-requests: write`

Notes:

- `pull-requests: write` is needed when you use `reporter: github-pr-review`
- `checks: write` is needed when the workflow falls back to `github-check`, for example on `push`

## Failure model

- If `fail_on_error` is `true`, any finding fails the action step
- `actionlint` findings are reported through `reviewdog`
- `zizmor` and `ghalint` findings are shown in the step summary
- the root action exposes a combined `has_findings` output

## Tool installation

Tools are pinned in [`/aqua.yaml`](./aqua.yaml) and installed through `aquaproj/aqua-installer`. The action executes each tool via `aqua exec -- ...`.

## Repository structure

```text
.github/
  workflows/
    ci-gha-lint.yaml
aqua.yaml
action.yaml
scripts/
  write-summary.sh
```

## Development notes

- The public API is the root `action.yaml`
- This repository intentionally avoids `pull_request_target`
- Tool versions are pinned in `aqua.yaml`
