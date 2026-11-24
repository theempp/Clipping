"""Generate 10 ZowoStudio YouTube banners (2560x1440) as HTML, render with headless Chrome.
Visual language taken from the user's reference banner: black/white, heavy geometric sans,
outlined repeated name, diagonal white band, ringed circle mark, plus signs, dot rows, soft waves.
YouTube safe area (all devices): 1546x423 centered -> x 507..2053, y 508..931.
"""
import subprocess, pathlib, sys

HERE = pathlib.Path(__file__).parent
OUT = HERE.parent
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
NAME = "ZOWOSTUDIO"

BASE_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@500;600;700;800;900&display=block');
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:2560px;height:1440px;overflow:hidden}
body{position:relative;font-family:'Montserrat',sans-serif;color:#fff;background:#141414}
.abs{position:absolute}
.ol{color:transparent;-webkit-text-stroke:2px rgba(255,255,255,.16);font-weight:900;white-space:nowrap;letter-spacing:.02em}
.ol.dk{-webkit-text-stroke:2px rgba(0,0,0,.12)}
.plus{position:absolute;font-weight:600;font-size:64px;line-height:1;transform:translate(-50%,-50%)}
.dots{position:absolute;background-image:radial-gradient(circle,#fff 42%,transparent 46%);}
.ring{position:absolute;border-radius:50%;transform:translate(-50%,-50%)}
.ring img{width:100%;height:100%;display:block;border-radius:50%}
.band{position:absolute;transform-origin:center}
.h{font-weight:900;line-height:.9;white-space:nowrap;letter-spacing:.01em}
.waves{position:absolute;inset:0}
"""

def waves(c1="#1c1c1c", c2="#181818", c3="#111"):
    return f"""<svg class="waves" viewBox="0 0 2560 1440" preserveAspectRatio="none">
<path d="M0 560 C 520 430, 980 650, 1500 560 S 2300 430, 2560 520 L2560 0 L0 0Z" fill="{c1}"/>
<path d="M0 980 C 600 860, 1100 1080, 1650 960 S 2350 900, 2560 980 L2560 1440 L0 1440Z" fill="{c2}"/>
<path d="M0 1120 C 700 1040, 1300 1200, 1900 1100 S 2400 1060, 2560 1100 L2560 1440 L0 1440Z" fill="{c3}"/>
</svg>"""

def plus(x, y, color="#fff", size=64):
    return f'<div class="plus" style="left:{x}px;top:{y}px;color:{color};font-size:{size}px">+</div>'

def dots(x, y, cols, rows, gap=26, size=9, color="#fff"):
    w, h = cols * gap, rows * gap
    bg = f"radial-gradient(circle,{color} {size/2}px,transparent {size/2+1}px)"
    return (f'<div class="abs" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px;'
            f'background-image:{bg};background-size:{gap}px {gap}px"></div>')

def ring(cx, cy, d, logo="logo-dark.png", border="#fff", bw=14, gap=12, gapc="#000"):
    return (f'<div class="ring" style="left:{cx}px;top:{cy}px;width:{d}px;height:{d}px;'
            f'border:{bw}px solid {border};padding:{gap}px;background:{gapc}">'
            f'<img src="{logo}"></div>')

def band(cx, cy, w, h=2600, rot=28, color="#fff"):
    return (f'<div class="band" style="left:{cx-w/2}px;top:{cy-h/2}px;width:{w}px;height:{h}px;'
            f'background:{color};transform:rotate({rot}deg)"></div>')

def olrow(text, x, y, size, cls="ol", reps=3, gap="0.45em"):
    t = (f'<span style="margin-right:{gap}">{text}</span>') * reps
    return f'<div class="abs {cls}" style="left:{x}px;top:{y}px;font-size:{size}px">{t}</div>'

B = {}

# 01 Signature: closest remix of the reference layout
B["01-signature"] = ("#141414", waves() + """
""" + olrow(NAME, 120, 300, 190, reps=2) + olrow(NAME, -260, 470, 190, reps=2)
  + olrow(NAME, 1180, 900, 190, reps=2) + olrow(NAME, 1500, 1070, 190, reps=2)
  + band(1320, 720, 170) + ring(1290, 720, 400)
  + """<div class="abs" style="right:1640px;top:575px;text-align:right">
  <div class="h" style="font-size:132px">ZOWO</div>
  <div style="font-weight:800;font-size:64px;letter-spacing:.32em;margin-top:22px;margin-right:-.32em">STUDIO</div>
  <div style="height:8px;width:330px;background:#fff;margin:22px 0 0 auto"></div></div>"""
  + plus(820, 560) + plus(2010, 560) + plus(800, 900) + plus(2010, 900)
  + dots(1620, 640, 6, 2) + dots(1620, 760, 3, 1))

# 02 Inverse: same system flipped to light
B["02-inverse"] = ("#efefef", waves("#e6e6e6", "#e9e9e9", "#e2e2e2")
  + olrow(NAME, 140, 300, 190, "ol dk", 2) + olrow(NAME, 1200, 980, 190, "ol dk", 2)
  + band(1240, 720, 150, rot=-28, color="#0f0f0f")
  + ring(1240, 720, 380, "logo-dark.png", "#0f0f0f", 14, 12, "#efefef")
  + """<div class="abs" style="left:1500px;top:600px;color:#0f0f0f">
  <div class="h" style="font-size:150px">ZOWO</div>
  <div style="display:flex;align-items:center;gap:26px;margin-top:20px">
   <div style="height:8px;width:120px;background:#0f0f0f"></div>
   <div style="font-weight:800;font-size:60px;letter-spacing:.34em">STUDIO</div></div></div>"""
  + plus(720, 600, "#0f0f0f") + plus(980, 860, "#0f0f0f") + plus(2020, 560, "#0f0f0f")
  + dots(640, 760, 8, 2, color="#0f0f0f"))

# 03 Split: diagonal black/white halves, mark on the seam
B["03-split"] = ("#0f0f0f", """
<div class="abs" style="inset:0;background:#f1f1f1;clip-path:polygon(1480px 0,2560px 0,2560px 1440px,1080px 1440px)"></div>
""" + olrow(NAME, -100, 330, 170, reps=1) + olrow(NAME, 1700, 960, 170, "ol dk", 1)
  + ring(1280, 720, 360, "logo-dark.png", "#fff", 14, 12, "#000")
  + """<div class="abs h" style="right:1520px;top:650px;font-size:160px">ZOWO</div>
<div class="abs h" style="left:1520px;top:650px;font-size:160px;color:#0f0f0f">STUDIO</div>"""
  + plus(620, 560) + plus(1960, 900, "#0f0f0f") + dots(1700, 560, 10, 1, color="#0f0f0f")
  + dots(640, 880, 10, 1))

# 04 Type wall: outlined rows fill the canvas, one solid line in the middle
rows = "".join(olrow(NAME, (-300 if i % 2 else 0), 60 + i * 185, 170, reps=4) for i in range(8) if i != 3 and i != 4)
B["04-type-wall"] = ("#111", rows
  + """<div class="abs" style="left:0;right:0;top:575px;height:290px;background:#111"></div>
<div class="abs" style="left:0;right:0;top:575px;height:4px;background:#fff"></div>
<div class="abs" style="left:0;right:0;top:861px;height:4px;background:#fff"></div>"""
  + ring(700, 720, 230, "logo-dark.png", "#fff", 10, 8)
  + """<div class="abs h" style="left:860px;top:655px;font-size:150px">ZOWO<span style="color:transparent;-webkit-text-stroke:3px #fff">STUDIO</span></div>"""
  + plus(2010, 640, size=56) + plus(2010, 800, size=56))

# 05 Big mark: oversized negative watermark of the logo bleeding off the right edge
B["05-big-mark"] = ("#0e0e0e", waves("#151515", "#131313", "#101010")
  + '<img class="abs" src="logo-light.png" style="left:1540px;top:-140px;width:1720px;opacity:.07">'
  + '<img class="abs" src="logo-light.png" style="left:600px;top:560px;width:300px">'
  + """<div class="abs" style="left:960px;top:598px">
  <div class="h" style="font-size:170px">ZOWOSTUDIO</div>
  <div style="display:flex;align-items:center;gap:24px;margin-top:26px">
   <div style="height:8px;width:260px;background:#fff"></div>
   <div style="font-weight:600;font-size:34px;letter-spacing:.4em;color:#bdbdbd">ZOWO · STUDIO</div></div></div>"""
  + plus(560, 520, size=50) + plus(2040, 920, size=50) + dots(1720, 540, 6, 2))

# 06 Crossbands: two diagonal bands form an X behind the mark
B["06-crossbands"] = ("#131313", waves()
  + olrow(NAME, 80, 330, 160, reps=2) + olrow(NAME, 1100, 1000, 160, reps=2)
  + band(1280, 720, 110, rot=32) + band(1280, 720, 110, rot=-32)
  + ring(1280, 720, 380)
  + """<div class="abs h" style="right:1530px;top:655px;font-size:150px">ZOWO</div>
<div class="abs h" style="left:1530px;top:655px;font-size:150px">STUDIO</div>"""
  + plus(1280, 455, size=48) + plus(1280, 985, size=48) + dots(640, 860, 7, 1) + dots(1740, 540, 7, 1))

# 07 Minimal: centred mark, spaced wordmark, crop-mark pluses at the safe-area corners
B["07-minimal"] = ("#0f0f0f", ""
  + '<img class="abs" src="logo-light.png" style="left:1160px;top:520px;width:240px">'
  + """<div class="abs" style="left:0;right:0;top:800px;text-align:center;font-weight:800;font-size:66px;letter-spacing:.55em;margin-right:-.55em">ZOWOSTUDIO</div>
<div class="abs" style="left:1200px;top:900px;width:160px;height:6px;background:#fff"></div>"""
  + plus(560, 550, "#6f6f6f", 52) + plus(2000, 550, "#6f6f6f", 52) + plus(560, 890, "#6f6f6f", 52) + plus(2000, 890, "#6f6f6f", 52)
  + olrow(NAME, 260, 60, 150, reps=2) + olrow(NAME, 900, 1180, 150, reps=2))

# 08 Dot field: halftone dot texture fading to the centre, ringed mark + stacked type
B["08-dot-field"] = ("#101010", """
<div class="abs" style="inset:0;background-image:radial-gradient(circle,rgba(255,255,255,.22) 3px,transparent 4px);background-size:34px 34px;
 -webkit-mask-image:radial-gradient(ellipse 1100px 520px at 50% 50%,transparent 45%,#000 100%)"></div>"""
  + ring(820, 720, 360)
  + """<div class="abs" style="left:1060px;top:560px">
  <div class="h" style="font-size:170px">ZOWO</div>
  <div class="h" style="font-size:170px;color:transparent;-webkit-text-stroke:3px #fff;margin-top:10px">STUDIO</div></div>"""
  + plus(1990, 600) + plus(1990, 840) + dots(1700, 900, 8, 1))

# 09 Stack: huge two-line type, logo stands in for the final O of ZOWO
B["09-stack"] = ("#121212", waves()
  + """<div class="abs" style="left:560px;top:505px">
  <div class="h" style="font-size:228px;display:flex;align-items:center">ZOW<img src="logo-light.png" style="width:192px;margin-left:10px;margin-top:-6px"></div>
  <div class="h" style="font-size:228px;color:transparent;-webkit-text-stroke:3px #fff;margin-top:6px">STUDIO</div></div>"""
  + band(1980, 720, 120, rot=28)
  + plus(1700, 560) + plus(2030, 900, "#0f0f0f") + dots(1640, 860, 4, 2))

# 10 Orbit: rings echo the reference avatar ring outward from the mark
rings = "".join(
    f'<div class="ring" style="left:1280px;top:660px;width:{d}px;height:{d}px;border:2px solid rgba(255,255,255,{o})"></div>'
    for d, o in [(420, .5), (600, .3), (820, .18), (1100, .12), (1460, .08), (1900, .06), (2500, .04)])
B["10-orbit"] = ("#0f0f0f", rings
  + ring(1280, 660, 300, bw=12, gap=10)
  + """<div class="abs" style="left:0;right:0;top:850px;text-align:center;font-weight:900;font-size:76px;letter-spacing:.3em;margin-right:-.3em">ZOWOSTUDIO</div>"""
  + plus(760, 660) + plus(1800, 660) + dots(560, 900, 5, 1) + dots(1870, 900, 5, 1))


# 03 refined. Seam runs (1480,0)->(1080,1440) and crosses the centre (1280,720).
# The angle perpendicular to the seam is 105.5deg, so two-tone ring borders split exactly on it.
DARK = "polygon(0 0,1480px 0,1080px 1440px,0 1440px)"
LIGHT = "polygon(1480px 0,2560px 0,2560px 1440px,1080px 1440px)"
SEAM_L = "polygon(0 0,63.9% 0,36.1% 100%,0 100%)"      # left of seam inside a square box
SEAM_R = "polygon(63.9% 0,100% 0,100% 100%,36.1% 100%)"

def split_ring(d=330, split_logo=True):
    bw, gap = 12, 12
    inner = d - 2 * bw - 2 * gap
    if split_logo:
        logo = (f'<img src="logo-light.png" class="abs" style="left:0;top:0;width:{inner}px;height:{inner}px;clip-path:{SEAM_L}">'
                f'<img src="logo-dark.png" class="abs" style="left:0;top:0;width:{inner}px;height:{inner}px;clip-path:{SEAM_R}">')
    else:
        logo = f'<img src="logo-dark.png" class="abs" style="left:0;top:0;width:{inner}px;height:{inner}px">'
    return (f'<div class="abs" style="left:{1280-d/2}px;top:{720-d/2}px;width:{d}px;height:{d}px;border-radius:50%;'
            f'background:linear-gradient(105.5deg,#fff 50%,#0f0f0f 50%);padding:{bw}px">'
            f'<div style="width:100%;height:100%;border-radius:50%;padding:{gap}px;'
            f'background:linear-gradient(105.5deg,#0f0f0f 50%,#f1f1f1 50%)">'
            f'<div style="position:relative;width:{inner}px;height:{inner}px">{logo}</div></div></div>')

def split_v2(split_logo, plain=False):
    dark_side = (f'<div class="abs" style="inset:0;clip-path:{DARK}">' + waves("#181818", "#151515", "#121212")
                 + olrow(NAME, -60, 300, 170, reps=1) + olrow(NAME, -420, 960, 170, reps=1) + '</div>')
    light_side = (f'<div class="abs" style="inset:0;background:#f1f1f1;clip-path:{LIGHT}">'
                  + waves("#e9e9e9", "#ececec", "#e6e6e6")
                  + olrow(NAME, 1380, 300, 170, "ol dk", 1) + olrow(NAME, 1640, 960, 170, "ol dk", 1)
                  # thin black stripe parallel to the seam, echoing the reference band
                  + band(1390, 720, 22, h=1600, rot=15.5, color="#0f0f0f") + '</div>')
    text = """
<div class="abs" style="right:1500px;top:640px;text-align:right">
  <div class="h" style="font-size:128px">ZOWO</div>
  <div style="height:8px;width:230px;background:#fff;margin:26px 0 0 auto"></div></div>
<div class="abs" style="left:1500px;top:640px;color:#0f0f0f">
  <div class="h" style="font-size:128px">STUDIO</div>
  <div style="height:8px;width:230px;background:#0f0f0f;margin-top:26px"></div></div>"""
    return ("#0f0f0f", dark_side + light_side + (ring(1280, 720, 330) if plain else split_ring(330, split_logo)) + text
            + plus(600, 560) + plus(600, 880) + plus(1990, 560, "#0f0f0f") + plus(1990, 880, "#0f0f0f")
            + dots(760, 860, 8, 1) + dots(1600, 556, 8, 1, color="#0f0f0f"))

B["03-split-v2"] = split_v2(True)
B["03-split-v2b"] = split_v2(False)
B["03-split-v3"] = split_v2(False, plain=True)  # same single ring + logo as 01


def page(bg, body):
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>{BASE_CSS}</style></head>'
            f'<body style="background:{bg}">{body}</body></html>')


def main(only=None):
    for key, (bg, body) in B.items():
        if only and key not in only:
            continue
        html = HERE / f"{key}.html"
        html.write_text(page(bg, body), encoding="utf-8")
        png = OUT / f"zowostudio-banner-{key}.png"
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        "--window-size=2560,1440", "--virtual-time-budget=6000",
                        f"--screenshot={png}", html.as_uri()],
                       check=True, capture_output=True)
        print("ok", png.name)


if __name__ == "__main__":
    main(sys.argv[1:] or None)
