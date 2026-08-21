#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source_dir="${LLAMACPP_SOURCE_DIR:-$repo_dir/.cache/llama.cpp-ece963f41}"
source_url="https://github.com/ggml-org/llama.cpp.git"
expected_commit="ece963f41b0b02d7a0d61436ae365762c073a4c8"
expected_tree="f59cbdf04f233655507cc98ee9f704b71bfd1403"
expected_archive_sha256="d0927d84cda1b6f613a0c953da5bb490d8960546ee3fb15a23810d89f6137f8b"
expected_archive_bytes="171663360"

if [[ ! -e "$source_dir" ]]; then
    mkdir -p "$(dirname "$source_dir")"
    git clone --filter=blob:none --no-checkout "$source_url" "$source_dir"
fi

if [[ ! -d "$source_dir/.git" ]]; then
    echo "llama.cpp source path is not a Git checkout: $source_dir" >&2
    exit 1
fi

if [[ -n "$(git -C "$source_dir" status --porcelain)" ]]; then
    echo "Refusing to change a dirty llama.cpp checkout: $source_dir" >&2
    exit 1
fi

if ! git -C "$source_dir" cat-file -e "${expected_commit}^{commit}" 2>/dev/null; then
    git -C "$source_dir" fetch --depth 1 origin "$expected_commit"
fi

actual_commit="$(git -C "$source_dir" rev-parse HEAD 2>/dev/null || true)"
if [[ "$actual_commit" != "$expected_commit" ]]; then
    git -C "$source_dir" checkout --detach "$expected_commit"
fi

actual_commit="$(git -C "$source_dir" rev-parse HEAD)"
actual_tree="$(git -C "$source_dir" rev-parse 'HEAD^{tree}')"
actual_build="$(git -C "$source_dir" describe --always --tags --dirty)"
if [[ "$actual_commit" != "$expected_commit" ]]; then
    echo "llama.cpp commit mismatch: expected $expected_commit, found $actual_commit" >&2
    exit 1
fi
if [[ "$actual_tree" != "$expected_tree" ]]; then
    echo "llama.cpp tree mismatch: expected $expected_tree, found $actual_tree" >&2
    exit 1
fi
if [[ "$actual_build" != "b10450" ]]; then
    echo "llama.cpp build tag mismatch: expected b10450, found $actual_build" >&2
    exit 1
fi
if [[ -n "$(git -C "$source_dir" status --porcelain)" ]]; then
    echo "llama.cpp checkout became dirty during verification" >&2
    exit 1
fi

archive_sha256="$(git -C "$source_dir" archive --format=tar HEAD | shasum -a 256 | awk '{print $1}')"
archive_bytes="$(git -C "$source_dir" archive --format=tar HEAD | wc -c | tr -d ' ')"
if [[ "$archive_sha256" != "$expected_archive_sha256" ]]; then
    echo "llama.cpp source archive SHA-256 mismatch: expected $expected_archive_sha256, found $archive_sha256" >&2
    exit 1
fi
if [[ "$archive_bytes" != "$expected_archive_bytes" ]]; then
    echo "llama.cpp source archive size mismatch: expected $expected_archive_bytes, found $archive_bytes" >&2
    exit 1
fi

printf 'llama.cpp source verified\n'
printf 'path=%s\n' "$source_dir"
printf 'commit=%s\n' "$actual_commit"
printf 'tree=%s\n' "$actual_tree"
printf 'build=%s\n' "$actual_build"
printf 'archive_bytes=%s\n' "$archive_bytes"
printf 'archive_sha256=%s\n' "$archive_sha256"
