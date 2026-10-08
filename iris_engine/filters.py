import math
from typing import Union, List
import numpy as np

class OneEuroFilter:
    """
    1-Euro Filter: Adaptive low-pass filter designed for human-computer interaction.
    Eliminates static jitter when stationary (f_min cutoff) while preserving instantaneous
    response with zero lag during rapid saccadic movements (beta * speed scaling).
    """
    def __init__(self, t0: float, x0: float, min_cutoff: float = 0.005, beta: float = 0.001, d_cutoff: float = 1.0):
        self.min_cutoff = float(min_cutoff)
        self.beta = float(beta)
        self.d_cutoff = float(d_cutoff)
        self.x_prev = float(x0)
        self.dx_prev = 0.0
        self.t_prev = float(t0)

    @staticmethod
    def _smoothing_factor(t_e: float, cutoff: float) -> float:
        r = 2.0 * math.pi * cutoff * t_e
        return r / (r + 1.0)

    def filter(self, t: float, x: float) -> float:
        t_e = t - self.t_prev
        if t_e <= 0.0:
            return self.x_prev

        # Calculate filtered derivative of input signal
        a_d = self._smoothing_factor(t_e, self.d_cutoff)
        dx = (x - self.x_prev) / t_e
        dx_hat = a_d * dx + (1.0 - a_d) * self.dx_prev

        # Calculate adaptive cutoff frequency
        cutoff = self.min_cutoff + self.beta * abs(dx_hat)
        a = self._smoothing_factor(t_e, cutoff)
        
        # Filter signal
        x_hat = a * x + (1.0 - a) * self.x_prev

        self.x_prev = x_hat
        self.dx_prev = dx_hat
        self.t_prev = t
        return x_hat

    def reset(self, t0: float, x0: float) -> None:
        self.x_prev = float(x0)
        self.dx_prev = 0.0
        self.t_prev = float(t0)

    def __call__(self, t: float, x: float) -> float:
        return self.filter(t, x)


class OneEuroFilter2D:
    """
    2D wrapper for cursor coordinate (X, Y) filtering.
    """
    def __init__(self, t0: float, x0: float, y0: float, min_cutoff: float = 0.005, beta: float = 0.001, d_cutoff: float = 1.0):
        self.filter_x = OneEuroFilter(t0, x0, min_cutoff=min_cutoff, beta=beta, d_cutoff=d_cutoff)
        self.filter_y = OneEuroFilter(t0, y0, min_cutoff=min_cutoff, beta=beta, d_cutoff=d_cutoff)

    def filter(self, t: float, x: float, y: float) -> tuple[float, float]:
        smooth_x = self.filter_x.filter(t, x)
        smooth_y = self.filter_y.filter(t, y)
        return smooth_x, smooth_y

    def reset(self, t0: float, x0: float, y0: float) -> None:
        self.filter_x.reset(t0, x0)
        self.filter_y.reset(t0, y0)


class SoftDeadzone2D:
    """
    Continuous cubic Hermite deadzone filter. Eliminates jump discontinuities
    and laddering stepping artifacts in pointer displacement.
    """
    def __init__(self, inner_radius: float = 1.0, outer_radius: float = 4.5):
        self.inner_radius = inner_radius
        self.outer_radius = outer_radius

    def apply(self, dx: float, dy: float) -> tuple[float, float, float]:
        speed = math.hypot(dx, dy)
        if speed <= self.inner_radius:
            return 0.0, 0.0, 0.0
        elif speed >= self.outer_radius:
            return dx, dy, speed
        else:
            t = (speed - self.inner_radius) / (self.outer_radius - self.inner_radius)
            factor = t * t * (3.0 - 2.0 * t)
            return dx * factor, dy * factor, speed

