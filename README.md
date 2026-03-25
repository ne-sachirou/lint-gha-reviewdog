# lint-gha-reviewdog

Reusable GitHub Actions workflow for linting GitHub Actions files with `actionlint`, `zizmor`, and `ghalint`.

This repository provides a reusable workflow as the public entry point and a composite action as its internal implementation. The main goal is to let another repository add one job and get:

- pull request feedback via `reviewdog`
- normal CI failures on `push`
- centrally managed tool versions
- optional per-tool execution

## Current behavior

- `actionlint` posts findings through `reviewdog`
- `zizmor` runs as CI and writes results to the job summary
- `ghalint` runs as CI and writes results to the job summary

`zizmor` and `ghalint` do not currently emit `reviewdog` comments. They fail the job when findings are detected.

## Reusable workflow

Workflow file:

[`/.github/workflows/wf-reviewdog-gha-lint.yaml`](/Users/ne-sachirou/dev/lint-gha-reviewdog/.github/workflows/wf-reviewdog-gha-lint.yaml)

Call it from another repository like this:

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
    permissions:
      checks: write
      contents: read
      pull-requests: write
    uses: ne-sachirou/lint-gha-reviewdog/.github/workflows/wf-reviewdog-gha-lint.yaml@v1
    secrets:
      github_token: ${{ github.token }}
```

If you only need one tool, set `toolset` to `actionlint`, `zizmor`, or `ghalint`.

## Inputs

| Name                 | Type      | Default            | Description                                                                         |
| -------------------- | --------- | ------------------ | ----------------------------------------------------------------------------------- |
| `toolset`            | `string`  | `all`              | Which tool jobs to run. Supported values: `all`, `actionlint`, `zizmor`, `ghalint`. |
| `reporter`           | `string`  | `github-pr-review` | `reviewdog` reporter used by `actionlint`.                                          |
| `filter_mode`        | `string`  | `added`            | `reviewdog` filter mode used by `actionlint`.                                       |
| `workdir`            | `string`  | `.`                | Directory to lint.                                                                  |
| `fail_on_error`      | `boolean` | `true`             | Fail the job when findings are detected.                                            |
| `use_aqua`           | `boolean` | `false`            | Reserved for future installation changes. Currently unused.                         |
| `actionlint_version` | `string`  | `v1.7.8`           | Version passed to `go install` for `actionlint`.                                    |
| `zizmor_version`     | `string`  | `v1.13.0`          | Container tag used for `zizmor`.                                                    |
| `ghalint_version`    | `string`  | `v1.2.3`           | Version passed to `go install` for `ghalint`.                                       |
| `reviewdog_version`  | `string`  | `v0.21.0`          | Version used by `reviewdog/action-setup`.                                           |

## Secrets

| Name           | Required | Description                                                                                     |
| -------------- | -------- | ----------------------------------------------------------------------------------------------- |
| `github_token` | No       | GitHub token used by `reviewdog`. If omitted, the workflow falls back to `${{ github.token }}`. |

## Output

| Name           | Description                                   |
| -------------- | --------------------------------------------- |
| `has_findings` | `true` if any enabled tool reported findings. |

## Permissions

Recommended caller permissions:

- `checks: write`
- `contents: read`
- `pull-requests: write`

Notes:

- `pull-requests: write` is needed when you use `reporter: github-pr-review`
- `checks: write` is needed when the workflow falls back to `github-check`, for example on `push`

## Failure model

- If `fail_on_error` is `true`, any finding fails the corresponding job
- `actionlint` findings are reported through `reviewdog`
- `zizmor` and `ghalint` findings are shown in the job summary
- the reusable workflow exposes a combined `has_findings` output

## Repository structure

```text
.github/
  actions/
    gha-lint/
      action.yaml
      scripts/
        write-summary.sh
  workflows/
    ci-gha-lint.yaml
    wf-reviewdog-gha-lint.yaml
```

## Development notes

- The public API is the reusable workflow
- The composite action is an internal implementation detail
- This repository intentionally avoids `pull_request_target`
- Tool versions are pinned in the reusable workflow inputs
