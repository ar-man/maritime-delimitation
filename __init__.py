"""
QGIS Plugin Package Init
Entry point required by QGIS Plugin Manager.
"""


def classFactory(iface):
    """
    Load MaritimeMedianLinePlugin class from file plugin.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    from .plugin import MaritimeMedianLinePlugin
    return MaritimeMedianLinePlugin(iface)
