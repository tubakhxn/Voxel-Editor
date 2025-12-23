"""Voxel editor clone with Mediapipe hand tracking rendered via OpenCV."""
from __future__ import annotations

import math
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence, Set, Tuple

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

GRID_COLS = 14
GRID_ROWS = 7
PINCH_THRESHOLD = 0.045

# Palette tuned to match the reference video (BGR order for OpenCV)
GRID_COLOR = (224, 216, 105)
BLOCK_FILL_COLOR = (231, 223, 110)
BLOCK_EDGE_COLOR = (170, 250, 255)
HIGHLIGHT_FILL_COLOR = (190, 255, 200)
HIGHLIGHT_EDGE_COLOR = (210, 255, 225)
HUD_BG = (8, 8, 8)
HUD_BORDER = (224, 215, 109)
TEXT_COLOR = (240, 240, 240)
CAPTION = "i built a voxel editor with live hand tracking (using mediapipe, threejs)"
HAND_MODEL_URL = "https://storage.googleapis.com/mediapipe-assets/hand_landmarker.task"
HAND_MODEL_PATH = Path(__file__).with_name("hand_landmarker.task")
INDEX_TIP_IDX = 8
THUMB_TIP_IDX = 4


@dataclass(frozen=True)
class Cell:
  """Immutable cell coordinate."""
  x: int
  y: int


def _ensure_hand_model() -> None:
  if HAND_MODEL_PATH.exists():
    return
  try:
    with urllib.request.urlopen(HAND_MODEL_URL, timeout=20) as response:
      HAND_MODEL_PATH.write_bytes(response.read())
  except Exception as exc:  # pragma: no cover - network failure path
    raise RuntimeError("Failed to download MediaPipe hand model") from exc


class LandmarkBundle:
  """Provides a unified attribute-based access for landmark lists."""

  def __init__(self, landmarks: Sequence[object]):
    self.landmark = landmarks


class HandTracker:
  """Wraps the MediaPipe Tasks hand landmarker for video frames."""

  def __init__(self) -> None:
    _ensure_hand_model()
    base_options = mp_python.BaseOptions(model_asset_path=str(HAND_MODEL_PATH))
    options = vision.HandLandmarkerOptions(
      base_options=base_options,
      running_mode=vision.RunningMode.VIDEO,
      num_hands=1,
      min_hand_presence_confidence=0.6,
      min_tracking_confidence=0.5,
      min_hand_detection_confidence=0.6,
    )
    self._landmarker = vision.HandLandmarker.create_from_options(options)
    self._last_timestamp_ms = 0

  def detect(self, rgb_frame: np.ndarray) -> Optional[LandmarkBundle]:
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
    timestamp_ms = int(time.perf_counter() * 1000)
    if timestamp_ms <= self._last_timestamp_ms:
      timestamp_ms = self._last_timestamp_ms + 1
    self._last_timestamp_ms = timestamp_ms
    result = self._landmarker.detect_for_video(mp_image, timestamp_ms)
    if result.hand_landmarks:
      return LandmarkBundle(result.hand_landmarks[0])
    return None

  def close(self) -> None:
    self._landmarker.close()


class GestureVoxelEditor:
  """Tracks hand gestures and manages voxel grid state."""

  def __init__(self) -> None:
    self.blocks: Set[Cell] = set()
    self.highlight: Optional[Cell] = None
    self.mode_label = "IDLE"
    self.frame_width = 1
    self.frame_height = 1
    self.cell_width = 1.0
    self.cell_height = 1.0
    self.is_pinching = False
    self.pinch_mode: Optional[str] = None
    self.last_pinched_cell: Optional[Cell] = None

  def update_frame_shape(self, shape: Tuple[int, int, int]) -> None:
    self.frame_height, self.frame_width = shape[:2]
    self.cell_width = self.frame_width / GRID_COLS
    self.cell_height = self.frame_height / GRID_ROWS

  def process_landmarks(self, hand_landmarks: Optional[LandmarkBundle]) -> None:
    if hand_landmarks is None:
      self.highlight = None
      self.mode_label = "IDLE"
      self._reset_pinch()
      return

    landmarks = hand_landmarks.landmark
    index_tip = landmarks[INDEX_TIP_IDX]
    thumb_tip = landmarks[THUMB_TIP_IDX]

    cell_x = min(int(index_tip.x * GRID_COLS), GRID_COLS - 1)
    cell_y = min(int(index_tip.y * GRID_ROWS), GRID_ROWS - 1)
    self.highlight = Cell(cell_x, cell_y)

    pinch_distance = math.dist(
      (index_tip.x, index_tip.y, getattr(index_tip, "z", 0.0)),
      (thumb_tip.x, thumb_tip.y, getattr(thumb_tip, "z", 0.0)),
    )
    pinch_active = pinch_distance < PINCH_THRESHOLD

    if pinch_active:
      self._handle_pinch()
    else:
      self._reset_pinch()
      self.mode_label = "TRACK"

  def _handle_pinch(self) -> None:
    if not self.highlight:
      return

    if not self.is_pinching:
      self.is_pinching = True
      self.pinch_mode = "erase" if self.highlight in self.blocks else "add"
      self._apply_pinch_cell(self.highlight)
      return

    if self.last_pinched_cell != self.highlight:
      self._apply_pinch_cell(self.highlight)

  def _reset_pinch(self) -> None:
    self.is_pinching = False
    self.pinch_mode = None
    self.last_pinched_cell = None

  def _apply_pinch_cell(self, cell: Cell) -> None:
    if self.pinch_mode == "add":
      if cell not in self.blocks:
        self.blocks.add(cell)
      self.mode_label = "DRAW"
    elif self.pinch_mode == "erase":
      if cell in self.blocks:
        self.blocks.remove(cell)
      self.mode_label = "ERASE"
    self.last_pinched_cell = cell

  def render(self, frame: np.ndarray) -> np.ndarray:
    overlay = frame.copy()
    self._draw_grid(overlay)
    self._draw_blocks(overlay)
    overlay = self._apply_scene_tints(overlay)
    blended = cv2.addWeighted(overlay, 0.7, frame, 0.3, 0)
    self._draw_caption(blended)
    self._draw_hud(blended)
    return blended

  def _draw_grid(self, canvas: np.ndarray) -> None:
    for col in range(GRID_COLS + 1):
      x = int(col * self.cell_width)
      cv2.line(canvas, (x, 0), (x, self.frame_height), GRID_COLOR, 1, cv2.LINE_AA)
    for row in range(GRID_ROWS + 1):
      y = int(row * self.cell_height)
      cv2.line(canvas, (0, y), (self.frame_width, y), GRID_COLOR, 1, cv2.LINE_AA)

    if self.highlight:
      self._draw_cell(canvas, self.highlight, HIGHLIGHT_FILL_COLOR, filled=True)
      self._draw_cell(canvas, self.highlight, HIGHLIGHT_EDGE_COLOR, thickness=2)

  def _draw_blocks(self, canvas: np.ndarray) -> None:
    for cell in self.blocks:
      self._draw_cell(canvas, cell, BLOCK_FILL_COLOR, filled=True)
      self._draw_cell(canvas, cell, BLOCK_EDGE_COLOR, thickness=1)

  def _draw_cell(self, canvas: np.ndarray, cell: Cell, color: Tuple[int, int, int], filled: bool = False, thickness: int = 1) -> None:
    x0 = int(cell.x * self.cell_width)
    y0 = int(cell.y * self.cell_height)
    x1 = int(x0 + self.cell_width)
    y1 = int(y0 + self.cell_height)
    if filled:
      cv2.rectangle(canvas, (x0, y0), (x1, y1), color, cv2.FILLED, lineType=cv2.LINE_AA)
    cv2.rectangle(canvas, (x0, y0), (x1, y1), color, thickness, lineType=cv2.LINE_AA)

  def _apply_scene_tints(self, canvas: np.ndarray) -> np.ndarray:
    tint_layer = np.zeros_like(canvas)
    center_left = (int(self.frame_width * 0.28), int(self.frame_height * 0.45))
    center_right = (int(self.frame_width * 0.72), int(self.frame_height * 0.35))
    radius = int(min(self.frame_width, self.frame_height) * 0.6)
    cv2.circle(tint_layer, center_left, radius, (180, 255, 255), -1, lineType=cv2.LINE_AA)
    cv2.circle(tint_layer, center_right, radius, (170, 240, 255), -1, lineType=cv2.LINE_AA)
    blended = cv2.addWeighted(tint_layer, 0.12, canvas, 0.88, 0)
    return blended

  def _draw_caption(self, canvas: np.ndarray) -> None:
    bar_height = int(self.frame_height * 0.16)
    bottom_bar = int(self.frame_height * 0.08)
    cv2.rectangle(canvas, (0, 0), (self.frame_width, bar_height), (0, 0, 0), cv2.FILLED)
    cv2.rectangle(
      canvas,
      (0, self.frame_height - bottom_bar),
      (self.frame_width, self.frame_height),
      (0, 0, 0),
      cv2.FILLED,
    )

    font = cv2.FONT_HERSHEY_COMPLEX
    scale = 0.8
    thickness = 1
    text_size, _ = cv2.getTextSize(CAPTION, font, scale, thickness)
    x_pos = (self.frame_width - text_size[0]) // 2
    y_pos = int(bar_height * 0.7)
    cv2.putText(canvas, CAPTION, (x_pos, y_pos), font, scale, TEXT_COLOR, thickness, lineType=cv2.LINE_AA)

  def _draw_hud(self, canvas: np.ndarray) -> None:
    block_str = f"{len(self.blocks):02d}"
    x, y, w, h = 25, 65, 170, 90
    glow = np.zeros_like(canvas)
    cv2.rectangle(glow, (x - 6, y - 6), (x + w + 6, y + h + 6), HUD_BORDER, cv2.FILLED)
    canvas[:] = cv2.addWeighted(glow, 0.18, canvas, 0.82, 0)

    cv2.rectangle(canvas, (x, y), (x + w, y + h), HUD_BG, cv2.FILLED)
    cv2.rectangle(canvas, (x, y), (x + w, y + h), HUD_BORDER, 1)

    cv2.putText(canvas, "EDITING", (x + 10, y + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, GRID_COLOR, 1, lineType=cv2.LINE_AA)
    cv2.putText(canvas, self.mode_label, (x + 10, y + 55), cv2.FONT_HERSHEY_SIMPLEX, 0.7, TEXT_COLOR, 2, lineType=cv2.LINE_AA)

    cv2.putText(canvas, "BLOCKS", (x + 10, y + 80), cv2.FONT_HERSHEY_SIMPLEX, 0.6, GRID_COLOR, 1, lineType=cv2.LINE_AA)
    cv2.putText(canvas, block_str, (x + 100, y + 80), cv2.FONT_HERSHEY_SIMPLEX, 0.9, TEXT_COLOR, 2, lineType=cv2.LINE_AA)


def main() -> None:
  cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
  if not cap.isOpened():
    raise RuntimeError("Cannot access webcam")

  cv2.namedWindow("Voxel Editor", cv2.WINDOW_NORMAL)
  editor = GestureVoxelEditor()
  tracker = HandTracker()

  try:
    while True:
      success, frame = cap.read()
      if not success:
        break

      frame = cv2.flip(frame, 1)
      editor.update_frame_shape(frame.shape)

      rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
      hand_landmarks = tracker.detect(rgb_frame)
      editor.process_landmarks(hand_landmarks)

      output = editor.render(frame)
      cv2.imshow("Voxel Editor", output)

      key = cv2.waitKey(1) & 0xFF
      if key in (27, ord("q")):
        break
  finally:
    tracker.close()

  cap.release()
  cv2.destroyAllWindows()


if __name__ == "__main__":
  main()
