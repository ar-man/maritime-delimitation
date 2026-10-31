# Maritime Delimitation Plugin (TALOS & UNCLOS)

**QGIS Plugin for Maritime Delimitation: Construction of Strict Equidistance Median Lines and Weighted Boundaries according to TALOS (IHO/IAG/IOC S-51) and UNCLOS 1982 Standards.**

---

## 📌 Overview

This plugin is designed for geodesists, hydrographers, maritime boundary specialists, and GIS analysts to perform maritime boundary delimitation between opposing or adjacent coastal States/features in strict compliance with authoritative international standards:

1. **UNCLOS 1982** (*United Nations Convention on the Law of the Sea*):
   - **Article 15**: Delimitation of the Territorial Sea between States with opposite or adjacent coasts based on the median line / equidistance principle.
   - **Article 33**: Contiguous Zone limits (up to 24 Nautical Miles).
   - **Articles 74 & 83**: Delimitation of the Exclusive Economic Zone (EEZ) and the Continental Shelf to achieve an *equitable solution*.
2. **TALOS Manual (IHO/IAG/IOC S-51)** (*A Manual on Technical Aspects of the United Nations Convention on the Law of the Sea*):
   - Identification of baselines, low-water basepoints, turning points, and construction tie-lines.
   - Technical execution of partial coastal effect / half-effect weighting.

---

## ✨ Key Features

- **Multi-Geometry Coastal Support**:
  - **Basepoints** (Point / MultiPoint): Low-water line coordinates, drying rocks, and critical basepoints.
  - **Baselines** (LineString / MultiLineString): Normal baselines, straight baselines, and archipelagic baselines.
  - **Coastlines / Islands** (Polygon / MultiPolygon): Continental coastlines or insular features.
- **Flexible Feature Selection**:
  - Select from two distinct layers (e.g. State A layer vs. State B layer).
  - Select features within the same layer using the *"Use selected features only"* option.
  - Interactive **"🎯 Pick on Map"** canvas tool: Click directly on features on the QGIS canvas to designate Baseline A or B.
- **Delimitation Modes (Opposite & Adjacent Coasts)**:
  - **Opposite Coasts Mode**: Computes the central median line traversing the maritime channel between two opposing shores.
  - **Adjacent Coasts Mode**: Computes the lateral maritime boundary extending seaward from the **Land Boundary Terminus (LBT)** out to a user-defined cutoff distance (e.g. 12 NM Territorial Sea, 24 NM Contiguous Zone, 200 NM EEZ, or custom reach).
  - Interactive map tools for setting the LBT point and seaward direction.
- **TALOS Maritime Weighting System**:
  - **1 : 1 Ratio (Strict Equidistance)**: Pure equidistance line where every point is equidistant to both baselines ($d_A = d_B$).
  - **1 : 2 Ratio (Half-Effect on Feature A)**: Boundaries drawn per $d_A = 0.5 \times d_B$, shifting the line **twice as close to Baseline A** (closer to the feature with weight 1, granting a larger maritime space to Feature B).
  - **2 : 1 Ratio (Half-Effect on Feature B)**: Boundary shifted twice as close to Baseline B.
  - **Custom Ratios**: Supports any arbitrary weighting ratio (e.g. 2:3, 3:4, or decimal values).
  - Real-time mathematical formula explanation banner directly within the dialog.
- **Cartographic & Geodetic Verification**:
  - **Construction Lines (Tie-Lines)**: Vector lines connecting boundary vertices to the closest controlling basepoints on each coast to mathematically verify equidistance and distance ratios.
  - **Line Smoothing (Chaikin Corner-Cutting)**: Produces smooth, publication-grade cartographic boundary lines without aliasing.
  - **Maritime Units**: Automatic metric and nautical unit calculations in **Nautical Miles (NM)** and **Kilometers (km)**.
- **Dual QGIS Integration**:
  - Rich interactive GUI dialog accessible from `Vector` -> `Maritime Delimitation (TALOS)`.
  - Registered **QGIS Processing Algorithm** in the Processing Toolbox for automated batch workflows and Graphical Modeler pipelines.

---

## 📐 Mathematical Formulation (TALOS & UNCLOS)

### 1. Strict Equidistance Line (1 : 1 Ratio)
According to Chapter 6 of the TALOS Manual (IHO S-51), an equidistance median line is defined as the locus of points $P$ equidistant from the nearest points on the baselines of both States:
$$\min_{a \in A} \text{dist}(P, a) = \min_{b \in B} \text{dist}(P, b) \iff d_A(P) - d_B(P) = 0$$

### 2. Weighted Coastal Delimitation (Partial / Half-Effect)
In the jurisprudence of the International Court of Justice (ICJ) and international arbitration tribunals (PCA, ITLOS), specific coastal features (such as small isolated islands, protruding islets, or disproportionate coastal lengths) are frequently given partial effect (e.g., *half-effect*) rather than full effect (1:1).

The weighted boundary is formulated mathematically by distance proportionality:
$$\frac{d_A(P)}{w_A} = \frac{d_B(P)}{w_B} \iff d_A(P) = \left(\frac{w_A}{w_B}\right) d_B(P)$$

- **Equal Weight ($w_A = 1, w_B = 1$)**:
  $$d_A = 1.0 \times d_B \quad (\text{Strict central equidistance})$$
- **Weight Ratio 1 : 2 ($w_A = 1, w_B = 2$)**:
  $$d_A = \frac{1}{2} d_B = 0.5 \times d_B$$
  The distance to Baseline A is **half** the distance to Baseline B. Consequently, the boundary lies **closer to Baseline A (weight 1)**, giving a broader maritime allocation to Baseline B (weight 2).

---

## 📁 Repository Structure

```
plugin_median/
├── metadata.txt                      # Official QGIS Plugin Manager metadata
├── __init__.py                       # Plugin entry point (classFactory)
├── plugin.py                         # Main QGIS plugin class (menu, toolbar, processing)
├── test_delimitation.py              # Self-contained automated test suite
├── core/
│   ├── __init__.py
│   ├── delimitation_engine.py       # Core delimitation computation engine
│   ├── marching_squares.py          # Vectorized Marching Squares & polyline assembler
│   └── geodetic_utils.py            # Coordinate transformations & Nautical Mile conversions
├── gui/
│   ├── __init__.py
│   ├── median_line_dialog.py        # PyQt dialog user interface
│   └── map_tool_picker.py           # Interactive canvas selection tools
├── processing/
│   ├── __init__.py
│   ├── provider.py                  # QGIS Processing Provider
│   └── median_line_algorithm.py     # QGIS Processing Algorithm
├── resources/
│   ├── icon.png                     # Plugin raster icon
│   └── icon.svg                     # Plugin vector icon
└── sample_data/                     # Sample datasets for instant testing
    ├── baseline_country_a.geojson   # Coastal baseline for Country A
    ├── baseline_country_b.geojson   # Coastal baseline for Country B
    ├── basepoints_country_a.geojson # Basepoints for Country A
    └── basepoints_country_b.geojson # Basepoints for Country B
```

---

## 🚀 Installation Guide

### Option 1: Direct Folder Installation
Copy the `plugin_median` folder into your QGIS plugins directory:
- **Windows**:
  `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\plugin_median`
- **Linux**:
  `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/plugin_median`
- **macOS**:
  `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/plugin_median`

### Option 2: Enable in QGIS
1. Launch **QGIS** (version 3.10 or higher).
2. Go to the menu: **Plugins** -> **Manage and Install Plugins...**.
3. Select the **Installed** tab.
4. Check the box next to **"Maritime Delimitation (TALOS & UNCLOS)"**.
5. The anchor icon will appear on your toolbar and under **Vector** -> **Maritime Delimitation (TALOS)**.

---

## 🛠️ How to Use (Step-by-Step)

### Method 1: Using the Interactive GUI Dialog

1. **Load Baseline or Basepoint Layers**:
   - Add your coastal vector layers into QGIS (or load the provided sample data in `sample_data/`).
2. **Open the Dialog**:
   - Click the toolbar icon or select **Vector** -> **Maritime Delimitation (TALOS)** -> **Generate Median Line (TALOS & UNCLOS)...**.
3. **Select Delimitation Mode**:
   - Choose **Opposite Coasts** (for facing coasts) or **Adjacent Coasts** (for adjacent coasts sharing an LBT).
   - If Adjacent mode is selected, set your **Seaward Extent Limit** (e.g. 12 NM Territorial Sea) and verify the LBT point.
4. **Configure Feature A & Feature B**:
   - Select layers for Feature A and Feature B.
   - Set weights (e.g. `1.0` and `1.0` for 1:1 strict equidistance, or choose a preset such as `1:2`).
5. **Adjust Parameters**:
   - Check *"Generate Construction / Tie Lines"* to visualize rays to controlling basepoints.
   - Check *"Apply Line Smoothing (Chaikin Corner-Cutting)"* for polished cartographic representation.
6. **Generate**:
   - Click **⚡ Generate Median Line (TALOS & UNCLOS)**.
   - The resulting median line and tie-lines will automatically load into QGIS, styled with distinct colors, and centered in the map canvas.

---

### Method 2: Using the QGIS Processing Toolbox

1. Open the **Processing Toolbox** in QGIS (`Ctrl + Alt + T`).
2. Navigate to **Maritime Delimitation (TALOS & UNCLOS)** -> **Generate Median Line (TALOS & UNCLOS)**.
3. Select your input layers, enter weight values, and click **Run**.
4. The algorithm can be incorporated seamlessly into QGIS **Graphical Modeler** workflows and Python scripts.

---

## 🧪 Verification and Automated Tests

Run the self-contained verification test suite from the terminal:

```bash
python test_delimitation.py
```

**Verification Results:**
- **Test 1 (1:1 Strict Equidistance)**: Symmetrical central boundary line ($d_A / d_B = 1.000$).
- **Test 2 (1:2 Opposite Weighted)**: Boundary consistently shifts closer to Baseline A with observed ratio $d_A / d_B = 0.500$.
- **Test 3 (2:1 Opposite Weighted)**: Boundary shifts closer to Baseline B with observed ratio $d_A / d_B = 2.000$.
- **Test 4 (Adjacent 12 NM Territorial Sea)**: Lateral boundary starts precisely at the LBT $(0, 0)$ and terminates at 22,224 meters (12.00 NM) in the seaward direction.
- **Test 5 (Adjacent 1:2 Weighted)**: Lateral boundary shifts towards State A's coastline.

---

## 📚 References & Technical Standards

1. **United Nations Convention on the Law of the Sea (UNCLOS)**, Montego Bay, 10 December 1982.
2. **IHO / IAG / IOC Special Publication No. 51 (TALOS-6)**: *A Manual on Technical Aspects of the United Nations Convention on the Law of the Sea - 1982*, 6th Edition, International Hydrographic Organization, Monaco, 2014.
3. **Beazley, P. B. (1994)**: *Technical Aspects of Maritime Boundary Delimitation*, International Boundaries Research Unit (IBRU), Durham University.
4. **Carleton, C. & Schofield, C. (2001)**: *Developments in the Technical Determination of Maritime Space: Delimitation, Dispute Resolution and Technical Issues in Maritime Boundary Delimitation*, Maritime Briefing, Vol. 3, No. 3.
5. **International Court of Justice (ICJ)**: *Maritime Delimitation in the Black Sea (Romania v. Ukraine)*, Judgment, I.C.J. Reports 2009.

---

## 📄 License

This plugin is licensed under the [GNU General Public License v2 (GPL-2.0)](https://www.gnu.org/licenses/old-licenses/gpl-2.0.en.html) or later, in accordance with QGIS Plugin Repository guidelines.
