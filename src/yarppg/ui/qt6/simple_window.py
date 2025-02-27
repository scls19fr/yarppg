"""Provides a PyQt window for displaying rPPG processing in real-time."""

import dataclasses
from collections import deque

import numpy as np
import pyqtgraph
import scipy.signal
from PyQt6 import QtCore, QtWidgets

import yarppg
from yarppg.ui.qt6 import camera, utils


@dataclasses.dataclass
class SimpleQt6WindowSettings(yarppg.UiSettings):
    """Settings for the simple Qt6 window."""

    blursize: int | None = None
    roi_alpha: float = 0.0
    video: int | str = 0
    frame_delay: float = float("nan")


class SimpleQt6Window(QtWidgets.QMainWindow):
    """A simple window displaying the webcam feed and processed signals."""

    new_image = QtCore.pyqtSignal(np.ndarray)

    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
        blursize: int | None = None,
        roi_alpha: float = 0,
    ):
        super().__init__(parent=parent)

        pyqtgraph.setConfigOptions(
            imageAxisOrder="row-major", antialias=True, foreground="k", background="w"
        )

        self.blursize = blursize
        self.roi_alpha = roi_alpha

        self.history = deque(maxlen=150)
        self.setWindowTitle("yet another rPPG")
        self._init_ui()
        self.tracker = yarppg.FpsTracker()
        self.new_image.connect(self.update_image)

    def _init_ui(self) -> None:
        child = QtWidgets.QWidget()
        layout = QtWidgets.QGridLayout()
        child.setLayout(layout)
        self.setCentralWidget(child)

        graph = pyqtgraph.GraphicsLayoutWidget()
        layout.addWidget(graph, 0, 0)
        self.img_item = pyqtgraph.ImageItem(axisOrder="row-major")
        vb = graph.addViewBox(col=0, row=0, invertX=True, invertY=True, lockAspect=True)  # type: ignore
        vb.addItem(self.img_item)

        grid = self._make_plots()
        layout.addWidget(grid, 0, 1)

        self.fps_label = QtWidgets.QLabel("FPS:")
        layout.addWidget(
            self.fps_label, 1, 0, alignment=QtCore.Qt.AlignmentFlag.AlignBottom
        )
        self.hr_label = QtWidgets.QLabel("HR:")
        font = self.hr_label.font()
        font.setPointSize(24)
        self.hr_label.setFont(font)
        layout.addWidget(
            self.hr_label, 1, 1, alignment=QtCore.Qt.AlignmentFlag.AlignCenter
        )

    def _make_plots(self) -> pyqtgraph.GraphicsLayoutWidget:
        # We create a 2-row layout with linked x-axes.
        # The first plot shows the signal obtained through the processor.
        # The second plot shows average R, G and B channels in the ROI.
        grid = pyqtgraph.GraphicsLayoutWidget()
        main_plot: pyqtgraph.PlotItem = grid.addPlot(row=0, col=0)  # type: ignore
        self.rgb_plot: pyqtgraph.PlotItem = grid.addPlot(row=1, col=0)  # type: ignore
        self.rgb_plot.setXLink(main_plot.vb)  # type: ignore[attr-defined]
        main_plot.hideAxis("bottom")
        main_plot.hideAxis("left")
        self.rgb_plot.hideAxis("left")
        self.plots = [main_plot]

        self.lines = [main_plot.plot(pen=pyqtgraph.mkPen("k", width=3))]
        for c in "rgb":
            pen = pyqtgraph.mkPen(c, width=1.5)
            line, plot = utils.add_multiaxis_plot(self.rgb_plot, pen=pen)
            self.plots.append(plot)
            self.lines.append(line)

        for plot in self.plots:
            plot.disableAutoRange()  # type: ignore

        return grid

    def update_image(self, frame: np.ndarray) -> None:
        """Update image plot item with new frame."""
        self.img_item.setImage(frame)

    def _handle_roi(
        self, frame: np.ndarray, roi: yarppg.RegionOfInterest
    ) -> np.ndarray:
        if self.blursize is not None and roi.face_rect is not None:
            yarppg.pixelate(frame, roi.face_rect, size=self.blursize)

        frame = yarppg.roi.overlay_mask(
            frame, roi.mask == 1, color=(98, 3, 252), alpha=self.roi_alpha
        )

        return frame

    def _handle_signals(self, result: yarppg.RppgResult) -> None:
        rgb = result.roi_mean
        self.history.append((result.value, rgb.r, rgb.g, rgb.b))
        data = np.asarray(self.history)

        self.plots[0].setXRange(0, len(data))  # type: ignore
        for i in range(4):
            self.lines[i].setData(np.arange(len(data)), data[:, i])
            self.plots[i].setYRange(*utils.get_autorange(data[:, i]))  # type: ignore

    def _handle_hrvalue(self, value: float) -> None:
        """Update user interface with the new HR value."""
        if np.isfinite(value):
            hr_bpm = self.tracker.fps * 60 / value
            self.hr_label.setText(f"HR: {hr_bpm:.1f}")

    def _update_fps(self):
        self.tracker.tick()
        self.fps_label.setText(f"FPS: {self.tracker.fps:.1f}")

    def on_result(self, result: yarppg.RppgResult, frame: np.ndarray) -> None:
        """Update user interface with the new rPPG results."""
        self._update_fps()
        self.new_image.emit(self._handle_roi(frame, result.roi))
        self._handle_signals(result)
        self._handle_hrvalue(result.hr)

    def keyPressEvent(self, e):  # noqa: N802
        """Handle key presses. Closes the window on Q."""
        if e.key() == ord("Q"):
            self.close()


def launch_window(rppg: yarppg.Rppg, config: SimpleQt6WindowSettings) -> int:
    """Launch a simple Qt6-based GUI visualizing rPPG results in real-time."""
    app = QtWidgets.QApplication([])
    win = SimpleQt6Window(blursize=config.blursize, roi_alpha=config.roi_alpha)

    cam = camera.Camera(config.video, delay_frames=config.frame_delay)
    cam.frame_received.connect(
        lambda frame: win.on_result(rppg.process_frame(frame), frame)
    )
    cam.start()

    win.show()
    ret = app.exec()
    cam.stop()
    return ret


if __name__ == "__main__":
    b, a = scipy.signal.iirfilter(2, [0.7, 1.8], fs=30, btype="band")
    livefilter = yarppg.DigitalFilter(b, a)
    processor = yarppg.FilteredProcessor(yarppg.Processor(), livefilter)

    rppg = yarppg.Rppg(processor=processor)
    launch_window(rppg, yarppg.settings.get_config(["ui=qt6_simple"]).ui)
