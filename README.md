# XRF Correction Factor Tool

A PySide6 desktop application for computing and managing XRF (X-ray fluorescence) correction factors for metallic coatings on foils.

## Features

- **Calibration sheets** — enter reference samples to compute per-element correction factors via Grubbs-tested mean CF
- **Analysis sheets** — apply calibration CFs to multi-element samples and validate via % error
- **Per-sheet geometry** — override the project-default electrode diameter individually per sheet
- **Mass / Mass Loading toggle** — input data as raw mass (mg) or areal loading (mg/cm²); switching modes auto-converts stored values
- **Statistics** — descriptive stats, uncertainty propagation, Grubbs outlier detection, linear/quadratic curve fitting
- **Visualization** — embedded matplotlib plots (CF per sample, CF vs. loading, parity plot, element contribution)
- **Excel I/O** — save and reload projects as `.xlsx` files; human-readable column layout
- **PDF export** — multi-page report with plots and summary statistics

## Installation

```bash
pip install -r requirements.txt
```

Requires Python 3.10+.

## Usage

```bash
python main.py
```

1. **New Project** — set a project name and default electrode diameter
2. **Add Calibration** — one sheet per element (e.g. Pb on Al, Cu on Al)
3. **Add Analysis** — select which calibrated elements appear in the mixed sample
4. Enter data in the **Data** tab; computed results appear in **Results**, **Statistics**, and **Visualization**
5. **Save** to `.xlsx` for later reloading; **Export PDF** for reports

## Project Structure

```
xrf_tool/
├── main.py
├── requirements.txt
├── models/
│   ├── project.py        # Data model (Project, CalibrationSheet, AnalysisSheet, samples)
│   └── calculations.py   # Correction factor math, stats, outlier detection, curve fitting
├── views/
│   ├── main_window.py
│   ├── project_panel.py
│   ├── data_tab.py
│   ├── results_tab.py
│   ├── statistics_tab.py
│   └── visualization_tab.py
├── xrf_io/
│   ├── excel_io.py       # openpyxl-based save/load
│   └── pdf_export.py     # matplotlib PDF backend
└── dialogs/
    ├── new_project_dialog.py
    └── add_sheet_dialog.py
```

## Dependencies

| Package | Purpose |
|---|---|
| PySide6 | GUI framework |
| numpy | Array math |
| scipy | Grubbs test, curve fitting |
| matplotlib | Plots and PDF export |
| openpyxl | Excel read/write |
