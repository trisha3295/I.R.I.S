import cv2
import numpy as np
from typing import Tuple, Optional, List

class HeadPoseEstimator:
    """
    6-DOF Head Pose & Gaze Vector Estimator via Levenberg-Marquardt Perspective-n-Point.
    Bypasses Euler angle decomposition to avoid Gimbal Lock and coordinate teleportation.
    """
    def __init__(self):
        # 3D Canonical Anthropometric Facial Reference (mm units)
        self.face_3d = np.array([
            (0.0, 0.0, 0.0),          # Nose tip (Landmark 1)
            (0.0, -330.0, -65.0),      # Chin (Landmark 152)
            (-225.0, 170.0, -135.0),   # Left Eye Outer Corner (Landmark 33)
            (225.0, 170.0, -135.0),    # Right Eye Outer Corner (Landmark 263)
            (-150.0, -150.0, -125.0),  # Left Mouth Corner (Landmark 61)
            (150.0, -150.0, -125.0)    # Right Mouth Corner (Landmark 291)
        ], dtype=np.float64)

        # Corresponding 2D landmark indices in 468-point FaceMesh
        self.landmark_indices = [1, 152, 33, 263, 61, 291]
        self.dist_coeffs = np.zeros((4, 1), dtype=np.float64)

    def estimate_pose(
        self, 
        landmarks: np.ndarray, 
        image_w: int, 
        image_h: int, 
        gaze_distance_mm: float = 1000.0
    ) -> Tuple[bool, Optional[Tuple[float, float]], Optional[np.ndarray], Optional[np.ndarray]]:
        """
        Calculates 6-DOF pose and projects gaze normal vector forward.
        Returns: (success, (projected_x, projected_y), rotation_vec, translation_vec)
        """
        # Extract 2D pixel coordinates for the 6 canonical points
        try:
            face_2d = np.array([
                (landmarks[idx][0], landmarks[idx][1])
                for idx in self.landmark_indices
            ], dtype=np.float64)
        except IndexError:
            return False, None, None, None

        # Camera Intrinsic Matrix (Pinhole approximation)
        focal_length = float(image_w)
        cam_matrix = np.array([
            [focal_length, 0.0, image_w / 2.0],
            [0.0, focal_length, image_h / 2.0],
            [0.0, 0.0, 1.0]
        ], dtype=np.float64)

        # Solve Perspective-n-Point with iterative Levenberg-Marquardt
        success, rvec, tvec = cv2.solvePnP(
            self.face_3d, 
            face_2d, 
            cam_matrix, 
            self.dist_coeffs, 
            flags=cv2.SOLVEPNP_ITERATIVE
        )

        if not success:
            return False, None, None, None

        # Project 3D vector forward from nose along face normal
        forward_point_3d = np.array([(0.0, 0.0, gaze_distance_mm)], dtype=np.float64)
        proj_point_2d, _ = cv2.projectPoints(forward_point_3d, rvec, tvec, cam_matrix, self.dist_coeffs)
        
        proj_x, proj_y = proj_point_2d[0][0]
        return True, (float(proj_x), float(proj_y)), rvec, tvec

    def get_euler_angles(self, rvec: np.ndarray) -> Tuple[float, float, float]:
        """
        Optional diagnostic: calculates pitch, yaw, roll in degrees for monitoring.
        """
        rmat, _ = cv2.Rodrigues(rvec)
        sy = np.sqrt(rmat[0, 0] ** 2 + rmat[1, 0] ** 2)
        singular = sy < 1e-6
        if not singular:
            pitch = np.degrees(np.arctan2(rmat[2, 1], rmat[2, 2]))
            yaw = np.degrees(np.arctan2(-rmat[2, 0], sy))
            roll = np.degrees(np.arctan2(rmat[1, 0], rmat[0, 0]))
        else:
            pitch = np.degrees(np.arctan2(-rmat[1, 2], rmat[1, 1]))
            yaw = np.degrees(np.arctan2(-rmat[2, 0], sy))
            roll = 0.0
        return float(pitch), float(yaw), float(roll)
