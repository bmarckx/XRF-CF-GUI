# XRF Correction Factor Tool

A PySide6 desktop application for computing and managing XRF (X-ray fluorescence)
correction factors for metallic coatings on foils.

## Features

- **Calibration sheets** — enter reference samples to compute per-element correction factors via Grubbs-tested mean CF
- **Analysis sheets** — apply correction factors to multi-element samples and validate via % error
- **Per-element CF sources** — each element can take its CF from a calibration sheet, a self-derived (residual) CF, or a custom value
- **Regime comparison** — compare all-calibration, all-self, capacity-based, and mixed (active) correction-factor regimes side by side
- **Capacity-based mass loading** — derive loading from practical specific capacity (mAh/g); active elements use mean practical SC ÷ expected SC, non-active elements use a residual capacity CF
- **Corrected mass & loading** — per element and total, in both mg and mg/cm²
- **Outlier handling** — automatic Grubbs detection plus manual per-sample exclusion; excluded samples are dropped from CF, self-CF, and mean-error calculations
- **Per-sheet geometry** — override the project-default electrode diameter per sheet; diameter entered in **cm or inches** (decimal or fraction, e.g. `1/2`)
- **Mass / Mass Loading toggle** — input data as raw mass (mg) or areal loading (mg/cm²); switching modes auto-converts stored values
- **Sheet operations** — duplicate sheets; move samples between sheets (with element remapping)
- **Statistics** — descriptive stats, uncertainty propagation, Grubbs outliers, linear/quadratic curve fitting
- **Visualization** — embedded matplotlib plots (CF per sample, CF vs. loading, parity plots, element contribution, regime comparison)
- **Excel I/O** — save and reload projects as `.xlsx`; human-readable layout
- **PDF export** — multi-page report with plots and summary statistics

---

## Option A — Install on a computer with NO internet (recommended for end users)

A fully self-contained package (Python + all libraries + the app) is built on an
internet-connected machine, then carried to the offline computer. **Nothing needs
to be installed on the offline machine** — no Python, no pip, no admin rights.

### On the offline computer

1. Copy `XRF-CF-Tool-Offline.zip` to the computer (USB drive, network share, etc.).
2. Right-click the zip → **Extract All…** to any folder (e.g. your Desktop or Documents).
3. Open the extracted folder and double-click **`install.bat`**.
4. A **"XRF-CF-Tool"** shortcut appears on your desktop. Double-click it to launch.
5. On first launch you'll be asked to pick a **default folder** for opening and
   saving project files. (You can change it later just by saving somewhere else.)

To move it later, re-run `install.bat`; to remove it, delete the desktop shortcut
and the folder `%LOCALAPPDATA%\Programs\XRF-CF-Tool`.

### Building the offline package (on an internet-connected machine)

From the project root (`xrf_tool/`):

```powershell
pip install -r requirements.txt pyinstaller
powershell -ExecutionPolicy Bypass -File packaging\build_offline_package.ps1
```

This produces **`packaging\XRF-CF-Tool-Offline.zip`** — that single file is the
complete deliverable to hand to the offline machine. Build on the **same OS/architecture**
as the target (Windows 64-bit → Windows 64-bit).

---

## Option B — Run from source (developers / internet available)

```bash
pip install -r requirements.txt
python main.py
```

Requires Python 3.10+.

### Quick start

1. **New Project** — set a project name and default electrode diameter (cm or inches)
2. **Add Calibration** — one sheet per element (e.g. Pb on Al, Cu on Al)
3. **Add Analysis** — select which calibrated elements appear in the mixed sample
4. Enter data in the **Data** tab; results appear in **Results**, **Statistics**, **Visualization**
5. **Save** to `.xlsx` for later reloading; **Export PDF** for reports

---

## Project Structure

```
xrf_tool/
├── main.py                 # Entry point (first-run setup + launch)
├── requirements.txt
├── models/
│   ├── project.py          # Data model (Project, CalibrationSheet, AnalysisSheet, samples)
│   ├── calculations.py     # CF math, capacity regimes, stats, outliers, curve fitting
│   ├── settings.py         # Persistent config (default folder), stored in %APPDATA%
│   └── units.py            # cm / inch (decimal & fraction) parsing
├── views/
│   ├── main_window.py
│   ├── project_panel.py    # Sheet tree: add / rename / duplicate / remove
│   ├── data_tab.py         # Sample entry, CF & capacity config, move samples
│   ├── results_tab.py
│   ├── statistics_tab.py
│   ├── visualization_tab.py
│   └── diameter_input.py   # cm / inch diameter widget
├── xrf_io/
│   ├── excel_io.py         # openpyxl-based save/load
│   └── pdf_export.py       # matplotlib PDF backend
├── dialogs/
│   ├── new_project_dialog.py
│   └── add_sheet_dialog.py
└── packaging/
    ├── XRF-CF-Tool.spec            # PyInstaller build spec
    ├── build_offline_package.ps1   # Builds the offline zip (run with internet)
    └── install.bat                 # Installs on the offline machine + desktop shortcut
```

## Dependencies

| Package | Purpose |
|---|---|
| PySide6 | GUI framework |
| numpy | Array math |
| scipy | Grubbs test, curve fitting |
| matplotlib | Plots and PDF export |
| openpyxl | Excel read/write |
| PyInstaller | (build-time only) freezes the app for offline distribution |

## Where settings live

First-run configuration (the default file-browser folder) is stored at:

```
%APPDATA%\XRF-CF-GUI\config.json
```

Delete that file to re-trigger the first-run folder prompt.
