"""
I.R.I.S. (Intelligent Real-time Interface System) Engine
Ultra-fast, zero-jitter, anti-Gimbal-lock webcam HCI platform.
"""

from .camera import ThreadedWebcamStream
from .preprocessor import LightingCompensator
from .filters import OneEuroFilter
from .pose_estimator import HeadPoseEstimator
from .gesture_engine import GestureEngine
from .controller import WindowsCursorController
from .tracker import FastFaceMeshTracker

__all__ = [
    "ThreadedWebcamStream",
    "LightingCompensator",
    "OneEuroFilter",
    "HeadPoseEstimator",
    "GestureEngine",
    "WindowsCursorController",
    "FastFaceMeshTracker",
]
