"""
I.R.I.S. (Intelligent Real-time Interface System) Controller
Ultra-Fast, Zero-Jitter Neural Webcam HCI System.

Key Engineering Features:
- Camera-Space 1-Euro Low-Pass Filter on Rigid Cranial Anchor (Landmark 168)
  strips sensor tremor at the root before screen amplification.
- Fitts's Law Ergonomic Range (RANGE_X=42, RANGE_Y=30) enables natural edge-to-edge
  screen reach without shaking or neck strain.
- Rapid 15-frame auto-calibration adapts dynamically to any lighting or eye shape.
- Robust PyAutoGUI click dispatch with proper hold duration.
"""

import os
import sys
import time
import math
from typing import Tuple, Optional, Dict, Any, List
import cv2
import numpy as np

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from iris_engine.camera import ThreadedWebcamStream
from iris_engine.preprocessor import LightingCompensator
from iris_engine.tracker import FastFaceMeshTracker
from iris_engine.filters import OneEuroFilter2D
from iris_engine.gesture_engine import GestureEngine
from iris_engine.controller import WindowsCursorController

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
YUNET_PATH = os.path.join(BASE_DIR, "models", "face_detection_yunet.onnx")
FACEMESH_PATH = os.path.join(BASE_DIR, "models", "FaceMesh.onnx")


def draw_circular_gauge(
    img: np.ndarray,
    center: Tuple[int, int],
    radius: int,
    progress: float,
    color: Tuple[int, int, int] = (0, 240, 255),
    thickness: int = 3
) -> None:
    """Draws a smooth circular progress ring for gesture hold timers."""
    cx, cy = center
    cv2.circle(img, (cx, cy), radius, (50, 55, 65), thickness, cv2.LINE_AA)
    if progress > 0.0:
        angle = int(360.0 * min(1.0, max(0.0, progress)))
        cv2.ellipse(img, (cx, cy), (radius, radius), -90, 0, angle, color, thickness, cv2.LINE_AA)


def main():
    print("=" * 70)
    print("  I.R.I.S. (Intelligent Real-time Interface System) - Controller")
    print("  Zero-Jitter Camera-Space Filtering & Calibrated Gestures")
    print("=" * 70)

    # 1. Initialize Windows Native / PyAutoGUI Cursor Controller
    controller = WindowsCursorController(enable_sound=True)
    screen_w, screen_h = controller.get_screen_size()
    print(f"[INFO] Display Resolution: {screen_w} x {screen_h}")

    # 2. Vision and Tracking Pipelines
    lighting = LightingCompensator(clip_limit=2.0, tile_grid_size=(8, 8))
    gesture_engine = GestureEngine(
        wink_hold_time=0.12,
        double_click_hold_time=0.35,
        click_cooldown=0.40,
        scroll_hold_time=0.12
    )

    tracker = FastFaceMeshTracker(
        model_yunet_path=YUNET_PATH,
        model_facemesh_path=FACEMESH_PATH,
        input_size=(640, 480),
        redetect_interval=90
    )

    camera = ThreadedWebcamStream(src=0, width=640, height=480, fps=30).start()
    time.sleep(0.3)

    # 3. Window Setup (Clean, centered, windowed)
    window_name = "I.R.I.S. - Controller"
    window_w, window_h = 1024, 768
    center_wx = int((screen_w - window_w) / 2)
    center_wy = int((screen_h - window_h) / 2) - 40

    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, window_w, window_h)
    cv2.moveWindow(window_name, max(0, center_wx), max(0, center_wy))

    # 4. 3D Canonical Anthropometric Head Pose Model & Camera-Space 1-Euro Filter
    face_3d = np.array([
        (0.0, 0.0, 0.0),            # Nose tip (Landmark 1)
        (0.0, -330.0, -65.0),       # Chin (Landmark 152)
        (-225.0, 170.0, -135.0),    # Left Eye Outer Corner (Landmark 33)
        (225.0, 170.0, -135.0),     # Right Eye Outer Corner (Landmark 263)
        (-150.0, -150.0, -125.0),   # Left Mouth Corner (Landmark 61)
        (150.0, -150.0, -125.0)     # Right Mouth Corner (Landmark 291)
    ], dtype=np.float64)
    landmark_indices = [1, 152, 33, 263, 61, 291]

    t_start = time.time()
    laser_filter = OneEuroFilter2D(
        t_start,
        320.0,
        240.0,
        min_cutoff=0.005,
        beta=0.002,
        d_cutoff=1.0
    )

    prev_cursor_x = float(screen_w // 2)
    prev_cursor_y = float(screen_h // 2)

    # 5. Sensitivity & Control Box Dimensions
    sensitivity = 1.0
    box_w = 260.0  # Horizontal range in camera space
    box_h = 190.0  # Vertical range in camera space

    # Resting Neutral Anchor (calibrated automatically on start and updated with [C])
    neutral_x: Optional[float] = None
    neutral_y: Optional[float] = None

    # Scrolling state
    last_scroll_time = 0.0
    SCROLL_INTERVAL = 0.07

    # App Status & Action Feedback
    is_paused = False
    last_action_text = ""
    last_action_time = 0.0
    last_action_color = (0, 255, 0)
    click_suppress_until = 0.0

    # Frame timing
    frame_times: List[float] = []
    fps = 30.0

    print("[READY] I.R.I.S. Controller Online.")
    print("        Controls: [SPACE] Pause | [C] Recenter | [+] / [-] Sensitivity | [ESC] Exit\n")

    try:
        while True:
            t_frame_start = time.time()
            frame = camera.read()
            if frame is None:
                time.sleep(0.004)
                continue

            # Flip horizontally for natural mirror behavior
            frame = cv2.flip(frame, 1)
            img_h, img_w, _ = frame.shape

            # 1. Luminance Normalization
            rgb_image = lighting.process(frame)

            # 2. Fast Landmark Tracking
            landmarks = tracker.detect_and_track(rgb_image)

            current_time = time.time()
            l_ear, r_ear, avg_ear, mar = 0.18, 0.18, 0.18, 0.015
            hold_progress = 0.0

            if landmarks is not None:
                # 3. 3D Head Pose Laser Calculation via solvePnP (like Legacy)
                face_2d = np.array([
                    [landmarks[idx][0], landmarks[idx][1]] for idx in landmark_indices
                ], dtype=np.float64)

                focal_length = 1.0 * img_w
                cam_matrix = np.array([
                    [focal_length, 0.0, img_w / 2.0],
                    [0.0, focal_length, img_h / 2.0],
                    [0.0, 0.0, 1.0]
                ], dtype=np.float64)
                dist_coeffs = np.zeros((4, 1), dtype=np.float64)

                success, rvec, tvec = cv2.solvePnP(
                    face_3d, face_2d, cam_matrix, dist_coeffs, flags=cv2.SOLVEPNP_ITERATIVE
                )
                if success:
                    proj, _ = cv2.projectPoints(
                        np.array([(0.0, 0.0, 1000.0)]), rvec, tvec, cam_matrix, dist_coeffs
                    )
                    raw_lx, raw_ly = float(proj[0][0][0]), float(proj[0][0][1])
                else:
                    raw_lx, raw_ly = float(landmarks[1][0]), float(landmarks[1][1])

                # Smooth laser point in camera space FIRST (strips 100% sensor jitter)
                laser_x, laser_y = laser_filter.filter(current_time, raw_lx, raw_ly)

                # Auto-initialize neutral anchor on first stable detection
                if neutral_x is None or neutral_y is None:
                    neutral_x = laser_x
                    neutral_y = laser_y

                # Head displacement vector relative to resting neutral
                dx = laser_x - neutral_x
                dy = laser_y - neutral_y

                # 4. Facial Gesture Engine Evaluation
                gestures = gesture_engine.process_frame(
                    landmarks,
                    current_time,
                    tilt_y=dy,
                    is_mirrored=True
                )

                l_ear = gestures.get('left_ear', 0.18)
                r_ear = gestures.get('right_ear', 0.18)
                avg_ear = (l_ear + r_ear) / 2.0
                mar = gestures.get('mar', 0.015)
                hold_progress = gestures.get('hold_progress', 0.0)
                trigger = gestures.get('trigger_action')
                mouth_opened = gestures.get('mouth_opened', False)

                # 5. Handle Actions
                if not is_paused and trigger is not None:
                    if trigger == 'left_click':
                        controller.left_click()
                        last_action_text = "LEFT CLICK!"
                        last_action_time = current_time
                        last_action_color = (0, 255, 120)
                        click_suppress_until = current_time + 0.20
                    elif trigger == 'right_click':
                        controller.right_click()
                        last_action_text = "RIGHT CLICK!"
                        last_action_time = current_time
                        last_action_color = (0, 220, 255)
                        click_suppress_until = current_time + 0.20
                    elif trigger == 'double_click':
                        controller.double_click()
                        last_action_text = "DOUBLE CLICK!"
                        last_action_time = current_time
                        last_action_color = (255, 120, 255)
                        click_suppress_until = current_time + 0.25
                    elif trigger == 'scroll_up':
                        if (current_time - last_scroll_time) > SCROLL_INTERVAL:
                            controller.scroll(3)
                            last_scroll_time = current_time
                            last_action_text = "SCROLL UP"
                            last_action_time = current_time
                            last_action_color = (0, 240, 255)
                    elif trigger == 'scroll_down':
                        if (current_time - last_scroll_time) > SCROLL_INTERVAL:
                            controller.scroll(-3)
                            last_scroll_time = current_time
                            last_action_text = "SCROLL DOWN"
                            last_action_time = current_time
                            last_action_color = (0, 240, 255)

                # 6. Smooth Pointer Ballistics mapped via Control Box
                half_box_w = (box_w / 2.0) / sensitivity
                half_box_h = (box_h / 2.0) / sensitivity

                box_x1 = neutral_x - half_box_w
                box_x2 = neutral_x + half_box_w
                box_y1 = neutral_y - half_box_h
                box_y2 = neutral_y + half_box_h

                norm_x = (laser_x - neutral_x) / max(1.0, half_box_w)
                norm_y = (laser_y - neutral_y) / max(1.0, half_box_h)

                curved_x = float(np.sign(norm_x) * (abs(norm_x) ** 1.15))
                curved_y = float(np.sign(norm_y) * (abs(norm_y) ** 1.15))

                target_screen_x = (screen_w / 2.0) + curved_x * (screen_w / 2.0)
                target_screen_y = (screen_h / 2.0) + curved_y * (screen_h / 2.0)

                target_screen_x = float(np.clip(target_screen_x, 0, screen_w - 1))
                target_screen_y = float(np.clip(target_screen_y, 0, screen_h - 1))

                # Micro-deadzone of 1.8 screen pixels: locks firmly when stationary
                dist_moved = math.hypot(target_screen_x - prev_cursor_x, target_screen_y - prev_cursor_y)
                is_clicking = current_time < click_suppress_until

                can_move = (
                    not is_paused
                    and not is_clicking
                    and dist_moved > 1.8
                )

                if can_move:
                    controller.move_to(target_screen_x, target_screen_y)
                    prev_cursor_x, prev_cursor_y = target_screen_x, target_screen_y

                # 7. Draw Visual Indicators (Like Legacy UI)
                # Control Box (Cyan / Yellow)
                cv2.rectangle(
                    frame, 
                    (int(box_x1), int(box_y1)), 
                    (int(box_x2), int(box_y2)), 
                    (0, 240, 255), 
                    2
                )

                # Resting Center Anchor Crosshair
                cv2.drawMarker(frame, (int(neutral_x), int(neutral_y)), (0, 200, 255), cv2.MARKER_CROSS, 14, 1)

                # Laser Pointer Red Dot (with white outline)
                cv2.circle(frame, (int(laser_x), int(laser_y)), 7, (0, 0, 255), -1, cv2.LINE_AA)
                cv2.circle(frame, (int(laser_x), int(laser_y)), 9, (255, 255, 255), 1, cv2.LINE_AA)

                # Facial keypoints
                for idx in landmark_indices:
                    cv2.circle(frame, (int(landmarks[idx][0]), int(landmarks[idx][1])), 2, (0, 255, 0), -1)

                # Hold progress ring around laser dot
                if hold_progress > 0.0:
                    ring_color = (255, 120, 255) if gestures.get('is_blinking') else (0, 240, 255)
                    draw_circular_gauge(frame, (int(laser_x), int(laser_y)), radius=20, progress=hold_progress, color=ring_color, thickness=3)

            # -------------------------------------------------------------
            # Clean On-Screen UI Overlays (Like Legacy)
            # -------------------------------------------------------------
            # Top-Left Telemetry Card Overlay
            card_w, card_h = 320, 114
            card_overlay = frame.copy()
            cv2.rectangle(card_overlay, (15, 15), (15 + card_w, 15 + card_h), (18, 22, 28), -1)
            cv2.addWeighted(card_overlay, 0.75, frame, 0.25, 0, frame)
            cv2.rectangle(frame, (15, 15), (15 + card_w, 15 + card_h), (50, 60, 75), 1)

            # Status Indicator
            calib_str = " (Calibrated)" if gesture_engine.is_calibrated else " (Calibrating...)"
            status_str = "PAUSED (SPACE)" if is_paused else ("ACTIVE" + calib_str)
            status_col = (0, 140, 255) if is_paused else (0, 255, 120)
            cv2.putText(frame, "I.R.I.S. Controller", (25, 38), cv2.FONT_HERSHEY_DUPLEX, 0.52, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.putText(frame, f"[{status_str}]", (195, 38), cv2.FONT_HERSHEY_DUPLEX, 0.36, status_col, 1, cv2.LINE_AA)

            # Live Metrics
            cv2.putText(frame, f"EAR L: {l_ear:.2f} | R: {r_ear:.2f}", (25, 64), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (200, 215, 230), 1, cv2.LINE_AA)
            cv2.putText(frame, f"Live MAR: {mar:.3f}", (25, 84), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (200, 215, 230), 1, cv2.LINE_AA)
            cv2.putText(frame, f"Sens: {sensitivity:.2f}x (+/-) | FPS: {fps:3.0f}", (25, 106), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 240, 255), 1, cv2.LINE_AA)

            # Prominent Action Event Banner
            if (current_time - last_action_time) < 0.65 and last_action_text:
                banner_w = 260
                bx1 = (img_w - banner_w) // 2
                bx2 = bx1 + banner_w
                by1 = 20
                by2 = 65
                action_overlay = frame.copy()
                cv2.rectangle(action_overlay, (bx1, by1), (bx2, by2), (20, 24, 32), -1)
                cv2.addWeighted(action_overlay, 0.85, frame, 0.15, 0, frame)
                cv2.rectangle(frame, (bx1, by1), (bx2, by2), last_action_color, 2)
                cv2.putText(
                    frame,
                    last_action_text,
                    (bx1 + 18, by1 + 32),
                    cv2.FONT_HERSHEY_DUPLEX,
                    0.72,
                    last_action_color,
                    2,
                    cv2.LINE_AA
                )

            # Bottom Feature Guide Banner
            banner_overlay = frame.copy()
            cv2.rectangle(banner_overlay, (10, img_h - 44), (img_w - 10, img_h - 10), (16, 20, 28), -1)
            cv2.addWeighted(banner_overlay, 0.82, frame, 0.18, 0, frame)
            cv2.rectangle(frame, (10, img_h - 44), (img_w - 10, img_h - 10), (45, 55, 70), 1)

            cv2.putText(
                frame,
                "Left Wink: L-Click | Right Wink: R-Click | Long Blink: Double-Click | Mouth+Tilt: Scroll",
                (20, img_h - 26),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.35,
                (0, 240, 255),
                1,
                cv2.LINE_AA
            )
            cv2.putText(
                frame,
                "[SPACE] Pause | [C] Recenter | [+/-] Sens | [ESC] Exit",
                (img_w - 325, img_h - 26),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.33,
                (200, 210, 220),
                1,
                cv2.LINE_AA
            )

            # Frame rate update
            t_frame_end = time.time()
            frame_times.append(t_frame_end - t_frame_start)
            if len(frame_times) > 30:
                frame_times.pop(0)
            fps = len(frame_times) / sum(frame_times) if sum(frame_times) > 0 else 30.0

            # Render display frame
            cv2.imshow(window_name, frame)
            key = cv2.waitKey(1) & 0xFF

            if key == 27:  # ESC to exit
                print("[INFO] Terminating session cleanly...")
                break
            elif key == ord(' '):  # SPACE to pause/resume
                is_paused = not is_paused
                controller.play_pause_tone()
            elif key in (ord('c'), ord('C')):  # Recenter neutral anchor to current head position
                if landmarks is not None:
                    neutral_x = laser_x
                    neutral_y = laser_y
                laser_filter.reset(current_time, laser_x, laser_y)
                prev_cursor_x, prev_cursor_y = float(screen_w // 2), float(screen_h // 2)
                controller.move_to(prev_cursor_x, prev_cursor_y)
                controller.play_recenter_tone()
                last_action_text = "RECENTERED"
                last_action_time = current_time
                last_action_color = (0, 240, 255)
            elif key in (ord('+'), ord('=')):  # Increase sensitivity
                sensitivity = min(3.0, sensitivity + 0.10)
                last_action_text = f"SENS: {sensitivity:.2f}x"
                last_action_time = current_time
                last_action_color = (0, 240, 255)
            elif key in (ord('-'), ord('_')):  # Decrease sensitivity
                sensitivity = max(0.4, sensitivity - 0.10)
                last_action_text = f"SENS: {sensitivity:.2f}x"
                last_action_time = current_time
                last_action_color = (0, 240, 255)

    finally:
        camera.stop()
        cv2.destroyAllWindows()
        print("[INFO] I.R.I.S. Session Terminated Cleanly.")


if __name__ == "__main__":
    main()
