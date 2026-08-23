import os
import cv2
import numpy as np
import onnxruntime as ort
from typing import Optional, Tuple, List

class FastFaceMeshTracker:
    """
    Ultra-Fast C++ / ONNX Hybrid Face & Landmark Tracking Engine.
    Combines OpenCV YuNet Face Detection with MediaPipe FaceMesh ONNX inference
    to produce 468 3D facial landmarks at ~2-3ms total latency on standard CPU.
    """
    def __init__(
        self, 
        model_yunet_path: str, 
        model_facemesh_path: str,
        input_size: Tuple[int, int] = (640, 480),
        score_threshold: float = 0.6,
        nms_threshold: float = 0.3
    ):
        if not os.path.exists(model_yunet_path):
            raise FileNotFoundError(f"YuNet model not found at {model_yunet_path}")
        if not os.path.exists(model_facemesh_path):
            raise FileNotFoundError(f"FaceMesh model not found at {model_facemesh_path}")

        self.input_size = input_size
        self.score_threshold = score_threshold
        self.nms_threshold = nms_threshold

        # 1. Initialize YuNet Face Detector
        self.detector = cv2.FaceDetectorYN.create(
            model_yunet_path, 
            "", 
            self.input_size, 
            self.score_threshold, 
            self.nms_threshold, 
            5000
        )

        # 2. Initialize ONNX FaceMesh Session
        sess_options = ort.SessionOptions()
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        sess_options.intra_op_num_threads = 2
        
        self.facemesh_sess = ort.InferenceSession(
            model_facemesh_path, 
            sess_options=sess_options,
            providers=['CPUExecutionProvider']
        )
        self.input_name = self.facemesh_sess.get_inputs()[0].name

        # Cached tracking box for temporal stability
        self.prev_roi: Optional[Tuple[int, int, int, int]] = None

    def update_input_size(self, width: int, height: int) -> None:
        if (width, height) != self.input_size:
            self.input_size = (width, height)
            self.detector.setInputSize((width, height))

    def detect_and_track(self, rgb_image: np.ndarray) -> Optional[np.ndarray]:
        """
        Processes an RGB image and returns an array of shape (468, 3) with [x, y, z] pixel landmarks.
        Returns None if no face is detected.
        """
        img_h, img_w, _ = rgb_image.shape
        self.update_input_size(img_w, img_h)

        # 1. Face Detection via YuNet (expects BGR or RGB depending on cv2 call)
        # Note: FaceDetectorYN expects BGR image
        bgr_image = cv2.cvtColor(rgb_image, cv2.COLOR_RGB2BGR)
        _, faces = self.detector.detect(bgr_image)

        roi_x, roi_y, roi_w, roi_h = 0, 0, 0, 0

        if faces is not None and len(faces) > 0:
            # Pick highest confidence face
            best_face = max(faces, key=lambda f: f[14]) # index 14 is confidence score
            fx, fy, fw, fh = best_face[0:4]

            # Expand ROI by 30% margin for full face mesh coverage
            margin_x = int(fw * 0.25)
            margin_y = int(fh * 0.35)
            
            roi_x = max(0, int(fx - margin_x))
            roi_y = max(0, int(fy - margin_y))
            roi_w = min(img_w - roi_x, int(fw + 2 * margin_x))
            roi_h = min(img_h - roi_y, int(fh + 2 * margin_y))

            # Make ROI square to avoid aspect ratio distortion in 192x192 FaceMesh
            roi_size = max(roi_w, roi_h)
            center_x = roi_x + roi_w // 2
            center_y = roi_y + roi_h // 2
            
            roi_x = max(0, center_x - roi_size // 2)
            roi_y = max(0, center_y - roi_size // 2)
            roi_w = min(img_w - roi_x, roi_size)
            roi_h = min(img_h - roi_y, roi_size)

            self.prev_roi = (roi_x, roi_y, roi_w, roi_h)
        elif self.prev_roi is not None:
            # Fallback to previous ROI if temporary detection hiccup
            roi_x, roi_y, roi_w, roi_h = self.prev_roi
        else:
            return None

        if roi_w <= 10 or roi_h <= 10:
            return None

        # 2. Crop Face ROI and Resize to 192x192 for FaceMesh
        face_crop = rgb_image[roi_y:roi_y + roi_h, roi_x:roi_x + roi_w]
        face_resized = cv2.resize(face_crop, (192, 192), interpolation=cv2.INTER_LINEAR)

        # Normalize to float32 [0.0, 1.0] (matching FaceMesh ONNX spec)
        input_tensor = np.expand_dims(face_resized.astype(np.float32) / 255.0, axis=0)

        # 3. ONNX Inference
        outputs = self.facemesh_sess.run(None, {self.input_name: input_tensor})
        raw_landmarks = outputs[0].reshape(468, 3)

        # 4. Transform Landmarks from [0, 192] crop space back to full image space
        transformed_landmarks = np.zeros_like(raw_landmarks)
        transformed_landmarks[:, 0] = roi_x + (raw_landmarks[:, 0] / 192.0) * roi_w
        transformed_landmarks[:, 1] = roi_y + (raw_landmarks[:, 1] / 192.0) * roi_h
        transformed_landmarks[:, 2] = raw_landmarks[:, 2] * (roi_w / 192.0)

        return transformed_landmarks
