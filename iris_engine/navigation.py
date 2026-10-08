import time
import math
from typing import Tuple, Optional, Dict, Any, List
import numpy as np
import cv2

class PointerNavigationEngine:
    """
    Advanced Multi-Method Pointer Navigation & Precision Targeting Engine.
    
    Implements 4 selectable navigation methods derived from HCI & Fitts's Law literature:
    1. BALLISTICS_RELATIVE: Non-linear sigmoid velocity ballistics with continuous soft deadzone
       (ergonomic, zero neck strain, sub-pixel precision at low speeds, fast sweep at high speeds).
    2. HYBRID_GAZE_POSE: Dual-stage control fusing head orientation (coarse glide) with
       sub-pixel iris/pupil deflection (fine-grained target snap).
    3. ABSOLUTE_ANCHOR: Calibrated raycasting with non-linear Control-Display transfer function.
    4. VELOCITY_JOYSTICK: Rate control joystick mode driven by head angle relative to resting neutral.

    Includes:
    - Integrated Fixation Dwell-Click Engine (hands-free auto-click with animated circular gauge).
    - 5-Point Affine Desktop Calibration Solver.
    """

    METHOD_BALLISTICS_RELATIVE = "ballistics_relative"
    METHOD_HYBRID_GAZE_POSE = "hybrid_gaze_pose"
    METHOD_ABSOLUTE_ANCHOR = "absolute_anchor"
    METHOD_VELOCITY_JOYSTICK = "velocity_joystick"

    ALL_METHODS = [
        METHOD_BALLISTICS_RELATIVE,
        METHOD_HYBRID_GAZE_POSE,
        METHOD_ABSOLUTE_ANCHOR,
        METHOD_VELOCITY_JOYSTICK
    ]

    def __init__(
        self,
        screen_w: int,
        screen_h: int,
        default_method: str = METHOD_BALLISTICS_RELATIVE,
        base_sensitivity: float = 1.0,
        enable_dwell_click: bool = False,
        dwell_time: float = 0.70,
        dwell_radius: float = 24.0
    ):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.current_method = default_method
        self.sensitivity = base_sensitivity
        self.is_sniper = False

        # Virtual cursor position (floating float coordinates)
        self.cursor_x = float(screen_w // 2)
        self.cursor_y = float(screen_h // 2)

        # Reference anchor points
        self.anchor_laser: Optional[Tuple[float, float]] = None
        self.prev_input_pt: Optional[Tuple[float, float]] = None
        self.prev_time: float = time.time()

        # Dwell click state
        self.enable_dwell_click = enable_dwell_click
        self.dwell_time = dwell_time
        self.dwell_radius = dwell_radius
        self.dwell_start_time: Optional[float] = None
        self.dwell_anchor_pos: Optional[Tuple[float, float]] = None
        self.dwell_progress: float = 0.0
        self.last_dwell_click_time: float = 0.0
        self.dwell_cooldown: float = 1.0

        # Continuous Soft Deadzone parameters
        self.deadzone_inner = 0.8   # Inner threshold where speed attenuation is 0
        self.deadzone_outer = 4.0   # Outer threshold where speed reaches 100%

        # Ballistics curve parameters
        self.ballistic_accel = 2.2
        self.ballistic_v_half = 12.0

        # Calibration state
        self.is_calibrated = False
        self.affine_matrix: Optional[np.ndarray] = None
        self.calib_step = 0
        self.calib_samples: List[Tuple[float, float]] = []

    def set_method(self, method: str) -> None:
        if method in self.ALL_METHODS:
            self.current_method = method
            # Reset anchors on mode switch
            self.prev_input_pt = None

    def cycle_method(self) -> str:
        idx = self.ALL_METHODS.index(self.current_method)
        next_idx = (idx + 1) % len(self.ALL_METHODS)
        self.set_method(self.ALL_METHODS[next_idx])
        return self.current_method

    def recenter(self, current_laser: Optional[Tuple[float, float]] = None) -> None:
        """Recenters cursor to screen center and resets tracking anchors."""
        self.cursor_x = float(self.screen_w // 2)
        self.cursor_y = float(self.screen_h // 2)
        if current_laser is not None:
            self.anchor_laser = current_laser
            self.prev_input_pt = current_laser
        self.dwell_start_time = None
        self.dwell_progress = 0.0

    def _apply_soft_deadzone(self, dx: float, dy: float) -> Tuple[float, float, float]:
        """
        Applies continuous cubic Hermite smoothstep attenuation to input deltas.
        Prevents jitter and eliminates laddering jumps.
        Returns: (attenuated_dx, attenuated_dy, speed)
        """
        speed = math.hypot(dx, dy)
        if speed <= self.deadzone_inner:
            return 0.0, 0.0, 0.0
        elif speed >= self.deadzone_outer:
            factor = 1.0
        else:
            # Hermite smoothstep transition
            t = (speed - self.deadzone_inner) / (self.deadzone_outer - self.deadzone_inner)
            factor = t * t * (3.0 - 2.0 * t)

        return dx * factor, dy * factor, speed

    def _calculate_ballistic_gain(self, speed: float) -> float:
        """
        Fitts' Law Sigmoid Ballistic Transfer Function.
        Micro-movements receive low gain for 1-pixel targeting;
        fast saccades accelerate to easily cross 1080p/4K monitors.
        """
        eff_sens = (self.sensitivity * 0.32) if self.is_sniper else self.sensitivity
        # Hill/Sigmoid saturation curve
        gain_mult = 1.0 + self.ballistic_accel * (math.pow(speed, 1.8) / (math.pow(speed, 1.8) + math.pow(self.ballistic_v_half, 1.8)))
        return eff_sens * gain_mult

    def update(
        self,
        laser_pt: Tuple[float, float],
        euler_angles: Tuple[float, float, float],
        gaze_offset: Tuple[float, float],
        current_time: float
    ) -> Tuple[float, float, Optional[str]]:
        """
        Computes the new cursor coordinate based on the selected navigation method.
        Returns: (target_cursor_x, target_cursor_y, triggered_action)
        """
        dt = max(1e-4, current_time - self.prev_time)
        self.prev_time = current_time

        lx, ly = laser_pt
        pitch, yaw, roll = euler_angles
        gx, gy = gaze_offset

        if self.anchor_laser is None:
            self.anchor_laser = (lx, ly)
        if self.prev_input_pt is None:
            self.prev_input_pt = (lx, ly)

        prev_lx, prev_ly = self.prev_input_pt
        raw_dx = lx - prev_lx
        raw_dy = ly - prev_ly
        self.prev_input_pt = (lx, ly)

        # -------------------------------------------------------------
        # 1. Method: BALLISTICS_RELATIVE (Fitts' Law Non-Linear Gain)
        # -------------------------------------------------------------
        if self.current_method == self.METHOD_BALLISTICS_RELATIVE:
            soft_dx, soft_dy, speed = self._apply_soft_deadzone(raw_dx, raw_dy)
            gain = self._calculate_ballistic_gain(speed)
            
            # Map head delta to cursor displacement
            disp_x = soft_dx * gain * 3.8
            disp_y = soft_dy * gain * 3.8

            self.cursor_x += disp_x
            self.cursor_y += disp_y

        # -------------------------------------------------------------
        # 2. Method: HYBRID_GAZE_POSE (Head Glide + Iris Micro-Trim)
        # -------------------------------------------------------------
        elif self.current_method == self.METHOD_HYBRID_GAZE_POSE:
            soft_dx, soft_dy, speed = self._apply_soft_deadzone(raw_dx, raw_dy)
            gain = self._calculate_ballistic_gain(speed)

            # Head coarse movement
            disp_x = soft_dx * gain * 3.6
            disp_y = soft_dy * gain * 3.6
            self.cursor_x += disp_x
            self.cursor_y += disp_y

            # Iris gaze fine-trim offset (up to +-35 pixels snap)
            trim_scale = 35.0 if not self.is_sniper else 12.0
            iris_trim_x = gx * trim_scale
            iris_trim_y = gy * trim_scale

            eff_x = self.cursor_x + iris_trim_x
            eff_y = self.cursor_y + iris_trim_y
            target_x = float(np.clip(eff_x, 0, self.screen_w - 1))
            target_y = float(np.clip(eff_y, 0, self.screen_h - 1))
            self.cursor_x = np.clip(self.cursor_x, 0, self.screen_w - 1)
            self.cursor_y = np.clip(self.cursor_y, 0, self.screen_h - 1)
            
            triggered_action = self._update_dwell(target_x, target_y, current_time)
            return target_x, target_y, triggered_action

        # -------------------------------------------------------------
        # 3. Method: ABSOLUTE_ANCHOR (Calibrated Absolute Raycast)
        # -------------------------------------------------------------
        elif self.current_method == self.METHOD_ABSOLUTE_ANCHOR:
            eff_sens = (self.sensitivity * 0.32) if self.is_sniper else self.sensitivity
            ax, ay = self.anchor_laser
            rel_x = (lx - ax) * eff_sens * 0.05
            rel_y = (ly - ay) * eff_sens * 0.05

            # Non-linear power transfer function for comfortable borders
            sign_x = 1.0 if rel_x >= 0 else -1.0
            sign_y = 1.0 if rel_y >= 0 else -1.0
            curved_x = sign_x * math.pow(abs(rel_x), 1.25)
            curved_y = sign_y * math.pow(abs(rel_y), 1.25)

            target_abs_x = (self.screen_w / 2.0) + curved_x * (self.screen_w / 2.0)
            target_abs_y = (self.screen_h / 2.0) + curved_y * (self.screen_h / 2.0)

            # Smooth follow
            alpha = 0.25
            self.cursor_x = alpha * target_abs_x + (1.0 - alpha) * self.cursor_x
            self.cursor_y = alpha * target_abs_y + (1.0 - alpha) * self.cursor_y

        # -------------------------------------------------------------
        # 4. Method: VELOCITY_JOYSTICK (Angle Proportional Rate Control)
        # -------------------------------------------------------------
        elif self.current_method == self.METHOD_VELOCITY_JOYSTICK:
            eff_sens = (self.sensitivity * 0.35) if self.is_sniper else self.sensitivity
            # Use pitch and yaw as virtual joystick axes
            joy_x = yaw * 0.20
            joy_y = -pitch * 0.25

            soft_jx, soft_jy, j_mag = self._apply_soft_deadzone(joy_x, joy_y)
            if j_mag > 0.0:
                speed_scale = math.pow(j_mag, 1.4) * eff_sens * 350.0
                norm_x = soft_jx / j_mag
                norm_y = soft_jy / j_mag
                self.cursor_x += norm_x * speed_scale * dt
                self.cursor_y += norm_y * speed_scale * dt

        # Clip cursor to screen bounds
        self.cursor_x = float(np.clip(self.cursor_x, 0, self.screen_w - 1))
        self.cursor_y = float(np.clip(self.cursor_y, 0, self.screen_h - 1))

        # Check dwell-click state machine
        triggered_action = self._update_dwell(self.cursor_x, self.cursor_y, current_time)

        return self.cursor_x, self.cursor_y, triggered_action

    def _update_dwell(self, cur_x: float, cur_y: float, current_time: float) -> Optional[str]:
        """Evaluates hands-free dwell fixation clicking."""
        if not self.enable_dwell_click:
            self.dwell_progress = 0.0
            self.dwell_start_time = None
            return None

        if self.dwell_anchor_pos is None:
            self.dwell_anchor_pos = (cur_x, cur_y)
            self.dwell_start_time = current_time
            self.dwell_progress = 0.0
            return None

        ax, ay = self.dwell_anchor_pos
        dist = math.hypot(cur_x - ax, cur_y - ay)

        if dist > self.dwell_radius:
            # Cursor moved out of fixation radius: reset dwell anchor
            self.dwell_anchor_pos = (cur_x, cur_y)
            self.dwell_start_time = current_time
            self.dwell_progress = 0.0
            return None

        if self.dwell_start_time is None:
            self.dwell_start_time = current_time

        elapsed = current_time - self.dwell_start_time
        self.dwell_progress = min(1.0, elapsed / self.dwell_time)

        if self.dwell_progress >= 1.0:
            if (current_time - self.last_dwell_click_time) > self.dwell_cooldown:
                self.last_dwell_click_time = current_time
                self.dwell_start_time = current_time
                self.dwell_progress = 0.0
                return 'dwell_click'

        return None

    def get_5point_calibration_targets(self) -> List[Tuple[int, int, str]]:
        """Returns standard 5-point desktop calibration targets."""
        w, h = self.screen_w, self.screen_h
        return [
            (w // 2, h // 2, "CENTER"),
            (int(w * 0.15), int(h * 0.15), "TOP-LEFT"),
            (int(w * 0.85), int(h * 0.15), "TOP-RIGHT"),
            (int(w * 0.15), int(h * 0.85), "BOTTOM-LEFT"),
            (int(w * 0.85), int(h * 0.85), "BOTTOM-RIGHT")
        ]

    def solve_affine_calibration(
        self, 
        recorded_head_pts: List[Tuple[float, float]], 
        target_screen_pts: List[Tuple[float, float]]
    ) -> bool:
        """Solves optimal affine transformation mapping user head points to screen space."""
        if len(recorded_head_pts) < 3 or len(target_screen_pts) < 3:
            return False

        src = np.array(recorded_head_pts, dtype=np.float32)
        dst = np.array(target_screen_pts, dtype=np.float32)

        matrix, inliers = cv2.estimateAffine2D(src, dst)
        if matrix is not None:
            self.affine_matrix = matrix
            self.is_calibrated = True
            return True
        return False
