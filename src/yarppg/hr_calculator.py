"""Heart rate calculation utilities."""

from collections import deque

import numpy as np
import scipy.signal


class HrCalculator:
    """Base class for heart rate calculation."""

    def update(self, value: float) -> float:  # noqa: ARG002
        """Process the new data and update HR estimate."""
        return np.nan

    def reset(self) -> None:
        """Clear the the internal state."""
        pass


class PeakBasedHrCalculator(HrCalculator):
    """Peak-based heart rate calculation."""

    def __init__(
        self,
        fs: float,
        window_seconds: float = 10,
        distance: float = 0.5,
        update_interval: int = 10,
    ):
        self.winsize = int(fs * window_seconds)
        self.values = deque(maxlen=self.winsize)
        self.mindist = int(fs * distance)

        self.update_interval = update_interval
        self.frames_seen = 0
        self.last_hr = np.nan

    def update(self, value: float) -> float:
        """Process the new data and update HR estimate in frames per beat."""
        self.frames_seen += 1
        self.values.append(value)
        if (
            len(self.values) < self.winsize
            or self.frames_seen % self.update_interval != 0
        ):
            return self.last_hr
        peaks, _ = scipy.signal.find_peaks(self.values, distance=self.mindist)
        self.last_hr = np.diff(peaks).mean()
        return self.last_hr

    def reset(self) -> None:
        """Clear the internal buffer and intermediate values."""
        self.frames_seen = 0
        self.values.clear()
        self.last_hr = np.nan
