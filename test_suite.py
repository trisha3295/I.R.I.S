import unittest
import time
import os
import numpy as np
import cv2

# Import engine components
from iris_engine.filters import OneEuroFilter, OneEuroFilter2D, SoftDeadzone2D
from iris_engine.preprocessor import LightingCompensator
from iris_engine.pose_estimator import HeadPoseEstimator
from iris_engine.gesture_engine import GestureEngine
from iris_engine.controller import WindowsCursorController
from iris_engine.tracker import FastFaceMeshTracker
from iris_engine.iris_detector import IrisGazeDetector
from iris_engine.navigation import PointerNavigationEngine

class TestIRISEngine(unittest.TestCase):

    def test_one_euro_filter_smoothing(self):
        """Verify that OneEuroFilter removes high-frequency jitter at rest."""
        t0 = time.time()
        f = OneEuroFilter(t0, 100.0, min_cutoff=0.005, beta=0.001)
        
        np.random.seed(42)
        outputs = []
        for i in range(50):
            t = t0 + i * 0.033
            noisy_x = 100.0 + np.random.normal(0, 2.0)
            filtered_x = f.filter(t, noisy_x)
            outputs.append(filtered_x)

        filtered_std = np.std(outputs[10:])
        self.assertLess(filtered_std, 2.0 * 0.35, "Filter failed to dampen stationary jitter.")

    def test_soft_deadzone_continuity(self):
        """Verify continuous cubic Hermite deadzone eliminates jump discontinuities."""
        deadzone = SoftDeadzone2D(inner_radius=1.0, outer_radius=4.0)
        
        # Below inner radius: 0 attenuation
        dx, dy, spd = deadzone.apply(0.5, 0.0)
        self.assertEqual(dx, 0.0)
        self.assertEqual(dy, 0.0)

        # Above outer radius: 100% transmission
        dx, dy, spd = deadzone.apply(5.0, 0.0)
        self.assertEqual(dx, 5.0)

        # Inside transition zone: continuous monotonic curve without sudden jumps
        prev_dx = 0.0
        for r in np.linspace(1.0, 4.0, 15):
            cur_dx, _, _ = deadzone.apply(float(r), 0.0)
            self.assertGreaterEqual(cur_dx, prev_dx)
            self.assertLessEqual(cur_dx, r)
            prev_dx = cur_dx

    def test_lighting_compensator(self):
        """Verify CLAHE luminance compensation in YCrCb color space."""
        compensator = LightingCompensator(clip_limit=2.0, tile_grid_size=(8, 8))
        dark_frame = np.ones((480, 640, 3), dtype=np.uint8) * 30
        enhanced_rgb = compensator.process(dark_frame)
        self.assertEqual(enhanced_rgb.shape, (480, 640, 3))
        self.assertGreater(np.mean(enhanced_rgb), np.mean(dark_frame))

    def test_asymmetry_wink_detection(self):
        """Verify relative asymmetry ratio for effortless left and right winks."""
        engine = GestureEngine(asymmetry_threshold=0.28, wink_hold_time=0.18)
        
        dummy_landmarks = np.zeros((468, 3), dtype=np.float32)
        
        # User Left Eye (EYE_LEFT_ANATOMIC: 362, 385, 387, 263, 373, 380)
        dummy_landmarks[362] = [180, 200, 0]; dummy_landmarks[263] = [220, 200, 0]
        dummy_landmarks[385] = [190, 192, 0]; dummy_landmarks[387] = [210, 192, 0]
        dummy_landmarks[380] = [190, 208, 0]; dummy_landmarks[373] = [210, 208, 0]

        # User Right Eye (EYE_RIGHT_ANATOMIC: 33, 160, 158, 133, 153, 144)
        dummy_landmarks[33] = [380, 200, 0]; dummy_landmarks[133] = [420, 200, 0]
        dummy_landmarks[160] = [390, 192, 0]; dummy_landmarks[158] = [410, 192, 0]
        dummy_landmarks[144] = [390, 208, 0]; dummy_landmarks[153] = [410, 208, 0]

        # Mouth landmarks
        dummy_landmarks[13] = [300, 320, 0]; dummy_landmarks[14] = [300, 330, 0]
        dummy_landmarks[78] = [280, 325, 0]; dummy_landmarks[308] = [320, 325, 0]

        res = engine.process_frame(dummy_landmarks, time.time())
        self.assertGreater(res['left_ear'], 0.25)
        self.assertGreater(res['right_ear'], 0.25)
        self.assertFalse(res['is_left_winking'])
        self.assertFalse(res['is_right_winking'])

        # Simulate Left Wink
        dummy_landmarks[385] = [190, 199, 0]; dummy_landmarks[387] = [210, 199, 0]
        dummy_landmarks[380] = [190, 201, 0]; dummy_landmarks[373] = [210, 201, 0]
        
        t0 = time.time()
        res_wink1 = engine.process_frame(dummy_landmarks, t0)
        self.assertTrue(res_wink1['is_left_winking'], "Left wink was not detected by asymmetry ratio.")

        # Reset left eye to open, simulate Right Wink
        dummy_landmarks[385] = [190, 192, 0]; dummy_landmarks[387] = [210, 192, 0]
        dummy_landmarks[380] = [190, 208, 0]; dummy_landmarks[373] = [210, 208, 0]

        dummy_landmarks[160] = [390, 199, 0]; dummy_landmarks[158] = [410, 199, 0]
        dummy_landmarks[144] = [390, 201, 0]; dummy_landmarks[153] = [410, 201, 0]

        res_wink2 = engine.process_frame(dummy_landmarks, t0 + 0.1)
        self.assertTrue(res_wink2['is_right_winking'], "Right wink was not detected by asymmetry ratio.")

    def test_pose_estimator_solve_pnp(self):
        """Verify 6-DOF Perspective-n-Point pose calculation."""
        estimator = HeadPoseEstimator()
        dummy_landmarks = np.zeros((468, 3), dtype=np.float32)
        dummy_landmarks[1] = [320, 240, 0]; dummy_landmarks[152] = [320, 340, 0]
        dummy_landmarks[33] = [260, 200, 0]; dummy_landmarks[263] = [380, 200, 0]
        dummy_landmarks[61] = [280, 300, 0]; dummy_landmarks[291] = [360, 300, 0]

        success, proj, rvec, tvec = estimator.estimate_pose(dummy_landmarks, 640, 480)
        self.assertTrue(success)
        self.assertIsNotNone(proj)

    def test_windows_cursor_controller(self):
        """Verify controller bounds and screen metrics."""
        controller = WindowsCursorController(enable_sound=False)
        sw, sh = controller.get_screen_size()
        self.assertGreater(sw, 0)
        self.assertGreater(sh, 0)
        cx, cy = controller.move_to(-50, -50)
        self.assertEqual((cx, cy), (0, 0))

    def test_iris_gaze_detector_speed_and_ratios(self):
        """Verify sub-millisecond pupil extraction and normalized gaze ratios."""
        detector = IrisGazeDetector()
        
        # Create a synthetic eye image
        frame = np.ones((480, 640, 3), dtype=np.uint8) * 220
        # Draw dark pupils
        cv2.circle(frame, (200, 200), 5, (20, 20, 20), -1)
        cv2.circle(frame, (400, 200), 5, (20, 20, 20), -1)

        dummy_landmarks = np.zeros((468, 3), dtype=np.float32)
        # Populate eye contour points around the drawn pupils
        for idx in detector.EYE_LEFT_CONTOUR:
            dummy_landmarks[idx] = [200 + np.random.uniform(-20, 20), 200 + np.random.uniform(-10, 10), 0]
        for idx in detector.EYE_RIGHT_CONTOUR:
            dummy_landmarks[idx] = [400 + np.random.uniform(-20, 20), 200 + np.random.uniform(-10, 10), 0]

        # Specific canthi
        dummy_landmarks[33] = [180, 200, 0]; dummy_landmarks[133] = [220, 200, 0]
        dummy_landmarks[159] = [200, 190, 0]; dummy_landmarks[145] = [200, 210, 0]
        dummy_landmarks[362] = [380, 200, 0]; dummy_landmarks[263] = [420, 200, 0]
        dummy_landmarks[386] = [400, 190, 0]; dummy_landmarks[374] = [400, 210, 0]

        t0 = time.time()
        for _ in range(50):
            res = detector.estimate_iris_gaze(frame, dummy_landmarks, is_blinking=False)
        t1 = time.time()

        avg_ms = ((t1 - t0) / 50.0) * 1000.0
        self.assertLess(avg_ms, 2.5, f"Iris detector took {avg_ms:.2f}ms (expected < 2.5ms)")
        self.assertIn('gaze_offset_x', res)
        self.assertIn('gaze_offset_y', res)

    def test_pointer_navigation_modes(self):
        """Verify all 4 pointer navigation modes and ballistics curves."""
        nav = PointerNavigationEngine(screen_w=1920, screen_h=1080)
        
        # 1. Test Ballistics Relative
        nav.set_method(PointerNavigationEngine.METHOD_BALLISTICS_RELATIVE)
        t = time.time()
        x1, y1, _ = nav.update((100.0, 100.0), (0, 0, 0), (0, 0), t)
        # Micro head move: small delta
        x2, y2, _ = nav.update((101.5, 100.0), (0, 0, 0), (0, 0), t + 0.033)
        small_disp = abs(x2 - x1)
        
        # Fast head saccade: large delta
        x3, y3, _ = nav.update((120.0, 100.0), (0, 0, 0), (0, 0), t + 0.066)
        large_disp = abs(x3 - x2)

        # Non-linear ballistics should accelerate faster displacement disproportionately
        self.assertGreater(large_disp, small_disp * 4.0, "Ballistics curve failed to accelerate large saccade.")

        # 2. Test Hybrid Gaze Pose
        nav.set_method(PointerNavigationEngine.METHOD_HYBRID_GAZE_POSE)
        hx1, hy1, _ = nav.update((120.0, 100.0), (0, 0, 0), (0.0, 0.0), t + 0.10)
        # Eye flick right (+0.5 offset) while head stays still
        hx2, hy2, _ = nav.update((120.0, 100.0), (0, 0, 0), (0.5, 0.0), t + 0.133)
        self.assertGreater(hx2, hx1, "Hybrid gaze offset failed to trim cursor position.")

        # 3. Test Cycle Methods
        initial_m = nav.current_method
        nav.cycle_method()
        self.assertNotEqual(nav.current_method, initial_m)

    def test_dwell_click_engine(self):
        """Verify fixation dwell-time clicking state machine."""
        nav = PointerNavigationEngine(
            screen_w=1920, 
            screen_h=1080, 
            enable_dwell_click=True,
            dwell_time=0.20, # Fast 200ms for test
            dwell_radius=20.0
        )
        
        t0 = time.time()
        # Initialize position
        _, _, action0 = nav.update((100.0, 100.0), (0, 0, 0), (0, 0), t0)
        self.assertIsNone(action0)

        # Fixate on same spot for 100ms: dwell should progress but not trigger yet
        _, _, action1 = nav.update((100.0, 100.0), (0, 0, 0), (0, 0), t0 + 0.10)
        self.assertIsNone(action1)
        self.assertGreater(nav.dwell_progress, 0.3)

        # Fixate past 200ms dwell threshold: should trigger dwell_click!
        _, _, action2 = nav.update((100.0, 100.0), (0, 0, 0), (0, 0), t0 + 0.22)
        self.assertEqual(action2, 'dwell_click')

    def test_5point_calibration_solver(self):
        """Verify 5-point desktop calibration affine solver."""
        nav = PointerNavigationEngine(screen_w=1920, screen_h=1080)
        targets = nav.get_5point_calibration_targets()
        self.assertEqual(len(targets), 5)

        # Simulate matching head points
        head_pts = [(t[0] * 0.1, t[1] * 0.1) for t in targets]
        screen_pts = [(float(t[0]), float(t[1])) for t in targets]

        success = nav.solve_affine_calibration(head_pts, screen_pts)
        self.assertTrue(success)
        self.assertTrue(nav.is_calibrated)
        self.assertIsNotNone(nav.affine_matrix)

    def test_temporal_facemesh_tracker_throughput(self):
        """Verify landmark-guided temporal FaceMesh tracker throughput."""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        yunet_path = os.path.join(base_dir, "models", "face_detection_yunet.onnx")
        facemesh_path = os.path.join(base_dir, "models", "FaceMesh.onnx")

        tracker = FastFaceMeshTracker(yunet_path, facemesh_path, input_size=(640, 480))
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)

        # First frame initializes
        _ = tracker.detect_and_track(dummy_frame)
        self.assertFalse(tracker.is_tracking)

        # Verify reset
        tracker.reset_tracking()
        self.assertIsNone(tracker.prev_landmarks)

    def test_left_wink_triggers_left_click(self):
        """Verify holding left wink fires left_click trigger action."""
        engine = GestureEngine(wink_hold_time=0.10, click_cooldown=0.20)
        dummy_landmarks = np.zeros((468, 3), dtype=np.float32)

        # Left eye (smaller X on mirrored screen)
        dummy_landmarks[362] = [180, 200, 0]; dummy_landmarks[263] = [220, 200, 0]
        dummy_landmarks[385] = [190, 199, 0]; dummy_landmarks[387] = [210, 199, 0]
        dummy_landmarks[380] = [190, 201, 0]; dummy_landmarks[373] = [210, 201, 0]

        # Right eye open
        dummy_landmarks[33] = [380, 200, 0]; dummy_landmarks[133] = [420, 200, 0]
        dummy_landmarks[160] = [390, 192, 0]; dummy_landmarks[158] = [410, 192, 0]
        dummy_landmarks[144] = [390, 208, 0]; dummy_landmarks[153] = [410, 208, 0]

        # Mouth closed
        dummy_landmarks[13] = [300, 320, 0]; dummy_landmarks[14] = [300, 325, 0]
        dummy_landmarks[78] = [280, 322, 0]; dummy_landmarks[308] = [320, 322, 0]

        t0 = time.time()
        # Start wink
        res1 = engine.process_frame(dummy_landmarks, t0)
        self.assertIsNone(res1['trigger_action'])
        # Hold past wink_hold_time
        res2 = engine.process_frame(dummy_landmarks, t0 + 0.12)
        self.assertEqual(res2['trigger_action'], 'left_click')

    def test_right_wink_triggers_right_click(self):
        """Verify holding right wink fires right_click trigger action."""
        engine = GestureEngine(wink_hold_time=0.10, click_cooldown=0.20)
        dummy_landmarks = np.zeros((468, 3), dtype=np.float32)

        # Left eye open
        dummy_landmarks[362] = [180, 200, 0]; dummy_landmarks[263] = [220, 200, 0]
        dummy_landmarks[385] = [190, 192, 0]; dummy_landmarks[387] = [210, 192, 0]
        dummy_landmarks[380] = [190, 208, 0]; dummy_landmarks[373] = [210, 208, 0]

        # Right eye closed
        dummy_landmarks[33] = [380, 200, 0]; dummy_landmarks[133] = [420, 200, 0]
        dummy_landmarks[160] = [390, 199, 0]; dummy_landmarks[158] = [410, 199, 0]
        dummy_landmarks[144] = [390, 201, 0]; dummy_landmarks[153] = [410, 201, 0]

        # Mouth closed
        dummy_landmarks[13] = [300, 320, 0]; dummy_landmarks[14] = [300, 325, 0]
        dummy_landmarks[78] = [280, 322, 0]; dummy_landmarks[308] = [320, 322, 0]

        t0 = time.time()
        res1 = engine.process_frame(dummy_landmarks, t0)
        self.assertIsNone(res1['trigger_action'])
        res2 = engine.process_frame(dummy_landmarks, t0 + 0.12)
        self.assertEqual(res2['trigger_action'], 'right_click')

    def test_long_blink_triggers_double_click(self):
        """Verify holding both eyes closed (long blink) fires double_click trigger action."""
        engine = GestureEngine(double_click_hold_time=0.30, click_cooldown=0.20)
        dummy_landmarks = np.zeros((468, 3), dtype=np.float32)

        # Both eyes closed
        dummy_landmarks[362] = [180, 200, 0]; dummy_landmarks[263] = [220, 200, 0]
        dummy_landmarks[385] = [190, 199, 0]; dummy_landmarks[387] = [210, 199, 0]
        dummy_landmarks[380] = [190, 201, 0]; dummy_landmarks[373] = [210, 201, 0]

        dummy_landmarks[33] = [380, 200, 0]; dummy_landmarks[133] = [420, 200, 0]
        dummy_landmarks[160] = [390, 199, 0]; dummy_landmarks[158] = [410, 199, 0]
        dummy_landmarks[144] = [390, 201, 0]; dummy_landmarks[153] = [410, 201, 0]

        # Mouth closed
        dummy_landmarks[13] = [300, 320, 0]; dummy_landmarks[14] = [300, 325, 0]
        dummy_landmarks[78] = [280, 322, 0]; dummy_landmarks[308] = [320, 322, 0]

        t0 = time.time()
        # Initial blink frame: should NOT fire double_click immediately (avoids normal blinks)
        res1 = engine.process_frame(dummy_landmarks, t0)
        self.assertTrue(res1['is_blinking'])
        self.assertIsNone(res1['trigger_action'])

        # Before threshold (0.15s): still no click
        res2 = engine.process_frame(dummy_landmarks, t0 + 0.15)
        self.assertIsNone(res2['trigger_action'])

        # Reached 0.32s long blink: fires double_click!
        res3 = engine.process_frame(dummy_landmarks, t0 + 0.32)
        self.assertEqual(res3['trigger_action'], 'double_click')

    def test_mouth_open_scroll_gestures(self):
        """Verify mouth open with head pitch tilt triggers scroll_up and scroll_down."""
        engine = GestureEngine(scroll_pitch_deadzone=5.0)
        dummy_landmarks = np.zeros((468, 3), dtype=np.float32)

        # Both eyes open
        dummy_landmarks[362] = [180, 200, 0]; dummy_landmarks[263] = [220, 200, 0]
        dummy_landmarks[385] = [190, 192, 0]; dummy_landmarks[387] = [210, 192, 0]
        dummy_landmarks[380] = [190, 208, 0]; dummy_landmarks[373] = [210, 208, 0]

        dummy_landmarks[33] = [380, 200, 0]; dummy_landmarks[133] = [420, 200, 0]
        dummy_landmarks[160] = [390, 192, 0]; dummy_landmarks[158] = [410, 192, 0]
        dummy_landmarks[144] = [390, 208, 0]; dummy_landmarks[153] = [410, 208, 0]

        # Mouth wide open (vert = 35, horiz = 40 => MAR = 0.875)
        dummy_landmarks[13] = [300, 310, 0]; dummy_landmarks[14] = [300, 345, 0]
        dummy_landmarks[78] = [280, 325, 0]; dummy_landmarks[308] = [320, 325, 0]

        # Head tilted UP (pitch = +10.0)
        res_up = engine.process_frame(dummy_landmarks, time.time(), pitch_angle=10.0)
        self.assertTrue(res_up['mouth_opened'])
        self.assertEqual(res_up['trigger_action'], 'scroll_up')

        # Head tilted DOWN (pitch = -10.0)
        res_dn = engine.process_frame(dummy_landmarks, time.time() + 0.1, pitch_angle=-10.0)
        self.assertTrue(res_dn['mouth_opened'])
        self.assertEqual(res_dn['trigger_action'], 'scroll_down')

if __name__ == "__main__":
    unittest.main()
