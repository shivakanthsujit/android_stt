#!/usr/bin/env bash

if [[ -z "${JAVA_HOME:-}" ]]; then
    jdk17_home="/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home"
    if [[ -x "$jdk17_home/bin/java" ]]; then
        export JAVA_HOME="$jdk17_home"
    elif java17_home="$(/usr/libexec/java_home -v 17 2>/dev/null)" && [[ -n "$java17_home" ]]; then
        export JAVA_HOME="$java17_home"
    else
        echo "JDK 17 was not found. Install it with: brew install openjdk@17" >&2
        return 1 2>/dev/null || exit 1
    fi
fi

if [[ -z "${ANDROID_HOME:-}" ]]; then
    export ANDROID_HOME="$HOME/Library/Android/sdk"
fi

export PATH="$JAVA_HOME/bin:$ANDROID_HOME/platform-tools:$PATH"

