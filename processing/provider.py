"""
Processing Provider for Maritime Delimitation Plugin.
Registers the algorithm into QGIS Processing Framework.
"""

try:
    from qgis.core import QgsProcessingProvider
    from qgis.PyQt.QtGui import QIcon
    import os
    HAS_QGIS = True
except ImportError:
    HAS_QGIS = False

from .median_line_algorithm import MedianLineProcessingAlgorithm


class MaritimeDelimitationProvider(QgsProcessingProvider):

    def __init__(self):
        super().__init__()

    def loadAlgorithms(self):
        self.addAlgorithm(MedianLineProcessingAlgorithm())

    def id(self):
        return 'maritime_delimitation'

    def name(self):
        return 'Maritime Delimitation (TALOS & UNCLOS)'

    def icon(self):
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'resources', 'icon.png')
        if os.path.exists(icon_path):
            return QIcon(icon_path)
        return super().icon()

    def longName(self):
        return self.name()
