#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$script_dir/android-env.sh"

echo "JAVA_HOME: $JAVA_HOME"
java -version
echo "ANDROID_HOME: $ANDROID_HOME"
adb version
adb devices -l
