"""Kai Cenat movie-stream trailer: 9:16, letterboxed widescreen band, headline in top bar, fade in/out."""
import subprocess, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter
FF = r"C:\clip-work\bin\ffmpeg.exe"
SRC = r"C:\Users\HOME!\Desktop\ScreenRecording_11-22-2026 01-51-57_1.mov"
CROP = "1790:852:0:48"             # drops viewer count, chat, sub counter, minimap
BAND_H = round(1080 * 852 / 1790 / 2) * 2
BAND_Y = (1920 - BAND_H) // 2
import json
C = json.loads(open(sys.argv[1], encoding="utf-8").read())
T_IN, T_OUT, TEXT, FI, FO, OUT = C["in"], C["out"], C["text"], C["fade_in"], C["fade_out"], C["file"]
EMOJI = "C:/clip-work/assets/emoji/apple_" + C["emoji"] + ".png"
SIZE = 60

f = ImageFont.truetype(r"C:\Windows\Fonts\Poppins-SemiBold.ttf", SIZE)
words, lines, cur = TEXT.split(), [], ""
for w in words:
    t = (cur + " " + w).strip()
    if f.getlength(t + " XX") > 900 and cur: lines.append(cur); cur = w
    else: cur = t
lines.append(cur)
if "|" in TEXT: lines = [l.strip() for l in TEXT.split("|")]
em = Image.open(EMOJI).convert("RGBA").resize((SIZE, SIZE), Image.LANCZOS)
lh = int(SIZE * 1.25); im = Image.new("RGBA", (1080, lh * len(lines) + 20)); d = ImageDraw.Draw(im)
for i, l in enumerate(lines):
    lw = f.getlength(l) + (em.width + 12 if i == len(lines) - 1 else 0)
    x, y = (1080 - lw) / 2, 10 + i * lh
    d.text((x, y), l, font=f, fill="white", stroke_width=2, stroke_fill=(0, 0, 0, 200))
    if i == len(lines) - 1: im.alpha_composite(em, (int(x + f.getlength(l) + 12), int(y + (lh - SIZE) / 2)))
im.save(OUT + "_headline.png"); HY = BAND_Y - im.height - 40

dur = T_OUT - T_IN
VF = ",".join(x for x in [f"fade=in:st=0:d={FI}" if FI else "", f"fade=out:st={dur-FO}:d={FO}" if FO else ""] if x) or "null"
fc = (f"[0:v]trim={T_IN}:{T_OUT},setpts=PTS-STARTPTS,crop={CROP},scale=1080:{BAND_H}:flags=lanczos:in_range=pc:out_range=tv,format=yuv420p,setsar=1[v];"
      f"color=black:s=1080x1920:r=60000/1001:d={dur}[bg];[bg][v]overlay=0:{BAND_Y}[b];"
      f"[b][1:v]overlay=0:{HY}:shortest=1,format=yuv420p,{VF}[out];"
      f"[0:a]atrim={T_IN}:{T_OUT},asetpts=PTS-STARTPTS,afade=in:st=0:d={0.4 if FI else 0.03},afade=out:st={dur-(FO or 0.05)}:d={FO or 0.05},"
      f"loudnorm=I=-14:TP=-1.5:LRA=11[a]")
subprocess.run([FF, "-v", "error", "-y", "-i", SRC, "-loop", "1", "-i", OUT + "_headline.png", "-filter_complex", fc,
    "-map", "[out]", "-map", "[a]", "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-r", "60000/1001",
    "-color_range", "tv", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", "-t", str(dur), OUT + ".mp4"], check=True)
print("band", BAND_H, BAND_Y, "headline y", HY)
