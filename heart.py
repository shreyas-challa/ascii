#!/usr/bin/env python3
"""
3D ASCII Heart — ray-marched pulsating heart with rich shading.

Builds a 3D heart from smooth-unioned sphere primitives (two mirrored
lobes + tapered body) and renders via numpy-accelerated ray marching
with Blinn-Phong shading, ambient occlusion, rim lighting, and glow.

Pulsates with a realistic lub-dub heartbeat at ~72 bpm.

Controls: Ctrl-C to quit.
"""

import math
import sys
import time
import shutil

try:
    import numpy as np
except ImportError:
    sys.stderr.write("Requires numpy: pip install numpy\n")
    sys.exit(1)

# ── 70-level ASCII shading ramp (dark → bright) ─────────────────────────────
SHADE = " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"
N_SHADE = len(SHADE)
_SHADE_LUT = np.array([ord(c) for c in SHADE], dtype=np.uint8)


# ── Heart SDF from smooth-unioned primitives ─────────────────────────────────
#
# Construction:
#   1. Two sphere lobes at (±0.65, 0.50, 0), radius 0.52 — mirrored via |x|.
#      Gap at x=0: 0.65 − 0.52 = 0.13 → produces the V-shaped cleft.
#   2. One body sphere at (0, −0.50, 0), radius 0.80 — the lower mass,
#      naturally tapers to a point at its south pole (y = −1.30).
#   3. Polynomial smooth-min (k=0.35) blends lobes into body.

def heart_f(px, py, pz):
    """Evaluate the heart SDF. Returns < 0 inside, > 0 outside."""
    x = np.abs(px)
    y = py
    z = pz

    # Upper lobes (mirrored by |x|)
    d_lobe = np.sqrt((x - 0.65)**2 + (y - 0.50)**2 + z * z) - 0.52

    # Lower body
    d_body = np.sqrt(px * px + (y + 0.50)**2 + z * z) - 0.80

    # Smooth minimum
    k = 0.35
    h = np.clip(0.5 + 0.5 * (d_body - d_lobe) / k, 0.0, 1.0)
    return d_lobe * h + d_body * (1.0 - h) - k * h * (1.0 - h)


def _normal(sx, sy, sz, eps=0.002):
    """Surface normal via central differences."""
    nx = heart_f(sx + eps, sy, sz) - heart_f(sx - eps, sy, sz)
    ny = heart_f(sx, sy + eps, sz) - heart_f(sx, sy - eps, sz)
    nz = heart_f(sx, sy, sz + eps) - heart_f(sx, sy, sz - eps)
    length = np.maximum(np.sqrt(nx * nx + ny * ny + nz * nz), 1e-12)
    return nx / length, ny / length, nz / length


# ── Rendering ────────────────────────────────────────────────────────────────

def render(cols, rows, scale, angle_y):
    """Ray-march and shade the heart. Returns a ready-to-print string."""

    inv_s = 1.0 / scale

    # Camera (orbits the heart)
    cam_dist = 3.0
    ca, sa = math.cos(angle_y), math.sin(angle_y)
    cam_x, cam_y, cam_z = cam_dist * sa, -0.15, -cam_dist * ca

    # Ray grid
    char_aspect = 2.2
    scr_aspect = (cols / rows) / char_aspect
    focal = 1.2

    u = np.linspace(-scr_aspect, scr_aspect, cols)
    v = np.linspace(0.55, -0.55, rows)
    uu, vv = np.meshgrid(u, v)

    dx, dy, dz = uu, vv, np.full_like(uu, focal)
    d_len = np.sqrt(dx * dx + dy * dy + dz * dz)
    dx /= d_len;  dy /= d_len;  dz /= d_len

    rx = dx * ca + dz * sa
    rz = -dx * sa + dz * ca
    dx, dz = rx, rz

    ox = np.full_like(uu, cam_x)
    oy = np.full_like(uu, cam_y)
    oz = np.full_like(uu, cam_z)

    # ── Ray march (fixed step + bisection) ────────────────────────────────
    shape = (rows, cols)
    hit   = np.zeros(shape, dtype=bool)
    hit_t = np.full(shape, 999.0)
    min_f = np.full(shape, 1e9)

    n_steps = 80
    t_near, t_far = 0.8, 5.5
    step_size = (t_far - t_near) / n_steps
    prev_f = None
    prev_t = t_near

    for i in range(n_steps):
        t = t_near + i * step_size
        px = ox + dx * t
        py = oy + dy * t
        pz = oz + dz * t

        f = heart_f(px * inv_s, py * inv_s, pz * inv_s)

        af = np.abs(f)
        min_f = np.where((~hit) & (af < min_f), af, min_f)

        if prev_f is not None:
            crossed = (prev_f > 0) & (f <= 0) & (~hit)
            if np.any(crossed):
                t_lo = np.where(crossed, prev_t, 0.0)
                t_hi = np.where(crossed, t, 0.0)
                for _ in range(12):
                    t_mid = 0.5 * (t_lo + t_hi)
                    mf = heart_f(
                        (ox + dx * t_mid) * inv_s,
                        (oy + dy * t_mid) * inv_s,
                        (oz + dz * t_mid) * inv_s,
                    )
                    inside = mf <= 0
                    t_hi = np.where(inside & crossed, t_mid, t_hi)
                    t_lo = np.where(~inside & crossed, t_mid, t_lo)
                hit_t = np.where(crossed, 0.5 * (t_lo + t_hi), hit_t)
                hit |= crossed

        prev_f = f
        prev_t = t
        if hit.all():
            break

    # ── Shading ───────────────────────────────────────────────────────────
    hx = ox + dx * hit_t
    hy = oy + dy * hit_t
    hz = oz + dz * hit_t
    sx, sy, sz = hx * inv_s, hy * inv_s, hz * inv_s

    nx, ny, nz = _normal(sx, sy, sz)

    vx, vy, vz = cam_x - hx, cam_y - hy, cam_z - hz
    v_len = np.maximum(np.sqrt(vx * vx + vy * vy + vz * vz), 1e-12)
    vx /= v_len;  vy /= v_len;  vz /= v_len

    ndv = nx * vx + ny * vy + nz * vz
    flip = ndv < 0
    nx = np.where(flip, -nx, nx)
    ny = np.where(flip, -ny, ny)
    nz = np.where(flip, -nz, nz)

    def _n3(a, b, c):
        l = math.sqrt(a * a + b * b + c * c)
        return a / l, b / l, c / l

    # Key light (upper-left-front)
    kl = _n3(-0.5, 0.8, -0.6)
    key_diff = np.maximum(0.0, nx * kl[0] + ny * kl[1] + nz * kl[2])

    # Blinn-Phong specular
    hh = (kl[0] + vx, kl[1] + vy, kl[2] + vz)
    hh_len = np.maximum(np.sqrt(hh[0]**2 + hh[1]**2 + hh[2]**2), 1e-12)
    hh = (hh[0] / hh_len, hh[1] / hh_len, hh[2] / hh_len)
    spec = np.maximum(0.0, nx * hh[0] + ny * hh[1] + nz * hh[2]) ** 48

    # Fill light (lower-right)
    fl = _n3(0.6, -0.3, -0.4)
    fill_diff = np.maximum(0.0, nx * fl[0] + ny * fl[1] + nz * fl[2])

    # Rim / Fresnel
    ndv2 = nx * vx + ny * vy + nz * vz
    rim = (1.0 - np.maximum(0.0, ndv2)) ** 3

    # Ambient occlusion (2-sample probe along normal)
    ao1 = heart_f(sx + nx * 0.06, sy + ny * 0.06, sz + nz * 0.06)
    ao2 = heart_f(sx + nx * 0.15, sy + ny * 0.15, sz + nz * 0.15)
    ao = np.clip(0.5 + ao1 * 8.0 + ao2 * 3.0, 0.15, 1.0)

    # Procedural surface texture
    tex = (np.sin(sx * 13 + sy * 7) * np.sin(sy * 11 + sz * 5)
           * np.sin(sz * 9 + sx * 3)) * 0.035

    # Compose
    lum = (0.05 + key_diff * 0.55 + fill_diff * 0.20
           + spec * 0.45 + rim * 0.40 + tex) * ao
    lum = np.clip(lum, 0.0, 1.0)

    # Atmospheric glow (background pixels)
    glow = np.clip(np.exp(-min_f * 12.0) * 0.25, 0.0, 0.35)
    final_lum = np.where(hit, lum, glow)

    # Map to characters
    idx = np.clip((final_lum * (N_SHADE - 1) + 0.5).astype(np.int32),
                  0, N_SHADE - 1)
    char_buf = _SHADE_LUT[idx]
    newlines = np.full((rows, 1), ord('\n'), dtype=np.uint8)
    return np.hstack([char_buf, newlines]).tobytes().decode('ascii')


# ── Animation ────────────────────────────────────────────────────────────────

def main():
    HOME  = "\x1b[H"
    HIDE  = "\x1b[?25l"
    SHOW  = "\x1b[?25h"
    CLEAR = "\x1b[2J"

    sys.stdout.write(HIDE + CLEAR)
    sys.stdout.flush()

    frame = 0
    t0 = time.monotonic()

    try:
        while True:
            t_frame = time.monotonic()

            cols, rows = shutil.get_terminal_size()
            rows = max(10, rows - 1)
            cols = max(20, cols)

            t = time.monotonic() - t0

            # Heartbeat (lub-dub at ~72 bpm)
            period = 60.0 / 72.0
            phase = (t % period) / period

            lub    = math.exp(-((phase - 0.15)**2) / 0.003) *  0.10
            dub    = math.exp(-((phase - 0.30)**2) / 0.002) *  0.06
            recoil = math.exp(-((phase - 0.50)**2) / 0.010) * -0.03
            scale  = 1.0 + lub + dub + recoil

            angle = math.sin(t * 0.35) * 0.40

            buf = render(cols, rows, scale, angle)

            elapsed = time.monotonic() - t0
            fps = frame / elapsed if elapsed > 0.01 else 0.0
            status = f" {fps:.0f} fps | Ctrl-C to quit"

            sys.stdout.write(HOME + buf + status.ljust(cols)[:cols])
            sys.stdout.flush()

            dt = time.monotonic() - t_frame
            remain = 0.04 - dt
            if remain > 0:
                time.sleep(remain)

            frame += 1

    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write(SHOW + CLEAR + HOME + "Goodbye!\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
