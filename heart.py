#!/usr/bin/env python3
"""
3D ASCII Heart — Demoscene-style terminal animation.

Renders the implicit heart surface:
    f(x,y,z) = (x^2 + 9/4*y^2 + z^2 - 1)^3 - x^2*z^3 - 9/80*y^2*z^3 = 0

Strategy (inspired by a][ donut):
  - Pre-compute a dense point cloud on the surface by scanning a 3D grid
    and keeping every voxel near f=0.
  - Each frame: rotate all points, perspective-project, z-buffer, shade
    using the analytic gradient for Lambertian lighting.

Controls: Ctrl-C to quit.
"""

import math
import sys
import time
import shutil

# ── Shading ramp (space = background, rightward = brighter) ─────────────────
SHADE_CHARS = " .,:;!*+?S#%@"
N_SHADES = len(SHADE_CHARS)

# ── Implicit heart equation ─────────────────────────────────────────────────
# f(x,y,z) = (x² + 9/4·y² + z² − 1)³ − x²·z³ − 9/80·y²·z³

def heart_f(x, y, z):
    """Evaluate the heart equation. Returns 0 on the surface."""
    a = x*x + 2.25*y*y + z*z - 1.0
    z3 = z*z*z
    return a*a*a - x*x*z3 - 0.1125*y*y*z3

def heart_grad(x, y, z):
    """Analytic gradient of f — used as the surface normal.

    a  = x² + 9/4·y² + z² − 1
    df/dx = 6a²·x   − 2x·z³
    df/dy = 13.5a²·y − 0.225y·z³
    df/dz = 6a²·z    − 3x²z²  − 0.3375y²z²
    """
    a  = x*x + 2.25*y*y + z*z - 1.0
    a2 = a*a
    z2 = z*z
    z3 = z2*z
    return (6.0*a2*x   - 2.0*x*z3,
            13.5*a2*y  - 0.225*y*z3,
            6.0*a2*z   - 3.0*x*x*z2 - 0.3375*y*y*z2)

# ── Surface sampling via 3D voxel grid ──────────────────────────────────────
# Scan a bounding box, keep points where |f| < threshold. This is brute-force
# but guarantees full coverage of the heart surface including all lobes.

def sample_surface(res=90, threshold=0.02):
    """Return parallel arrays (px, py, pz, nx, ny, nz) of surface points.

    res      — grid divisions per axis (higher = denser, slower startup)
    threshold — isosurface thickness |f| < threshold
    """
    # Bounding box for the heart (empirically determined)
    lo, hi = -1.5, 1.5

    step = (hi - lo) / res
    pts_x, pts_y, pts_z = [], [], []
    nrm_x, nrm_y, nrm_z = [], [], []

    for ix in range(res + 1):
        x = lo + ix * step
        for iy in range(res + 1):
            y = lo + iy * step
            for iz in range(res + 1):
                z = lo + iz * step

                val = heart_f(x, y, z)
                if abs(val) < threshold:
                    # Compute surface normal from gradient
                    gx, gy, gz = heart_grad(x, y, z)
                    gl = math.sqrt(gx*gx + gy*gy + gz*gz)
                    if gl > 1e-10:
                        gx /= gl; gy /= gl; gz /= gl
                    else:
                        continue   # degenerate point, skip

                    pts_x.append(x)
                    pts_y.append(y)
                    pts_z.append(z)
                    nrm_x.append(gx)
                    nrm_y.append(gy)
                    nrm_z.append(gz)

    return pts_x, pts_y, pts_z, nrm_x, nrm_y, nrm_z

# ── Main animation loop ────────────────────────────────────────────────────

def main():
    # -- Sample surface once --------------------------------------------------
    sys.stdout.write("\x1b[2J\x1b[HSampling heart surface...")
    sys.stdout.flush()

    # res=90 gives ~20-30k points — good density for a full-screen render
    px, py, pz, nx_, ny_, nz_ = sample_surface(res=90, threshold=0.018)
    N = len(px)

    sys.stdout.write(f"\r{N} surface points sampled.     \n")
    sys.stdout.flush()
    time.sleep(0.3)

    # -- Light direction (normalised) — front upper-right --------------------
    Lx, Ly, Lz = 0.6, 0.6, -0.8
    Ll = math.sqrt(Lx*Lx + Ly*Ly + Lz*Lz)
    Lx /= Ll; Ly /= Ll; Lz /= Ll

    # -- ANSI codes -----------------------------------------------------------
    HOME  = "\x1b[H"       # cursor to (0, 0)
    HIDE  = "\x1b[?25l"    # hide cursor
    SHOW  = "\x1b[?25h"    # show cursor
    CLEAR = "\x1b[2J"      # clear screen

    sys.stdout.write(HIDE + CLEAR)
    sys.stdout.flush()

    frame = 0
    t0 = time.monotonic()

    try:
        while True:
            tf = time.monotonic()

            # -- Terminal size ------------------------------------------------
            cols, rows = shutil.get_terminal_size()
            rows = max(6, rows - 2)    # leave room for status bar
            cols = max(20, cols)

            # -- Time ---------------------------------------------------------
            t = frame * 0.03

            # -- Pulsation (heartbeat) ----------------------------------------
            # Asymmetric: fast systole (contraction), slower diastole (relax)
            beat_phase = (t * 2.0) % (2.0 * math.pi)
            pulse = math.sin(beat_phase)
            pulse = pulse * abs(pulse)            # sharpen the beat
            scale_factor = 1.0 + 0.08 * pulse    # ±8 % size change

            # -- Scale to fit terminal ----------------------------------------
            # Heart spans ~3 units (from -1.5 to 1.5). We want it to fill
            # roughly 70% of the smaller screen dimension.
            #
            # Projection: sx = cols/2 + K1 * x2 * ooz * aspect
            # At model centre ooz ≈ 1/K2, so:
            #   K1 * 1.5 / K2 * aspect  should ≈ cols * 0.35
            #   K1 * 1.5 / K2           should ≈ rows * 0.35
            #
            # Solving for K1 with the K2 factor included:
            K2 = 5.0
            aspect = 2.0

            desired_half_x = cols * 0.38   # how many chars from centre to edge
            desired_half_y = rows * 0.38

            need_K1_x = desired_half_x * K2 / (1.5 * aspect)
            need_K1_y = desired_half_y * K2 / 1.5

            K1 = min(need_K1_x, need_K1_y) * scale_factor

            # -- Rotation angles ----------------------------------------------
            # A = slow rock around X,  B = continuous spin around Y
            A = math.sin(t * 0.15) * 0.35        # gentle nod ±20°
            B = t * 0.45                          # ~26°/s Y spin

            sinA, cosA = math.sin(A), math.cos(A)
            sinB, cosB = math.sin(B), math.cos(B)

            # -- Clear buffers ------------------------------------------------
            sz = cols * rows
            output = bytearray(b' ' * sz)         # char buffer (bytes)
            zbuf   = [-1e9] * sz                   # depth buffer

            # -- Project each point -------------------------------------------
            for i in range(N):
                # Original point — remap so heart stands upright:
                #   Heart eq z-axis has lobes (z>0) and tip (z<0).
                #   We want z → screen-Y (up), x → screen-X, y → depth.
                x0 = px[i]          # model x → screen x
                y0 = -pz[i]         # model z → screen y (negate: z>0 lobes = screen up)
                z0 = py[i]          # model y → depth

                # --- Rotate around X axis (angle A) — gentle nod ---
                y1 = y0 * cosA - z0 * sinA
                z1 = y0 * sinA + z0 * cosA

                # --- Rotate around Y axis (angle B) — continuous spin ---
                x2 = x0 * cosB + z1 * sinB
                z2 = -x0 * sinB + z1 * cosB

                # --- Perspective projection ---
                ooz = 1.0 / (z2 + K2)

                # Screen coordinates (centred)
                sx = int(cols  * 0.5 + K1 * x2 * ooz * aspect)
                sy = int(rows * 0.5 + K1 * y1 * ooz)

                if not (0 <= sx < cols and 0 <= sy < rows):
                    continue

                idx = sy * cols + sx

                # Z-buffer: closer points have smaller z2 (camera at −K2)
                # We want to draw the point closest to the camera, i.e. with
                # the smallest z2, so store as −z2 and keep the maximum.
                depth = -z2
                if depth <= zbuf[idx]:
                    continue
                zbuf[idx] = depth

                # --- Rotate normal (same remapping + rotations) ---
                nnx = nx_[i]
                nny = -nz_[i]       # same remap as positions
                nnz = ny_[i]

                nny1 = nny * cosA - nnz * sinA
                nnz1 = nny * sinA + nnz * cosA

                nnx2 = nnx * cosB + nnz1 * sinB
                nnz2 = -nnx * sinB + nnz1 * cosB

                # --- Lambertian shading ---
                # dot(normal, light). The normal should point outward
                # (toward the camera). If it points away, flip it.
                dot = nnx2 * Lx + nny1 * Ly + nnz2 * Lz

                # If normal's z-component points toward camera (−Z),
                # that's "outward". If it points +Z, it's inward → flip.
                if nnz2 > 0:
                    dot = -dot

                # Map luminance [0, 1] → shade index
                # Ambient term (0.15) keeps the dark side visible
                lum = max(0.0, dot) * 0.85 + 0.15
                lum = max(0.0, min(1.0, lum))
                si = int(lum * (N_SHADES - 1) + 0.5)
                si = max(0, min(N_SHADES - 1, si))

                output[idx] = ord(SHADE_CHARS[si])

            # -- Assemble output string ---------------------------------------
            lines = []
            for r in range(rows):
                s = r * cols
                lines.append(output[s:s + cols].decode('ascii'))

            elapsed = time.monotonic() - t0
            fps = (frame / elapsed) if elapsed > 0.01 else 0
            status = f" {N} pts | {fps:.0f} fps | Ctrl-C quit"
            lines.append(status.ljust(cols))

            # Write entire frame in one syscall → no flicker
            sys.stdout.write(HOME + '\n'.join(lines))
            sys.stdout.flush()

            # -- Frame-rate cap (~30 fps) -------------------------------------
            dt = time.monotonic() - tf
            rem = 0.033 - dt
            if rem > 0:
                time.sleep(rem)

            frame += 1

    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write(SHOW + CLEAR + HOME + "Goodbye!\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
