"""Facecam AI upscale (default since 2026-11-24): Real-ESRGAN realesr-general-x4v3 weights run in our own
SRVGGNetCompact; no third-party code. Weights audited and hash-pinned (vault 'Tools and Repos'); model path from
CLIP_SR_MODEL, default C:/clip-work/models. torch is imported lazily so the worker runs without it (no SR)."""
import hashlib
import os
import subprocess
from pathlib import Path

MODEL = Path(os.environ.get("CLIP_SR_MODEL", r"C:\clip-work\models\realesr-general-x4v3.pth"))
SHA256 = "8dc7edb9ac80ccdc30c3a5dca6616509367f05fbc184ad95b731f05bece96292"


def _net():
    import torch
    from torch import nn

    class SRVGGNetCompact(nn.Module):
        def __init__(self, feat=64, convs=32, scale=4):
            super().__init__()
            layers = [nn.Conv2d(3, feat, 3, 1, 1), nn.PReLU(feat)]
            for _ in range(convs):
                layers += [nn.Conv2d(feat, feat, 3, 1, 1), nn.PReLU(feat)]
            layers.append(nn.Conv2d(feat, 3 * scale * scale, 3, 1, 1))
            self.body, self.up, self.scale = nn.Sequential(*layers), nn.PixelShuffle(scale), scale

        def forward(self, x):
            return self.up(self.body(x)) + nn.functional.interpolate(x, scale_factor=self.scale, mode="nearest")


    return SRVGGNetCompact


def load_model(device):
    if hashlib.sha256(MODEL.read_bytes()).hexdigest() != SHA256:
        raise RuntimeError(f"{MODEL} hash mismatch; re-audit before use")
    import torch
    m = _net()()
    m.load_state_dict(torch.load(MODEL, map_location="cpu", weights_only=True)["params"], strict=True)
    m.eval().to(device)
    return m.half() if device == "cuda" else m


def upscale_region(source, ss, t, crop, out, fps=60, batch=8, mix=1.0, ffmpeg="ffmpeg"):
    """Crop (x,y,w,h) from source[ss:ss+t], 4x upscale every frame, write a near-lossless mp4. Cached by args.
    mix<1 blends the AI result with a bicubic upscale to keep skin/hair texture."""
    x, y, w, h = crop
    out = Path(out)
    key = hashlib.sha1(f"{source}|{ss:.3f}|{t:.3f}|{crop}|{fps}|{mix}|{SHA256}".encode()).hexdigest()[:12]
    stamp = out.with_suffix(".key")
    if out.exists() and stamp.exists() and stamp.read_text() == key:
        return out
    import numpy as np
    import torch
    from torch import nn
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    m = load_model(dev)
    W4, H4 = w * 4, h * 4
    rd = subprocess.Popen([ffmpeg, "-v", "error", "-ss", f"{ss:.3f}", "-t", f"{t:.3f}", "-i", str(source),
                           "-vf", f"fps={fps},crop={w}:{h}:{x}:{y}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                          stdout=subprocess.PIPE)
    wr = subprocess.Popen([ffmpeg, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W4}x{H4}",
                           "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "fast", "-crf", "8",
                           "-pix_fmt", "yuv444p", str(out)], stdin=subprocess.PIPE)
    fsz, n = w * h * 3, 0
    with torch.inference_mode():
        while True:
            buf = []
            for _ in range(batch):
                b = rd.stdout.read(fsz)
                if len(b) < fsz: break
                buf.append(np.frombuffer(b, np.uint8).reshape(h, w, 3))
            if not buf: break
            xb = torch.from_numpy(np.stack(buf)).to(dev).permute(0, 3, 1, 2)
            xb = (xb.half() if dev == "cuda" else xb.float()) / 255.0
            yb = m(xb)
            if mix < 1.0:
                yb = mix * yb + (1 - mix) * nn.functional.interpolate(xb, scale_factor=4, mode="bicubic")
            yb = yb.clamp_(0, 1).mul_(255).round_().byte().permute(0, 2, 3, 1).cpu().numpy()
            wr.stdin.write(yb.tobytes()); n += len(buf)
    wr.stdin.close(); wr.wait(); rd.wait()
    if wr.returncode or n == 0:
        raise RuntimeError(f"sr upscale failed ({n} frames)")
    stamp.write_text(key)
    return out

