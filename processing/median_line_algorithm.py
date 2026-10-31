"""
Maritime Delimitation - QGIS Processing Algorithm
Integrates TALOS / UNCLOS Median Line generation into the QGIS Processing Toolbox.
"""

try:
    from qgis.core import (
        QgsProcessing,
        QgsProcessingAlgorithm,
        QgsProcessingParameterFeatureSource,
        QgsProcessingParameterNumber,
        QgsProcessingParameterBoolean,
        QgsProcessingParameterEnum,
        QgsProcessingParameterFeatureSink,
        QgsProcessingOutputVectorLayer,
        QgsFeatureSink,
        QgsWkbTypes,
        QgsFields,
        QgsField,
        QgsFeature,
        QgsGeometry,
        QgsPointXY
    )
    from qgis.PyQt.QtCore import QVariant, QCoreApplication
    from qgis.PyQt.QtGui import QIcon
    HAS_QGIS = True
except ImportError:
    HAS_QGIS = False

from ..core.delimitation_engine import DelimitationEngine


class MedianLineProcessingAlgorithm(QgsProcessingAlgorithm):
    """
    QGIS Processing Algorithm for Maritime Delimitation (TALOS & UNCLOS).
    """

    BASELINE_A = 'BASELINE_A'
    WEIGHT_A = 'WEIGHT_A'
    BASELINE_B = 'BASELINE_B'
    WEIGHT_B = 'WEIGHT_B'
    MODE = 'MODE'
    SEAWARD_DISTANCE = 'SEAWARD_DISTANCE'
    RESOLUTION = 'RESOLUTION'
    SMOOTH = 'SMOOTH'
    GENERATE_TIE_LINES = 'GENERATE_TIE_LINES'
    OUTPUT = 'OUTPUT'
    OUTPUT_TIE_LINES = 'OUTPUT_TIE_LINES'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return MedianLineProcessingAlgorithm()

    def name(self):
        return 'generate_median_line'

    def displayName(self):
        return self.tr('Generate Median Line (TALOS & UNCLOS)')

    def group(self):
        return self.tr('Maritime Delimitation')

    def groupId(self):
        return 'maritime_delimitation'

    def shortHelpString(self):
        return self.tr(
            "Constructs maritime Median Lines (Equidistance Line) and Weighted Maritime Boundaries according to TALOS (IHO/IAG/IOC S-51) and UNCLOS 1982 standards.\n\n"
            "Inputs:\n"
            "- Baseline / Basepoints A and Weight A\n"
            "- Baseline / Basepoints B and Weight B\n"
            "- Delimitation Mode: Opposite Coasts or Adjacent Coasts\n"
            "- Seaward Distance Limit: Seaward cutoff limit for Adjacent mode (e.g. 22,224 m = 12 NM Territorial Sea)\n\n"
            "Weighting Concept:\n"
            "Maritime distance ratio: dA / dB = Weight A / Weight B.\n"
            "A 1:1 ratio produces a strict equidistance median line (full effect).\n"
            "A 1:2 ratio draws the boundary twice as close to Baseline A (shifted towards the feature with weight 1), reflecting partial coastal effect or half-effect."
        )

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterEnum(
                self.MODE,
                self.tr('Delimitation Mode'),
                options=[
                    self.tr('Opposite Coasts'),
                    self.tr('Adjacent Coasts')
                ],
                defaultValue=0
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.BASELINE_A,
                self.tr('Baseline / Basepoints A'),
                [QgsProcessing.TypeVectorPoint, QgsProcessing.TypeVectorLine, QgsProcessing.TypeVectorPolygon]
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.WEIGHT_A,
                self.tr('Feature A Weight (Weight A)'),
                type=QgsProcessingParameterNumber.Double,
                defaultValue=1.0,
                minValue=0.01,
                maxValue=100.0
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.BASELINE_B,
                self.tr('Baseline / Basepoints B'),
                [QgsProcessing.TypeVectorPoint, QgsProcessing.TypeVectorLine, QgsProcessing.TypeVectorPolygon]
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.WEIGHT_B,
                self.tr('Feature B Weight (Weight B)'),
                type=QgsProcessingParameterNumber.Double,
                defaultValue=1.0,
                minValue=0.01,
                maxValue=100.0
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.SEAWARD_DISTANCE,
                self.tr('Seaward Cutoff Distance for Adjacent Mode in Meters (Default: 22224 m / 12 NM)'),
                type=QgsProcessingParameterNumber.Double,
                defaultValue=22224.0,
                minValue=0.0
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.RESOLUTION,
                self.tr('Calculation Grid Resolution in Meters (0 = Automatic)'),
                type=QgsProcessingParameterNumber.Double,
                defaultValue=0.0,
                minValue=0.0
            )
        )

        self.addParameter(
            QgsProcessingParameterBoolean(
                self.SMOOTH,
                self.tr('Apply Line Smoothing (Chaikin Corner-Cutting)'),
                defaultValue=True
            )
        )

        self.addParameter(
            QgsProcessingParameterBoolean(
                self.GENERATE_TIE_LINES,
                self.tr('Generate Construction / Tie Lines'),
                defaultValue=False
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                self.tr('Median Line'),
                type=QgsProcessing.TypeVectorLine
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_TIE_LINES,
                self.tr('Tie Lines (Construction)'),
                type=QgsProcessing.TypeVectorLine,
                optional=True
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        mode_idx = self.parameterAsEnum(parameters, self.MODE, context)
        mode = DelimitationEngine.MODE_ADJACENT if mode_idx == 1 else DelimitationEngine.MODE_OPPOSITE

        source_a = self.parameterAsSource(parameters, self.BASELINE_A, context)
        weight_a = self.parameterAsDouble(parameters, self.WEIGHT_A, context)

        source_b = self.parameterAsSource(parameters, self.BASELINE_B, context)
        weight_b = self.parameterAsDouble(parameters, self.WEIGHT_B, context)

        seaward_dist = self.parameterAsDouble(parameters, self.SEAWARD_DISTANCE, context)
        seaward_distance = seaward_dist if seaward_dist > 0.0 else None

        res_input = self.parameterAsDouble(parameters, self.RESOLUTION, context)
        resolution = res_input if res_input > 0.0 else None

        smooth = self.parameterAsBoolean(parameters, self.SMOOTH, context)
        gen_tie = self.parameterAsBoolean(parameters, self.GENERATE_TIE_LINES, context)

        if source_a is None or source_b is None:
            raise ValueError(self.tr("Input Baseline A or B is invalid."))

        geoms_a = [f.geometry() for f in source_a.getFeatures() if f.hasGeometry()]
        geoms_b = [f.geometry() for f in source_b.getFeatures() if f.hasGeometry()]

        crs = source_a.sourceCrs()

        engine = DelimitationEngine(
            geometries_a=geoms_a,
            geometries_b=geoms_b,
            weight_a=weight_a,
            weight_b=weight_b,
            source_crs=crs,
            resolution=resolution,
            smooth_line=smooth,
            mode=mode,
            seaward_distance=seaward_distance,
            feedback=feedback
        )

        result = engine.compute()
        if not result or not result.get('median_lines'):
            feedback.reportError(self.tr("No median line could be generated."))
            return {}

        # Setup Output Sink
        out_fields = QgsFields()
        out_fields.append(QgsField("id", QVariant.Int))
        out_fields.append(QgsField("name", QVariant.String))
        out_fields.append(QgsField("weight_a", QVariant.Double))
        out_fields.append(QgsField("weight_b", QVariant.Double))
        out_fields.append(QgsField("ratio", QVariant.String))
        out_fields.append(QgsField("length_m", QVariant.Double))
        out_fields.append(QgsField("length_km", QVariant.Double))
        out_fields.append(QgsField("length_nm", QVariant.Double))
        out_fields.append(QgsField("method", QVariant.String))

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context, out_fields, QgsWkbTypes.LineString, crs
        )

        summary = result['summary']
        for idx, line in enumerate(result['median_lines'], start=1):
            q_pts = [QgsPointXY(pt[0], pt[1]) for pt in line]
            geom = QgsGeometry.fromPolylineXY(q_pts)
            length_m = geom.length()
            if crs.isGeographic():
                length_m *= 111320.0
            length_km = length_m / 1000.0
            length_nm = length_m / 1852.0

            feat = QgsFeature(out_fields)
            feat.setGeometry(geom)
            feat.setAttributes([
                idx,
                f"Median Line {idx}",
                weight_a,
                weight_b,
                f"{weight_a}:{weight_b}",
                round(length_m, 2),
                round(length_km, 3),
                round(length_nm, 3),
                "TALOS Equidistance Delimitation"
            ])
            sink.addFeature(feat, QgsFeatureSink.FastInsert)

        outputs = {self.OUTPUT: dest_id}

        # Optional Tie lines sink
        if gen_tie and result.get('tie_lines'):
            tie_fields = QgsFields()
            tie_fields.append(QgsField("id", QVariant.Int))
            tie_fields.append(QgsField("dist_a_m", QVariant.Double))
            tie_fields.append(QgsField("dist_b_m", QVariant.Double))
            tie_fields.append(QgsField("dist_a_nm", QVariant.Double))
            tie_fields.append(QgsField("dist_b_nm", QVariant.Double))
            tie_fields.append(QgsField("ratio_obs", QVariant.Double))

            (tie_sink, tie_dest_id) = self.parameterAsSink(
                parameters, self.OUTPUT_TIE_LINES, context, tie_fields, QgsWkbTypes.LineString, crs
            )
            if tie_sink is not None:
                for idx, t in enumerate(result['tie_lines'], start=1):
                    p = QgsPointXY(t['p'][0], t['p'][1])
                    qa = QgsPointXY(t['qa'][0], t['qa'][1])
                    qb = QgsPointXY(t['qb'][0], t['qb'][1])
                    geom = QgsGeometry.fromPolylineXY([qa, p, qb])
                    feat = QgsFeature(tie_fields)
                    feat.setGeometry(geom)
                    feat.setAttributes([
                        idx,
                        round(t['dist_a_m'], 1),
                        round(t['dist_b_m'], 1),
                        round(t['dist_a_nm'], 2),
                        round(t['dist_b_nm'], 2),
                        round(t['ratio_obs'], 3)
                    ])
                    tie_sink.addFeature(feat, QgsFeatureSink.FastInsert)
                outputs[self.OUTPUT_TIE_LINES] = tie_dest_id

        return outputs
