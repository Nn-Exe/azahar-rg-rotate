#!/usr/bin/env python3
# usage: perf_sample.py <package> <seconds>
import subprocess, sys, time, os
ADB=os.path.expanduser('~/Library/Android/sdk/platform-tools/adb')
pkg=sys.argv[1]; secs=float(sys.argv[2]) if len(sys.argv)>2 else 10
def sh(cmd): return subprocess.run([ADB,'shell',cmd],capture_output=True,text=True).stdout
pid=sh(f'pidof {pkg}').split()[0]
def threads():
    out=sh(f'for t in /proc/{pid}/task/*; do echo "$(cat $t/comm)|$(cat $t/stat)"; done')
    d={}
    for l in out.splitlines():
        if '|' not in l: continue
        name,stat=l.split('|',1)
        f=stat.rsplit(')',1)[1].split()
        if len(f)>15: d.setdefault(name.strip(),[]).append(int(f[11])+int(f[12]))
    return {k:sum(v) for k,v in d.items()}
def freq(c): return int(sh(f'cat /sys/devices/system/cpu/cpu{c}/cpufreq/scaling_cur_freq') or 0)//1000
layers=[l.strip() for l in sh('dumpsys SurfaceFlinger --list').splitlines() if 'SurfaceView' in l and pkg+'/' in l and 'Background' not in l]
for L in layers: sh(f"dumpsys SurfaceFlinger --latency-clear '{L}'")
t0=threads(); f0=(freq(6),freq(0)); time.sleep(secs); t1=threads(); f1=(freq(6),freq(0))
for k in ('NativeEmulation','VulkanWorker','mali-cmar-backe','AudioTrack'):
    if k in t0 and k in t1: print(f"{k:16s} {100*(t1[k]-t0[k])/100/secs:5.0f}% of one core")
print(f"cpu6 (A75) {f0[0]}->{f1[0]} MHz   cpu0 (A55) {f0[1]}->{f1[1]} MHz")
best=None
for L in layers:
    out=sh(f"dumpsys SurfaceFlinger --latency '{L}'").splitlines()
    ts=sorted({int(p[1]) for p in (l.split() for l in out[1:]) if len(p)==3 and p[1].isdigit() and 0<int(p[1])<9e18})
    if len(ts)>2 and (best is None or len(ts)>len(best[1])): best=(L,ts)
if best:
    L,ts=best; span=(ts[-1]-ts[0])/1e9
    gaps=[(b-a)/1e6 for a,b in zip(ts,ts[1:])]; gaps.sort()
    print(f"presented: {len(ts)} frames / {span:.1f}s = {len(ts)/span:.1f} fps  (median gap {gaps[len(gaps)//2]:.1f} ms, worst {gaps[-1]:.0f} ms)")
else: print("no frame timestamps")
