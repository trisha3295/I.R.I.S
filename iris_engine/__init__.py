"""
I.R.I.S. (Intelligent Real-time Interface System) Engine
Ultra-fast, zero-jitter, anti-Gimbal-lock webcam HCI platform.
"""

from .camera import ThreadedWebcamStream
from .preprocessor import LightingCompensator
from .filters import OneEuroFilter, OneEuroFilter2D, SoftDeadzone2D
from .pose_estimator import HeadPoseEstimator
from .gesture_engine import GestureEngine
from .controller import WindowsCursorController
from .tracker import FastFaceMeshTracker
from .iris_detector import IrisGazeDetector
from .navigation import PointerNavigationEngine

__all__ = [
    "ThreadedWebcamStream",
    "LightingCompensator",
    "OneEuroFilter",
    "OneEuroFilter2D",
    "SoftDeadzone2D",
    "HeadPoseEstimator",
    "GestureEngine",
    "WindowsCursorController",
    "FastFaceMeshTracker",
    "IrisGazeDetector",
    "PointerNavigationEngine",
]

