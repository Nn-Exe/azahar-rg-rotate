# Azahar RG Rotate

**An unofficial build of the [Azahar](https://github.com/azahar-emu/azahar) Nintendo 3DS emulator, tuned exclusively for the Anbernic RG Rotate.**

> This is not an official Azahar release and is not affiliated with or endorsed by the Azahar team.
> All of the emulator is their work. This repository only carries a small set of device-specific
> changes on top of it. If you are not using an RG Rotate, use the official builds from
> [azahar-emu.org](https://azahar-emu.org) instead. Bugs in this build should be reported here,
> not to the Azahar team.

## Credit

Azahar is developed by the [Azahar Emulator Project](https://github.com/azahar-emu/azahar) and its
contributors, continuing the legacy of Citra. Everything that makes this emulator work, from the
CPU JIT to the Vulkan renderer to the Android app, is theirs. Please support the upstream project.
The original upstream README is kept as [README.upstream.md](README.upstream.md).

This build is licensed under the same terms as Azahar: GPLv2 or any later version. See
[license.txt](license.txt).

## Why this exists

The RG Rotate is a weak, low-memory handheld:

| Part | Value |
| --- | --- |
| SoC | Unisoc Tiger T618 (2x Cortex-A75 @ 2.0 GHz + 6x Cortex-A55) |
| GPU | ARM Mali-G52 MP2 @ 850 MHz |
| RAM | 3 GB |
| Screen | 3.5" 720x720 square IPS |
| OS | Android 12 |

The official Android build assumes more RAM and a phone-shaped screen. On this device, save
states crashed the emulator every time. This build fixes those and sets defaults that fit the hardware. Nothing here is a
general improvement to Azahar; it is specific to this device.

## Download and install

Grab the latest `azahar-rgrotate-release.apk` from the
[Releases](../../releases) page and sideload it. It installs as a separate app named
**"Azahar RG Rotate"** (package `org.azahar_emu.azahar.rgrotate`), so it can live next to the
official app without conflicts. On first launch, pick your Azahar user folder again. Save states
from other builds cannot be loaded (Azahar locks states to the build that created them).

## What is changed

Full technical details are in [RG_ROTATE.md](RG_ROTATE.md). In short:

### 1. Save states no longer crash (the actual bug fix)

Upstream `SaveState` serialized the whole emulated state into memory, copied it, then allocated a
third worst-case buffer before compressing. With New 3DS mode that is roughly 800 MB of temporary
allocations, and on a 3 GB device Android's low-memory killer terminates the process mid-save,
which looks like an instant crash with no log. Loading had the same problem in reverse.

Save states are now streamed through zstd directly to and from disk with a custom stream buffer
(`src/common/zstd_stream.*`, `src/core/savestate.cpp`). Peak extra memory drops from ~800 MB to
under 1 MB. The file format is unchanged. Verified on the device: quick save and load work on
titles that crashed 100% of the time before.

The root-cause analysis was shared with the Azahar team in
[azahar-emu/azahar#2557](https://github.com/azahar-emu/azahar/pull/2557) so it can be fixed
properly upstream.

### 2. Emulation thread priority

The emulation thread and the Vulkan worker thread run at Android's urgent-display priority so
background apps cannot push them out of the run queue. An earlier version also pinned these
threads to the two Cortex-A75 cores; that was removed because every thread they create (the
emulated CPU cores, the Vulkan present threads and the Mali driver's own workers) inherits the
pin, crowding the whole emulator onto two cores.

### 3. Defaults that fit the device

| Setting | Official default | This build | Why |
| --- | --- | --- | --- |
| Landscape layout | Large Screen | Original (stacked) | Stacked screens at 1.5x fill the 720x720 panel exactly. |
| Portrait layout | Top full width | Original (stacked) | Android reports the square panel as portrait; this gives the largest top screen. |
| Async shader compilation | Off | On | Shader compiles stall for seconds on this CPU. |
| Performance overlay | Off | On (FPS + speed) | So you can see how a game is doing. Toggle in Settings > Layout. |
| Check for updates | On | Off | The updater would replace this build with an official one. |

Vulkan stays the default renderer, as upstream.

### 4. Build changes

- Separate `rgRotate` product flavor with its own package id and app name.
- `arm64-v8a` only, link-time optimization, `-march=armv8.2-a+crc -mtune=cortex-a75`.
- Vulkan validation layers not packaged (debug-only, saves ~10 MB).

## Building

```sh
git clone --recursive https://github.com/Nn-Exe/azahar-rg-rotate.git
cd azahar-rg-rotate/src/android
./gradlew assembleRgRotateRelease
```

Requires JDK 17, Android SDK with `cmake;3.31.6` and `ndk;27.3.13750724`. Output:
`app/build/outputs/apk/rgRotate/release/app-rgRotate-release.apk`.

## Disclosure

The changes in this repository were developed with the assistance of an AI coding tool (Claude
Code) and verified by a human on the actual device. Because of the upstream project's
[AI policy](AI-POLICY.md), this code is not being submitted to Azahar as a contribution; only the
root-cause analysis was shared with them.
