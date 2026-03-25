#!/usr/bin/env bash

set -euo pipefail

tool_name="$1"
has_findings="$2"
command_line="$3"
log_file="$4"

{
  echo "### ${tool_name}"
  echo
  echo "- findings: ${has_findings}"
  echo "- command: \`${command_line}\`"
  echo
  if [ -s "${log_file}" ]; then
    echo "<details><summary>raw output</summary>"
    echo
    echo '```text'
    sed -n '1,200p' "${log_file}"
    echo '```'
    echo "</details>"
  else
    echo "No output."
  fi
  echo
} >> "${GITHUB_STEP_SUMMARY}"
