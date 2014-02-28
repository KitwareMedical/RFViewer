#!/usr/bin/env python

"""Examine ultrasound RF data."""

import argparse
import sys

import numpy as np
import pyqtgraph as pg
from pyqtgraph.dockarea import Dock
from pyqtgraph.Qt import QtCore, QtGui
import SimpleITK as sitk

class RFViewerLogic(QtCore.QObject):
    """Controls the RFViewers."""

    def __init__(self):
        super(RFViewerLogic, self).__init__()


class RFViewerWindow(QtGui.QMainWindow):
    """View the RF data."""

    def __init__(self, filepath, logic=None):
        super(RFViewerWindow, self).__init__()

        if logic is None:
            logic = RFViewerLogic()
        self.logic = logic

        self.filepath = filepath
        print('Reading ' + filepath + '...')
        self.image = sitk.ReadImage(filepath)
        print('Done')

        self.initializeUI()

    def initializeUI(self):
        self.resize(1024, 768)
        self.setWindowTitle(self.filepath + ' Viewer')

        exit_action = QtGui.QAction('&Exit', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.setStatusTip('Exit application')
        exit_action.triggered.connect(QtGui.QApplication.instance().quit)
        self.addAction(exit_action)

        self.dock_area = pg.dockarea.DockArea()

        rf_image_arr = sitk.GetArrayFromImage(self.image)
        rf_image_arr = rf_image_arr.squeeze()
        rf_image_arr = rf_image_arr.transpose()
        rf_min = rf_image_arr.min()
        rf_max = rf_image_arr.max()

        rf_image_dock = Dock('RF Image', size=(660, 750))
        widget = pg.GraphicsWindow(border=True)
        widget.setWindowTitle('RF Image')
        rf_image_dock.addWidget(widget)
        layout = widget.addLayout(row=0, col=0)

        full_view = layout.addViewBox(row=0, col=0, rowspan=2, lockAspect=True)
        full_image_item = pg.ImageItem(rf_image_arr)
        spacing = self.image.GetSpacing()
        size = self.image.GetSize()
        rect = QtCore.QRectF(0, 0, 640,
                640*size[1]*spacing[1]/size[0]/spacing[0])
        print(rect)
        full_image_item.setRect(rect)
        full_view.addItem(full_image_item)

        roi_view = layout.addViewBox(row=2, col=0)
        roi = pg.EllipseROI([300, 200], [80, 60], pen=(3,9))
        full_view.addItem(roi)
        roi_image_item = pg.ImageItem()
        roi_view.addItem(roi_image_item)
        def roi_update():
            roi_image_item.setImage(roi.getArrayRegion(rf_image_arr,
                                                       full_image_item),
                                    levels=(rf_min, rf_max))
        roi.sigRegionChanged.connect(roi_update)
        roi_update()

        plot_roi = pg.LineROI((320, 300), (320, 450), 9, pen=(4,9))
        full_view.addItem(plot_roi)
        rf_plot = layout.addPlot(row=3, col=0)
        rf_plot_curve = rf_plot.plot(pen=plot_roi.pen)
        def update_plot():
            data = plot_roi.getArrayRegion(rf_image_arr,
                                           full_image_item)
            rf_plot_curve.setData(data[:,data.shape[1]/2])
        plot_roi.sigRegionChanged.connect(update_plot)
        update_plot()


        self.dock_area.addDock(rf_image_dock)

        self.setCentralWidget(self.dock_area)
        self.show()
        full_image_item.setRect(rect)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rf_files', nargs='+')
    args = parser.parse_args()

    app = pg.mkQApp()

    logic = RFViewerLogic()
    viewers = []
    for filepath in args.rf_files:
        viewers.append(RFViewerWindow(filepath, logic))

    sys.exit(app.exec_())
