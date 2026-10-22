#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
command -v node >/dev/null || { echo "Install Node.js 22+ first"; exit 1; }
command -v npm >/dev/null || { echo "npm was not found"; exit 1; }
npm install
if [ ! -d android ]; then npx cap add android; fi
npx cap sync android
cd android
./gradlew assembleDebug
cp app/build/outputs/apk/debug/app-debug.apk ../Blaugrana-debug.apk
echo "APK created: $(pwd)/../Blaugrana-debug.apk"
