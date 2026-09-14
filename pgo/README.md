# Profile-guided optimization data

`rgrotate.profdata` is produced from `.profraw` files written by the profiling build
(`./gradlew assembleRgRotateRelease -Ppgo=generate`) while playing on the RG Rotate:

```sh
NDK=$HOME/Library/Android/sdk/ndk/27.3.13750724/toolchains/llvm/prebuilt/darwin-x86_64
adb pull /sdcard/Android/data/org.azahar_emu.azahar.rgrotate.profile/files/pgo ./raw
$NDK/bin/llvm-profdata merge -output=rgrotate.profdata raw/*.profraw
```

Then build the optimized app with `./gradlew assembleRgRotateRelease -Ppgo=use`.

The profile is tied to the exact source revision it was recorded on. Re-record after
changing native code, or the `-fprofile-use` build will silently ignore stale functions.
