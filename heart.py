#!/usr/bin/env python3
"""
3D ASCII Heart Animation
Renders a pulsating, rotating 3D heart using implicit surface equation.
Uses ANSI escape codes for terminal control, z-buffer for depth sorting,
and depth-based ASCII shading.
"""

import math
import os
import sys
import time

# ASCII shading characters from dark to bright
SHADES = " .:-=+*#%@"

# Heart surface equation: (x² + (9/4)y² + z² - 1)³ - x²z³ - (9/80)y²z³ = 0
def heart_equation(x, y, z):
    """
    Evaluate the implicit 3D heart equation.
    Returns value close to 0 when point is on surface.
    """
    a = x * x + (9.0 / 4.0) * y * y + z * z - 1.0
    return a * a * a - x * x * z * z * z - (9.0 / 80.0) * y * y * z * z * z

def sample_heart_surface(num_theta=100, num_phi=80):
    """
    Sample points on heart surface using parametric approximation.
    Uses spherical parameterization adjusted to match implicit equation.
    """
    points = []
    
    for i in range(num_theta):
        theta = 2.0 * math.pi * i / num_theta
        for j in range(num_phi):
            phi = math.pi * j / num_phi
            
            # Base spherical coordinates
            x = math.sin(phi) * math.cos(theta)
            y = math.sin(phi) * math.sin(theta)
            z = math.cos(phi)
            
            # Transform sphere into heart shape
            # Flatten top to create atrial separation
            if z > 0.3:
                # Create cleft between atria
                cleft = abs(math.sin(theta))
                if cleft < 0.3:
                    z -= 0.4 * (0.3 - cleft)
                z *= 0.85
            
            # Elongate bottom (ventricles)
            if z < 0:
                z *= 1.3
            
            # Flatten sides
            r_xy = math.sqrt(x * x + y * y)
            if r_xy > 0:
                flatten = 0.9 + 0.1 * abs(y) / r_xy
                x *= flatten
                y *= flatten * 0.67  # y scaling from equation (9/4 factor)
            
            # Verify point is on implicit surface
            if abs(heart_equation(x, y, z)) < 0.5:
                points.append((x, y, z))
    
    return points

def rotate_3d(x, y, z, angle_x, angle_y, angle_z=0):
    """
    Rotate point around X, Y, and Z axes using rotation matrices.
    Order: Z -> Y -> X rotation (intrinsic rotations).
    """
    # Rotate around Z axis
    cos_z, sin_z = math.cos(angle_z), math.sin(angle_z)
    x1 = x * cos_z - y * sin_z
    y1 = x * sin_z + y * cos_z
    x, y = x1, y1
    
    # Rotate around Y axis
    cos_y, sin_y = math.cos(angle_y), math.sin(angle_y)
    x1 = x * cos_y + z * sin_y
    z1 = -x * sin_y + z * cos_y
    x, z = x1, z1
    
    # Rotate around X axis
    cos_x, sin_x = math.cos(angle_x), math.sin(angle_x)
    y1 = y * cos_x - z * sin_x
    z1 = y * sin_x + z * cos_x
    y, z = y1, z1
    
    return x, y, z

def project_3d_to_2d(x, y, z, width, height, fov=80):
    """
    Perspective projection from 3D to 2D screen coordinates.
    FOV controls the field of view (larger = more zoomed out).
    Returns (screen_x, screen_y, depth) or (-1, -1, -999) if behind camera.
    """
    # Camera distance
    distance = 50
    
    # Perspective divide
    if z + distance > 0:
        factor = fov / (z + distance)
        screen_x = width / 2 + x * factor * 2.0  # x2 for aspect ratio
        screen_y = height / 2 - y * factor
        return int(screen_x), int(screen_y), z
    return -1, -1, -999

def get_terminal_size():
    """Get terminal dimensions using stty or environment variables."""
    try:
        # Try using shutil (Python 3.3+)
        import shutil
        size = shutil.get_terminal_size()
        return size.columns, size.lines
    except:
        # Fallback to environment variables
        return int(os.environ.get('COLUMNS', 80)), int(os.environ.get('LINES', 24))

def render_frame(points, width, height, rot_x, rot_y, rot_z, scale):
    """
    Render a single frame with z-buffer and depth shading.
    Returns buffer as list of strings (one per row).
    """
    # Initialize empty buffer and z-buffer
    buffer = [[' ' for _ in range(width)] for _ in range(height)]
    z_buffer = [[-float('inf') for _ in range(width)] for _ in range(height)]
    
    for x, y, z in points:
        # Apply pulsation scale
        x *= scale
        y *= scale
        z *= scale
        
        # Apply 3D rotation
        xr, yr, zr = rotate_3d(x, y, z, rot_x, rot_y, rot_z)
        
        # Project to 2D
        px, py, depth = project_3d_to_2d(xr, yr, zr, width, height)
        
        if px < 0:
            continue
        
        # Check bounds
        if 0 <= px < width and 0 <= py < height:
            # Z-buffer: only draw if this point is closer
            if depth > z_buffer[py][px]:
                z_buffer[py][px] = depth
                
                # Depth-based shading (normalized to shade range)
                # Map depth from [-25, 25] to [0, len(SHADES)-1]
                shade_idx = int((depth + 25) / 50 * (len(SHADES) - 1))
                shade_idx = max(0, min(len(SHADES) - 1, shade_idx))
                buffer[py][px] = SHADES[shade_idx]
    
    return [''.join(row) for row in buffer]

def clear_screen():
    """Clear terminal using ANSI escape codes (no flicker)."""
    # \033[2J = clear entire screen
    # \033[H = move cursor to home position (0,0)
    sys.stdout.write('\033[2J\033[H')
    sys.stdout.flush()

def hide_cursor():
    """Hide terminal cursor for cleaner animation."""
    sys.stdout.write('\033[?25l')
    sys.stdout.flush()

def show_cursor():
    """Show terminal cursor."""
    sys.stdout.write('\033[?25h')
    sys.stdout.flush()

def main():
    """Main animation loop."""
    # Sample heart surface once (reusable points)
    print("Sampling heart surface...")
    points = sample_heart_surface(num_theta=120, num_phi=90)
    print(f"Generated {len(points)} surface points")
    time.sleep(0.5)
    
    # Setup terminal
    hide_cursor()
    clear_screen()
    
    try:
        frame_count = 0
        start_time = time.time()
        
        while True:
            frame_start = time.time()
            
            # Get current terminal size
            width, height = get_terminal_size()
            # Leave room for stats line
            height = max(5, height - 1)
            width = max(20, width)
            
            # Animation parameters based on time
            t = frame_count * 0.05
            
            # Pulsation: sinusoidal scale factor (heartbeat effect)
            # Two-phase pulsation for realistic heartbeat
            pulse = math.sin(t * 2) * 0.5 + 0.5  # 0 to 1
            scale = 16.0 + 3.0 * pulse
            
            # Continuous rotation around multiple axes
            rot_x = t * 0.3  # Rotate around X
            rot_y = t * 0.5  # Rotate around Y (faster)
            rot_z = t * 0.1  # Slow Z rotation for extra 3D effect
            
            # Render frame
            frame = render_frame(points, width, height, rot_x, rot_y, rot_z, scale)
            
            # Calculate FPS
            elapsed = time.time() - start_time
            fps = frame_count / elapsed if elapsed > 0 else 0
            
            # Draw frame
            clear_screen()
            sys.stdout.write('\n'.join(frame))
            sys.stdout.write(f"\n\nPoints: {len(points)} | FPS: {fps:.1f} | Scale: {scale:.1f}")
            sys.stdout.flush()
            
            # Frame rate limiting (~30 FPS = 33ms per frame)
            frame_time = time.time() - frame_start
            sleep_time = max(0, 0.033 - frame_time)
            if sleep_time > 0:
                time.sleep(sleep_time)
            
            frame_count += 1
            
    except KeyboardInterrupt:
        pass
    finally:
        # Cleanup
        show_cursor()
        clear_screen()
        print("3D ASCII Heart - Goodbye!")

if __name__ == "__main__":
    main()
