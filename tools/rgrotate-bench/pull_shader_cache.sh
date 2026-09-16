#!/bin/zsh
# Pull the device's warmed Vulkan shader caches into a zip for the GitHub release.
#   ./pull_shader_cache.sh [user-folder-on-device] [out.zip]
ADB=$HOME/Library/Android/sdk/platform-tools/adb
USER=${1:-/sdcard/Azahar Rotate}; OUT=${2:-rgrotate-shader-cache-vulkan.zip}
T=$(mktemp -d); $ADB pull "$USER/shaders/vulkan" "$T/" >/dev/null && (cd "$T" && zip -qr "$OLDPWD/$OUT" vulkan) && echo "wrote $OUT"; rm -rf "$T"
