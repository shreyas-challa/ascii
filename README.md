# 3D ASCII Heart Animation

A terminal-based animated 3D ASCII heart that pulsates and rotates, inspired by classic demoscene renders. Built with Python 3 using only the standard library.

![Demo](demo.gif)

## Features

- **True 3D Rendering**: Uses the implicit heart surface equation: `(x² + (9/4)y² + z² - 1)³ - x²z³ - (9/80)y²z³ = 0`
- **Real-time Animation**: 
  - Continuous rotation around X, Y, and Z axes
  - Sinusoidal pulsation simulating a heartbeat
  - ~30 FPS on modern terminals
- **Depth Effects**:
  - Z-buffer for proper depth sorting (closer points overwrite farther ones)
  - 10-level ASCII shading ( `.` → `@` ) based on depth
- **Terminal Optimized**:
  - ANSI escape codes for flicker-free rendering
  - Dynamic terminal size detection
  - Hidden cursor for clean animation

## Requirements

- Python 3.6+
- Terminal with ANSI escape code support (most modern terminals)

## Installation

```bash
# Clone the repository
git clone https://github.com/shreyas-challa/ascii.git
cd ascii

# Run the animation
python heart.py
```

## Usage

Simply run the script:

```bash
python heart.py
```

The heart will:
1. Sample ~10,000 points on the implicit heart surface
2. Begin rotating and pulsating
3. Display real-time FPS and point count

Press `Ctrl+C` to exit.

## How It Works

### 1. Surface Sampling
The heart surface is sampled using a parametric approximation that satisfies the implicit equation:

```python
def sample_heart_surface(num_theta=100, num_phi=80):
    # Spherical parameterization transformed to heart shape
    x = sin(φ) * cos(θ)
    y = sin(φ) * sin(θ)  
    z = cos(φ)
    
    # Apply heart deformations:
    # - Flatten top for atrial separation
    # - Elongate bottom for ventricles
    # - Verify against implicit equation
```

### 2. 3D Transformations
Each point undergoes rotation around all three axes using rotation matrices:

```python
def rotate_3d(x, y, z, angle_x, angle_y, angle_z):
    # Apply Z → Y → X rotation order
    # Uses standard rotation matrix multiplication
```

### 3. Perspective Projection
3D points are projected to 2D using perspective projection:

```python
def project_3d_to_2d(x, y, z, width, height, fov=80):
    distance = 50
    factor = fov / (z + distance)
    screen_x = width/2 + x * factor * 2.0
    screen_y = height/2 - y * factor
```

### 4. Rendering Pipeline
1. **Clear**: ANSI escape code `\033[2J\033[H` clears screen and moves cursor to (0,0)
2. **Transform**: Rotate all points by current animation angles
3. **Project**: Convert 3D coordinates to 2D screen space
4. **Z-Buffer**: Only draw if point is closer than existing pixel
5. **Shade**: Select ASCII character based on depth
6. **Display**: Output entire frame at once

### 5. Animation Loop
- **Pulsation**: `scale = 16.0 + 3.0 * sin(t * 2)` creates heartbeat effect
- **Rotation**: Continuous rotation on all three axes at different speeds
- **Frame Limiting**: Target ~30 FPS with `time.sleep()`

## Performance

- **Point Count**: 10,800 surface points (configurable)
- **Frame Rate**: ~30 FPS on modern hardware
- **CPU Usage**: Optimized with pre-sampled points and efficient loops

## Customization

Edit these variables in `heart.py`:

```python
SHADES = " .:-=+*#%@"      # Shading characters
num_theta = 120            # Surface resolution (higher = smoother)
num_phi = 90
fov = 80                   # Field of view (zoom level)
scale = 16.0               # Base heart size
```

## License

MIT License - Feel free to use, modify, and distribute!

## Acknowledgments

- Heart surface equation based on mathematical heart surfaces
- Inspired by classic ASCII art demoscene productions
