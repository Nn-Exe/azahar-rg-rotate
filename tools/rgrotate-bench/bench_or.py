#!/usr/bin/env python3
# usage: bench_or.py <tag> <seconds>
# Deterministic heavy scene: boot Omega Ruby, two A presses (language + confirm), then the
# opening movie plays with no further input. Frame limiter must be OFF to expose headroom.
import subprocess, sys, os, time
ADB=os.path.expanduser('~/Library/Android/sdk/platform-tools/adb')
S=os.path.dirname(os.path.abspath(__file__))
PKG='org.azahar_emu.azahar.rgrotate'; USER='/sdcard/Azahar Rotate'
ROM='!/storage/A4D0-0DB3/roms/3ds/Pokemon Omega Ruby (USA) (En,Ja,Fr,De,Es,It,Ko) (Rev 2).3ds'
tag,secs=sys.argv[1],int(sys.argv[2])
def sh(c):
    for _ in range(3):
        r=subprocess.run([ADB,'shell',c],capture_output=True,text=True)
        if 'no devices' not in r.stdout+r.stderr: return r.stdout
        subprocess.run([ADB,'wait-for-device'],capture_output=True); time.sleep(2)
    return ''
def shot(n): open(f'{S}/{tag}_{n}.png','wb').write(subprocess.run([ADB,'exec-out','screencap','-p'],capture_output=True).stdout)
sh(f'am force-stop {PKG}'); time.sleep(2)
sh(f"rm -f {USER}/log/*.csv".replace('Azahar Rotate','Azahar\\ Rotate'))
sh(f"am start -n {PKG}/org.citra.citra_emu.activities.EmulationActivity --es SelectedGame '{ROM}' --es SelectedTitle 'Pokemon Omega Ruby'")
time.sleep(42)
if PKG not in sh('dumpsys window | grep mCurrentFocus'): print('ABORT: not foreground'); sys.exit(2)
sh('input swipe 696 468 696 468 180'); time.sleep(5)
sh('input swipe 696 468 696 468 180')
time.sleep(secs)
shot('scene')
o=subprocess.run(['python3',f'{S}/perf_sample.py',PKG,'10'],capture_output=True,text=True).stdout
print(o.strip(),flush=True)
sh('input keyevent KEYCODE_BACK'); time.sleep(2)
sh('input swipe 230 600 230 150 500'); time.sleep(2)
sh('input tap 131 680'); time.sleep(3); sh('input tap 490 421'); time.sleep(8)
csv=sh("ls -t /sdcard/Azahar\\ Rotate/log/*.csv 2>/dev/null | head -1").strip()
print('csv:',csv,flush=True)
if csv:
    subprocess.run([ADB,'pull',csv,f'{S}/{tag}.csv'],capture_output=True); sh(f"rm -f '{csv}'")
