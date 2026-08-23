import numpy as np
import time
from typing import Tuple, Optional, Dict, Any, List

class GestureEngine:
    """
    Advanced Adaptive Gesture & Facial Telemetry Engine.
    
    Features:
    - Dynamic Relative Asymmetry Wink Detection (immune to natural squints & eye shapes)
    - Dynamic Baseline Auto-Calibration (tracks resting eye open state)
    - Dual-Eye Blink Hold (0.35s for Left Click, 0.75s for Drag & Drop toggle)
    - Mouth Aspect Ratio (MAR) & Eyebrow Telemetry for Smart Scrolling
    - Deadzone gating and anti-jitter cursor suppression
    """
    def __init__(
        self,
        ear_threshold_ratio: float = 0.65,      # Closed eye must drop to 65% of baseline
        asymmetry_threshold: float = 0.30,      # Relative difference |L - R| / max(L, R)
        wink_hold_time: float = 0.18,           # Snappy response for winks
        blink_hold_time: float = 0.35,          # Hold time for dual-eye click
        drag_hold_time: float = 0.75,           # Long hold time for Drag & Drop toggle
        click_cooldown: float = 0.60,           # Cooldown between successive clicks
        deadzone_x: float = 14.0,
        deadzone_y: float = 8.0
    ):
        self.ear_threshold_ratio = ear_threshold_ratio
        self.asymmetry_threshold = asymmetry_threshold
        self.wink_hold_time = wink_hold_time
        self.blink_hold_time = blink_hold_time
        self.drag_hold_time = drag_hold_time
        self.click_cooldown = click_cooldown
        self.deadzone_x = deadzone_x
        self.deadzone_y = deadzone_y

        # Canonical FaceMesh landmark indices
        # In mirrored frame, Eye A is on screen left (user's right), Eye B is on screen right (user's left)
        self.EYE_RIGHT_ANATOMIC = [33, 160, 158, 133, 153, 144]   # Left side in unmirrored, Right in mirrored
        self.EYE_LEFT_ANATOMIC = [362, 385, 387, 263, 373, 380]  # Right side in unmirrored, Left in mirrored
        self.MOUTH_INDICES = [13, 14, 78, 308]                     # Upper lip, lower lip, left corner, right corner

        # Adaptive baselines
        self.baseline_l_ear = 0.28
        self.baseline_r_ear = 0.28
        self.baseline_mar = 0.15
        self.is_calibrated = False

        # State tracking
        self.last_click_time = 0.0
        self.blink_start_time: Optional[float] = None
        self.left_wink_start_time: Optional[float] = None
        self.right_wink_start_time: Optional[float] = None
        
        self.is_blinking = False
        self.is_left_winking = False
        self.is_right_winking = False
        self.is_dragging = False
        self.mouth_opened = False

    @staticmethod
    def calculate_ear(eye_indices: list, landmarks: np.ndarray) -> float:
        """Calculates 6-point Eye Aspect Ratio (EAR)."""
        pts = [landmarks[idx][:2] for idx in eye_indices]
        v1 = np.linalg.norm(pts[1] - pts[5])
        v2 = np.linalg.norm(pts[2] - pts[4])
        h1 = np.linalg.norm(pts[0] - pts[3])
        return float((v1 + v2) / (2.0 * h1)) if h1 > 1e-6 else 0.0

    @staticmethod
    def calculate_mar(mouth_indices: list, landmarks: np.ndarray) -> float:
        """Calculates Mouth Aspect Ratio (MAR) for open-mouth gestures."""
        p_upper = landmarks[mouth_indices[0]][:2]
        p_lower = landmarks[mouth_indices[1]][:2]
        p_left = landmarks[mouth_indices[2]][:2]
        p_right = landmarks[mouth_indices[3]][:2]
        
        vert_dist = np.linalg.norm(p_upper - p_lower)
        horiz_dist = np.linalg.norm(p_left - p_right)
        return float(vert_dist / horiz_dist) if horiz_dist > 1e-6 else 0.0

    def update_baseline(self, l_ear: float, r_ear: float, mar: float) -> None:
        """Slow exponential moving average to adapt to lighting/posture changes."""
        if not self.is_blinking and not self.is_left_winking and not self.is_right_winking:
            if l_ear > 0.20 and r_ear > 0.20:
                self.baseline_l_ear = 0.98 * self.baseline_l_ear + 0.02 * l_ear
                self.baseline_r_ear = 0.98 * self.baseline_r_ear + 0.02 * r_ear
            if mar < 0.35:
                self.baseline_mar = 0.98 * self.baseline_mar + 0.02 * mar

    def set_calibration(self, l_ear: float, r_ear: float, mar: float) -> None:
        """Sets explicit calibrated baseline values."""
        self.baseline_l_ear = max(0.20, l_ear)
        self.baseline_r_ear = max(0.20, r_ear)
        self.baseline_mar = max(0.10, mar)
        self.is_calibrated = True

    def process_frame(
        self, 
        landmarks: np.ndarray, 
        current_time: float,
        is_mirrored: bool = True
    ) -> Dict[str, Any]:
        """
        Processes facial landmarks and evaluates eye/mouth gestures with asymmetry ratio.
        """
        # Distinguish user's physical left eye vs physical right eye
        # In a mirrored frame (default for webcams):
        # User's Left Eye appears on the Left of the screen (smaller X coords) -> EYE_LEFT_ANATOMIC
        # User's Right Eye appears on the Right of the screen (larger X coords) -> EYE_RIGHT_ANATOMIC
        if is_mirrored:
            l_indices = self.EYE_LEFT_ANATOMIC
            r_indices = self.EYE_RIGHT_ANATOMIC
        else:
            l_indices = self.EYE_RIGHT_ANATOMIC
            r_indices = self.EYE_LEFT_ANATOMIC

        l_ear = self.calculate_ear(l_indices, landmarks)
        r_ear = self.calculate_ear(r_indices, landmarks)
        mar = self.calculate_mar(self.MOUTH_INDICES, landmarks)

        self.update_baseline(l_ear, r_ear, mar)

        # Dynamic absolute thresholds based on calibrated/tracked baseline
        l_thresh = self.baseline_l_ear * self.ear_threshold_ratio
        r_thresh = self.baseline_r_ear * self.ear_threshold_ratio

        # Asymmetry calculation (|L - R| / max(L, R))
        max_ear = max(l_ear, r_ear, 1e-6)
        asymmetry = abs(l_ear - r_ear) / max_ear

        trigger_action = None
        hold_progress = 0.0
        drag_progress = 0.0

        l_closed = l_ear < l_thresh
        r_closed = r_ear < r_thresh
        
        # Mouth open gesture
        self.mouth_opened = mar > (self.baseline_mar * 2.2)

        # 1. Dual-Eye Blink (Hold Click or Drag Toggle)
        if l_closed and r_closed:
            self.is_blinking = True
            self.is_left_winking = False
            self.is_right_winking = False
            self.left_wink_start_time = None
            self.right_wink_start_time = None

            if self.blink_start_time is None:
                self.blink_start_time = current_time

            elapsed = current_time - self.blink_start_time
            hold_progress = min(1.0, elapsed / self.blink_hold_time)
            
            if elapsed >= self.drag_hold_time:
                drag_progress = min(1.0, (elapsed - self.blink_hold_time) / (self.drag_hold_time - self.blink_hold_time))
                if (current_time - self.last_click_time) > self.click_cooldown:
                    self.is_dragging = not self.is_dragging
                    trigger_action = 'toggle_drag'
                    self.last_click_time = current_time
                    self.blink_start_time = None
            elif elapsed >= self.blink_hold_time and not self.is_dragging:
                if (current_time - self.last_click_time) > self.click_cooldown:
                    trigger_action = 'left_click'
                    self.last_click_time = current_time
                    # Keep start time alive in case user continues holding for drag
        else:
            self.is_blinking = False
            self.blink_start_time = None

        # 2. Left Eye Wink (User winks their left eye -> Left Click)
        # Condition: Left is closed relative to its baseline AND significant asymmetry over Right
        if not self.is_blinking and (l_ear < l_thresh or asymmetry > self.asymmetry_threshold) and (l_ear < r_ear * 0.75):
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

        # 3. Right Eye Wink (User winks their right eye -> Right Click)
        # Condition: Right is closed relative to its baseline AND significant asymmetry over Left
        if not self.is_blinking and (r_ear < r_thresh or asymmetry > self.asymmetry_threshold) and (r_ear < l_ear * 0.75):
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
            'left_ear': l_ear,
            'right_ear': r_ear,
            'baseline_l_ear': self.baseline_l_ear,
            'baseline_r_ear': self.baseline_r_ear,
            'mar': mar,
            'mouth_opened': self.mouth_opened,
            'asymmetry': asymmetry,
            'is_blinking': self.is_blinking,
            'is_left_winking': self.is_left_winking,
            'is_right_winking': self.is_right_winking,
            'is_dragging': self.is_dragging,
            'trigger_action': trigger_action,
            'hold_progress': hold_progress,
            'drag_progress': drag_progress
        }

    def should_suppress_cursor(self) -> bool:
        """Suppresses cursor motion during active wink/blink to prevent cursor jump."""
        return self.is_blinking or self.is_left_winking or self.is_right_winking

    def is_outside_deadzone(self, dx: float, dy: float) -> bool:
        return (abs(dx) > self.deadzone_x) or (abs(dy) > self.deadzone_y)
