# Azahar for the Anbernic RG Rotate

This branch (`rg-rotate`) is a device-specific build of Azahar for the Anbernic RG Rotate:

| Part | Value |
| --- | --- |
| SoC | Unisoc Tiger T618 (2x Cortex-A75 @ 2.0 GHz + 6x Cortex-A55) |
| GPU | ARM Mali-G52 MP2 @ 850 MHz |
| RAM | 3 GB |
| Screen | 3.5" 720x720 square IPS |
| OS | Android 12 |

## Build

```sh
cd src/android
JAVA_HOME=/Library/Java/JavaVirtualMachines/openjdk-17.jdk/Contents/Home \
ANDROID_HOME=$HOME/Library/Android/sdk \
./gradlew assembleRgRotateRelease
```

Output: `src/android/app/build/outputs/apk/rgRotate/release/app-rgRotate-release.apk`

Requires SDK `cmake;3.31.6` and `ndk;27.3.13750724`.

## Changes from upstream

### Save-state crash fix (`src/core/savestate.cpp`, `src/common/zstd_stream.*`)

Upstream serialized the whole emulated state into a `std::ostringstream`, copied it out with
`str()`, and then allocated a third `ZSTD_compressBound`-sized buffer before writing. With New 3DS
mode (256 MB FCRAM) that is roughly 800 MB of transient allocations on top of the emulator's normal
footprint. On a 3 GB device Android's low-memory killer terminates the process, which looks like
an instant crash with no log. Loading did the same in reverse.

Save states are now streamed through zstd directly to and from the file with a custom
`std::streambuf`, so the peak extra memory is the zstd context plus a few hundred KB of staging
buffers. Compression level 1 keeps the pause short on the T618. The file format is unchanged
(256-byte CST header followed by one zstd frame).

### Thread priority (`src/common/thread.cpp`, `jni/native.cpp`, `vk_scheduler.cpp`)

`RaiseCurrentThreadPriority()` sets nice -8 (Android's `THREAD_PRIORITY_URGENT_DISPLAY`) on the
emulation thread and the Vulkan worker thread. Logged at startup as `EmuThread priority boost
applied`.

Big-core pinning was tried and removed: threads inherit their creator's affinity, so pinning the
emulation thread also pinned the 4 emulated-CPU threads, the Vulkan present threads and about a
dozen Mali driver threads to cores 6 and 7, leaving the six A55 cores idle.

### Smaller Vulkan upload buffer (`vk_texture_runtime.cpp`)

The texture upload staging ring is 128 MiB instead of 512 MiB. On Mali it is host-visible system
RAM, which matters on a 3 GB device.

### Measured performance

Deterministic benchmark on the device (Pokemon Ultra Sun booted with no input, frame limiter off,
identical settings in both apps, frame times compared at matching frame indices), second half of
~5,600 frames:

| Build | Run 1 | Run 2 |
| --- | --- | --- |
| Official Azahar 2126.1.1 | 21.8 ms | 23.4 ms |
| This build | 23.7 ms | 23.7 ms |

The two are at parity within run-to-run noise. This build's value is the save-state fix, the
lower memory footprint and the device defaults, not raw speed. The benchmark tooling is in
[tools/rgrotate-bench](tools/rgrotate-bench).

### Measured CPU profile (2026-09-16, Pokemon Ultra Sun, Route 1 overworld)

Recorded with `tools/rgrotate-bench/profile.sh` (30 s, 28k samples) while standing in the
overworld:

| Where | Share of CPU |
| --- | --- |
| libcitra-android.so | 23% |
| Linux kernel | 22% |
| JIT-generated code (unsymbolized) | 22% |
| Mali GL driver | 15% |
| bionic libc | 10% |

Hottest named functions: audio time-stretching (`soundtouch`, 3.3%), JIT block dispatch
(`AddressSpace::GetOrEmit`, 1.9%), `memcpy` (2.6%), PLT stubs (2.6%), mutex lock/unlock (2.6%),
`ARM_Dynarmic::SetPageTable` (1.2%), PICA command list processing (~2% across
`ProcessCmdList`/`WriteInternalReg*`). No single dominant hotspot.

During the game's intro movie the picture is different: YUV-to-RGB conversion
(`HW::Y2R::PerformConversion`) alone takes 5.8%. That is video playback only and does not occur
during normal play.

### Changes tested and rejected

Measured with `tools/rgrotate-bench/bench_gp.py`, same save, same overworld scene, frame limiter
off, mean frame time over a 3,200-frame window:

| Configuration | Frame time | vs baseline |
| --- | --- | --- |
| Baseline (New 3DS mode, audio stretching on) | 8.17 ms | — |
| Audio stretching off | 8.27 ms | 1.1% slower |
| Old 3DS mode (`is_new_3ds = 0`) | 8.28 ms | 1.3% slower |

Neither helped, so neither was adopted. Audio stretching costs measurable CPU but runs on its own
thread and is not on the critical path. Emulating 2 cores instead of 4 did not pay off either.

Note the headroom: 8.17 ms per frame is roughly 122 system frames per second, about double what
the console needs, so this scene runs at full speed with room to spare. Optimization effort should
target heavy scenes (battle animations, towns), not the overworld.

### Pokemon Omega Ruby opening movie: first-play slowdown is shader compilation

The opening movie is the heaviest reproducible scene found so far (boot, choose a language, no
further input; the language is never saved, so every relaunch repeats it). On a cold cache it runs
at about 12 FPS with a near-freeze; on a warm one it holds 29-30 FPS. Steady-state the emulation
thread sits at ~40% of one core, so this is shader compilation rather than emulation speed.

### Shader caches are portable, so a game can be pre-cached without playing it

`shaders/vulkan/` holds two different things. `transferable/*.vkch` describe the shaders and the
pipeline configurations the game asked for; they contain no driver data and work on any device.
`pipeline/*.bin` is the GPU driver's own compiled blob (named after the driver version) and is
only useful on that driver. At boot `ShaderDiskCache::Init` walks the transferable cache and builds
every entry up front behind the loading progress bar, so anything listed there never compiles
mid-game.

Measured on the device with the Omega Ruby opening movie (60 s, limiter on):

| Cache present | Frames | Seconds below full speed |
| --- | --- | --- |
| Nothing | 6,867 | 3, including a near-freeze at 0:18 |
| `transferable/` only, driver blob deleted | 9,699 | 1, at startup only |
| Both | 7,520 | 0 |

The portable half alone removes the stutter, so a cache produced by anyone who has played a game
can be dropped into a fresh install. The release ships `rgrotate-shader-cache-vulkan.zip`;
`tools/rgrotate-bench/pull_shader_cache.sh` regenerates it from a device.

### Why stutter happens at all with async shader compilation enabled

`vk_rasterizer.cpp` picks `wait_built = !async_shaders || regs.pipeline.num_vertices <= 6`, so any
draw of six or fewer vertices blocks until its shader is ready even when async compilation is on.
Full-screen quads in cutscenes and fades are exactly those draws, which is why intros stall on a
cold cache while ordinary gameplay does not. Raising that threshold would trade a missing effect
for a few frames against the stall; not attempted here.

### Settings tested on the heaviest scene available

Omega Ruby opening movie, frame limiter off to expose headroom, frame times compared at matching
frame indices (the sequence is deterministic). "100% of full speed" is calibrated from a
limiter-on run of the same scene, which measures 116 system frames per second. Note a system
frame here is a screen swap, and the 3DS has two screens, so full speed is about 116/s rather
than 60/s.

| Setting | Speed | Verdict |
| --- | --- | --- |
| Native resolution (default) | 157% | 57% headroom |
| Resolution 2x | 86% | **too slow, do not use** |
| Emulated CPU clock 75% | 157% | no effect |
| Emulated CPU clock 150% | 157% | no effect |
| Skip duplicate frames | 157% | no effect on speed |

Resolution is the only setting that moved the needle, and only upward in cost. Because the games
already run at 100% with headroom to spare at native, rendering *below* native would buy speed
that is not needed; it would only trade sharpness for battery and heat.

Sub-native scaling is also not expressible today: `res_scale` is a `u32` multiplied into every
surface dimension (`SurfaceParams::GetScaledWidth`), so fractional factors would require reworking
the rasterizer cache, and non-integer scaling is a classic source of texture alignment bugs.
Do not set resolution to Auto either: on a 720x720 panel that resolves to roughly 1.8x native,
which is in the same territory as the 2x result above.

### Defaults tuned for the device

| Setting | Upstream Android default | RG Rotate default | Why |
| --- | --- | --- | --- |
| Landscape layout | Large Screen | Original (stacked) | Square panel: stacked screens at 1.5x fill 720x720 exactly. |
| Portrait layout | Top full width | Original (stacked) | Android reports the square panel as portrait; this gives the largest top screen (600x360 over 480x360). |
| Check for updates on start | On | Off | The updater would offer official builds that lack these changes. |
| Async shader compilation (Vulkan) | Off | On | Shader compiles stall for seconds on the T618; compiling off-thread trades a few frames of missing geometry for smooth play. |
| Performance overlay | Off | On (FPS + speed) | So the effect of these changes is visible. Toggle in Settings > Layout. |

Everything else (New 3DS mode on, native resolution, hardware shaders, shader JIT, disk shader
cache, accurate multiplication off, frame limiter on) is already the best choice for this SoC.

### Build changes (`src/android/app/build.gradle.kts`)

- New `rgRotate` product flavor with package id `org.azahar_emu.azahar.rgrotate`, so it installs
  next to the official APK without a signature conflict.
- `arm64-v8a` only; the x86_64 slice is dropped.
- Link-time optimization on, `-march=armv8.2-a+crc -mtune=cortex-a75` for the T618's cores
  (enables LSE atomics and CRC instructions).
- Vulkan validation layers are no longer downloaded or packaged (debug-only, ~10 MB).

## Profile-guided optimization

The build supports PGO for the games you actually play:

1. `./gradlew assembleRgRotateRelease -Ppgo=generate` builds **Azahar RG Rotate (Profiling)**,
   a separate, slower app (package `org.azahar_emu.azahar.rgrotate.profile`) whose native code
   is instrumented. Every time emulation pauses or stops it writes counters to
   `Android/data/org.azahar_emu.azahar.rgrotate.profile/files/pgo/`.
2. Play the target games for a while, then pull the `.profraw` files and merge them as described
   in [pgo/README.md](pgo/README.md).
3. `./gradlew assembleRgRotateRelease -Ppgo=use` builds the normal app with the compiler laying
   out and inlining code according to that profile.

## After installing

The package id differs from the official app, so pick your Azahar user folder again on first run.
Save states from other builds are not loadable (Azahar locks states to the build that created
them), so create fresh ones.
