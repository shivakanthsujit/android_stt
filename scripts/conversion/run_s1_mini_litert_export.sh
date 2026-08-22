#!/usr/bin/env bash
set -euo pipefail

run_id=${1:?usage: run_s1_mini_litert_export.sh YYYYMMDDTHHMMSSZ}
if [[ ! ${run_id} =~ ^[0-9]{8}T[0-9]{6}Z$ ]]; then
  echo "Invalid UTC run ID: ${run_id}" >&2
  exit 2
fi

artifact_root=/data/rise/android_stt/litert-conversion
workspace=${artifact_root}/workspace
output_dir=${artifact_root}/runs/s1-mini-block32-ctx4096-${run_id}
log_path=${artifact_root}/export-${run_id}.log
exit_path=${artifact_root}/export-${run_id}.exit

for target in "${output_dir}" "${log_path}" "${exit_path}"; do
  if [[ -e ${target} ]]; then
    echo "Refusing to overwrite conversion target: ${target}" >&2
    exit 2
  fi
done

set +e
"${artifact_root}/env/bin/python" \
  "${workspace}/scripts/conversion/export_s1_mini_litertlm.py" \
  --config "${workspace}/conversion/config/s1-mini-litertlm-block32-v1.json" \
  --source-dir "${artifact_root}/models/s1-mini-bf16" \
  --output-dir "${output_dir}" \
  >"${log_path}" 2>&1
status=$?
set -e
printf '%s\n' "${status}" >"${exit_path}"
exit "${status}"
