#!/usr/bin/env python

"""Examine ultrasound RF data."""

import argparse
import sys

import numpy as np
import pyqtgraph as pg
from pyqtgraph.dockarea import Dock
from pyqtgraph.Qt import QtCore, QtGui
import SimpleITK as sitk

class RFImageDock(Dock):
    """Display the RF Image"""

    def __init__(self, logic, *args, **kwargs):
        super(RFImageDock, self).__init__(*args, **kwargs)
        self.logic = logic
        self.initializeUI()

    def initializeUI(self):
        logic = self.logic

        widget = pg.GraphicsWindow(border=True)
        widget.setWindowTitle('RF Image')
        self.addWidget(widget)
        layout = widget.addLayout(row=0, col=0)

        full_view = layout.addViewBox(row=0, col=0, rowspan=2, lockAspect=True)
        full_image_item = pg.ImageItem(logic.rf_image_array)
        spacing = logic.rf_image.GetSpacing()
        size = logic.rf_image.GetSize()
        rect = QtCore.QRectF(0, 0,
                             640, 640*size[1]*spacing[1]/size[0]/spacing[0])
        full_image_item.setRect(rect)
        full_view.addItem(full_image_item)

        roi_view = layout.addViewBox(row=2, col=0)
        roi = pg.EllipseROI([300, 200], [80, 60], pen=(3, 9))
        full_view.addItem(roi)
        roi_image_item = pg.ImageItem()
        roi_view.addItem(roi_image_item)

        def roi_update():
            roi_image_item.setImage(roi.getArrayRegion(logic.rf_image_array,
                                                       full_image_item),
                                    levels=(logic.rf_image_min,
                                            logic.rf_image_max))
        roi.sigRegionChanged.connect(roi_update)
        roi_update()

        plot_roi = pg.LineROI((320, 300), (320, 450), 9, pen=(4, 9))
        full_view.addItem(plot_roi)
        rf_plot = layout.addPlot(row=3, col=0)
        rf_plot_curve = rf_plot.plot(pen=plot_roi.pen)

        def update_plot():
            data = plot_roi.getArrayRegion(logic.rf_image_array,
                                           full_image_item)
            rf_plot_curve.setData(data[:, data.shape[1]/2])
        plot_roi.sigRegionChanged.connect(update_plot)
        update_plot()

        full_image_item.setRect(rect)


class RFViewerLogic(QtCore.QObject):
    """Controls the RFViewers."""

    _filepath = ''
    _rf_image = None
    _rf_image_array = None
    _rf_image_min = 0
    _rf_image_max = 0

    def __init__(self, filepath):
        super(RFViewerLogic, self).__init__()
        self._filepath = filepath
        self._load_rf_image()

    def _load_rf_image(self):
        filepath = self.filepath
        print('Loading ' + filepath + '...')
        self._rf_image = sitk.ReadImage(filepath)
        rf_image_array = sitk.GetArrayFromImage(self._rf_image)
        rf_image_array = rf_image_array.squeeze()
        rf_image_array = rf_image_array.transpose()
        self._rf_image_array = rf_image_array
        self._rf_image_min = rf_image_array.min()
        self._rf_image_max = rf_image_array.max()
        print('Done')

    def get_filepath(self):
        return self._filepath

    filepath = property(get_filepath,
                        doc='RF data filepath')

    def get_rf_image(self):
        return self._rf_image

    rf_image = property(get_rf_image,
                        doc='RF SimpleITK Image')

    def get_rf_image_array(self):
        return self._rf_image_array

    rf_image_array = property(get_rf_image_array,
                              doc='RF image NumPy array')

    def get_rf_image_min(self):
        return self._rf_image_min

    rf_image_min = property(get_rf_image_min,
                            doc='RF image minimum value')

    def get_rf_image_max(self):
        return self._rf_image_max

    rf_image_max = property(get_rf_image_max,
                            doc='RF image maximum value')


class RFViewerWindow(QtGui.QMainWindow):
    """View the RF data."""

    def __init__(self, logic):
        super(RFViewerWindow, self).__init__()
        self.logic = logic
        self.initializeUI()

    def initializeUI(self):
        self.resize(1024, 768)
        self.setWindowTitle(self.logic.filepath + ' Viewer')

        exit_action = QtGui.QAction('&Exit', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.setStatusTip('Exit application')
        exit_action.triggered.connect(QtGui.QApplication.instance().quit)
        self.addAction(exit_action)

        self.dock_area = pg.dockarea.DockArea()

        logic = self.logic

        rf_image_dock = RFImageDock(logic, 'RF Image', size=(660, 750))

        self.dock_area.addDock(rf_image_dock)

        self.setCentralWidget(self.dock_area)
        self.show()


class RFViewer(object):
    """View RF data."""

    def __init__(self, filepath):
        self.logic = RFViewerLogic(filepath)
        self.window = RFViewerWindow(self.logic)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rf_files', nargs='+')
    args = parser.parse_args()

    app = pg.mkQApp()

    viewers = []
    for filepath in args.rf_files:
        viewers.append(RFViewer(filepath))

    sys.exit(app.exec_())
