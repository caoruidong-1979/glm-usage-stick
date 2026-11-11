#!/usr/bin/env python3
"""Bake the pixelfx campfire sprite sheet into indexed frames for the stick.

Input : the pixelfx repo's exported sheet + json for fire/campfire
        (render it first:  node tools/render.mjs fire/campfire --sheet )
Output: src/flame_frames.{h,cpp}  — 8bpp indexed frames in PROGMEM plus the
        palette/ramp tables, and tools/previews/*.png simulating the on-device
        flame screen at several remaining-quota states.

Sizing: the effect's 128x128 frames only use a middle band (flame tips ~y48,
ground glow ~y120), so the bake crops the content window and nearest-neighbour
upscales it to OUT_W x OUT_H — the fire reads ~67% bigger on the panel at a
straight 1:1 blit.

Color:  every pixel maps to the nearest of a fixed master palette built from
the effect's own ramp colors, so the 9 fire-ramp indices can be remapped at
runtime. The firmware interpolates between 5 keyframe ramps (platinum → gold
→ lava → ember → coals) for a continuous color shift as quota burns down.

Run:  python tools/bake_flame.py [path-to-pixelfx-records-fire-campfire]
"""

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
PREVIEW_DIR = ROOT / "tools" / "previews"

SRC_W, SRC_H = 128, 128
CROP_Y0, CROP_Y1 = 24, 120          # content window: flame + logs + floor glow
CROP_XC, CROP_COLS = 64, 96         # centered horizontal window
OUT_W, OUT_H = 160, 160             # panel-side frame size (nearest-neighbour x1.667)
FRAME_STRIDE = 2                    # every 2nd of the 30fps frames -> 15fps loop
FPS = 30 // FRAME_STRIDE

# Portrait (vertical full-screen) bake: narrower crop around the fire body,
# scaled to the panel's 170px width; the fire column reads taller.
V_CROP_X0, V_CROP_X1 = 20, 108
V_CROP_Y0, V_CROP_Y1 = 8, 120
V_OUT_W, V_OUT_H = 170, 216

# ── Master palette ────────────────────────────────────────────────────────
# index 0 = transparent (rendered as the screen background on device)
# 1..9   = fire ramp  (REMAPPABLE at runtime — see RAMP_KEYS below)
# 10..15 = wood ramp  (logs, untouched by remap)
# 16..18 = ash        19 = smoke
FIRE_RAMP = ["#4a1712", "#8a1f17", "#c9281f", "#f2561d", "#ff8a2a",
             "#ffc23d", "#ffe26b", "#fff3a6", "#ffffff"]
WOOD_RAMP = ["#0e080a", "#24130f", "#3b2216", "#5a3520", "#8a5a34", "#b9884f"]
ASH_RAMP = ["#2a2530", "#4a4350", "#6b6270"]
SMOKE = ["#5b5566"]

# ── Fire-ramp keyframes, interpolated by remaining quota ─────────────────
# 100% platinum (hotter/whiter than the stock ramp) · 75% gold (stock
# campfire) · 50% lava · 25% ember · 0% dying coals (ember dimmed to 55%).
LAVA = ["#14060a", "#380a10", "#6e1210", "#ac2410", "#e8501a",
        "#ff8c2a", "#ffd25a"]
EMBER = ["#1a0a0e", "#3d1012", "#701a14", "#a8301a", "#e0561e",
         "#ff8a2a", "#ffc46a"]
COALS_DIM = 0.55

RAMP_KEYS = [
    ("platinum", None),   # derived from FIRE_RAMP, pushed toward white
    ("gold", FIRE_RAMP),
    ("lava", LAVA),
    ("ember", EMBER),
    ("coals", None),      # ember * COALS_DIM
]
RAMP_KEY_REMAINING = [100.0, 75.0, 50.0, 25.0, 0.0]   # firmware mirrors this


def hx(s):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def to_rgb255(c):
    return (int(round(c[0])), int(round(c[1])), int(round(c[2])))


def resample(ramp, n):
    """Linearly resample a hex ramp to n entries, keeping both endpoints."""
    pts = np.array([hx(c) for c in ramp], dtype=np.float64)
    src_x = np.linspace(0, 1, len(pts))
    dst_x = np.linspace(0, 1, n)
    return np.stack([np.interp(dst_x, src_x, pts[:, c]) for c in range(3)], axis=1)


def key_ramp(name, ramp):
    n = len(FIRE_RAMP)
    if name == "platinum":
        base = np.array([hx(c) for c in FIRE_RAMP], dtype=np.float64)
        white = np.array([255, 255, 255], dtype=np.float64)
        # push the mid/top of the ramp toward white, keep the dark base dark
        t = np.linspace(0, 1, n) ** 1.5
        return base + (white - base) * (t * 0.55)[:, None]
    if name == "coals":
        return resample(EMBER, n) * COALS_DIM
    return resample(ramp, n) if ramp else None


def interp_ramp(remaining):
    """Continuous ramp for a remaining% — firmware does the same in fixed point."""
    keys = [key_ramp(n, r) for n, r in RAMP_KEYS]
    xs = RAMP_KEY_REMAINING
    rem = min(100.0, max(0.0, remaining))
    for i in range(len(xs) - 1):
        if xs[i] >= rem >= xs[i + 1]:
            t = (xs[i] - rem) / (xs[i] - xs[i + 1])
            return keys[i] * (1 - t) + keys[i + 1] * t
    return keys[0] if rem > 50 else keys[-1]


def rows_for(remaining):
    """Bottom-anchored crop: 100% remaining -> full frame, 0% -> logs+coals."""
    return max(8, round(OUT_H * (0.20 + 0.80 * remaining / 100.0)))


def rgb565(c):
    r, g, b = int(c[0]), int(c[1]), int(c[2])
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


def main():
    sheet_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else \
        ROOT.parent / "pixelfx" / "records" / "fire" / "campfire"
    sheet = Image.open(sheet_dir / "campfire.png").convert("RGBA")
    meta = json.load(open(sheet_dir / "campfire.json"))["meta"]["pixelfx"]
    cols, (fw, fh) = meta["columns"], meta["frameSize"]
    assert (fw, fh) == (SRC_W, SRC_H), f"unexpected frame size {fw}x{fh}"
    total = meta["frames"]

    pal_rgb = [None] + FIRE_RAMP + WOOD_RAMP + ASH_RAMP + SMOKE  # index 0 unused
    pal = np.array([[0, 0, 0]] + [hx(c) for c in pal_rgb[1:]], dtype=np.int32)
    n_pal = len(pal)

    cx0 = CROP_XC - CROP_COLS // 2
    # nearest-neighbour maps into the CROPPED window (crop-local coordinates)
    xmap = (np.arange(OUT_W) * CROP_COLS // OUT_W).astype(np.int32)
    ymap = (np.arange(OUT_H) * (CROP_Y1 - CROP_Y0) // OUT_H).astype(np.int32)
    vxmap = (np.arange(V_OUT_W) * (V_CROP_X1 - V_CROP_X0) // V_OUT_W).astype(np.int32)
    vymap = (np.arange(V_OUT_H) * (V_CROP_Y1 - V_CROP_Y0) // V_OUT_H).astype(np.int32)

    frames_idx = []
    frames_idx_v = []
    for f in range(0, total, FRAME_STRIDE):
        col, row = f % cols, f // cols
        tile = np.asarray(sheet.crop((col * fw, row * fh, (col + 1) * fw, (row + 1) * fh)))
        alpha = tile[:, :, 3].astype(np.int32)
        rgb = tile[:, :, :3].astype(np.int32)
        rgb = rgb * alpha[:, :, None] // 255          # composite over black
        crop = rgb[CROP_Y0:CROP_Y1, cx0:cx0 + CROP_COLS]
        crop_a = alpha[CROP_Y0:CROP_Y1, cx0:cx0 + CROP_COLS]

        flat = crop.reshape(-1, 3)
        d = ((flat[:, None, :] - pal[None, :, :]) ** 2).sum(axis=2)
        idx = np.argmin(d, axis=1).astype(np.uint8).reshape(crop.shape[:2])
        idx[crop_a < 40] = 0

        up = idx[ymap][:, xmap]                        # nearest-neighbour upscale
        frames_idx.append(up)

        # portrait: quantize the tall-narrow window from the same source tile
        vcrop = rgb[V_CROP_Y0:V_CROP_Y1, V_CROP_X0:V_CROP_X1]
        vcrop_a = alpha[V_CROP_Y0:V_CROP_Y1, V_CROP_X0:V_CROP_X1]
        vflat = vcrop.reshape(-1, 3)
        vd = ((vflat[:, None, :] - pal[None, :, :]) ** 2).sum(axis=2)
        vidx = np.argmin(vd, axis=1).astype(np.uint8).reshape(vcrop.shape[:2])
        vidx[vcrop_a < 40] = 0
        frames_idx_v.append(vidx[vymap][:, vxmap])
    n_frames = len(frames_idx)
    assert len(frames_idx_v) == n_frames
    print(f"quantized {n_frames} frames @ {FPS}fps, palette {n_pal} entries, "
          f"landscape crop y[{CROP_Y0}:{CROP_Y1}] x[{cx0}:{cx0 + CROP_COLS}] -> {OUT_W}x{OUT_H}, "
          f"portrait crop y[{V_CROP_Y0}:{V_CROP_Y1}] x[{V_CROP_X0}:{V_CROP_X1}] -> {V_OUT_W}x{V_OUT_H}")

    # ── emit flame_frames.h / .cpp ────────────────────────────────────────
    SRC_DIR.mkdir(exist_ok=True)
    (SRC_DIR / "flame_frames.h").write_text(
        "// Generated by tools/bake_flame.py from pixelfx fire/campfire. Do not edit.\n"
        "#pragma once\n#include <stdint.h>\n\n"
        f"#define FLAME_W {OUT_W}\n#define FLAME_H {OUT_H}\n"
        f"#define FLAME_FRAME_COUNT {n_frames}\n#define FLAME_FPS {FPS}\n"
        "#define FLAME_TRANSP_INDEX 0\n"
        f"#define FLAME_FIRE_FIRST 1\n#define FLAME_FIRE_COUNT {len(FIRE_RAMP)}\n"
        f"#define FLAME_PALETTE_LEN {n_pal}\n"
        "// fire-ramp keyframe table, interpolated by remaining quota (see ui.cpp);\n"
        "// keys sit at 100/75/50/25/0% remaining: platinum, gold, lava, ember, coals\n"
        "#define FLAME_RAMP_KEYS 5\n"
        "// portrait (vertical full-screen) variant, same frames, tall-narrow crop\n"
        f"#define FLAMEV_W {V_OUT_W}\n#define FLAMEV_H {V_OUT_H}\n"
        f"extern const uint8_t kFlameFrames[FLAME_FRAME_COUNT * FLAME_W * FLAME_H];\n"
        f"extern const uint8_t kFlameFramesV[FLAME_FRAME_COUNT * FLAMEV_W * FLAMEV_H];\n"
        f"extern const uint16_t kFlameBasePalette[FLAME_PALETTE_LEN];\n"
        "extern const uint16_t kFlameRampKeys[FLAME_RAMP_KEYS][FLAME_FIRE_COUNT];\n",
        encoding="utf-8", newline="\n")

    def emit_array(f, name, frames, w, h):
        f.write(f"const uint8_t {name}[FLAME_FRAME_COUNT * {w} * {h}] PROGMEM = {{\n")
        for i, idx in enumerate(frames):
            f.write(f"// frame {i}\n")
            for y in range(h):
                f.write(",".join(str(v) for v in idx[y]) + ",\n")
        f.write("};\n\n")

    with open(SRC_DIR / "flame_frames.cpp", "w", encoding="utf-8", newline="\n") as f:
        f.write("// Generated by tools/bake_flame.py from pixelfx fire/campfire. Do not edit.\n"
                "#include \"flame_frames.h\"\n#include <Arduino.h>\n\n")
        emit_array(f, "kFlameFrames", frames_idx, OUT_W, OUT_H)
        emit_array(f, "kFlameFramesV", frames_idx_v, V_OUT_W, V_OUT_H)
        f.write("const uint16_t kFlameBasePalette[FLAME_PALETTE_LEN] = {\n    " +
                ", ".join(f"0x{rgb565(c):04X}" for c in pal) + "\n};\n\n")
        f.write("const uint16_t kFlameRampKeys[FLAME_RAMP_KEYS][FLAME_FIRE_COUNT] = {\n")
        for name, ramp in RAMP_KEYS:
            vals = key_ramp(name, ramp)
            f.write("    { " + ", ".join(f"0x{rgb565(c):04X}" for c in vals) + " }, // " + name + "\n")
        f.write("};\n")
    kb = (n_frames * OUT_W * OUT_H + n_frames * V_OUT_W * V_OUT_H) / 1024
    print(f"wrote src/flame_frames.{{h,cpp}}  ({kb:.0f} KB of frame data)")

    # ── previews: simulate the device flame screen at several states ──────
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    SW, SH = 320, 170
    fx, fy = 4, 5                       # mirrors ui.cpp layout
    tx = fx + OUT_W + 12
    for remaining in (100, 75, 50, 25, 5, 0):
        ramp = interp_ramp(remaining)
        lut = pal.astype(np.float64).copy()
        lut[1:1 + len(FIRE_RAMP)] = ramp
        lut[0] = (0, 0, 0)
        rows = rows_for(remaining)
        canvas = np.zeros((SH, SW, 3), dtype=np.uint8)
        idx = frames_idx[12]                           # mid-loop frame
        img = lut[idx]
        img[idx == 0] = 0
        y0 = fy + (OUT_H - rows)
        canvas[y0:y0 + rows, fx:fx + OUT_W] = img[OUT_H - rows:]
        pil = Image.fromarray(canvas)
        d = ImageDraw.Draw(pil)
        d.text((tx, 6), "GLM CODING PLAN", fill=(120, 120, 120))
        top = to_rgb255(ramp[-1])
        d.text((tx, 22), f"{remaining}%", fill=top)
        d.text((tx, 58), f"ramp top RGB {top}", fill=(120, 120, 120))
        d.text((tx, 74), f"rows {rows}/{OUT_H}", fill=(120, 120, 120))
        pil.save(PREVIEW_DIR / f"state_{remaining:03d}.png")
    states = [Image.open(PREVIEW_DIR / f"state_{r:03d}.png")
              for r in (100, 50, 0)]
    montage = Image.new("RGB", (SW, SH * 3), (16, 16, 16))
    for i, s in enumerate(states):
        montage.paste(s, (0, i * SH))
    montage.save(PREVIEW_DIR / "montage.png")

    # portrait screen: 170x320, fire bottom-anchored, NO text — pure ambiance
    PW, PH = 170, 320
    pm = Image.new("RGB", (PW * 3, PH), (16, 16, 16))
    for i, remaining in enumerate((100, 50, 0)):
        ramp = interp_ramp(remaining)
        lut_p = pal.astype(np.float64).copy()
        lut_p[1:1 + len(FIRE_RAMP)] = ramp
        lut_p[0] = (0, 0, 0)
        rows = max(8, round(V_OUT_H * (0.20 + 0.80 * remaining / 100.0)))
        canvas = np.zeros((PH, PW, 3), dtype=np.uint8)
        idxv = frames_idx_v[12]
        img = lut_p[idxv]
        img[idxv == 0] = 0
        y0 = PH - rows
        canvas[y0:, :] = img[V_OUT_H - rows:]
        pm.paste(Image.fromarray(canvas), (i * PW, 0))
    pm.save(PREVIEW_DIR / "portrait.png")
    print("previews: tools/previews/state_*.png + montage.png + portrait.png")


if __name__ == "__main__":
    main()
