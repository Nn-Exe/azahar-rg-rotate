#!/bin/zsh
# CPU-profile the RG Rotate build on the device with simpleperf.
#
#   ./profile.sh [seconds] [package]
#
# Requires the app to be running a game already. Writes perf.data plus a symbolized
# report next to this script. The release APK ships stripped .so files, so symbolization
# uses the unstripped libraries Gradle leaves in the build tree (~440 MB, kept out of git).
# Profile the build that produced that tree, or symbol names will be wrong.
set -e
SECS=${1:-30}
PKG=${2:-org.azahar_emu.azahar.rgrotate}
NDK=$HOME/Library/Android/sdk/ndk/27.3.13750724
SP=$NDK/simpleperf
OUT=$(cd "$(dirname "$0")" && pwd)
SYMFS=$(cd "$(dirname "$0")/../.." && pwd)/src/android/app/build/intermediates/merged_native_libs/rgRotateRelease/mergeRgRotateReleaseNativeLibs/out/lib

echo "Recording ${SECS}s of $PKG ..."
python3 "$SP/app_profiler.py" -p "$PKG" -r "-e cpu-clock -f 1000 -g --duration $SECS" \
    -o "$OUT/perf.data" --ndk_path "$NDK" -lib "$SYMFS" --no_gui

echo "Top functions:"
python3 "$SP/report.py" -i "$OUT/perf.data" --symfs "$SYMFS" -g --sort dso,symbol 2>/dev/null | head -60 \
    | tee "$OUT/perf-report.txt"
echo
echo "Full report: $OUT/perf-report.txt   Raw: $OUT/perf.data"
echo "Flamegraph: python3 $SP/report_html.py -i $OUT/perf.data --symfs $SYMFS -o $OUT/perf.html"
