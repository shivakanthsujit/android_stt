#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"
. "$repo_dir/scripts/android-env.sh"

./gradlew assembleDebug
echo "APK: $repo_dir/app/build/outputs/apk/debug/app-debug.apk"
