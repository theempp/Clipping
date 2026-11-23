"""BBL revision: hook ('what does BBL stand for?') -> rewind flashback -> setup ('natural BBL').
Builds a 16:9 composite, then the normal pipeline renders (layout, captions, zooms) + QA + uploads."""
import json, subprocess, sys
from dataclasses import replace
from pathlib import Path
from clipworker.config import load_settings, env
from clipworker.remote.supabase import Supabase
from clipworker.remote.rights import RightsGate
from clipworker.pipeline import Pipeline
from clipworker.store import Store

cfg, scratch = Path(sys.argv[1]), Path(sys.argv[2])
apply = len(sys.argv) > 3 and sys.argv[3] == "apply"
JOB, VOD, VOFF = "9c657122a680439b", r"C:\clip-work\vods\lacy-2937465519\vod_60-240m.mp4", 3600.0
A, B = (27.90, 31.00), (12.15, 22.75)   # seconds from capture start
RW = 1.2                                # rewind length (D112: intense VHS rewind + tape sound)
s = replace(load_settings(cfg), work_dir=scratch)
ff = env("FFMPEG_BIN", "ffmpeg")
store = Store(Path(r"C:\clip-work\dryrun\20261123-024738\dryrun.sqlite3"))
job = store.job(JOB)
cap0 = job.data["capture"]["start_ts"]
wfile = scratch / "bbl_words.json"   # original window words (the job row holds v2's remapped ones)
if not wfile.exists():
    from clipworker.transcribe import WhisperXTranscriber
    wav0 = scratch / "bbl_window.wav"; wav0.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([env("FFMPEG_BIN", "ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{cap0 - VOFF:.3f}",
                    "-t", "40", "-i", VOD, "-vn", "-ac", "1", "-ar", "16000", str(wav0)], check=True)
    wfile.write_text(json.dumps([{"start": w.start, "end": w.end, "text": w.text}
                                 for w in WhisperXTranscriber.auto().transcribe(str(wav0))]))
orig_words = json.loads(wfile.read_text())
t0 = cap0 - VOFF + B[0] - 1                       # read once, from just before B
a0, a1 = A[0] - B[0] + 1, A[1] - B[0] + 1
b0, b1 = 1.0, B[1] - B[0] + 1
r_n = round((A[0] - B[0]) * 60 / (RW * 60))      # keep every n-th frame of the B..A gap
d = scratch / "bbl"; d.mkdir(parents=True, exist_ok=True)
out, wav = d / "composite.mp4", d / "composite.wav"
shake = "crop=iw-48:ih-48:24+24*sin(n*1.7):24+24*cos(n*2.3),scale=1920:1080,setsar=1"
fc = (f"[0:v]fps=60,scale=1920:1080,setsar=1,split=3[va][vr][vb];"
      f"[va]trim={a0}:{a1},setpts=PTS-STARTPTS,fade=out:st={a1-a0-0.08}:d=0.08:color=white[A];"
      f"[vr]trim={b0}:{a0},select='not(mod(n\,{r_n}))',setpts=N/60/TB,reverse,trim=0:{RW},setpts=PTS-STARTPTS,"
      f"{shake},rgbashift=rh=-30:bh=30:gv=6,eq=saturation=0.7:contrast=1.12:brightness=0.10:gamma=1.15,"
      f"noise=alls=38:allf=t+u,vignette=PI/6,gblur=sigma=1.2,"
      f"fade=in:st=0:d=0.1:color=white,fade=out:st={RW-0.15}:d=0.15:color=white[R0];"
      f"color=c=white@0.45:s=1920x26:r=60:d={RW},format=rgba[bar1];color=c=white@0.3:s=1920x12:r=60:d={RW},format=rgba[bar2];"
      f"[R0][bar1]overlay=x=0:y='mod(t*3180,H)':shortest=1[R1];[R1][bar2]overlay=x=0:y='mod(t*1860+400,H)':shortest=1,format=yuv420p[R];"
      f"[vb]trim={b0}:{b1},setpts=PTS-STARTPTS,fade=in:st=0:d=0.35:color=white[B];"
      f"[A][R][B]concat=n=3:v=1:a=0[v];"
      f"[0:a]aformat=sample_rates=48000:channel_layouts=stereo,asplit=3[aa][ar][ab];"
      f"[aa]atrim={a0}:{a1},asetpts=PTS-STARTPTS,afade=out:st={a1-a0-0.1}:d=0.1,aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[AA];"
      # tape rewind: the skipped audio reversed, sped up ~13x via sample-rate trick, flutter + band-limit
      f"[ar]atrim={b0}:{a0},asetpts=PTS-STARTPTS,areverse,asetrate=48000*{(a0-b0)/RW:.3f},aresample=48000,"
      f"atrim=0:{RW},highpass=f=300,lowpass=f=7000,tremolo=f=18:d=0.6,volume=0.9,"
      f"afade=in:d=0.08,afade=out:st={RW-0.2}:d=0.2[RWS];"
      f"anoisesrc=r=48000:a=0.25:c=pink:d={RW},highpass=f=800,aformat=channel_layouts=stereo,"
      f"afade=in:d={RW*0.8:.2f},afade=out:st={RW-0.1}:d=0.1[RISE];"
      f"[RWS][RISE]amix=inputs=2:normalize=0,aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[AR];"
      f"[ab]atrim={b0}:{b1},asetpts=PTS-STARTPTS,afade=in:d=0.25,aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[AB];"
      f"[AA][AR][AB]concat=n=3:v=0:a=1,loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[a]")
print("segments: A", a1 - a0, "rewind", RW, "B", b1 - b0)
if not apply:
    sys.exit()
subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{t0:.3f}", "-t", f"{A[1]-B[0]+2:.3f}",
                "-i", VOD, "-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset",
                "veryfast", "-crf", "16", "-c:a", "aac", "-b:a", "192k", str(out)], check=True)
subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y", "-i", str(out), "-ac", "1", "-ar", "16000", str(wav)], check=True)
la, lb0 = A[1] - A[0], (A[1] - A[0]) + RW
words = [{**w, "start": w["start"] - A[0], "end": w["end"] - A[0]} for w in orig_words
         if A[0] <= w["start"] and w["end"] <= A[1]]
words += [{**w, "start": w["start"] - B[0] + lb0, "end": w["end"] - B[0] + lb0} for w in orig_words
          if B[0] <= w["start"] and w["end"] <= B[1]]
total = lb0 + (B[1] - B[0])
data = job.data
data["capture"] = {**data["capture"], "video": str(out), "audio": str(wav), "end_ts": data["capture"]["start_ts"] + total}
data["peak_ts"] = data["capture"]["start_ts"] + 1.5   # punch-in on the hook line
data["words"] = words
data["judgment"] = {**data["judgment"], "trim_in": 0.0, "trim_out": total,
                    "title": "What does BBL stand for?", "hook": "Wait, what does BBL stand for?"}
data["title"] = "What does BBL stand for?"
store.db.execute("update jobs set data=? where id=?", (json.dumps(data), JOB)); store.db.commit()
sb = Supabase(env("SUPABASE_URL", required=True), env("SUPABASE_SERVICE_ROLE_KEY", required=True))
clip = sb.select("clips", job_id=f"eq.{JOB}", select="*")[0]
r = sb.http.get(f"{sb.url}/storage/v1/object/{sb.bucket}/{clip['storage_path']}", headers=sb.h); r.raise_for_status()
(d / "orig.mp4").write_bytes(r.content)
sb.upload(clip["storage_path"].rsplit("/", 1)[0] + "/clip.v2.mp4", d / "orig.mp4", "video/mp4")
pipe = Pipeline(s, store, RightsGate(lambda: [], roster=set()), None, None, sb)
res = pipe._rerender(clip, store.job(JOB), {"zoom": False}, "What does BBL stand for?", (clip.get("revision") or 0) + 1)
print("uploaded" if res else "QA FAILED", total)
