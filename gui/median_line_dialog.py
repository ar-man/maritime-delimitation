"""
Maritime Delimitation - Median Line GUI Dialog
PyQt dialog for configuring baselines, basepoints, weights, and generating TALOS-compliant median lines.
"""

import os
from collections import defaultdict

try:
    from qgis.PyQt.QtCore import Qt, pyqtSignal, QVariant
    from qgis.PyQt.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
        QLabel, QComboBox, QDoubleSpinBox, QCheckBox, QPushButton,
        QRadioButton, QButtonGroup, QLineEdit, QFileDialog, QProgressBar,
        QTabWidget, QTextBrowser, QMessageBox, QFrame, QScrollArea, QWidget
    )
    from qgis.PyQt.QtGui import QIcon, QFont, QColor
    from qgis.core import (
        QgsProject, QgsMapLayerProxyModel, QgsVectorLayer,
        QgsFeature, QgsGeometry, QgsField, QgsWkbTypes,
        QgsCoordinateReferenceSystem, QgsCoordinateTransform,
        QgsVectorFileWriter, QgsPointXY, QgsLineSymbol, QgsSingleSymbolRenderer
    )
    from qgis.gui import QgsMapLayerComboBox
    HAS_QGIS = True
except ImportError:
    HAS_QGIS = False
    from PyQt5.QtWidgets import QDialog  # fallback for typing

from ..core.delimitation_engine import DelimitationEngine
from .map_tool_picker import FeaturePickerMapTool, PointPickerMapTool


class MedianLineDialog(QDialog):
    """
    Main User Interface Dialog for TALOS Maritime Delimitation.
    """

    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.canvas = iface.mapCanvas() if iface else None
        self.picker_tool = None
        self.point_picker_tool = None
        self.active_pick_target = None  # 'A' or 'B'
        self.active_point_pick_target = None  # 'LBT' or 'SEAWARD'
        self.selected_fid_a = None
        self.selected_fid_b = None
        self.custom_lbt_point = None
        self.custom_seaward_point = None

        self.setWindowTitle("Maritime Delimitation - Median Line (TALOS & UNCLOS)")
        self.resize(760, 800)
        self.setMinimumSize(680, 720)

        # Set window icon
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'resources', 'icon.svg')
        if not os.path.exists(icon_path):
            icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'resources', 'icon.png')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self._init_ui()
        self._connect_signals()
        self._update_formula_banner()
        self._on_mode_changed(0)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # Header Banner
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1a365d, stop:1 #2b6cb0);
                border-radius: 8px;
                padding: 10px;
            }
        """)
        header_layout = QVBoxLayout(header_frame)
        title_label = QLabel("Maritime Delimitation: Median Line (TALOS & UNCLOS)")
        title_label.setStyleSheet("color: white; font-size: 16px; font-weight: bold;")
        subtitle_label = QLabel("Construction of Strict Equidistance Lines & Weighted Boundaries from Coastal Baselines or Basepoints")
        subtitle_label.setStyleSheet("color: #e2e8f0; font-size: 11px;")
        header_layout.addWidget(title_label)
        header_layout.addWidget(subtitle_label)
        main_layout.addWidget(header_frame)

        # Tabs: Tab 1: Delimitation Parameters, Tab 2: TALOS & UNCLOS Principles
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # Tab 1: Delimitation Parameters
        tab_params = QWidget()
        tab_layout = QVBoxLayout(tab_params)
        tab_layout.setSpacing(12)

        # Scroll Area for parameters
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(12)
        scroll_layout.setContentsMargins(0, 0, 5, 0)

        # Group 0: Delimitation Mode (Opposite / Adjacent)
        group_mode = QGroupBox("Delimitation Mode (Coasts Configuration)")
        group_mode.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid #cbd5e1; border-radius: 6px; margin-top: 6px; padding-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #1e293b; }")
        layout_mode = QVBoxLayout(group_mode)
        layout_mode.setSpacing(8)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Coasts Relationship:"))
        self.cmb_mode = QComboBox()
        self.cmb_mode.addItem("Opposite Coasts", "opposite")
        self.cmb_mode.addItem("Adjacent Coasts", "adjacent")
        mode_row.addWidget(self.cmb_mode, 1)
        layout_mode.addLayout(mode_row)

        # Mode description banner
        self.banner_mode = QFrame()
        self.banner_mode.setStyleSheet("""
            QFrame {
                background-color: #f0f9ff;
                border: 1px solid #7dd3fc;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        banner_mode_layout = QVBoxLayout(self.banner_mode)
        self.lbl_mode_desc = QLabel()
        self.lbl_mode_desc.setWordWrap(True)
        self.lbl_mode_desc.setStyleSheet("color: #0c4a6e; font-size: 11px;")
        banner_mode_layout.addWidget(self.lbl_mode_desc)
        layout_mode.addWidget(self.banner_mode)

        scroll_layout.addWidget(group_mode)

        # Dedicated Group for Adjacent Coasts Options
        self.group_adj_options = QGroupBox("Adjacent Coasts Delimitation Settings")
        self.group_adj_options.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid #fde047; border-radius: 6px; background-color: #fffef7; margin-top: 6px; padding-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #854d0e; }")
        layout_adj = QGridLayout(self.group_adj_options)
        layout_adj.setSpacing(8)

        # 1. Seaward reach / extent
        layout_adj.addWidget(QLabel("Seaward Extent Limit:"), 0, 0)
        self.cmb_seaward_extent = QComboBox()
        self.cmb_seaward_extent.addItem("12 Nautical Miles (Territorial Sea — UNCLOS Art. 15)", 22224.0)
        self.cmb_seaward_extent.addItem("24 Nautical Miles (Contiguous Zone — UNCLOS Art. 33)", 44448.0)
        self.cmb_seaward_extent.addItem("200 Nautical Miles (EEZ & Continental Shelf — UNCLOS Arts. 74/83)", 370400.0)
        self.cmb_seaward_extent.addItem("Automatic (Baseline Extent)", None)
        self.cmb_seaward_extent.addItem("Custom Distance...", -1)
        layout_adj.addWidget(self.cmb_seaward_extent, 0, 1)

        custom_ext_row = QHBoxLayout()
        self.spn_custom_extent = QDoubleSpinBox()
        self.spn_custom_extent.setRange(0.1, 1000.0)
        self.spn_custom_extent.setValue(12.0)
        self.spn_custom_extent.setEnabled(False)
        self.cmb_custom_extent_unit = QComboBox()
        self.cmb_custom_extent_unit.addItem("Nautical Miles (NM)", "NM")
        self.cmb_custom_extent_unit.addItem("Kilometers (km)", "km")
        self.cmb_custom_extent_unit.setEnabled(False)
        custom_ext_row.addWidget(self.spn_custom_extent)
        custom_ext_row.addWidget(self.cmb_custom_extent_unit)
        layout_adj.addLayout(custom_ext_row, 0, 2)

        # 2. Land Boundary Terminus (LBT)
        layout_adj.addWidget(QLabel("Land Boundary Terminus (LBT):"), 1, 0)
        self.lbl_lbt_status = QLabel("Automatic (Closest intersection of Baselines A & B)")
        self.lbl_lbt_status.setStyleSheet("color: #475569; font-style: italic; font-size: 11px;")
        layout_adj.addWidget(self.lbl_lbt_status, 1, 1)

        lbt_btn_row = QHBoxLayout()
        self.btn_pick_lbt = QPushButton("🎯 Pick LBT on Map")
        self.btn_pick_lbt.setToolTip("Click on map canvas to set Land Boundary Terminus coordinates")
        self.btn_reset_lbt = QPushButton("↺ Auto")
        self.btn_reset_lbt.setToolTip("Reset LBT to automatic detection")
        lbt_btn_row.addWidget(self.btn_pick_lbt)
        lbt_btn_row.addWidget(self.btn_reset_lbt)
        layout_adj.addLayout(lbt_btn_row, 1, 2)

        # 3. Seaward Direction
        layout_adj.addWidget(QLabel("Seaward Direction:"), 2, 0)
        self.lbl_seaward_status = QLabel("Automatic (Outward into open sea away from coasts)")
        self.lbl_seaward_status.setStyleSheet("color: #475569; font-style: italic; font-size: 11px;")
        layout_adj.addWidget(self.lbl_seaward_status, 2, 1)

        sea_btn_row = QHBoxLayout()
        self.btn_pick_seaward = QPushButton("🧭 Pick Direction on Map")
        self.btn_pick_seaward.setToolTip("Click a point in the sea on map canvas to ensure boundary extends seaward")
        self.btn_reset_seaward = QPushButton("↺ Auto")
        self.btn_reset_seaward.setToolTip("Reset seaward direction to automatic detection")
        sea_btn_row.addWidget(self.btn_pick_seaward)
        sea_btn_row.addWidget(self.btn_reset_seaward)
        layout_adj.addLayout(sea_btn_row, 2, 2)

        self.group_adj_options.setVisible(False)
        scroll_layout.addWidget(self.group_adj_options)

        # Group 1: Baseline / Basepoints A
        group_a = QGroupBox("1. Coastal Baseline / Basepoints A (State / Side A)")
        group_a.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid #cbd5e1; border-radius: 6px; margin-top: 6px; padding-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #1e293b; }")
        layout_a = QGridLayout(group_a)
        layout_a.setSpacing(8)

        layout_a.addWidget(QLabel("Feature A Layer:"), 0, 0)
        self.cmb_layer_a = QgsMapLayerComboBox()
        self.cmb_layer_a.setFilters(QgsMapLayerProxyModel.PointLayer | QgsMapLayerProxyModel.LineLayer | QgsMapLayerProxyModel.PolygonLayer)
        layout_a.addWidget(self.cmb_layer_a, 0, 1)

        self.btn_pick_a = QPushButton("🎯 Pick on Map")
        self.btn_pick_a.setToolTip("Click a feature on map canvas to select Baseline A")
        layout_a.addWidget(self.btn_pick_a, 0, 2)

        self.chk_selected_a = QCheckBox("Use selected features only")
        self.chk_selected_a.setChecked(False)
        layout_a.addWidget(self.chk_selected_a, 1, 1, 1, 2)

        layout_a.addWidget(QLabel("Feature A Weight (Weight A):"), 2, 0)
        self.spn_weight_a = QDoubleSpinBox()
        self.spn_weight_a.setRange(0.01, 100.0)
        self.spn_weight_a.setValue(1.0)
        self.spn_weight_a.setSingleStep(0.1)
        self.spn_weight_a.setDecimals(2)
        layout_a.addWidget(self.spn_weight_a, 2, 1)

        self.lbl_info_a = QLabel("Label / Side A Name:")
        layout_a.addWidget(self.lbl_info_a, 3, 0)
        self.txt_name_a = QLineEdit("Baseline A (State A)")
        layout_a.addWidget(self.txt_name_a, 3, 1, 1, 2)

        scroll_layout.addWidget(group_a)

        # Group 2: Baseline / Basepoints B
        group_b = QGroupBox("2. Coastal Baseline / Basepoints B (State / Side B)")
        group_b.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid #cbd5e1; border-radius: 6px; margin-top: 6px; padding-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #1e293b; }")
        layout_b = QGridLayout(group_b)
        layout_b.setSpacing(8)

        layout_b.addWidget(QLabel("Feature B Layer:"), 0, 0)
        self.cmb_layer_b = QgsMapLayerComboBox()
        self.cmb_layer_b.setFilters(QgsMapLayerProxyModel.PointLayer | QgsMapLayerProxyModel.LineLayer | QgsMapLayerProxyModel.PolygonLayer)
        layout_b.addWidget(self.cmb_layer_b, 0, 1)

        self.btn_pick_b = QPushButton("🎯 Pick on Map")
        self.btn_pick_b.setToolTip("Click a feature on map canvas to select Baseline B")
        layout_b.addWidget(self.btn_pick_b, 0, 2)

        self.chk_selected_b = QCheckBox("Use selected features only")
        self.chk_selected_b.setChecked(False)
        layout_b.addWidget(self.chk_selected_b, 1, 1, 1, 2)

        layout_b.addWidget(QLabel("Feature B Weight (Weight B):"), 2, 0)
        self.spn_weight_b = QDoubleSpinBox()
        self.spn_weight_b.setRange(0.01, 100.0)
        self.spn_weight_b.setValue(1.0)
        self.spn_weight_b.setSingleStep(0.1)
        self.spn_weight_b.setDecimals(2)
        layout_b.addWidget(self.spn_weight_b, 2, 1)

        self.lbl_info_b = QLabel("Label / Side B Name:")
        layout_b.addWidget(self.lbl_info_b, 3, 0)
        self.txt_name_b = QLineEdit("Baseline B (State B)")
        layout_b.addWidget(self.txt_name_b, 3, 1, 1, 2)

        scroll_layout.addWidget(group_b)

        # Group 3: Weighting Presets & Real-Time Formula Banner
        group_weights = QGroupBox("3. Maritime Weighting Ratio Configuration (TALOS S-51)")
        group_weights.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid #cbd5e1; border-radius: 6px; margin-top: 6px; padding-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #1e293b; }")
        layout_weights = QVBoxLayout(group_weights)
        layout_weights.setSpacing(8)

        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Weighting Ratio Presets:"))
        self.cmb_presets = QComboBox()
        self.cmb_presets.addItem("1 : 1 (Strict Equidistance / Median Line - Full Effect)", (1.0, 1.0))
        self.cmb_presets.addItem("1 : 2 (Weighted towards Baseline A - 1:2 / Half Effect on A)", (1.0, 2.0))
        self.cmb_presets.addItem("2 : 1 (Weighted towards Baseline B - 2:1 / Half Effect on B)", (2.0, 1.0))
        self.cmb_presets.addItem("1 : 1.5 (Partial Effect 67% on A)", (1.0, 1.5))
        self.cmb_presets.addItem("2 : 3 (Partial Effect 67%)", (2.0, 3.0))
        self.cmb_presets.addItem("3 : 4 (Partial Effect 75%)", (3.0, 4.0))
        self.cmb_presets.addItem("Custom (Set Weights A & B Manually)", None)
        preset_row.addWidget(self.cmb_presets, 1)
        layout_weights.addLayout(preset_row)

        # Dynamic Formula Explanation Banner
        self.banner_formula = QFrame()
        self.banner_formula.setStyleSheet("""
            QFrame {
                background-color: #f0fdf4;
                border: 1px solid #86efac;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        banner_layout = QVBoxLayout(self.banner_formula)
        self.lbl_formula_math = QLabel()
        self.lbl_formula_math.setStyleSheet("color: #166534; font-weight: bold; font-size: 13px;")
        self.lbl_formula_desc = QLabel()
        self.lbl_formula_desc.setStyleSheet("color: #14532d; font-size: 11px;")
        self.lbl_formula_desc.setWordWrap(True)
        banner_layout.addWidget(self.lbl_formula_math)
        banner_layout.addWidget(self.lbl_formula_desc)
        layout_weights.addWidget(self.banner_formula)

        scroll_layout.addWidget(group_weights)

        # Group 4: Calculation & Geodetic Options
        group_calc = QGroupBox("4. Calculation & Geodetic Parameters (TALOS S-51)")
        group_calc.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid #cbd5e1; border-radius: 6px; margin-top: 6px; padding-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #1e293b; }")
        layout_calc = QGridLayout(group_calc)
        layout_calc.setSpacing(8)

        layout_calc.addWidget(QLabel("Grid Density / Resolution:"), 0, 0)
        res_row = QHBoxLayout()
        self.rad_res_auto = QRadioButton("Automatic (Fast Adaptive)")
        self.rad_res_auto.setChecked(True)
        self.rad_res_fine = QRadioButton("Fine (High Precision)")
        self.rad_res_custom = QRadioButton("Custom:")
        self.spn_res_custom = QDoubleSpinBox()
        self.spn_res_custom.setRange(1.0, 50000.0)
        self.spn_res_custom.setValue(100.0)
        self.spn_res_custom.setSuffix(" m")
        self.spn_res_custom.setEnabled(False)

        res_group = QButtonGroup(self)
        res_group.addButton(self.rad_res_auto)
        res_group.addButton(self.rad_res_fine)
        res_group.addButton(self.rad_res_custom)

        res_row.addWidget(self.rad_res_auto)
        res_row.addWidget(self.rad_res_fine)
        res_row.addWidget(self.rad_res_custom)
        res_row.addWidget(self.spn_res_custom)
        res_row.addStretch()
        layout_calc.addLayout(res_row, 0, 1)

        self.chk_smooth = QCheckBox("Apply Line Smoothing (Chaikin Corner-Cutting)")
        self.chk_smooth.setChecked(True)
        layout_calc.addWidget(self.chk_smooth, 1, 0, 1, 2)

        self.chk_tie_lines = QCheckBox("Generate Construction / Tie Lines (Connecting lines to nearest controlling basepoints)")
        self.chk_tie_lines.setChecked(True)
        layout_calc.addWidget(self.chk_tie_lines, 2, 0, 1, 2)

        scroll_layout.addWidget(group_calc)

        # Group 5: Output Destination
        group_out = QGroupBox("5. Output Layer Settings")
        group_out.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid #cbd5e1; border-radius: 6px; margin-top: 6px; padding-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #1e293b; }")
        layout_out = QGridLayout(group_out)
        layout_out.setSpacing(8)

        layout_out.addWidget(QLabel("Output Layer Name:"), 0, 0)
        self.txt_layer_name = QLineEdit("Median_Line_TALOS")
        layout_out.addWidget(self.txt_layer_name, 0, 1)

        layout_out.addWidget(QLabel("Storage Type:"), 1, 0)
        out_row = QHBoxLayout()
        self.rad_out_memory = QRadioButton("Temporary Scratch Layer (Memory)")
        self.rad_out_memory.setChecked(True)
        self.rad_out_file = QRadioButton("Save to File...")
        out_group = QButtonGroup(self)
        out_group.addButton(self.rad_out_memory)
        out_group.addButton(self.rad_out_file)
        out_row.addWidget(self.rad_out_memory)
        out_row.addWidget(self.rad_out_file)
        out_row.addStretch()
        layout_out.addLayout(out_row, 1, 1)

        self.txt_file_path = QLineEdit()
        self.txt_file_path.setPlaceholderText("Select GeoPackage / Shapefile destination...")
        self.txt_file_path.setEnabled(False)
        self.btn_browse_file = QPushButton("Browse...")
        self.btn_browse_file.setEnabled(False)
        file_row = QHBoxLayout()
        file_row.addWidget(self.txt_file_path, 1)
        file_row.addWidget(self.btn_browse_file)
        layout_out.addLayout(file_row, 2, 1)

        scroll_layout.addWidget(group_out)
        scroll_area.setWidget(scroll_content)
        tab_layout.addWidget(scroll_area)
        self.tab_widget.addTab(tab_params, "⚙️ Delimitation Parameters")

        # Tab 2: TALOS & UNCLOS Concept and Documentation
        tab_help = QWidget()
        tab_help_layout = QVBoxLayout(tab_help)
        self.txt_help = QTextBrowser()
        self.txt_help.setOpenExternalLinks(True)
        self.txt_help.setHtml(self._get_talos_help_html())
        tab_help_layout.addWidget(self.txt_help)
        self.tab_widget.addTab(tab_help, "📖 TALOS & UNCLOS Principles")

        # Progress Bar & Status
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel("Ready. Select baseline/basepoints layers and configure weighting.")
        self.lbl_status.setStyleSheet("color: #475569; font-style: italic;")
        main_layout.addWidget(self.lbl_status)

        # Action Buttons
        btn_layout = QHBoxLayout()
        self.btn_reset = QPushButton("Reset Defaults")
        self.btn_close = QPushButton("Close")
        self.btn_run = QPushButton("⚡ Generate Median Line (TALOS & UNCLOS)")
        self.btn_run.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                font-weight: bold;
                font-size: 13px;
                padding: 8px 16px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
            QPushButton:pressed {
                background-color: #1e40af;
            }
        """)

        btn_layout.addWidget(self.btn_reset)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_close)
        btn_layout.addWidget(self.btn_run)
        main_layout.addLayout(btn_layout)

    def _connect_signals(self):
        self.btn_close.clicked.connect(self.reject)
        self.btn_reset.clicked.connect(self._reset_defaults)
        self.btn_run.clicked.connect(self._run_delimitation)

        self.spn_weight_a.valueChanged.connect(self._on_weight_changed)
        self.spn_weight_b.valueChanged.connect(self._on_weight_changed)
        self.cmb_presets.currentIndexChanged.connect(self._on_preset_changed)

        self.rad_res_custom.toggled.connect(lambda checked: self.spn_res_custom.setEnabled(checked))
        self.rad_out_file.toggled.connect(self._on_output_type_toggled)
        self.btn_browse_file.clicked.connect(self._browse_output_file)

        self.btn_pick_a.clicked.connect(lambda: self._start_canvas_pick('A'))
        self.btn_pick_b.clicked.connect(lambda: self._start_canvas_pick('B'))

        self.cmb_mode.currentIndexChanged.connect(self._on_mode_changed)
        self.cmb_seaward_extent.currentIndexChanged.connect(self._on_seaward_extent_changed)
        self.btn_pick_lbt.clicked.connect(lambda: self._start_point_pick('LBT'))
        self.btn_reset_lbt.clicked.connect(self._reset_lbt)
        self.btn_pick_seaward.clicked.connect(lambda: self._start_point_pick('SEAWARD'))
        self.btn_reset_seaward.clicked.connect(self._reset_seaward)

    def _on_mode_changed(self, index):
        mode = self.cmb_mode.currentData()
        if mode == "opposite":
            self.lbl_mode_desc.setText(
                "Opposite Coasts: Two coasts facing each other across maritime waters. "
                "The median line runs equidistant between both shores.\n"
                "Examples: Malacca Strait (Indonesia – Malaysia), Celebes Sea (Indonesia – Philippines), Dover Strait (UK – France)."
            )
            self.banner_mode.setStyleSheet(
                "QFrame { background-color: #f0f9ff; border: 1px solid #7dd3fc; border-radius: 6px; padding: 8px; }"
            )
            self.group_adj_options.setVisible(False)
        else:
            self.lbl_mode_desc.setText(
                "Adjacent Coasts: Two coasts meet at a land border point (Land Boundary Terminus / LBT). "
                "The lateral maritime boundary extends seaward into open water from the LBT up to the specified distance limit.\n"
                "Examples: Pacific Ocean & Arafura Sea (Indonesia – Papua New Guinea), North Sea (Germany – Netherlands)."
            )
            self.banner_mode.setStyleSheet(
                "QFrame { background-color: #fefce8; border: 1px solid #fde047; border-radius: 6px; padding: 8px; }"
            )
            self.group_adj_options.setVisible(True)

    def _on_seaward_extent_changed(self, index):
        is_custom = (self.cmb_seaward_extent.currentData() == -1)
        self.spn_custom_extent.setEnabled(is_custom)
        self.cmb_custom_extent_unit.setEnabled(is_custom)

    def _start_point_pick(self, target):
        if not self.canvas:
            QMessageBox.warning(self, "Map Canvas", "Map canvas is not available.")
            return

        self.active_point_pick_target = target
        if not self.point_picker_tool:
            self.point_picker_tool = PointPickerMapTool(self.canvas)
            self.point_picker_tool.point_picked.connect(self._on_point_picked)

        self.canvas.setMapTool(self.point_picker_tool)
        name = "Land Boundary Terminus (LBT)" if target == 'LBT' else "Seaward Direction Point"
        self.lbl_status.setText(f"🎯 Click on map canvas to set {name}...")

    def _on_point_picked(self, point):
        x, y = point.x(), point.y()
        if self.active_point_pick_target == 'LBT':
            self.custom_lbt_point = [x, y]
            self.lbl_lbt_status.setText(f"Custom: X={x:.2f}, Y={y:.2f}")
            self.lbl_status.setText(f"LBT point set to coordinates ({x:.2f}, {y:.2f}).")
        elif self.active_point_pick_target == 'SEAWARD':
            self.custom_seaward_point = [x, y]
            self.lbl_seaward_status.setText(f"Seaward Point: X={x:.2f}, Y={y:.2f}")
            self.lbl_status.setText(f"Seaward direction set towards coordinates ({x:.2f}, {y:.2f}).")

        if self.point_picker_tool:
            self.point_picker_tool.deactivate()
            if self.canvas:
                self.canvas.unsetMapTool(self.point_picker_tool)

    def _reset_lbt(self):
        self.custom_lbt_point = None
        self.lbl_lbt_status.setText("Automatic (Closest intersection of Baselines A & B)")
        self.lbl_status.setText("LBT reset to automatic detection.")

    def _reset_seaward(self):
        self.custom_seaward_point = None
        self.lbl_seaward_status.setText("Automatic (Outward into open sea away from coasts)")
        self.lbl_status.setText("Seaward direction reset to automatic detection.")

    def _on_preset_changed(self, index):
        data = self.cmb_presets.currentData()
        if data is not None:
            wa, wb = data
            self.spn_weight_a.blockSignals(True)
            self.spn_weight_b.blockSignals(True)
            self.spn_weight_a.setValue(wa)
            self.spn_weight_b.setValue(wb)
            self.spn_weight_a.blockSignals(False)
            self.spn_weight_b.blockSignals(False)
            self._update_formula_banner()

    def _on_weight_changed(self):
        # Update preset combobox to custom if doesn't match
        wa = self.spn_weight_a.value()
        wb = self.spn_weight_b.value()

        matched = False
        for i in range(self.cmb_presets.count()):
            data = self.cmb_presets.itemData(i)
            if data is not None and abs(data[0] - wa) < 1e-4 and abs(data[1] - wb) < 1e-4:
                self.cmb_presets.blockSignals(True)
                self.cmb_presets.setCurrentIndex(i)
                self.cmb_presets.blockSignals(False)
                matched = True
                break

        if not matched:
            self.cmb_presets.blockSignals(True)
            self.cmb_presets.setCurrentIndex(self.cmb_presets.count() - 1)  # Custom
            self.cmb_presets.blockSignals(False)

        self._update_formula_banner()

    def _update_formula_banner(self):
        wa = self.spn_weight_a.value()
        wb = self.spn_weight_b.value()
        ratio = wa / wb

        if abs(wa - wb) < 1e-4:
            math_text = "Formula: dA = dB  (1 : 1 Ratio — Strict Equidistance)"
            desc_text = "Every point along the median line is at equal distance to Baseline A and Baseline B (UNCLOS Art. 15, Strict Equidistance - Full Effect)."
            self.banner_formula.setStyleSheet("QFrame { background-color: #eff6ff; border: 1px solid #93c5fd; border-radius: 6px; padding: 10px; }")
            self.lbl_formula_math.setStyleSheet("color: #1e40af; font-weight: bold; font-size: 13px;")
            self.lbl_formula_desc.setStyleSheet("color: #1e3a8a; font-size: 11px;")
        elif wa < wb:
            math_text = f"Formula: dA = {ratio:.3f} × dB  (Weight Ratio {wa:g} : {wb:g} — Shifted towards Feature A)"
            desc_text = f"Because Feature A weight ({wa:g}) is lower than Feature B ({wb:g}), the distance to Feature A is {ratio:.3f} times the distance to Feature B. The maritime boundary lies CLOSER to Feature A (Feature B receives a larger maritime allocation, reflecting partial coastal effect / half-effect)."
            self.banner_formula.setStyleSheet("QFrame { background-color: #fefce8; border: 1px solid #fde047; border-radius: 6px; padding: 10px; }")
            self.lbl_formula_math.setStyleSheet("color: #854d0e; font-weight: bold; font-size: 13px;")
            self.lbl_formula_desc.setStyleSheet("color: #713f12; font-size: 11px;")
        else:
            math_text = f"Formula: dA = {ratio:.3f} × dB  (Weight Ratio {wa:g} : {wb:g} — Shifted towards Feature B)"
            desc_text = f"Because Feature B weight ({wb:g}) is lower than Feature A ({wa:g}), the distance to Feature B is {1.0/ratio:.3f} times the distance to Feature A. The maritime boundary lies CLOSER to Feature B (Feature A receives a larger maritime allocation)."
            self.banner_formula.setStyleSheet("QFrame { background-color: #faf5ff; border: 1px solid #d8b4fe; border-radius: 6px; padding: 10px; }")
            self.lbl_formula_math.setStyleSheet("color: #6b21a8; font-weight: bold; font-size: 13px;")
            self.lbl_formula_desc.setStyleSheet("color: #581c87; font-size: 11px;")

        self.lbl_formula_math.setText(math_text)
        self.lbl_formula_desc.setText(desc_text)

    def _on_output_type_toggled(self, checked):
        self.txt_file_path.setEnabled(checked)
        self.btn_browse_file.setEnabled(checked)

    def _browse_output_file(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Maritime Boundary Layer", "", "GeoPackage (*.gpkg);;Shapefile (*.shp)"
        )
        if path:
            self.txt_file_path.setText(path)

    def _reset_defaults(self):
        self.cmb_presets.setCurrentIndex(0)
        self.spn_weight_a.setValue(1.0)
        self.spn_weight_b.setValue(1.0)
        self.chk_selected_a.setChecked(False)
        self.chk_selected_b.setChecked(False)
        self.rad_res_auto.setChecked(True)
        self.chk_smooth.setChecked(True)
        self.chk_tie_lines.setChecked(True)
        self.txt_layer_name.setText("Median_Line_TALOS")
        self.rad_out_memory.setChecked(True)
        self.cmb_mode.setCurrentIndex(0)
        self._on_mode_changed(0)
        self.cmb_seaward_extent.setCurrentIndex(0)
        self.spn_custom_extent.setValue(12.0)
        self._reset_lbt()
        self._reset_seaward()
        self.lbl_status.setText("Parameters reset to defaults.")

    def _start_canvas_pick(self, target):
        if not self.canvas:
            QMessageBox.warning(self, "Map Canvas", "Map canvas is not available.")
            return

        target_layer = self.cmb_layer_a.currentLayer() if target == 'A' else self.cmb_layer_b.currentLayer()
        if not target_layer:
            QMessageBox.warning(self, "Select Layer", f"Please select a layer for Feature {target} first.")
            return

        self.active_pick_target = target
        if not self.picker_tool:
            self.picker_tool = FeaturePickerMapTool(self.canvas, target_layer)
            self.picker_tool.feature_picked.connect(self._on_feature_picked)

        self.picker_tool.set_target_layer(target_layer)
        self.canvas.setMapTool(self.picker_tool)
        self.lbl_status.setText(f"🎯 Click on map canvas to select Feature {target}...")

    def _on_layer_a_changed(self, layer):
        if self.cmb_layer_b.count() > 1 and self.cmb_layer_b.currentLayer() == layer:
            idx = 1 if self.cmb_layer_a.currentIndex() == 0 else 0
            self.cmb_layer_b.setCurrentIndex(idx)

    def _on_feature_picked(self, layer, feat):
        fid = feat.id()
        if self.active_pick_target == 'A':
            self.selected_fid_a = fid
            self.chk_selected_a.setChecked(True)
            self.lbl_info_a.setText(f"Feature A (FID {fid}):")
            self.lbl_status.setText(f"Feature A selected (ID: {fid}) from layer '{layer.name()}'.")
        else:
            self.selected_fid_b = fid
            self.chk_selected_b.setChecked(True)
            self.lbl_info_b.setText(f"Feature B (FID {fid}):")
            self.lbl_status.setText(f"Feature B selected (ID: {fid}) from layer '{layer.name()}'.")

        if self.picker_tool:
            self.picker_tool.deactivate()
            if self.canvas:
                self.canvas.unsetMapTool(self.picker_tool)

    def _get_selected_geometries(self, layer, selected_only, specific_fid=None):
        if not layer or not layer.isValid():
            return []

        # If a specific feature was picked via Canvas Picker Tool
        if specific_fid is not None:
            feat = layer.getFeature(specific_fid)
            if feat.isValid() and feat.hasGeometry():
                return [QgsGeometry(feat.geometry())]

        geoms = []
        if selected_only:
            if layer.selectedFeatureCount() == 0:
                return None  # None indicates selection was required but none found
            for feat in layer.selectedFeatures():
                geom = feat.geometry()
                if geom and not geom.isEmpty():
                    geoms.append(QgsGeometry(geom))
        else:
            for feat in layer.getFeatures():
                geom = feat.geometry()
                if geom and not geom.isEmpty():
                    geoms.append(QgsGeometry(geom))
        return geoms

    def _run_delimitation(self):
        layer_a = self.cmb_layer_a.currentLayer()
        layer_b = self.cmb_layer_b.currentLayer()

        if not layer_a or not layer_b:
            QMessageBox.critical(self, "Input Error", "Please select layers for both Baseline A and Baseline B.")
            return

        fid_a = self.selected_fid_a if self.chk_selected_a.isChecked() else None
        fid_b = self.selected_fid_b if self.chk_selected_b.isChecked() else None

        geoms_a = self._get_selected_geometries(layer_a, self.chk_selected_a.isChecked(), fid_a)
        geoms_b = self._get_selected_geometries(layer_b, self.chk_selected_b.isChecked(), fid_b)

        if geoms_a is None:
            QMessageBox.warning(
                self, "No Selected Features",
                f"Option 'Use selected features only' is checked for Feature A, but no features are selected on layer '{layer_a.name()}'.\n\n"
                "Please select features on the map canvas first or uncheck the option."
            )
            return

        if geoms_b is None:
            QMessageBox.warning(
                self, "No Selected Features",
                f"Option 'Use selected features only' is checked for Feature B, but no features are selected on layer '{layer_b.name()}'.\n\n"
                "Please select features on the map canvas first or uncheck the option."
            )
            return

        if not geoms_a:
            QMessageBox.critical(self, "Geometry Error", f"No valid geometry found on Baseline A layer ('{layer_a.name()}').")
            return
        if not geoms_b:
            QMessageBox.critical(self, "Geometry Error", f"No valid geometry found on Baseline B layer ('{layer_b.name()}').")
            return

        # Check if identical features or layer without distinction
        if layer_a == layer_b:
            same_feature = False
            if fid_a is not None and fid_b is not None and fid_a == fid_b:
                same_feature = True
            elif not self.chk_selected_a.isChecked() and not self.chk_selected_b.isChecked():
                same_feature = True

            if same_feature:
                QMessageBox.warning(
                    self, "Identical Layer & Features",
                    f"Baseline A and Baseline B reference the exact same layer and feature ('{layer_a.name()}').\n\n"
                    "TALOS & UNCLOS maritime delimitation requires two distinct coastal baselines/basepoints from opposing or adjacent sides.\n"
                    "Please choose a different layer for Feature B or select distinct features using '🎯 Pick on Map'."
                )
                return

        wa = self.spn_weight_a.value()
        wb = self.spn_weight_b.value()

        # Resolution
        if self.rad_res_custom.isChecked():
            res_val = self.spn_res_custom.value()
        elif self.rad_res_fine.isChecked():
            res_val = None  # engine will use fine adaptive resolution
        else:
            res_val = None

        self.btn_run.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(10)
        self.lbl_status.setText("Processing maritime delimitation...")

        try:
            # Setup engine
            class ProgressFeedback:
                def __init__(self, pbar, lbl):
                    self.pbar = pbar
                    self.lbl = lbl

                def setProgress(self, val):
                    self.pbar.setValue(int(val))

                def pushInfo(self, msg):
                    self.lbl.setText(msg)

                def isCanceled(self):
                    return False

            feedback = ProgressFeedback(self.progress_bar, self.lbl_status)

            source_crs = layer_a.crs()
            delim_mode = self.cmb_mode.currentData() or "opposite"

            seaward_dist = None
            if delim_mode == "adjacent":
                ext_val = self.cmb_seaward_extent.currentData()
                if ext_val == -1:
                    custom_val = self.spn_custom_extent.value()
                    unit = self.cmb_custom_extent_unit.currentData()
                    seaward_dist = custom_val * 1852.0 if unit == "NM" else custom_val * 1000.0
                else:
                    seaward_dist = ext_val

            engine = DelimitationEngine(
                geometries_a=geoms_a,
                geometries_b=geoms_b,
                weight_a=wa,
                weight_b=wb,
                name_a=self.txt_name_a.text(),
                name_b=self.txt_name_b.text(),
                source_crs=source_crs,
                resolution=res_val,
                smooth_line=self.chk_smooth.isChecked(),
                mode=delim_mode,
                seaward_distance=seaward_dist,
                lbt_point=self.custom_lbt_point,
                seaward_point=self.custom_seaward_point,
                feedback=feedback
            )

            result = engine.compute()

            if not result or not result.get('median_lines'):
                QMessageBox.warning(self, "No Line Generated", "No median line could be generated for this delimitation area.")
                return

            # Create Output Layer
            out_layer = self._create_median_line_layer(result, source_crs)
            try:
                symbol = QgsLineSymbol.createSimple({
                    'line_color': '#e11d48',
                    'line_width': '0.8',
                    'line_style': 'solid'
                })
                out_layer.setRenderer(QgsSingleSymbolRenderer(symbol))
                out_layer.triggerRepaint()
            except Exception:
                pass

            QgsProject.instance().addMapLayer(out_layer)

            # Auto-zoom canvas to show generated median line
            if self.canvas and not out_layer.extent().isEmpty():
                self.canvas.setExtent(out_layer.extent())
                self.canvas.refresh()

            # Optional tie lines layer
            if self.chk_tie_lines.isChecked() and result.get('tie_lines'):
                tie_layer = self._create_tie_lines_layer(result['tie_lines'], source_crs)
                try:
                    tie_symbol = QgsLineSymbol.createSimple({
                        'line_color': '#0284c7',
                        'line_width': '0.3',
                        'line_style': 'dot'
                    })
                    tie_layer.setRenderer(QgsSingleSymbolRenderer(tie_symbol))
                    tie_layer.triggerRepaint()
                except Exception:
                    pass
                QgsProject.instance().addMapLayer(tie_layer)

            summary = result['summary']
            seaward_info = f"\n• Seaward Reach: {summary.get('seaward_distance_nm', 0):.2f} NM ({summary.get('seaward_distance_m', 0)/1000:.2f} km)" if summary.get('seaward_distance_m') else ""
            msg = (
                f"Maritime Delimitation Completed Successfully!\n\n"
                f"• Mode: {summary.get('mode_desc', summary.get('mode'))}\n"
                f"• Lines Generated: {summary['num_lines']}\n"
                f"• Total Length: {summary['total_length_km']:.2f} km ({summary['total_length_nm']:.2f} Nautical Miles)\n"
                f"• Weights A : B = {summary['weight_a']} : {summary['weight_b']} ({summary['ratio_desc']}){seaward_info}\n"
                f"• Calculation CRS: {summary['calc_crs']}\n\n"
                f"Layer '{out_layer.name()}' has been added and focused on the QGIS canvas."
            )
            QMessageBox.information(self, "Delimitation Successful", msg)
            self.lbl_status.setText("Delimitation completed successfully!")

        except Exception as e:
            QMessageBox.critical(self, "Execution Error", f"An error occurred during delimitation:\n{str(e)}")
            self.lbl_status.setText("Execution failed.")
        finally:
            self.btn_run.setEnabled(True)
            self.progress_bar.setVisible(False)

    def _create_median_line_layer(self, result, crs):
        lines = result['median_lines']
        summary = result['summary']

        uri = f"LineString?crs={crs.authid()}"
        out_layer = QgsVectorLayer(uri, self.txt_layer_name.text(), "memory")
        pr = out_layer.dataProvider()

        # Add fields
        fields = [
            QgsField("id", QVariant.Int),
            QgsField("name", QVariant.String),
            QgsField("weight_a", QVariant.Double),
            QgsField("weight_b", QVariant.Double),
            QgsField("ratio", QVariant.String),
            QgsField("length_m", QVariant.Double),
            QgsField("length_km", QVariant.Double),
            QgsField("length_nm", QVariant.Double),
            QgsField("method", QVariant.String),
            QgsField("calc_crs", QVariant.String)
        ]
        pr.addAttributes(fields)
        out_layer.updateFields()

        features = []
        for idx, line_coords in enumerate(lines, start=1):
            q_pts = [QgsPointXY(pt[0], pt[1]) for pt in line_coords]
            geom = QgsGeometry.fromPolylineXY(q_pts)

            feat = QgsFeature()
            feat.setGeometry(geom)

            # Calculate geodesic / metric length
            length_m = geom.length()
            if crs.isGeographic():
                # Estimate in meters using equator approx if in degrees
                length_m *= 111320.0
            length_km = length_m / 1000.0
            length_nm = length_m / 1852.0

            feat.setAttributes([
                idx,
                f"Median Line {idx} ({summary['ratio_desc']})",
                summary['weight_a'],
                summary['weight_b'],
                f"{summary['weight_a']}:{summary['weight_b']}",
                round(length_m, 2),
                round(length_km, 3),
                round(length_nm, 3),
                "TALOS Equidistance Delimitation",
                summary['calc_crs']
            ])
            features.append(feat)

        pr.addFeatures(features)
        out_layer.updateExtents()

        # If user selected save to file
        if self.rad_out_file.isChecked() and self.txt_file_path.text():
            file_path = self.txt_file_path.text()
            QgsVectorFileWriter.writeAsVectorFormat(
                out_layer, file_path, "UTF-8", crs, "GPKG" if file_path.endswith(".gpkg") else "ESRI Shapefile"
            )
            # Reopen from file
            out_layer = QgsVectorLayer(file_path, self.txt_layer_name.text(), "ogr")

        return out_layer

    def _create_tie_lines_layer(self, tie_lines, crs):
        uri = f"LineString?crs={crs.authid()}"
        tie_layer = QgsVectorLayer(uri, f"{self.txt_layer_name.text()}_TieLines", "memory")
        pr = tie_layer.dataProvider()

        fields = [
            QgsField("id", QVariant.Int),
            QgsField("dist_a_m", QVariant.Double),
            QgsField("dist_b_m", QVariant.Double),
            QgsField("dist_a_nm", QVariant.Double),
            QgsField("dist_b_nm", QVariant.Double),
            QgsField("ratio_obs", QVariant.Double)
        ]
        pr.addAttributes(fields)
        tie_layer.updateFields()

        features = []
        for idx, t in enumerate(tie_lines, start=1):
            p = QgsPointXY(t['p'][0], t['p'][1])
            qa = QgsPointXY(t['qa'][0], t['qa'][1])
            qb = QgsPointXY(t['qb'][0], t['qb'][1])

            # Line from QA -> P -> QB
            geom = QgsGeometry.fromPolylineXY([qa, p, qb])
            feat = QgsFeature()
            feat.setGeometry(geom)
            feat.setAttributes([
                idx,
                round(t['dist_a_m'], 1),
                round(t['dist_b_m'], 1),
                round(t['dist_a_nm'], 2),
                round(t['dist_b_nm'], 2),
                round(t['ratio_obs'], 3)
            ])
            features.append(feat)

        pr.addFeatures(features)
        tie_layer.updateExtents()
        return tie_layer

    def _get_talos_help_html(self):
        return """
        <div style="font-family: sans-serif; font-size: 12px; line-height: 1.6; color: #1e293b;">
            <h2 style="color: #1e3a8a; border-bottom: 2px solid #3b82f6; padding-bottom: 5px;">
                Maritime Boundary Delimitation Guide (TALOS & UNCLOS)
            </h2>
            
            <h3 style="color: #0369a1;">1. Legal Framework: UNCLOS 1982</h3>
            <p>
                The United Nations Convention on the Law of the Sea (<b>UNCLOS 1982</b>) establishes international legal provisions for maritime delimitation between States with opposite or adjacent coasts:
            </p>
            <ul>
                <li><b>Article 15 (Territorial Sea):</b> Where the coasts of two States are opposite or adjacent, neither is entitled to extend its territorial sea beyond the <i>median line</i> (equidistance line) every point of which is equidistant from the nearest points on the baselines, failing historic title or other special circumstances.</li>
                <li><b>Article 33 (Contiguous Zone):</b> The contiguous zone may not extend beyond 24 nautical miles from the baselines.</li>
                <li><b>Articles 74 & 83 (Exclusive Economic Zone & Continental Shelf):</b> Delimitation shall be effected by agreement on the basis of international law in order to achieve an <i>equitable solution</i>.</li>
            </ul>

            <h3 style="color: #0369a1;">2. Technical Standard: TALOS Manual (IHO/IAG/IOC S-51)</h3>
            <p>
                <b>TALOS</b> (<i>A Manual on Technical Aspects of the United Nations Convention on the Law of the Sea</i>) is the official technical standard jointly compiled by the <i>International Hydrographic Organization</i> (IHO), <i>International Association of Geodesy</i> (IAG), and <i>Intergovernmental Oceanographic Commission</i> (IOC).
            </p>
            <ul>
                <li><b>Equidistance / Median Line Principle:</b> A line every point of which is strictly equidistant (1:1) from the nearest points on the baselines of the two coastal States (<i>d<sub>A</sub> = d<sub>B</sub></i>).</li>
                <li><b>Controlling Basepoints & Turning Points:</b> The critical physical coastal points on baselines or low-water lines that directly determine changes in boundary direction.</li>
                <li><b>Construction Lines (Tie-Lines / Bisectors):</b> Vector rays connecting maritime boundary vertices to their nearest controlling baseline points to mathematically verify equidistance and distance ratios.</li>
            </ul>

            <h3 style="color: #0369a1;">3. Coastal Effect & Weighting Ratios (Half-Effect Concept)</h3>
            <p>
                In international jurisprudence (e.g. International Court of Justice — ICJ, ITLOS, and PCA arbitral awards), specific coastal features (such as small isolated islands, protruding capes, or disproportionate coast lengths) are frequently accorded partial effect (e.g. <i>half-effect</i>) rather than full effect (1:1) to achieve an equitable result:
            </p>
            <div style="background-color: #f8fafc; border-left: 4px solid #3b82f6; padding: 10px; margin: 10px 0;">
                <b>Weighted Distance Formula:</b><br>
                <code>d<sub>A</sub> / w<sub>A</sub> = d<sub>B</sub> / w<sub>B</sub>  &hArr;  d<sub>A</sub> = (w<sub>A</sub> / w<sub>B</sub>) &times; d<sub>B</sub></code>
            </div>
            <ul>
                <li><b>1 : 1 Ratio:</b> Strict Equidistance (Full effect for both coastal features). <code>d<sub>A</sub> = d<sub>B</sub></code>.</li>
                <li><b>1 : 2 Ratio:</b> Feature A has weight 1, Feature B has weight 2. This yields <code>d<sub>A</sub> = 0.5 &times; d<sub>B</sub></code>. 
                The maritime boundary is positioned <b>twice as close to Feature A</b> (closer to the feature with weight 1), granting a broader maritime entitlement to Feature B (half-effect on A).</li>
                <li><b>2 : 1 Ratio:</b> Feature A has weight 2, Feature B has weight 1. The line is positioned <b>twice as close to Feature B</b>.</li>
            </ul>

            <h3 style="color: #0369a1;">4. Maritime Distance Units</h3>
            <p>
                In adherence to TALOS and UNCLOS standards, maritime distances and lengths are reported in:
                <ul>
                    <li><b>Nautical Miles (NM / M):</b> Exactly 1 international Nautical Mile = 1,852 meters.</li>
                    <li><b>Kilometers (km) & Meters (m).</b></li>
                </ul>
            </p>

            <h3 style="color: #0369a1;">5. Delimitation Between Adjacent Coastal States</h3>
            <p>
                For neighboring States sharing a contiguous coastline (<i>adjacent States</i>):
            </p>
            <ul>
                <li><b>Land Boundary Terminus (LBT):</b> The terminal point where the terrestrial border meets the sea coast. It serves as the physical point of origin for the lateral maritime boundary.</li>
                <li><b>Seaward Extension:</b> The lateral boundary starts at the LBT and propagates outward into open sea (away from land). The engine automatically filters inland contour branches so that only the seaward boundary is preserved.</li>
                <li><b>Maritime Zone Cutoff Limits (UNCLOS 1982):</b>
                    <ul>
                        <li><b>12 Nautical Miles (22,224 m):</b> Territorial Sea boundary (Article 15).</li>
                        <li><b>24 Nautical Miles (44,448 m):</b> Contiguous Zone limit (Article 33).</li>
                        <li><b>200 Nautical Miles (370,400 m):</b> Exclusive Economic Zone & Continental Shelf limit (Articles 74 & 83).</li>
                    </ul>
                </li>
            </ul>
        </div>
        """
