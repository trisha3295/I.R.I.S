import cv2
import time
from threading import Thread, Lock
from typing import Optional, Tuple
import numpy as np

class ThreadedWebcamStream:
    """
    High-performance daemon-threaded video capture buffer.
    Eliminates OpenCV synchronous read latency by constantly buffering the newest frame.
    """
    def __init__(self, src: int = 0, width: int = 640, height: int = 480, fps: int = 30):
        self.src = src
        self.width = width
        self.height = height
        self.fps = fps
        
        # Prefer DirectShow on Windows for instant initialization and minimal driver lag
        self.stream = cv2.VideoCapture(self.src, cv2.CAP_DSHOW)
        if not self.stream.isOpened():
            # Fallback to default backend if DirectShow is unavailable
            self.stream = cv2.VideoCapture(self.src)
            
        self.stream.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.stream.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.stream.set(cv2.CAP_PROP_FPS, self.fps)
        self.stream.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        self.grabbed, self.frame = self.stream.read()
        self.lock = Lock()
        self.stopped = False
        self._thread: Optional[Thread] = None

    def start(self) -> 'ThreadedWebcamStream':
        self._thread = Thread(target=self._update, daemon=True)
        self._thread.start()
        return self

    def _update(self) -> None:
        while not self.stopped:
            grabbed, frame = self.stream.read()
            if not grabbed:
                self.stop()
                break
            with self.lock:
                self.grabbed = grabbed
                self.frame = frame
            time.sleep(0.001)  # Micro-yield to prevent thread starvation

    def read(self) -> Optional[np.ndarray]:
        with self.lock:
            if self.frame is not None:
                return self.frame.copy()
            return None

    def get_resolution(self) -> Tuple[int, int]:
        return int(self.stream.get(cv2.CAP_PROP_FRAME_WIDTH)), int(self.stream.get(cv2.CAP_PROP_FRAME_HEIGHT))

    def stop(self) -> None:
        self.stopped = True
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=0.5)
        if self.stream.isOpened():
            self.stream.release()

    def __enter__(self) -> 'ThreadedWebcamStream':
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()
