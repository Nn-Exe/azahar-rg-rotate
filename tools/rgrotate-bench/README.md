# RG Rotate benchmark tools

Deterministic A/B benchmark for Azahar builds on a USB-connected RG Rotate.

## Method

1. In both apps' `config.ini` set `use_frame_limit = 0` and `record_frame_times = 1`, and make
   renderer/layout settings identical.
2. Run `bench3.py`, which boots the ROM with **no game input** (so every run emulates the same
   sequence), waits, samples thread CPU usage, then closes the game through the in-game drawer.
   A clean close is required: `PerfStats` only writes its per-frame CSV (milliseconds per frame)
   in its destructor, so `am force-stop` produces nothing.
3. Compare the CSVs at matching frame indices (e.g. the second half of the shortest run).
4. Afterwards restore `use_frame_limit = 1` and `record_frame_times = 0`.

```sh
BENCH_OUT=/tmp/bench python3 bench3.py org.azahar_emu.azahar /sdcard/Azahar off_r1 100
BENCH_OUT=/tmp/bench python3 bench3.py org.azahar_emu.azahar.rgrotate "/sdcard/Azahar Rotate" mine_r1 100
```

Run each build at least twice; the first run warms the disk shader cache.

## Lessons

- Do not script gameplay navigation by tapping: scene detection from screenshots misfires and
  taps advance cutscenes, so two builds end up measuring different scenes.
- `am start` with extras: pass the ROM path in single quotes inside one `adb shell` string, or
  literal quote characters end up in the path and the game never loads.
- The coordinates in the drawer-close sequence assume the 720x720 panel.
