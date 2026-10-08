import numpy as np
import time
from typing import Tuple, Optional, Dict, Any, List


class GestureEngine:
    """
    Calibrated Adaptive Gesture & Facial Telemetry Engine for I.R.I.S.

    Gesture Map:
      - Left Wink  (0.12s)       -> Left Click
      - Right Wink (0.12s)       -> Right Click
      - Long Dual Blink (0.35s)  -> Double Click
      - Mouth Open + Head Up     -> Scroll Up
      - Mouth Open + Head Down   -> Scroll Down
    """

    def __init__(
        self,
        wink_hold_time: float = 0.12,
        double_click_hold_time: float = 0.35,
        click_cooldown: float = 0.40,
        scroll_pitch_deadzone: float = 6.0,
        scroll_hold_time: float = 0.0,
        **kwargs
    ):
        self.wink_hold_time = wink_hold_time
        self.double_click_hold_time = double_click_hold_time
        self.click_cooldown = click_cooldown
        self.scroll_pitch_deadzone = scroll_pitch_deadzone
        self.scroll_hold_time = scroll_hold_time

        # FaceMesh landmark indices
        self.EYE_RIGHT_ANATOMIC = [33, 160, 158, 133, 153, 144]
        self.EYE_LEFT_ANATOMIC  = [362, 385, 387, 263, 373, 380]
        self.MOUTH_INDICES      = [13, 14, 78, 308]

        # Adaptive baselines
        self.baseline_l_ear = 0.18
        self.baseline_r_ear = 0.18
        self.baseline_mar   = 0.015
        self.calibration_samples: List[Tuple[float, float, float]] = []
        self.is_calibrated = False

        # State tracking
        self.last_click_time: float = 0.0
        self.blink_start_time: Optional[float] = None
        self.left_wink_start_time: Optional[float] = None
        self.right_wink_start_time: Optional[float] = None

        self.is_blinking = False
        self.is_left_winking = False
        self.is_right_winking = False
        self.mouth_opened = False
        self.mouth_open_start_time: Optional[float] = None

    @staticmethod
    def calculate_ear(eye_indices: list, landmarks: np.ndarray) -> float:
        """6-point Eye Aspect Ratio."""
        pts = [landmarks[idx][:2] for idx in eye_indices]
        v1 = np.linalg.norm(pts[1] - pts[5])
        v2 = np.linalg.norm(pts[2] - pts[4])
        h1 = np.linalg.norm(pts[0] - pts[3])
        return float((v1 + v2) / (2.0 * h1)) if h1 > 1e-6 else 0.0

    @staticmethod
    def calculate_mar(mouth_indices: list, landmarks: np.ndarray) -> float:
        """Mouth Aspect Ratio."""
        p_upper = landmarks[mouth_indices[0]][:2]
        p_lower = landmarks[mouth_indices[1]][:2]
        p_left  = landmarks[mouth_indices[2]][:2]
        p_right = landmarks[mouth_indices[3]][:2]
        vert = np.linalg.norm(p_upper - p_lower)
        horiz = np.linalg.norm(p_left - p_right)
        return float(vert / horiz) if horiz > 1e-6 else 0.0

    def update_baseline(self, l_ear: float, r_ear: float, mar: float) -> None:
        """Initial 15-frame rapid calibration, followed by gentle running EMA."""
        if len(self.calibration_samples) < 15:
            self.calibration_samples.append((l_ear, r_ear, mar))
            if len(self.calibration_samples) >= 15:
                self.baseline_l_ear = float(np.mean([s[0] for s in self.calibration_samples]))
                self.baseline_r_ear = float(np.mean([s[1] for s in self.calibration_samples]))
                self.baseline_mar   = float(np.mean([s[2] for s in self.calibration_samples]))
                self.is_calibrated = True
            return

        if not self.is_blinking and not self.is_left_winking and not self.is_right_winking:
            if l_ear > 0.14 and r_ear > 0.14:
                self.baseline_l_ear = 0.99 * self.baseline_l_ear + 0.01 * l_ear
                self.baseline_r_ear = 0.99 * self.baseline_r_ear + 0.01 * r_ear
            if 0.005 < mar < 0.035:
                self.baseline_mar = 0.99 * self.baseline_mar + 0.01 * mar

    def process_frame(
        self,
        landmarks: np.ndarray,
        current_time: float,
        pitch_angle: float = 0.0,
        tilt_y: float = 0.0,
        is_mirrored: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Evaluate facial gestures using calibrated relative eye closure drops.
        """
        # User physical Left Eye vs Right Eye landmarks
        l_indices = self.EYE_LEFT_ANATOMIC
        r_indices = self.EYE_RIGHT_ANATOMIC

        l_ear = self.calculate_ear(l_indices, landmarks)
        r_ear = self.calculate_ear(r_indices, landmarks)
        mar = self.calculate_mar(self.MOUTH_INDICES, landmarks)

        self.update_baseline(l_ear, r_ear, mar)

        # Calibrated relative drops (0.0 = wide open, > 0.12 = closing/closed)
        drop_l = (self.baseline_l_ear - l_ear) / max(self.baseline_l_ear, 1e-4)
        drop_r = (self.baseline_r_ear - r_ear) / max(self.baseline_r_ear, 1e-4)

        trigger_action: Optional[str] = None
        hold_progress = 0.0

        # Physical mouth opening verification:
        # Check inner lip vertical pixel distance and outer mouth aspect ratio.
        # This completely prevents head-lift perspective foreshortening from falsely tripping mouth open!
        inner_lip_px = abs(float(landmarks[14][1] - landmarks[13][1]))
        outer_lip_px = abs(float(landmarks[17][1] - landmarks[0][1]))
        mouth_w = np.linalg.norm(landmarks[78][:2] - landmarks[308][:2])
        
        # Genuine opening requires physical separation of inner lips AND elevated aspect ratio
        is_inner_open = (inner_lip_px >= 3.0) or (outer_lip_px >= 6.0 and inner_lip_px >= 1.5)
        is_mar_high = (mar >= 0.08) or (mar >= max(0.06, self.baseline_mar * 2.5))
        
        self.mouth_opened = bool(is_inner_open and is_mar_high)

        # Track mouth open duration
        if self.mouth_opened:
            if self.mouth_open_start_time is None:
                self.mouth_open_start_time = current_time
        else:
            self.mouth_open_start_time = None

        mouth_hold_elapsed = (current_time - self.mouth_open_start_time) if self.mouth_open_start_time else 0.0

        # ── SCROLL: Genuine Mouth Open + Head Tilt ────────────────────
        if self.mouth_opened and mouth_hold_elapsed >= self.scroll_hold_time:
            is_up = (tilt_y < -9.0) or (pitch_angle > max(5.0, self.scroll_pitch_deadzone))
            is_down = (tilt_y > 9.0) or (pitch_angle < -max(5.0, self.scroll_pitch_deadzone))

            if is_up:
                trigger_action = 'scroll_up'
            elif is_down:
                trigger_action = 'scroll_down'

        # Closure classifications
        diff = abs(drop_l - drop_r)
        # Dual blink: both eyes drop significantly
        is_dual_blink = (drop_l >= 0.12 and drop_r >= 0.12 and diff < 0.22)
        
        # Asymmetric wink: winking eye drops >= 0.12, other eye drops noticeably less
        is_left_wink = (drop_l >= 0.12 and (drop_l - drop_r >= 0.06)) and not is_dual_blink
        is_right_wink = (drop_r >= 0.12 and (drop_r - drop_l >= 0.06)) and not is_dual_blink

        # ── DUAL-EYE BLINK → Double Click (0.35s hold) ───────────────
        if is_dual_blink:
            self.is_blinking = True
            self.is_left_winking = False
            self.is_right_winking = False
            self.left_wink_start_time = None
            self.right_wink_start_time = None

            if self.blink_start_time is None:
                self.blink_start_time = current_time

            elapsed = current_time - self.blink_start_time
            hold_progress = min(1.0, elapsed / self.double_click_hold_time)

            if elapsed >= self.double_click_hold_time:
                if (current_time - self.last_click_time) > self.click_cooldown:
                    trigger_action = 'double_click'
                    self.last_click_time = current_time
                    self.blink_start_time = None
        else:
            self.is_blinking = False
            self.blink_start_time = None

        # ── LEFT WINK → Left Click (0.12s hold) ──────────────────────
        if not self.is_blinking and is_left_wink:
            self.is_left_winking = True
            self.is_right_winking = False
            self.right_wink_start_time = None

            if self.left_wink_start_time is None:
                self.left_wink_start_time = current_time

            elapsed = current_time - self.left_wink_start_time
            hold_progress = max(hold_progress, min(1.0, elapsed / self.wink_hold_time))

            if elapsed >= self.wink_hold_time:
                if (current_time - self.last_click_time) > self.click_cooldown:
                    trigger_action = 'left_click'
                    self.last_click_time = current_time
                    self.left_wink_start_time = None
        else:
            if not self.is_blinking:
                self.is_left_winking = False
                self.left_wink_start_time = None

        # ── RIGHT WINK → Right Click (0.12s hold) ─────────────────────
        if not self.is_blinking and is_right_wink:
            self.is_right_winking = True
            self.is_left_winking = False
            self.left_wink_start_time = None

            if self.right_wink_start_time is None:
                self.right_wink_start_time = current_time

            elapsed = current_time - self.right_wink_start_time
            hold_progress = max(hold_progress, min(1.0, elapsed / self.wink_hold_time))

            if elapsed >= self.wink_hold_time:
                if (current_time - self.last_click_time) > self.click_cooldown:
                    trigger_action = 'right_click'
                    self.last_click_time = current_time
                    self.right_wink_start_time = None
        else:
            if not self.is_blinking:
                self.is_right_winking = False
                self.right_wink_start_time = None

        return {
            'left_ear':        l_ear,
            'right_ear':       r_ear,
            'drop_l':          drop_l,
            'drop_r':          drop_r,
            'baseline_l_ear':  self.baseline_l_ear,
            'baseline_r_ear':  self.baseline_r_ear,
            'mar':             mar,
            'mouth_opened':    self.mouth_opened,
            'is_blinking':     self.is_blinking,
            'is_left_winking': self.is_left_winking,
            'is_right_winking': self.is_right_winking,
            'trigger_action':  trigger_action,
            'hold_progress':   hold_progress,
        }

    def should_suppress_cursor(self) -> bool:
        """Suppress cursor motion during intentional clicks or scrolling."""
        return self.is_left_winking or self.is_right_winking or self.is_blinking or self.mouth_opened
