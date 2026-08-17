#!/usr/bin/env bash
set -euo pipefail

. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/android-env.sh"

adb logcat -s LocalFlow:V '*:S'
