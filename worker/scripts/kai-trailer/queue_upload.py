"""Queue hand-made Kai clips as pending_review (nothing posts)."""
import json, subprocess, sys
from datetime import datetime
from pathlib import Path
from clipworker.config import load_settings, env
from clipworker.remote.supabase import Supabase
from clipworker.qa import check_clip, CampaignRules
FF, FP = r"C:\clip-work\bin\ffmpeg.exe", r"C:\clip-work\bin\ffprobe.exe"
D = Path(r"C:\clip-work\renders\kai-trailer")
load_settings(Path(r"C:\clip-work\Clipping\worker\config\channels.toml"))
sb = Supabase(env("SUPABASE_URL", required=True), env("SUPABASE_SERVICE_ROLE_KEY", required=True))
st = sb.select("streamers", slug="eq.kaicenat", select="id,pod_id")[0]
rec_start = datetime(2026, 11, 22, 1, 51, 57).astimezone()   # screen recording file name, local time
CLIPS = {
 "on_point": dict(title="Kai Cenat's new job comes with a LIFE sentence 💀", hook="You can't get caught. So be on point.",
                  description="the job interview was crazy 💀\n#kaicenat #streamer #movie"),
 "cold_open": dict(title="Kai Cenat walking in like the rent is 3 months LATE 😭", hook="Kai walks up to the door",
                   description="the knock said everything 😭\n#kaicenat #streamer #movie"),
}
for k, meta in CLIPS.items():
    C = json.loads((D / f"clip_{k}.json").read_text(encoding="utf-8")); clip = D / (C["file"] + ".mp4")
    thumb = D / (C["file"] + "_thumb.jpg")
    subprocess.run([FF, "-v", "error", "-y", "-ss", "2", "-i", str(clip), "-frames:v", "1", "-q:v", "3", str(thumb)], check=True)
    qa = check_clip(clip, None, CampaignRules(min_s=10, max_s=30, permitted=True), title=meta["title"], ffmpeg=FF, ffprobe=FP)
    dur = float(subprocess.run([FP, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(clip)], capture_output=True, text=True).stdout)
    print(k, "qa", qa.passed, qa.failures)
    if not qa.passed: continue
    job = f"kai-movie-{k.replace('_', '-')}"; base = f"kaicenat/{job}"
    sb.upload(f"{base}/clip.mp4", clip, "video/mp4"); sb.upload(f"{base}/thumb.jpg", thumb, "image/jpeg")
    sb.insert("clips", {"job_id": job, "streamer_id": st["id"], "campaign_id": None, "channel_key": "twitch:kaicenat",
        "state": "pending_review", "title": meta["title"], "hook": meta["hook"], "description": meta["description"],
        "category": "funny", "moment_at": (rec_start.timestamp() + C["in"]) and datetime.fromtimestamp(rec_start.timestamp() + C["in"]).astimezone().isoformat(),
        "duration_s": round(dur, 2), "storage_path": f"{base}/clip.mp4", "thumb_path": f"{base}/thumb.jpg", "source_path": None,
        "qa": {"passed": qa.passed, "fails": qa.failures, "metrics": qa.metrics, "duration": dur, "zoom": False},
        "pod_id": st["pod_id"],
        "manifest": {"manual": True, "video": str(clip), "source": r"Desktop\ScreenRecording_11-22-2026 01-51-57_1.mov", "recipe": C,
                     "duration": round(dur, 2), "fps": 59.94, "caption_version": "headline-v1", "zooms": []}},
        on_conflict="job_id", ignore_duplicates=True)
    print("queued", base)
