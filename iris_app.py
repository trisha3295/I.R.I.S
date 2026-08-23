import os
import sys
import time
from typing import Dict, Any, List, Optional, Tuple
import cv2
import numpy as np

# Add parent directory to path for module resolution
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from iris_engine.camera import ThreadedWebcamStream
from iris_engine.preprocessor import LightingCompensator
from iris_engine.tracker import FastFaceMeshTracker
from iris_engine.pose_estimator import HeadPoseEstimator
from iris_engine.filters import OneEuroFilter2D
from iris_engine.gesture_engine import GestureEngine
from iris_engine.controller import WindowsCursorController

# Model paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
YUNET_PATH = os.path.join(BASE_DIR, "models", "face_detection_yunet.onnx")
FACEMESH_PATH = os.path.join(BASE_DIR, "models", "FaceMesh.onnx")


def draw_rounded_card(img, pt1, pt2, fill_color, border_color=None, radius=8, thickness=1):
    """Draws a clean modern rounded card with optional border."""
    x1, y1 = pt1
    x2, y2 = pt2
    w = x2 - x1
    h = y2 - y1
    r = min(radius, w // 2, h // 2)

    # Fill Card Body
    cv2.rectangle(img, (x1 + r, y1), (x2 - r, y2), fill_color, -1)
    cv2.rectangle(img, (x1, y1 + r), (x2, y2 - r), fill_color, -1)
    cv2.circle(img, (x1 + r, y1 + r), r, fill_color, -1)
    cv2.circle(img, (x2 - r, y1 + r), r, fill_color, -1)
    cv2.circle(img, (x1 + r, y2 - r), r, fill_color, -1)
    cv2.circle(img, (x2 - r, y2 - r), r, fill_color, -1)

    # Optional Outline Border
    if border_color is not None:
        cv2.line(img, (x1 + r, y1), (x2 - r, y1), border_color, thickness)
        cv2.line(img, (x1 + r, y2), (x2 - r, y2), border_color, thickness)
        cv2.line(img, (x1, y1 + r), (x1, y2 - r), border_color, thickness)
        cv2.line(img, (x2, y1 + r), (x2, y2 - r), border_color, thickness)
        cv2.ellipse(img, (x1 + r, y1 + r), (r, r), 180, 0, 90, border_color, thickness)
        cv2.ellipse(img, (x2 - r, y1 + r), (r, r), 270, 0, 90, border_color, thickness)
        cv2.ellipse(img, (x1 + r, y2 - r), (r, r), 90, 0, 90, border_color, thickness)
        cv2.ellipse(img, (x2 - r, y2 - r), (r, r), 0, 0, 90, border_color, thickness)


def draw_circular_gauge(img, center, radius, progress, color=(0, 240, 255), thickness=3):
    """Draws a smooth circular progress ring around facial points (e.g. nose tip for click timer)."""
    cx, cy = center
    # Background ring
    cv2.circle(img, (cx, cy), radius, (50, 55, 65), thickness, cv2.LINE_AA)
    # Active arc
    if progress > 0.0:
        angle = int(360.0 * min(1.0, max(0.0, progress)))
        cv2.ellipse(img, (cx, cy), (radius, radius), -90, 0, angle, color, thickness, cv2.LINE_AA)


def render_dashboard_panel(
    panel: np.ndarray,
    gestures: Dict[str, Any],
    recent_actions: List[str],
    sensitivity: float,
    is_paused: bool,
    is_scrolling: bool,
    is_sniper: bool,
    is_calibrating: bool,
    calib_progress: float,
    sound_enabled: bool,
    head_tracked: bool
) -> None:
    """
    Renders the modern Cyber-Glass interactive control & tutorial sidebar.
    """
    pw = panel.shape[1]
    ph = panel.shape[0]

    # Dark Cyber Background
    panel[:] = (15, 17, 22)

    # 1. Header Banner
    draw_rounded_card(panel, (10, 10), (pw - 10, 48), (24, 28, 38), (40, 46, 60), radius=6)
    cv2.putText(panel, "I.R.I.S. CONTROL & TUTORIAL", (18, 33), cv2.FONT_HERSHEY_DUPLEX, 0.46, (0, 230, 255), 1, cv2.LINE_AA)

    # 2. Card: Eye Telemetry & Relative Asymmetry
    c1_y1, c1_y2 = 54, 146
    draw_rounded_card(panel, (10, c1_y1), (pw - 10, c1_y2), (20, 24, 32), (38, 44, 58), radius=6)
    cv2.putText(panel, "LIVE EYE ASYMMETRY TELEMETRY", (18, c1_y1 + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (160, 175, 195), 1, cv2.LINE_AA)

    l_ear = gestures.get('left_ear', 0.28)
    r_ear = gestures.get('right_ear', 0.28)
    asymmetry = gestures.get('asymmetry', 0.0)
    base_l = gestures.get('baseline_l_ear', 0.28)
    base_r = gestures.get('baseline_r_ear', 0.28)

    # Left Eye Gauge (User Left)
    l_active = gestures.get('is_left_winking', False)
    l_bar_col = (0, 255, 140) if not l_active else (0, 180, 255)
    cv2.putText(panel, f"L EAR: {l_ear:.2f}", (18, c1_y1 + 38), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (230, 230, 230), 1, cv2.LINE_AA)
    cv2.rectangle(panel, (85, c1_y1 + 28), (pw - 25, c1_y1 + 40), (35, 40, 52), -1)
    l_fill = int((pw - 110) * min(1.0, max(0.0, l_ear / 0.40)))
    cv2.rectangle(panel, (85, c1_y1 + 28), (85 + l_fill, c1_y1 + 40), l_bar_col, -1)
    # Baseline marker
    mark_l = int(85 + (pw - 110) * min(1.0, base_l / 0.40))
    cv2.line(panel, (mark_l, c1_y1 + 26), (mark_l, c1_y1 + 42), (255, 255, 255), 1)

    # Right Eye Gauge (User Right)
    r_active = gestures.get('is_right_winking', False)
    r_bar_col = (0, 255, 140) if not r_active else (0, 180, 255)
    cv2.putText(panel, f"R EAR: {r_ear:.2f}", (18, c1_y1 + 60), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (230, 230, 230), 1, cv2.LINE_AA)
    cv2.rectangle(panel, (85, c1_y1 + 50), (pw - 25, c1_y1 + 62), (35, 40, 52), -1)
    r_fill = int((pw - 110) * min(1.0, max(0.0, r_ear / 0.40)))
    cv2.rectangle(panel, (85, c1_y1 + 50), (85 + r_fill, c1_y1 + 62), r_bar_col, -1)
    # Baseline marker
    mark_r = int(85 + (pw - 110) * min(1.0, base_r / 0.40))
    cv2.line(panel, (mark_r, c1_y1 + 48), (mark_r, c1_y1 + 64), (255, 255, 255), 1)

    # Asymmetry Differential Readout
    asym_pct = int(asymmetry * 100)
    asym_col = (0, 255, 220) if asym_pct > 30 else (140, 150, 165)
    cv2.putText(panel, f"Asymmetry Index: {asym_pct}%", (18, c1_y1 + 82), cv2.FONT_HERSHEY_SIMPLEX, 0.35, asym_col, 1, cv2.LINE_AA)

    # 3. Card: Interactive Gesture Tutorial Grid
    c2_y1, c2_y2 = 152, 356
    draw_rounded_card(panel, (10, c2_y1), (pw - 10, c2_y2), (20, 24, 32), (38, 44, 58), radius=6)
    cv2.putText(panel, "GESTURE GUIDE (REACTIVE)", (18, c2_y1 + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (0, 230, 255), 1, cv2.LINE_AA)

    # 1. Head Glide
    h_col = (0, 255, 140) if head_tracked else (120, 130, 140)
    cv2.circle(panel, (24, c2_y1 + 35), 4, h_col, -1)
    cv2.putText(panel, "1. Move Head : Cursor Glide", (36, c2_y1 + 39), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (240, 240, 240), 1, cv2.LINE_AA)

    # 2. Hold Blink
    hold_prog = gestures.get('hold_progress', 0.0)
    b_col = (0, 240, 255) if hold_prog > 0.0 else (120, 130, 140)
    cv2.circle(panel, (24, c2_y1 + 62), 4, b_col, -1)
    cv2.putText(panel, "2. Hold Blink (0.35s) : Left Click", (36, c2_y1 + 66), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (240, 240, 240), 1, cv2.LINE_AA)
    # Mini Progress Bar
    cv2.rectangle(panel, (36, c2_y1 + 74), (pw - 25, c2_y1 + 81), (35, 40, 52), -1)
    if hold_prog > 0.0:
        cv2.rectangle(panel, (36, c2_y1 + 74), (36 + int((pw - 61) * hold_prog), c2_y1 + 81), (0, 230, 255), -1)

    # 3. Left Wink
    lw_col = (0, 255, 140) if gestures.get('is_left_winking', False) else (120, 130, 140)
    cv2.circle(panel, (24, c2_y1 + 100), 4, lw_col, -1)
    cv2.putText(panel, "3. Left Wink : Left Click (Instant)", (36, c2_y1 + 104), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (240, 240, 240), 1, cv2.LINE_AA)

    # 4. Right Wink
    rw_col = (0, 255, 140) if gestures.get('is_right_winking', False) else (120, 130, 140)
    cv2.circle(panel, (24, c2_y1 + 126), 4, rw_col, -1)
    cv2.putText(panel, "4. Right Wink : Right Click (Instant)", (36, c2_y1 + 130), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (240, 240, 240), 1, cv2.LINE_AA)

    # 5. Drag & Drop Hold
    is_drag = gestures.get('is_dragging', False)
    drag_col = (255, 120, 0) if is_drag else (120, 130, 140)
    cv2.circle(panel, (24, c2_y1 + 152), 4, drag_col, -1)
    drag_label = "5. Long Hold (0.75s) : DRAGGING" if is_drag else "5. Long Hold (0.75s) : Drag & Drop"
    cv2.putText(panel, drag_label, (36, c2_y1 + 156), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (240, 240, 240), 1, cv2.LINE_AA)

    # 6. Scroll Mode
    scroll_col = (0, 220, 255) if (is_scrolling or gestures.get('mouth_opened', False)) else (120, 130, 140)
    cv2.circle(panel, (24, c2_y1 + 178), 4, scroll_col, -1)
    cv2.putText(panel, "6. Open Mouth / [S] : Smooth Scroll", (36, c2_y1 + 182), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (240, 240, 240), 1, cv2.LINE_AA)

    # 4. Card: Quick Hotkey Toggles & Status
    c3_y1, c3_y2 = 362, ph - 10
    draw_rounded_card(panel, (10, c3_y1), (pw - 10, c3_y2), (20, 24, 32), (38, 44, 58), radius=6)
    
    # Feature Status Badges
    cal_str = f"CALIBRATING ({int(calib_progress*100)}%)" if is_calibrating else "CALIBRATED"
    cal_col = (0, 240, 255) if is_calibrating else (0, 255, 140)
    cv2.putText(panel, f"[A] Auto-Calib: {cal_str}", (18, c3_y1 + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.34, cal_col, 1, cv2.LINE_AA)

    snip_str = "SNIPER 0.3x" if is_sniper else "NORMAL"
    snip_col = (0, 240, 255) if is_sniper else (180, 180, 180)
    cv2.putText(panel, f"[Z] Precision: {snip_str}", (18, c3_y1 + 36), cv2.FONT_HERSHEY_SIMPLEX, 0.34, snip_col, 1, cv2.LINE_AA)

    snd_str = "ON" if sound_enabled else "MUTED"
    snd_col = (0, 255, 140) if sound_enabled else (120, 120, 120)
    cv2.putText(panel, f"[M] Audio: {snd_str} | [S] Scroll: {'ON' if is_scrolling else 'OFF'}", (18, c3_y1 + 54), cv2.FONT_HERSHEY_SIMPLEX, 0.34, snd_col, 1, cv2.LINE_AA)

    p_str = "PAUSED (SPACE)" if is_paused else "ACTIVE TRACKING"
    p_col = (0, 140, 255) if is_paused else (0, 255, 140)
    cv2.putText(panel, f"[SPACE] {p_str} | Sens: {sensitivity:.1f}x", (18, c3_y1 + 72), cv2.FONT_HERSHEY_SIMPLEX, 0.34, p_col, 1, cv2.LINE_AA)

    # Event Log
    if recent_actions:
        latest = recent_actions[-1]
        cv2.putText(panel, f">> {latest}", (18, c3_y1 + 92), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 230, 255), 1, cv2.LINE_AA)


def main():
    print("=" * 68)
    print("  I.R.I.S. (Intelligent Real-time Interface System) v2.0 Platform")
    print("=" * 68)
    
    # 1. Initialize Windows Cursor & Sound Controller
    controller = WindowsCursorController(enable_sound=True)
    screen_w, screen_h = controller.get_screen_size()
    print(f"[1] Native Windows Controller: {screen_w}x{screen_h} primary display")

    # 2. Signal Filters & Geometry Engines
    lighting = LightingCompensator(clip_limit=2.0, tile_grid_size=(8, 8))
    t_start = time.time()
    cursor_filter = OneEuroFilter2D(t_start, screen_w / 2.0, screen_h / 2.0, min_cutoff=0.005, beta=0.001, d_cutoff=1.0)
    pose_estimator = HeadPoseEstimator()
    gesture_engine = GestureEngine(
        ear_threshold_ratio=0.68,
        asymmetry_threshold=0.28,
        wink_hold_time=0.18,
        blink_hold_time=0.35,
        drag_hold_time=0.75,
        click_cooldown=0.55,
        deadzone_x=14.0,
        deadzone_y=8.0
    )

    # 3. Neural Trackers
    tracker = FastFaceMeshTracker(
        model_yunet_path=YUNET_PATH,
        model_facemesh_path=FACEMESH_PATH,
        input_size=(640, 480)
    )

    # 4. Camera Thread
    camera = ThreadedWebcamStream(src=0, width=640, height=480, fps=30).start()
    time.sleep(0.4)

    # State variables
    is_paused = False
    is_scrolling = False
    is_sniper = False
    show_debug = True
    show_tutorial_panel = True
    sensitivity = 1.0
    prev_smooth_x, prev_smooth_y = screen_w / 2.0, screen_h / 2.0
    recent_actions: List[str] = []
    
    # Auto-calibration state
    is_calibrating = False
    calib_start_time = 0.0
    calib_samples: List[Tuple[float, float, float]] = []

    # Scroll tracking
    prev_pitch = 0.0

    frame_times = []
    fps = 30.0
    latency_ms = 0.0

    window_name = "I.R.I.S. Control Monitor"
    cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)

    print("\n[READY] I.R.I.S. v2.0 Online. Press ESC to exit.\n")

    try:
        while True:
            t_frame_start = time.time()
            frame = camera.read()
            if frame is None:
                time.sleep(0.005)
                continue

            frame = cv2.flip(frame, 1)
            img_h, img_w, _ = frame.shape

            # 1. Luminance Equalization (YCrCb CLAHE)
            rgb_image = lighting.process(frame)

            # 2. Neural 468-point 3D FaceMesh Tracking
            landmarks = tracker.detect_and_track(rgb_image)
            head_tracked = landmarks is not None

            # Dynamic Sensitivity Motion Box
            effective_sens = (sensitivity * 0.35) if is_sniper else sensitivity
            box_w_factor = max(0.18, 0.38 / effective_sens)
            box_h_factor = max(0.18, 0.38 / effective_sens)
            box_w = int(img_w * box_w_factor)
            box_h = int(img_h * box_h_factor)
            box_x1 = int((img_w - box_w) / 2)
            box_y1 = int((img_h - box_h) / 2)
            box_x2 = box_x1 + box_w
            box_y2 = box_y1 + box_h

            if show_debug:
                # Outer Cyber ROI Box
                box_col = (0, 240, 255) if is_sniper else ((0, 255, 140) if not is_paused else (0, 140, 255))
                cv2.rectangle(frame, (box_x1, box_y1), (box_x2, box_y2), box_col, 1)

            gestures = {'hold_progress': 0.0, 'left_ear': 0.28, 'right_ear': 0.28, 'asymmetry': 0.0}

            if landmarks is not None:
                current_time = time.time()

                # 3. Gesture Evaluation with Relative Asymmetry
                gestures = gesture_engine.process_frame(landmarks, current_time, is_mirrored=True)
                trigger = gestures.get('trigger_action')

                # Auto-Calibration sampling
                if is_calibrating:
                    calib_samples.append((gestures['left_ear'], gestures['right_ear'], gestures['mar']))
                    if (current_time - calib_start_time) >= 2.5:
                        # Finalize Calibration
                        arr = np.array(calib_samples)
                        mean_l = float(np.mean(arr[:, 0]))
                        mean_r = float(np.mean(arr[:, 1]))
                        mean_m = float(np.mean(arr[:, 2]))
                        gesture_engine.set_calibration(mean_l, mean_r, mean_m)
                        is_calibrating = False
                        controller.play_recenter_tone()
                        recent_actions.append(f"CALIBRATED (L:{mean_l:.2f}, R:{mean_r:.2f})")
                        if len(recent_actions) > 6:
                            recent_actions.pop(0)

                # Trigger Mouse Actions
                if not is_paused and not is_calibrating and trigger is not None:
                    if trigger == 'left_click':
                        controller.left_click()
                        recent_actions.append(f"LEFT CLICK [{time.strftime('%H:%M:%S')}]")
                        cv2.circle(frame, (box_x1 + 30, box_y1 + 30), 14, (0, 255, 0), -1)
                    elif trigger == 'right_click':
                        controller.right_click()
                        recent_actions.append(f"RIGHT CLICK [{time.strftime('%H:%M:%S')}]")
                        cv2.circle(frame, (box_x2 - 30, box_y1 + 30), 14, (0, 0, 255), -1)
                    elif trigger == 'toggle_drag':
                        dragging = controller.toggle_drag()
                        recent_actions.append(f"{'DRAG ON' if dragging else 'DRAG OFF'} [{time.strftime('%H:%M:%S')}]")
                    if len(recent_actions) > 6:
                        recent_actions.pop(0)

                # 4. 6-DOF Head Pose Estimation via solvePnP
                success, proj_point, rvec, tvec = pose_estimator.estimate_pose(landmarks, img_w, img_h)

                if success and proj_point is not None:
                    laser_x, laser_y = proj_point
                    pitch, yaw, roll = pose_estimator.get_euler_angles(rvec)

                    # Smooth Head-Tilt Scrolling
                    if is_scrolling or gestures.get('mouth_opened', False):
                        pitch_delta = pitch - prev_pitch
                        if abs(pitch) > 6.0:
                            scroll_speed = int(np.clip(-pitch / 4.0, -4, 4))
                            if scroll_speed != 0:
                                controller.scroll(scroll_speed)
                    prev_pitch = pitch

                    # 3D Gaze Vector Visuals
                    if show_debug:
                        nose_2d = (int(landmarks[1][0]), int(landmarks[1][1]))
                        target_2d = (int(laser_x), int(laser_y))
                        cv2.line(frame, nose_2d, target_2d, (0, 240, 255), 2, cv2.LINE_AA)
                        
                        # Circular Hold Ring on Nose
                        hold_prog = gestures.get('hold_progress', 0.0)
                        draw_circular_gauge(frame, nose_2d, radius=18, progress=hold_prog, color=(0, 230, 255), thickness=3)

                    # Screen Coordinate Remapping & One Euro Filtering
                    raw_screen_x = np.interp(laser_x, [box_x1, box_x2], [0, screen_w])
                    raw_screen_y = np.interp(laser_y, [box_y1, box_y2], [0, screen_h])

                    smooth_x, smooth_y = cursor_filter.filter(current_time, raw_screen_x, raw_screen_y)
                    dx = smooth_x - prev_smooth_x
                    dy = smooth_y - prev_smooth_y

                    # Move cursor if not paused, not calibrating, and outside deadzone
                    if not is_paused and not is_calibrating and not gesture_engine.should_suppress_cursor():
                        if gesture_engine.is_outside_deadzone(dx, dy):
                            controller.move_to(smooth_x, smooth_y)
                            prev_smooth_x, prev_smooth_y = smooth_x, smooth_y

                # Render Eye Pupil & Contour Reticles
                if show_debug:
                    for eye_idx in gesture_engine.EYE_LEFT_ANATOMIC + gesture_engine.EYE_RIGHT_ANATOMIC:
                        pt = (int(landmarks[eye_idx][0]), int(landmarks[eye_idx][1]))
                        cv2.circle(frame, pt, 1, (255, 220, 0), -1)

            # Top Camera Glassmorphism Header Bar
            header_overlay = frame.copy()
            cv2.rectangle(header_overlay, (10, 10), (img_w - 10, 52), (18, 20, 26), -1)
            cv2.addWeighted(header_overlay, 0.82, frame, 0.18, 0, frame)

            status_txt = "PAUSED (SPACE)" if is_paused else ("SCROLL MODE" if is_scrolling else ("DRAGGING" if controller.is_dragging else "ACTIVE"))
            status_col = (0, 140, 255) if is_paused else ((0, 220, 255) if is_scrolling else (0, 255, 140))
            cv2.putText(frame, "I.R.I.S. v2.0", (20, 32), cv2.FONT_HERSHEY_DUPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.putText(frame, f"[{status_txt}]", (140, 32), cv2.FONT_HERSHEY_DUPLEX, 0.48, status_col, 1, cv2.LINE_AA)
            cv2.putText(frame, f"FPS: {fps:4.1f} | Latency: {latency_ms:4.1f}ms", (20, 46), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (180, 180, 180), 1, cv2.LINE_AA)

            # FPS & Latency metrics
            t_frame_end = time.time()
            latency_ms = (t_frame_end - t_frame_start) * 1000.0
            frame_times.append(t_frame_end - t_frame_start)
            if len(frame_times) > 30:
                frame_times.pop(0)
            fps = len(frame_times) / sum(frame_times) if sum(frame_times) > 0 else 30.0

            # Side Tutorial & Command Dashboard
            if show_tutorial_panel:
                panel_w = 360
                panel = np.zeros((img_h, panel_w, 3), dtype=np.uint8)
                cal_prog = min(1.0, (time.time() - calib_start_time) / 2.5) if is_calibrating else 1.0
                render_dashboard_panel(
                    panel, 
                    gestures, 
                    recent_actions, 
                    sensitivity, 
                    is_paused, 
                    is_scrolling,
                    is_sniper,
                    is_calibrating,
                    cal_prog,
                    controller.enable_sound,
                    head_tracked
                )
                display_canvas = np.hstack([frame, panel])
            else:
                display_canvas = frame

            cv2.imshow(window_name, display_canvas)
            key = cv2.waitKey(1) & 0xFF

            if key == 27:  # ESC
                print("[INFO] Shutting down I.R.I.S. cleanly...")
                break
            elif key == ord(' '):  # Pause / Resume
                is_paused = not is_paused
                controller.play_pause_tone()
            elif key in (ord('c'), ord('C')):  # Recenter
                cursor_filter.reset(time.time(), screen_w / 2.0, screen_h / 2.0)
                controller.move_to(screen_w / 2.0, screen_h / 2.0)
                prev_smooth_x, prev_smooth_y = screen_w / 2.0, screen_h / 2.0
                controller.play_recenter_tone()
                recent_actions.append(f"RECENTERED [{time.strftime('%H:%M:%S')}]")
                if len(recent_actions) > 6:
                    recent_actions.pop(0)
            elif key in (ord('a'), ord('A')):  # Auto-Calibrate
                is_calibrating = True
                calib_start_time = time.time()
                calib_samples = []
                print("[INFO] Starting 2.5s Auto-Calibration...")
            elif key in (ord('s'), ord('S')):  # Scroll Mode
                is_scrolling = not is_scrolling
                recent_actions.append(f"SCROLL {'ON' if is_scrolling else 'OFF'}")
                if len(recent_actions) > 6:
                    recent_actions.pop(0)
            elif key in (ord('z'), ord('Z')):  # Sniper / Precision Mode
                is_sniper = not is_sniper
                recent_actions.append(f"PRECISION {'0.3x' if is_sniper else 'OFF'}")
                if len(recent_actions) > 6:
                    recent_actions.pop(0)
            elif key in (ord('m'), ord('M')):  # Mute / Unmute Audio Chimes
                snd = controller.toggle_sound()
                recent_actions.append(f"AUDIO {'ON' if snd else 'MUTED'}")
                if len(recent_actions) > 6:
                    recent_actions.pop(0)
            elif key in (ord('t'), ord('T')):  # Toggle Tutorial Panel
                show_tutorial_panel = not show_tutorial_panel
            elif key in (ord('h'), ord('H')):  # Toggle HUD
                show_debug = not show_debug
            elif key in (ord('+'), ord('=')):  # Increase sensitivity
                sensitivity = min(3.0, sensitivity + 0.1)
            elif key in (ord('-'), ord('_')):  # Decrease sensitivity
                sensitivity = max(0.4, sensitivity - 0.1)

    finally:
        controller.release_drag()
        camera.stop()
        cv2.destroyAllWindows()
        print("[INFO] I.R.I.S. Session Terminated.")

if __name__ == "__main__":
    main()
