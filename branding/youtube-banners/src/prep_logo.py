import sys
from PIL import Image, ImageFilter, ImageOps, ImageDraw
src = sys.argv[1]
im = Image.open(src).convert("L")
im = im.resize((im.width*2, im.height*2), Image.LANCZOS)
b = im.point(lambda v: 255 if v > 128 else 0)
# flood-fill outside white region from corner -> mark as 128
ImageDraw.floodfill(b, (0, 0), 128)
disc = b.point(lambda v: 0 if v == 128 else 255).filter(ImageFilter.MinFilter(7)).filter(ImageFilter.GaussianBlur(1.4))
bbox = disc.point(lambda v: 255 if v > 20 else 0).getbbox()
pad = 6
bbox = (bbox[0]-pad, bbox[1]-pad, bbox[2]+pad, bbox[3]+pad)
gray = im.crop(bbox); a = disc.crop(bbox)
dark = Image.merge("RGBA", (gray, gray, gray, a))           # black disc, white marks
inv = ImageOps.invert(gray)
light = Image.merge("RGBA", (inv, inv, inv, a))             # white disc, black marks
# marks only (white shapes, transparent elsewhere)
marks_a = Image.composite(gray, Image.new("L", gray.size, 0), a.point(lambda v: 255 if v > 250 else 0))
white = Image.new("L", gray.size, 255)
marks = Image.merge("RGBA", (white, white, white, marks_a))
for n, img in [("logo-dark.png", dark), ("logo-light.png", light), ("logo-marks.png", marks)]:
    img.save(n); print(n, img.size)
