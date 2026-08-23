import unittest
import time
import os
import numpy as np
import cv2

# Import engine components
from iris_engine.filters import OneEuroFilter, OneEuroFilter2D
from iris_engine.preprocessor import LightingCompensator
from iris_engine.pose_estimator import HeadPoseEstimator
from iris_engine.gesture_engine import GestureEngine
from iris_engine.controller import WindowsCursorController
from iris_engine.tracker import FastFaceMeshTracker

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

        # Now simulate Left Wink (User closes left eye: height drops from 16 to 2)
        dummy_landmarks[385] = [190, 199, 0]; dummy_landmarks[387] = [210, 199, 0]
        dummy_landmarks[380] = [190, 201, 0]; dummy_landmarks[373] = [210, 201, 0]
        
        t0 = time.time()
        res_wink1 = engine.process_frame(dummy_landmarks, t0)
        self.assertTrue(res_wink1['is_left_winking'], "Left wink was not detected by asymmetry ratio.")

        # Reset left eye to open, simulate Right Wink (User closes right eye)
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
        """Verify controller bounds and click/sound methods."""
        controller = WindowsCursorController(enable_sound=False)
        sw, sh = controller.get_screen_size()
        cx, cy = controller.move_to(-50, -50)
        self.assertEqual((cx, cy), (0, 0))

    def test_onnx_tracker_throughput(self):
        """Verify ONNX FaceMesh throughput."""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        yunet_path = os.path.join(base_dir, "models", "face_detection_yunet.onnx")
        facemesh_path = os.path.join(base_dir, "models", "FaceMesh.onnx")

        tracker = FastFaceMeshTracker(yunet_path, facemesh_path, input_size=(640, 480))
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Warmup (2 iterations)
        _ = tracker.detect_and_track(dummy_frame)
        _ = tracker.detect_and_track(dummy_frame)
        
        t0 = time.time()
        res = tracker.detect_and_track(dummy_frame)
        t1 = time.time()
        self.assertIsNone(res)
        self.assertLess((t1 - t0) * 1000.0, 30.0)

if __name__ == "__main__":
    unittest.main()
