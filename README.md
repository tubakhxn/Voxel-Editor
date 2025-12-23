# Voxel editor with live hand gestures

Built by **tubakhxn**, this project recreates the viral "schach" demo: a turquoise voxel art tool that floats over your webcam feed and reacts to real hand gestures. Two targets are included:

1. **Python desktop app** — OpenCV + MediaPipe Tasks render the HUD, grid, and voxel mesh right on top of your live camera.
2. **Web build** — Three.js + MediaPipe Hands power the same experience in the browser.

Both stacks share the same art direction (black letterbox, cyan grid, neon blocks) so the captured output matches the reference frame.

## What this project demonstrates

- **Realtime hand tracking**: MediaPipe delivers precise thumb/index landmarks every frame.
- **Gesture semantics**: Pinching toggles between `DRAW` and `ERASE` modes, letting you sweep across the grid without releasing.
- **Stylized compositing**: Layered gradients, HUD chrome, and translucent voxels mirror the exact vibe of the original clip.
- **Cross-stack parity**: The Python OpenCV renderer and the browser Three.js scene share identical interaction rules and visual constants.

## Quick start (Python / OpenCV)

```bash
git clone https://github.com/tubakhxn/relex.git
cd relex
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python voxel_editor.py
```

When the window opens:

1. Let the app access your webcam.
2. Keep your hand roughly centered; once `TRACK` appears you can start drawing.
3. Pinch thumb + index to enter `DRAW` (on empty cells) or `ERASE` (on filled cells) and slide your hand to continue the stroke.
4. Release to exit the mode; press `q` or `Esc` to quit.

## Quick start (Web / Three.js)

1. Open `index.html` in a Chromium-based browser (camera permission required).
2. The grid and HUD appear on top of your mirrored webcam feed.
3. Use the same pinch gesture to lay down or delete voxels.

## Forking + contributions

Want to remix the effect for your own feed?

1. Click **Fork** on GitHub under `tubakhxn/relex`.
2. Clone your fork and create a feature branch.
3. Make changes, run the Python/web builds locally, and open a pull request describing what you tweaked.

Ideas worth exploring:

- Alternate block palettes or HUD typography.
- Saving/loading voxel states as JSON.
- Networked collab sessions using WebRTC.

## Key files

- `voxel_editor.py` — OpenCV renderer, MediaPipe Tasks tracker, gesture logic.
- `main.js` — Three.js grid scene, MediaPipe Hands integration.
- `styles.css` — Shared visual language (letterbox, HUD glow, gradients).
- `requirements.txt` — Minimal Python dependencies (opencv-python, mediapipe, numpy).

Feel free to tag @tubakhxn when you post your recreation—would love to see the hand sculptures you make.


