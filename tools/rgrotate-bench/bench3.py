#!/usr/bin/env python3
# usage: bench3.py <package> <userdir> <tag> <run_seconds>
# Deterministic: boots the ROM and sends NO game input, so both builds emulate the same sequence.
# Frame times are compared at matching frame indices afterwards.
import subprocess, sys, os, time
ADB=os.path.expanduser('~/Library/Android/sdk/platform-tools/adb')
S=os.environ.get('BENCH_OUT', os.path.dirname(os.path.abspath(__file__)))
pkg,userdir,tag,secs=sys.argv[1],sys.argv[2],sys.argv[3],int(sys.argv[4])
ROM='!/storage/A4D0-0DB3/roms/3ds/Pokemon Ultra Sun (USA) (En,Ja,Fr,De,Es,It,Zh,Ko).3ds'
def sh(c): return subprocess.run([ADB,'shell',c],capture_output=True,text=True).stdout
def focus(): return sh('dumpsys window | grep mCurrentFocus')
def shot(n): open(f'{S}/{tag}_{n}.png','wb').write(subprocess.run([ADB,'exec-out','screencap','-p'],capture_output=True).stdout)
sh(f'am force-stop {pkg}'); time.sleep(2)
sh(f"am start -n {pkg}/org.citra.citra_emu.activities.EmulationActivity --es SelectedGame '{ROM}' --es SelectedTitle 'Pokemon Ultra Sun'")
time.sleep(10)
if pkg not in focus(): print('ABORT launch:',focus().strip()); sys.exit(2)
print(f'{tag}: running {secs}s with no input',flush=True)
time.sleep(secs)
if pkg not in focus(): print('ABORT: lost foreground:',focus().strip()); sys.exit(2)
shot('end')
o=subprocess.run(['python3',f'{S}/perf_sample.py',pkg,'10'],capture_output=True,text=True).stdout
print(o.strip(),flush=True)
# close via drawer so PerfStats writes its CSV
sh('input keyevent KEYCODE_BACK'); time.sleep(2)
sh('input swipe 230 600 230 150 500'); time.sleep(2)
if pkg not in focus(): print('ABORT drawer:',focus().strip()); sys.exit(2)
sh('input tap 131 680'); time.sleep(3); sh('input tap 490 421'); time.sleep(8)
csv=sh(f"ls -t '{userdir}/log/'*.csv 2>/dev/null | head -1").strip()
print('csv:',csv,flush=True)
if csv:
    subprocess.run([ADB,'pull',csv,f'{S}/{tag}.csv'],capture_output=True); sh(f"rm -f '{csv}'")
