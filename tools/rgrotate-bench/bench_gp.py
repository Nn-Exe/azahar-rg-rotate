#!/usr/bin/env python3
# usage: bench_gp.py <tag> <hold_seconds>
# Loads the in-game save into the Route 1 overworld and measures frame times while standing still.
import subprocess, sys, os, time, struct
ADB=os.path.expanduser('~/Library/Android/sdk/platform-tools/adb')
S=os.path.dirname(os.path.abspath(__file__))
PKG='org.azahar_emu.azahar.rgrotate'; USER='/sdcard/Azahar Rotate'
tag,hold=sys.argv[1],int(sys.argv[2])
ROM='!/storage/A4D0-0DB3/roms/3ds/Pokemon Ultra Sun (USA) (En,Ja,Fr,De,Es,It,Zh,Ko).3ds'
def sh(c):
    for _ in range(3):
        r=subprocess.run([ADB,'shell',c],capture_output=True,text=True)
        if 'no devices' not in r.stdout+r.stderr: return r.stdout
        subprocess.run([ADB,'wait-for-device'],capture_output=True); time.sleep(2)
    return ''
def fg(): return PKG in sh('dumpsys window | grep mCurrentFocus')
def shot(n): open(f'{S}/{tag}_{n}.png','wb').write(subprocess.run([ADB,'exec-out','screencap','-p'],capture_output=True).stdout)
def sig():
    raw=subprocess.run([ADB,'exec-out','screencap'],capture_output=True).stdout
    if len(raw)<16: return []
    W,H,f=struct.unpack('<III',raw[:12]); hdr=16 if len(raw)>=16+W*H*4 else 12
    px=raw[hdr:]
    return [ (px[(y*W+x)*4]+px[(y*W+x)*4+1]+px[(y*W+x)*4+2])//3 for y in range(0,H,12) for x in range(0,W,12) ]
sh(f'am force-stop {PKG}'); time.sleep(2)
sh(f"am start -n {PKG}/org.citra.citra_emu.activities.EmulationActivity --es SelectedGame '{ROM}' --es SelectedTitle 'Pokemon Ultra Sun'")
time.sleep(34)
if not fg(): print('ABORT: not foreground'); sys.exit(2)
sh('input tap 423 618')            # START on title
time.sleep(9)
def region(x,y,w,h):
    raw=subprocess.run([ADB,'exec-out','screencap'],capture_output=True).stdout
    if len(raw)<16: return 0
    W,H,f=struct.unpack('<III',raw[:12]); hdr=16 if len(raw)>=16+W*H*4 else 12
    px=raw[hdr:]; t=n=0
    for yy in range(y,y+h,3):
        for xx in range(x,x+w,3):
            o=(yy*W+xx)*4; t+=px[o]+px[o+1]+px[o+2]; n+=3
    return t//max(1,n)
# In the overworld the emulated bottom screen is dark; on the Continue menu it is bright blue.
ok=False
for attempt in range(3):
    sh('input swipe 696 468 696 468 180')   # A (held; a plain tap does not register)
    time.sleep(30)
    top=region(200,100,320,120); bot=region(260,520,200,120)
    print(f'{tag}: attempt {attempt+1} top={top} bottom={bot}',flush=True)
    if top>60 and bot<90: ok=True; break
shot('scene')
if not ok:
    print('ABORT: never reached the overworld'); sh(f'am force-stop {PKG}'); sys.exit(1)
time.sleep(hold)
o=subprocess.run(['python3',f'{S}/perf_sample.py',PKG,'10'],capture_output=True,text=True).stdout
print(o.strip(),flush=True)
sh('input keyevent KEYCODE_BACK'); time.sleep(2)
sh('input swipe 230 600 230 150 500'); time.sleep(2)
sh('input tap 131 680'); time.sleep(3); sh('input tap 490 421'); time.sleep(8)
csv=sh(f"ls -t '{USER}/log/'*.csv 2>/dev/null | head -1").strip()
print('csv:',csv,flush=True)
if csv:
    subprocess.run([ADB,'pull',csv,f'{S}/{tag}.csv'],capture_output=True); sh(f"rm -f '{csv}'")
