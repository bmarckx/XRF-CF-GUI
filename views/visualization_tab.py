import numpy as np
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, QPushButton, QFileDialog

from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT

from models.project import CalibrationSheet, AnalysisSheet
from models.calculations import (
    compute_calibration_sheet, compute_analysis_sheet, fit_correction_factors
)


CALIB_PLOTS = ["CF per sample", "CF vs. Mass Loading", "% Error per sample", "Corrected vs. Measured"]
ANA_PLOTS   = ["% Error per sample", "Corrected vs. Measured", "Element contribution"]


class VisualizationTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.project = None
        self.sheet = None

        layout = QVBoxLayout(self)

        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Plot:"))
        self.plot_combo = QComboBox()
        self.plot_combo.setMinimumWidth(220)
        self.plot_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.plot_combo.currentIndexChanged.connect(self._redraw)
        ctrl.addWidget(self.plot_combo)
        ctrl.addStretch()
        self.save_btn = QPushButton("Save Figure…")
        self.save_btn.clicked.connect(self._save_figure)
        ctrl.addWidget(self.save_btn)
        layout.addLayout(ctrl)

        self.fig = Figure(figsize=(6, 4))
        self.canvas = FigureCanvasQTAgg(self.fig)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas, stretch=1)

    def set_context(self, project, sheet):
        self.project = project
        self.sheet = sheet

        self.plot_combo.blockSignals(True)
        self.plot_combo.clear()
        if isinstance(sheet, CalibrationSheet):
            self.plot_combo.addItems(CALIB_PLOTS)
        elif isinstance(sheet, AnalysisSheet):
            self.plot_combo.addItems(ANA_PLOTS)
        self.plot_combo.blockSignals(False)

        self._redraw()

    def refresh(self):
        self._redraw()

    def _redraw(self):
        self.fig.clear()
        ax = self.fig.add_subplot(111)

        if self.project is None or self.sheet is None or self.plot_combo.count() == 0:
            ax.text(0.5, 0.5, "No sheet selected", ha="center", va="center", transform=ax.transAxes)
            self.canvas.draw()
            return

        choice = self.plot_combo.currentText()

        if isinstance(self.sheet, CalibrationSheet):
            r = compute_calibration_sheet(self.sheet, self.project)
            ids = [sr.sample_id for sr in r.sample_results]
            cfs = [sr.corr_factor for sr in r.sample_results]
            errs = [sr.pct_error for sr in r.sample_results]
            mls = [sr.mass_loading for sr in r.sample_results]
            corr = [sr.corrected_loading for sr in r.sample_results]
            outliers = set(r.outlier_indices)
            colors = ["#d35400" if i in outliers else "#2980b9" for i in range(len(ids))]

            if choice == "CF per sample":
                ax.bar(ids, cfs, color=colors)
                ax.axhline(r.correction_factor, color="k", linestyle="--", label=f"Mean = {r.correction_factor:.4f}")
                ax.fill_between([-0.5, len(ids) - 0.5],
                                r.correction_factor - r.cf_std,
                                r.correction_factor + r.cf_std,
                                alpha=0.15, color="gray", label=f"±σ = {r.cf_std:.4f}")
                ax.set_ylabel("Correction Factor")
                ax.set_title(f"{r.element} on {r.substrate} — Per-Sample CF")
                ax.legend(loc="best")
                y_lo = min(0.9, min(cfs) * 0.98) if cfs else 0.9
                y_hi = max(1.1, max(cfs) * 1.02) if cfs else 1.1
                ax.set_ylim(y_lo, y_hi)
            elif choice == "CF vs. Mass Loading":
                ax.scatter(mls, cfs, c=colors, s=60)
                fit = fit_correction_factors(mls, cfs, "linear")
                if fit:
                    ax.plot(fit.x_fit, fit.y_fit, "r--", label=f"linear, R²={fit.r_squared:.3f}")
                    ax.legend()
                ax.set_xlabel("Mass Loading (mg/cm²)")
                ax.set_ylabel("Correction Factor")
                ax.set_title(f"{r.element} CF vs. Loading")
            elif choice == "% Error per sample":
                ax.bar(ids, errs, color=colors)
                ax.set_ylabel("% Error")
                ax.set_title(f"{r.element} on {r.substrate} — % Error")
            elif choice == "Corrected vs. Measured":
                ax.scatter(mls, corr, c=colors, s=60)
                lo, hi = min(mls + corr), max(mls + corr)
                ax.plot([lo, hi], [lo, hi], "k--", label="y = x")
                ax.set_xlabel("Measured Mass Loading (mg/cm²)")
                ax.set_ylabel("Corrected Loading (mg/cm²)")
                ax.set_title("Parity Plot")
                ax.legend()

        elif isinstance(self.sheet, AnalysisSheet):
            calib_results = {cs.element: compute_calibration_sheet(cs, self.project)
                             for cs in self.project.calibration_sheets}
            r = compute_analysis_sheet(self.sheet, calib_results, self.project)
            ids = [sr.sample_id for sr in r.sample_results]
            mls = [sr.mass_loading for sr in r.sample_results]
            corr = [sr.corrected_total for sr in r.sample_results]
            errs = [sr.pct_error for sr in r.sample_results]
            sigs = [sr.sigma_corrected for sr in r.sample_results]
            outliers = set(r.outlier_indices)
            colors = ["#d35400" if i in outliers else "#27ae60" for i in range(len(ids))]

            if choice == "% Error per sample":
                ax.bar(ids, errs, color=colors)
                ax.set_ylabel("% Error")
                ax.set_title(f"{r.name} — % Error (mean = {r.mean_pct_error:.2f}%)")
            elif choice == "Corrected vs. Measured":
                ax.errorbar(mls, corr, yerr=sigs, fmt="o", color="#2c3e50", ecolor="gray",
                            capsize=3, markersize=7)
                lo, hi = min(mls + corr), max(mls + corr)
                ax.plot([lo, hi], [lo, hi], "k--", label="y = x")
                ax.set_xlabel("Measured Mass Loading (mg/cm²)")
                ax.set_ylabel("Corrected Total (mg/cm²)")
                ax.set_title(f"{r.name} — Parity Plot")
                ax.legend()
            elif choice == "Element contribution":
                bottoms = np.zeros(len(ids))
                cmap = ["#2980b9", "#27ae60", "#8e44ad", "#e67e22", "#c0392b"]
                for ei, el in enumerate(self.sheet.elements):
                    cf = r.correction_factors.get(el, 1.0)
                    contribs = [sr.xrf_per_element.get(el, 0) * cf for sr in r.sample_results]
                    ax.bar(ids, contribs, bottom=bottoms, color=cmap[ei % len(cmap)], label=el)
                    bottoms += np.array(contribs)
                ax.plot(ids, mls, "kx", markersize=10, label="Measured")
                ax.set_ylabel("Corrected Loading (mg/cm²)")
                ax.set_title(f"{r.name} — Element Contribution to Corrected Total")
                ax.legend()

        ax.tick_params(axis="x", rotation=45)
        self.fig.tight_layout()
        self.canvas.draw()

    def _save_figure(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save figure", "", "PNG (*.png);;PDF (*.pdf);;SVG (*.svg)")
        if path:
            self.fig.savefig(path, dpi=200, bbox_inches="tight")
