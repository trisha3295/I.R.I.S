import cv2
import numpy as np

class LightingCompensator:
    """
    Dynamic Ambient Light Normalization Engine.
    Converts incoming BGR frames to the YCrCb color space and applies CLAHE strictly
    to the luminance (Y) channel. Neutralizes room light fluctuations (50Hz/60Hz mains flicker)
    and eliminates shadow noise without introducing color distortion.
    """
    def __init__(self, clip_limit: float = 2.0, tile_grid_size: tuple = (8, 8)):
        self.clip_limit = clip_limit
        self.tile_grid_size = tile_grid_size
        self._clahe = cv2.createCLAHE(clipLimit=self.clip_limit, tileGridSize=self.tile_grid_size)

    def process(self, frame_bgr: np.ndarray) -> np.ndarray:
        """
        Applies luminance equalization to BGR frame. Returns normalized RGB frame.
        """
        # Convert BGR to YCrCb
        ycrcb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2YCrCb)
        
        # Equalize Luminance (Y) channel only
        ycrcb[:, :, 0] = self._clahe.apply(ycrcb[:, :, 0])
        
        # Convert back to RGB for neural network consumption
        rgb_normalized = cv2.cvtColor(ycrcb, cv2.COLOR_YCrCb2RGB)
        return rgb_normalized

    def update_params(self, clip_limit: float = 2.0, tile_grid_size: tuple = (8, 8)) -> None:
        self.clip_limit = clip_limit
        self.tile_grid_size = tile_grid_size
        self._clahe = cv2.createCLAHE(clipLimit=self.clip_limit, tileGridSize=self.tile_grid_size)
