"""
Main QGIS Plugin Class for Maritime Median Line (TALOS & UNCLOS Delimitation).
"""

import os
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from qgis.core import QgsApplication

from .gui.median_line_dialog import MedianLineDialog
from .processing.provider import MaritimeDelimitationProvider


class MaritimeMedianLinePlugin:
    """
    QGIS Plugin implementation for Maritime Delimitation & Weighted Median Line.
    """

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.dialog = None
        self.action = None
        self.provider = None

    def tr(self, message):
        return QCoreApplication.translate('MaritimeMedianLinePlugin', message)

    def initProcessing(self):
        """Initializes the QGIS Processing Provider."""
        self.provider = MaritimeDelimitationProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def initGui(self):
        """Creates menu items and toolbar buttons in QGIS."""
        icon_path = os.path.join(self.plugin_dir, 'resources', 'icon.svg')
        if not os.path.exists(icon_path):
            icon_path = os.path.join(self.plugin_dir, 'resources', 'icon.png')
        icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()

        self.action = QAction(
            icon,
            self.tr("Generate Median Line (TALOS & UNCLOS)..."),
            self.iface.mainWindow()
        )
        self.action.setObjectName("maritimeMedianLineAction")
        self.action.setToolTip(self.tr("Maritime Delimitation: Generate Median Line & Weighted Boundaries per TALOS & UNCLOS"))
        self.action.triggered.connect(self.run)

        # Add to Vector Menu
        self.iface.addPluginToVectorMenu(self.tr("Maritime Delimitation (TALOS)"), self.action)
        # Add to Plugin Toolbar
        self.iface.addToolBarIcon(self.action)

        # Initialize Processing provider
        self.initProcessing()

    def unload(self):
        """Cleans up menus, toolbar buttons, and processing provider on plugin unload."""
        if self.action:
            self.iface.removePluginVectorMenu(self.tr("Maritime Delimitation (TALOS)"), self.action)
            self.iface.removeToolBarIcon(self.action)
            del self.action
            self.action = None

        if self.provider:
            QgsApplication.processingRegistry().removeProvider(self.provider)
            self.provider = None

        if self.dialog:
            self.dialog.close()
            self.dialog = None

    def run(self):
        """Opens the Maritime Delimitation dialog."""
        if not self.dialog:
            self.dialog = MedianLineDialog(self.iface, self.iface.mainWindow())
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
