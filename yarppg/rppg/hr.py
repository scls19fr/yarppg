import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal
import scipy.signal


def bpm_from_inds(inds, ts):
    if len(inds) < 2:
        return np.nan

    return 60. / np.mean(np.diff(ts[inds]))


def get_f(ts):
    return 1. / np.mean(np.diff(ts))


def from_peaks(vs, ts, mindist=0.35):
    if len(ts) != len(vs) or len(ts) < 2:
        return np.nan
    f = get_f(ts)
    peaks, _ = scipy.signal.find_peaks(vs, distance=int(f*mindist))

    return bpm_from_inds(peaks, ts)


def from_fft(vs, ts):
    f = get_f(ts)
    vf = np.fft.fft(vs)
    xf = np.linspace(0.0, f/2., len(vs)//2)
    return 60*xf[np.argmax(np.abs(vf[:len(vf)//2]))]


class HRCalculator(QObject):
    new_hr = pyqtSignal(float)

    def __init__(self, parent=None, update_interval=30, winsize=300,
                 filt_fun=None, hr_fun=None):
        QObject.__init__(self, parent)

        self._counter = 0
        self.update_interval = update_interval
        self.winsize = winsize
        self.filt_fun = filt_fun
        self.hr_fun = from_peaks
        if hr_fun is not None and callable(hr_fun):
            self.hr_fun = hr_fun

    def update(self, rppg):
        self._counter += 1
        if self._counter >= self.update_interval:
            self._counter = 0
            ts = rppg.get_ts(self.winsize)
            vs = next(rppg.get_vs(self.winsize))
            if self.filt_fun is not None and callable(self.filt_fun):
                vs = self.filt_fun(vs)
            self.new_hr.emit(self.hr_fun(vs, ts))
