"""
Interactive Canvas Map Tool for picking features on the QGIS Map Canvas.
"""

try:
    from qgis.gui import QgsMapTool, QgsRubberBand
    from qgis.core import QgsWkbTypes, QgsGeometry, QgsPointXY
    from qgis.PyQt.QtCore import Qt, pyqtSignal
    from qgis.PyQt.QtGui import QColor, QCursor
    HAS_QGIS_GUI = True
except ImportError:
    HAS_QGIS_GUI = False


class FeaturePickerMapTool(QgsMapTool):
    """
    Map tool allowing the user to click a feature on the map canvas to select it.
    """
    feature_picked = pyqtSignal(object, object)  # layer, feature

    def __init__(self, canvas, target_layer=None):
        super().__init__(canvas)
        self.canvas = canvas
        self.target_layer = target_layer
        self.rubber_band = None
        self.setCursor(QCursor(Qt.CrossCursor))

    def set_target_layer(self, layer):
        self.target_layer = layer

    def canvasPressEvent(self, event):
        if not self.target_layer or not self.target_layer.isValid():
            return

        point = self.toMapCoordinates(event.pos())
        # Search radius in map units
        search_radius = self.canvas.mapUnitsPerPixel() * 10
        rect = QgsGeometry.fromPointXY(point).buffer(search_radius, 4).boundingBox()

        req = self.target_layer.getFeatures(rect)
        closest_feat = None
        min_dist = float('inf')

        pt_geom = QgsGeometry.fromPointXY(point)
        for feat in req:
            geom = feat.geometry()
            if geom and not geom.isEmpty():
                dist = pt_geom.distance(geom)
                if dist < min_dist:
                    min_dist = dist
                    closest_feat = feat

        if closest_feat is not None:
            self._highlight_feature(closest_feat)
            self.feature_picked.emit(self.target_layer, closest_feat)

    def _highlight_feature(self, feat):
        if self.rubber_band:
            self.rubber_band.reset()
        else:
            geom_type = feat.geometry().type()
            self.rubber_band = QgsRubberBand(self.canvas, geom_type)
            self.rubber_band.setColor(QColor(255, 0, 0, 180))
            self.rubber_band.setWidth(3)

        self.rubber_band.setToGeometry(feat.geometry(), self.target_layer)
        self.rubber_band.show()

    def deactivate(self):
        if self.rubber_band:
            self.rubber_band.reset()
            self.rubber_band = None
        super().deactivate()


class PointPickerMapTool(QgsMapTool):
    """
    Map tool allowing the user to click a coordinate point on the map canvas.
    Used for picking Land Boundary Terminus (LBT) or Seaward direction point.
    """
    point_picked = pyqtSignal(object)  # QgsPointXY

    def __init__(self, canvas):
        super().__init__(canvas)
        self.canvas = canvas
        self.rubber_band = None
        self.setCursor(QCursor(Qt.CrossCursor))

    def canvasPressEvent(self, event):
        point = self.toMapCoordinates(event.pos())
        self._highlight_point(point)
        self.point_picked.emit(point)

    def _highlight_point(self, point):
        if not self.rubber_band:
            self.rubber_band = QgsRubberBand(self.canvas, QgsWkbTypes.PointGeometry)
            self.rubber_band.setColor(QColor(220, 38, 38, 220))
            self.rubber_band.setWidth(8)
            self.rubber_band.setIcon(QgsRubberBand.ICON_CIRCLE)
            self.rubber_band.setIconSize(10)

        self.rubber_band.setToGeometry(QgsGeometry.fromPointXY(point), None)
        self.rubber_band.show()

    def deactivate(self):
        if self.rubber_band:
            self.rubber_band.reset()
            self.rubber_band = None
        super().deactivate()

