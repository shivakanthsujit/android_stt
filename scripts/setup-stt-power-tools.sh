#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tool_dir="$repo_dir/.cache/stt-eval/tools"
trace_processor="$tool_dir/trace_processor_shell"
trace_processor_url="https://commondatastorage.googleapis.com/perfetto-luci-artifacts/v57.2/mac-arm64/trace_processor_shell"
trace_processor_sha256="98a41b80e9f60da0373d64aff6455681f8c26b7c391ae5736324a5b11e3dacc2"

if [[ "$(uname -s)" != "Darwin" || "$(uname -m)" != "arm64" ]]; then
    echo "This pinned setup script currently supports macOS ARM64 only." >&2
    exit 1
fi

mkdir -p "$tool_dir"
if [[ ! -f "$trace_processor" ]]; then
    curl \
        --fail \
        --location \
        --output "$trace_processor.partial" \
        "$trace_processor_url"
    partial_sha256="$(shasum -a 256 "$trace_processor.partial" | awk '{print $1}')"
    if [[ "$partial_sha256" != "$trace_processor_sha256" ]]; then
        echo "Downloaded trace_processor_shell SHA-256 mismatch: $partial_sha256" >&2
        exit 1
    fi
    chmod +x "$trace_processor.partial"
    mv "$trace_processor.partial" "$trace_processor"
fi

actual_sha256="$(shasum -a 256 "$trace_processor" | awk '{print $1}')"
if [[ "$actual_sha256" != "$trace_processor_sha256" ]]; then
    echo "Unexpected trace_processor_shell SHA-256: $actual_sha256" >&2
    exit 1
fi

echo "Verified Perfetto trace processor:"
"$trace_processor" --version
echo "SHA-256: $actual_sha256"
