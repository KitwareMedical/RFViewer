#!/usr/bin/env python

"""Examine ultrasound RF data."""

import argparse
import sys

import pyqtgraph as pg
from pyqtgraph.dockarea import Dock
from pyqtgraph.Qt import QtCore, QtGui
import SimpleITK as sitk
import numpy as np
import scipy.signal


class PlotsDock(Dock):
    """Display the RF, B-Mode, and spectrum in the ROI"""

    _images_to_plot = []

    def __init__(self, *args, **kwargs):
        super(PlotsDock, self).__init__(*args, **kwargs)
        self.initializeUI()

    def initializeUI(self):
        widget = pg.GraphicsWindow()
        widget.setWindowTitle('Plots')
        self.addWidget(widget)
        self.layout = widget.addLayout()

    def add_image_to_plot(self,
                          plot_roi,
                          image_array,
                          image_item,
                          title,
                          axis_labels,
                          row=0):
        plot = self.layout.addPlot(row=row, col=0)
        plot_curve = plot.plot(pen=plot_roi.pen)
        plot.setTitle(title)
        plot.setLabels(**axis_labels)
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
            yy = data[data.shape[0]/2, :]
            # TODO: do not assume 40 MHz sampling
            xx = 1./40. * np.arange(len(yy))
            plot_curve.setData(xx, yy)


class ImageDock(Dock):
    """Display the image.  The full image and a zoomed in ROI is displayed."""

    def __init__(self, image_logic, roi_logic,
                 description='Image', *args, **kwargs):
        super(ImageDock, self).__init__(description, *args, **kwargs)
        self.image_logic = image_logic
        self.roi_logic = roi_logic
        self.description = description
        self.initializeUI()

    def initializeUI(self):
        image_logic = self.image_logic
        roi_logic = self.roi_logic

        widget = pg.GraphicsWindow(border=True)
        widget.setWindowTitle(self.description)
        self.addWidget(widget)
        layout = widget.addLayout(row=0, col=0)

        view = layout.addViewBox(row=0, col=0, rowspan=2, lockAspect=True)
        self.view = view
        full_image_item = pg.ImageItem(image_logic.image_array)
        self.full_image_item = full_image_item
        spacing = image_logic.image.GetSpacing()
        size = image_logic.image.GetSize()
        rect = QtCore.QRectF(0, 0,
                             640, 640*size[1]*spacing[1]/size[0]/spacing[0])
        full_image_item.setRect(rect)
        view.addItem(full_image_item)

        zoom_roi_view = layout.addViewBox(row=2, col=0)
        self.zoom_roi = pg.EllipseROI([300, 200], roi_logic.zoom_roi_pos,
                                      pen=(3, 9))
        view.addItem(self.zoom_roi)
        self.roi_image_item = pg.ImageItem()
        zoom_roi_view.addItem(self.roi_image_item)

        self.zoom_roi.sigRegionChanged.connect(self.roi_logic.set_zoom_roi_pos)
        self.roi_logic.zoom_roi_pos_changed.connect(self.update_zoom_roi_content)
        self.update_zoom_roi_content(self.zoom_roi)

        full_image_item.setRect(rect)

    def add_plot_roi(self):
        roi_logic = self.roi_logic
        size = (9, 150)
        plot_roi = pg.RectROI(roi_logic.plot_roi_pos, size,
                              centered=True, pen=(4, 9))
        self.view.addItem(plot_roi)
        return plot_roi

    def get_full_image_item(self):
        return self.full_image_item

    def update_zoom_roi_content(self, roi_or_pos):
        """When ROI, it is from self, other from the ImageLogic"""
        if isinstance(roi_or_pos, pg.ROI):
            pos = roi_or_pos.pos()
        else:
            pos = roi_or_pos
        self.zoom_roi.setPos(pos, update=False)
        image_logic = self.image_logic
        region = self.zoom_roi.getArrayRegion(image_logic.image_array,
                                              self.full_image_item)
        self.roi_image_item.setImage(region,
                                     levels=(image_logic.image_min,
                                             image_logic.image_max))


class ROILogic(QtCore.QObject):
    """Controls the ROIs"""
    _zoom_roi_pos = (80., 60.)
    _plot_roi_pos = (320., 300.)

    def __init__(self):
        super(ROILogic, self).__init__()

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


class ImageLogic(QtCore.QObject):
    """Controls the Images."""

    _filepath = None
    _image = None
    _image_array = None
    _image_min = 0
    _image_max = 0

    def __init__(self, filepath=None):
        super(ImageLogic, self).__init__()
        self._filepath = filepath
        if filepath:
            self._load_image()

    def _load_image(self):
        filepath = self.filepath
        print('Loading ' + filepath + '...')
        self.image = sitk.ReadImage(filepath)
        print('Done')

    def get_filepath(self):
        return self._filepath

    filepath = property(get_filepath,
                        doc='Input image filepath')

    def get_image(self):
        return self._image

    def set_image(self, image):
        self._image = image
        image_array = sitk.GetArrayFromImage(self._image)
        image_array = image_array.squeeze()
        image_array = image_array.transpose()
        self._image_array = image_array
        self._image_min = image_array.min()
        self._image_max = image_array.max()

    image = property(get_image,
                     set_image,
                     doc='SimpleITK Image')

    def get_image_array(self):
        return self._image_array

    image_array = property(get_image_array,
                           doc='Image NumPy array')

    def get_image_min(self):
        return self._image_min

    image_min = property(get_image_min,
                         doc='Image minimum value')

    def get_image_max(self):
        return self._image_max

    image_max = property(get_image_max,
                         doc='Image maximum value')


class RFViewerWindow(QtGui.QMainWindow):
    """View the RF data."""

    def __init__(self, filepath, roi_logic):
        super(RFViewerWindow, self).__init__()
        self.filepath = filepath
        self.roi_logic = roi_logic
        self.initializeUI()

    def initializeUI(self):
        self.resize(1024, 768)
        self.setWindowTitle(filepath + ' Viewer')

        exit_action = QtGui.QAction('&Exit', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.setStatusTip('Exit application')
        exit_action.triggered.connect(QtGui.QApplication.instance().quit)
        self.addAction(exit_action)

        self.dock_area = pg.dockarea.DockArea()

        roi_logic = self.roi_logic

        rf_image_logic = ImageLogic(self.filepath)
        rf_image_dock = ImageDock(rf_image_logic, roi_logic,
                                  'RF Image', size=(660, 750))
        self.dock_area.addDock(rf_image_dock)

        plots_dock = PlotsDock('Image ROI Content Plots',
                               size=(1000, 500))
        self.dock_area.addDock(plots_dock, 'bottom', rf_image_dock)

        b_mode_image = sitk.Image(rf_image_logic.image)
        array = sitk.GetArrayFromImage(b_mode_image)
        hilbert = scipy.signal.hilbert(array, axis=1)
        envelope = np.abs(hilbert)
        b_mode_image = sitk.GetImageFromArray(envelope)
        b_mode_image.CopyInformation(rf_image_logic.image)
        b_mode_image_logic = ImageLogic()
        b_mode_image_logic.image = b_mode_image
        b_mode_dock = ImageDock(b_mode_image_logic, roi_logic,
                                'B Mode', size=(660, 750))
        self.dock_area.addDock(b_mode_dock, 'right', rf_image_dock)

        rf_plot_roi = rf_image_dock.add_plot_roi()
        labels = {'bottom': 'Time (usec)'}
        plots_dock.add_image_to_plot(rf_plot_roi,
                                     rf_image_logic.image_array,
                                     rf_image_dock.get_full_image_item(),
                                     'RF',
                                     labels,
                                     0)
        b_mode_plot_roi = b_mode_dock.add_plot_roi()
        plots_dock.add_image_to_plot(b_mode_plot_roi,
                                     b_mode_image_logic.image_array,
                                     b_mode_dock.get_full_image_item(),
                                     'B-Mode',
                                     labels,
                                     1)

        self.setCentralWidget(self.dock_area)
        self.show()


class RFViewer(object):
    """View RF data."""

    def __init__(self, filepath):
        self.roi_logic = ROILogic()
        self.window = RFViewerWindow(filepath, self.roi_logic)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rf_files', nargs='+')
    args = parser.parse_args()

    app = pg.mkQApp()

    viewers = []
    for filepath in args.rf_files:
        viewers.append(RFViewer(filepath))

    sys.exit(app.exec_())
