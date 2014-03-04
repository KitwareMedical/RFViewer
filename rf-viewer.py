#!/usr/bin/env python

"""Examine ultrasound RF data."""

import argparse
import sys

import pyqtgraph as pg
from pyqtgraph.dockarea import Dock
from pyqtgraph.Qt import QtCore, QtGui
import SimpleITK as sitk


class PlotsDock(Dock):
    """Display the RF, B-Mode, and spectrum in the ROI"""

    _images_to_plot = []

    def __init__(self, logic, *args, **kwargs):
        super(PlotsDock, self).__init__(*args, **kwargs)
        self.logic = logic

        self.initializeUI()

    def initializeUI(self):
        widget = pg.GraphicsWindow()
        widget.setWindowTitle('Plots')
        self.addWidget(widget)
        self.layout = widget.addLayout()

    def add_image_to_plot(self, plot_roi, image_array, image_item):
        plot = self.layout.addPlot()
        plot_curve = plot.plot(pen=plot_roi.pen)
        plot_roi.sigRegionChanged.connect(self.update_plot_content)
        self._images_to_plot.append((plot_curve,
                                     plot_roi,
                                     image_array,
                                     image_item))
        self.update_plot_content(plot_roi)

    def update_plot_content(self, roi_or_pos):
        """When ROI, it is from self, other from the Logic"""
        if isinstance(roi_or_pos, pg.ROI):
            pos = roi_or_pos.pos()
        else:
            pos = roi_or_pos
        for plot_curve, plot_roi, image_array, image_item in self._images_to_plot:
            plot_roi.setPos(pos, update=False)
            data = plot_roi.getArrayRegion(image_array,
                                           image_item)
            plot_curve.setData(data[data.shape[0]/2, :])


class ImageDock(Dock):
    """Display the image.  The full image and a zoomed in ROI is displayed."""

    def __init__(self, logic, description='Image', *args, **kwargs):
        super(ImageDock, self).__init__(description, *args, **kwargs)
        self.logic = logic
        self.description = description
        self.initializeUI()

    def initializeUI(self):
        logic = self.logic

        widget = pg.GraphicsWindow(border=True)
        widget.setWindowTitle(self.description)
        self.addWidget(widget)
        layout = widget.addLayout(row=0, col=0)

        view = layout.addViewBox(row=0, col=0, rowspan=2, lockAspect=True)
        self.view = view
        full_image_item = pg.ImageItem(logic.rf_image_array)
        self.full_image_item = full_image_item
        spacing = logic.rf_image.GetSpacing()
        size = logic.rf_image.GetSize()
        rect = QtCore.QRectF(0, 0,
                             640, 640*size[1]*spacing[1]/size[0]/spacing[0])
        full_image_item.setRect(rect)
        view.addItem(full_image_item)

        zoom_roi_view = layout.addViewBox(row=2, col=0)
        self.zoom_roi = pg.EllipseROI([300, 200], logic.zoom_roi_pos,
                                      pen=(3, 9))
        view.addItem(self.zoom_roi)
        self.roi_image_item = pg.ImageItem()
        zoom_roi_view.addItem(self.roi_image_item)

        self.zoom_roi.sigRegionChanged.connect(self.update_zoom_roi_content)
        self.zoom_roi.sigRegionChangeFinished.connect(logic.set_zoom_roi_pos)
        logic.zoom_roi_pos_changed.connect(self.update_zoom_roi_content)
        self.update_zoom_roi_content(self.zoom_roi)

        full_image_item.setRect(rect)

    def add_plot_roi(self):
        logic = self.logic
        size = (9, 150)
        plot_roi = pg.RectROI(logic.plot_roi_pos, size,
                              centered=True, pen=(4, 9))
        self.view.addItem(plot_roi)
        return plot_roi

    def get_full_image_item(self):
        return self.full_image_item

    def update_zoom_roi_content(self, roi_or_pos):
        """When ROI, it is from self, other from the Logic"""
        if isinstance(roi_or_pos, pg.ROI):
            pos = roi_or_pos.pos()
        else:
            pos = roi_or_pos
        self.zoom_roi.setPos(pos, update=False)
        logic = self.logic
        region = self.zoom_roi.getArrayRegion(logic.rf_image_array,
                                              self.full_image_item)
        self.roi_image_item.setImage(region,
                                     levels=(logic.rf_image_min,
                                             logic.rf_image_max))


class RFViewerLogic(QtCore.QObject):
    """Controls the RFViewers."""

    _filepath = ''
    _rf_image = None
    _rf_image_array = None
    _rf_image_min = 0
    _rf_image_max = 0
    _zoom_roi_pos = (80., 60.)
    _plot_roi_pos = (320., 300.)

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

    def get_zoom_roi_pos(self):
        return self._zoom_roi_pos

    def set_zoom_roi_pos(self, roi_or_pos):
        if isinstance(roi_or_pos, pg.ROI):
            pos = roi_or_pos.pos()
        else:
            pos = roi_or_pos
        if (pos[0], pos[1]) != self._zoom_roi_pos:
            self._zoom_roi_pos = (pos[0], pos[1])
            self.zoom_roi_pos_changed.emit(self._zoom_roi_pos)

    zoom_roi_pos = property(get_zoom_roi_pos,
                            set_zoom_roi_pos,
                            doc='Set the position of the zoom in ROI')

    zoom_roi_pos_changed = QtCore.pyqtSignal(object)

    def get_plot_roi_pos(self):
        return self._plot_roi_pos

    def set_plot_roi_pos(self, roi_or_pos):
        if isinstance(roi_or_pos, pg.ROI):
            pos = roi_or_pos.pos()
        else:
            pos = roi_or_pos
        if (pos[0], pos[1]) != self._plot_roi_pos:
            self._plot_roi_pos = (pos[0], pos[1])
            self.plot_roi_pos_changed.emit(self._plot_roi_pos)

    plot_roi_pos = property(get_plot_roi_pos,
                            set_plot_roi_pos,
                            doc='Set the position of the zoom in ROI')

    plot_roi_pos_changed = QtCore.pyqtSignal(object)


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

        rf_image_dock = ImageDock(logic, 'RF Image', size=(660, 750))
        self.dock_area.addDock(rf_image_dock)
        plots_dock = PlotsDock(logic,
                               'Image ROI Content Plots',
                               size=(100, 200))
        self.dock_area.addDock(plots_dock, 'bottom', rf_image_dock)

        rf_plot_roi = rf_image_dock.add_plot_roi()
        plots_dock.add_image_to_plot(rf_plot_roi,
                                     logic.rf_image_array,
                                     rf_image_dock.get_full_image_item())

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
