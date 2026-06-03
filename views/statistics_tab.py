import math
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QComboBox, QGroupBox, QFormLayout
)
from PySide6.QtCore import Qt

from models.project import CalibrationSheet, AnalysisSheet, CF_SOURCE_CALIBRATION
from models.calculations import (
    compute_calibration_sheet, compute_analysis_sheet,
    descriptive_stats, fit_correction_factors,
)


class StatisticsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.project = None
        self.sheet = None
        self._last_fit = None

        layout = QVBoxLayout(self)

        stat_grp = QGroupBox("Descriptive Statistics")
        stat_l   = QVBoxLayout(stat_grp)
        self.stat_table = QTableWidget()
        self.stat_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.stat_table.setEditTriggers(QTableWidget.NoEditTriggers)
        stat_l.addWidget(self.stat_table)
        layout.addWidget(stat_grp)

        out_grp = QGroupBox("Outliers (Grubbs test, α = 0.05)")
        out_l   = QVBoxLayout(out_grp)
        self.out_label = QLabel("—")
        out_l.addWidget(self.out_label)
        layout.addWidget(out_grp)

        unc_grp = QGroupBox("Uncertainty Budget")
        unc_l   = QVBoxLayout(unc_grp)
        self.unc_label = QLabel("—")
        self.unc_label.setWordWrap(True)
        unc_l.addWidget(self.unc_label)
        layout.addWidget(unc_grp)

        self.fit_grp = QGroupBox("Curve Fit")
        fit_l   = QVBoxLayout(self.fit_grp)
        ctrl    = QHBoxLayout()
        self.model_combo = QComboBox()
        self.model_combo.addItems(["linear", "quadratic"])
        self.fit_btn = QPushButton("Run Fit")
        self.fit_btn.clicked.connect(self._run_fit)
        ctrl.addWidget(QLabel("Model:")); ctrl.addWidget(self.model_combo)
        ctrl.addWidget(self.fit_btn); ctrl.addStretch()
        fit_l.addLayout(ctrl)
        self.fit_label = QLabel("Run a fit to see results.")
        self.fit_label.setWordWrap(True)
        fit_l.addWidget(self.fit_label)
        layout.addWidget(self.fit_grp)

        layout.addStretch()

    def set_context(self, project, sheet):
        self.project = project
        self.sheet = sheet
        self._last_fit = None
        self.refresh()

    @property
    def last_fit(self):
        return self._last_fit

    def refresh(self):
        has_sheet = self.project is not None and self.sheet is not None
        self.fit_btn.setEnabled(has_sheet)
        is_calib = isinstance(self.sheet, CalibrationSheet)
        self.fit_grp.setTitle("Curve Fit (CF vs. Mass Loading)" if is_calib
                              else "Curve Fit (% Error vs. Mass Loading)")

        if not has_sheet:
            self.stat_table.setRowCount(0); self.stat_table.setColumnCount(0)
            self.out_label.setText("—")
            self.unc_label.setText("—")
            self.fit_label.setText("Run a fit to see results.")
            return

        if is_calib:
            r = compute_calibration_sheet(self.sheet, self.project)
            cfs  = [sr.corr_factor   for sr in r.sample_results]
            errs = [sr.pct_error     for sr in r.sample_results]
            mlds = [sr.mass_loading  for sr in r.sample_results]

            self._populate_stat_table({
                "Correction factor": descriptive_stats(cfs),
                "% Error":           descriptive_stats(errs),
                "Mass loading":      descriptive_stats(mlds),
            })

            if r.outlier_indices:
                ids = [r.sample_results[i].sample_id for i in r.outlier_indices]
                self.out_label.setText(f"Flagged: {', '.join(ids)}")
            else:
                self.out_label.setText("No outliers detected.")

            self.unc_label.setText(
                f"CF = {r.correction_factor:.4f} ± {r.cf_uncertainty:.4f}  (1σ standard error)<br>"
                f"σ<sub>CF</sub> (sample std) = {r.cf_std:.4f}  |  n = {len(cfs)}"
            )
        else:
            calib_results = {cs.element: compute_calibration_sheet(cs, self.project)
                             for cs in self.project.calibration_sheets}
            r = compute_analysis_sheet(self.sheet, calib_results, self.project)

            errs      = [sr.pct_error        for sr in r.sample_results]
            ref_errs  = [sr.ref_pct_error     for sr in r.sample_results]
            corrs     = [sr.corrected_total   for sr in r.sample_results]
            masses    = [sr.corrected_mass_total for sr in r.sample_results]
            sigs      = [sr.sigma_corrected   for sr in r.sample_results]
            self_cfs  = [sr.self_cf for sr in r.sample_results
                         if not math.isnan(sr.self_cf)]

            ecs = self.sheet.element_cf_sources
            has_override = any(ecs.get(el, CF_SOURCE_CALIBRATION) != CF_SOURCE_CALIBRATION
                               for el in self.sheet.elements)

            stat_blocks = {
                "% Error (active)":      descriptive_stats(errs),
                "Corrected total load.": descriptive_stats(corrs),
                "Corrected total mass":  descriptive_stats(masses),
                "σ_corrected":           descriptive_stats(sigs),
            }
            if has_override:
                stat_blocks["% Error (ref. calib)"] = descriptive_stats(ref_errs)
            if self_cfs:
                stat_blocks["Self CF (per sample)"] = descriptive_stats(self_cfs)

            prac_scs = [getattr(self.sheet.samples[j], "practical_specific_capacity", float("nan"))
                        for j in range(len(r.sample_results))]
            prac_scs = [v for v in prac_scs if not math.isnan(v)]
            cap_loadings = [sr.cap_regime_loading for sr in r.sample_results
                            if not math.isnan(sr.cap_regime_loading)]
            if prac_scs:
                stat_blocks["Practical SC (mAh/g)"]       = descriptive_stats(prac_scs)
            if cap_loadings:
                stat_blocks["Cap.-regime loading (mg/cm²)"] = descriptive_stats(cap_loadings)

            self._populate_stat_table(stat_blocks)

            if r.outlier_indices:
                ids = [r.sample_results[i].sample_id for i in r.outlier_indices]
                self.out_label.setText(f"Flagged: {', '.join(ids)}")
            else:
                self.out_label.setText("No outliers detected.")

            # Uncertainty budget
            unc_lines = []
            for el in self.sheet.elements:
                src = ecs.get(el, CF_SOURCE_CALIBRATION)
                active_cf = r.correction_factors.get(el, float("nan"))
                ref_cf    = r.ref_correction_factors.get(el, float("nan"))
                cr = calib_results.get(el)
                if src == CF_SOURCE_CALIBRATION and cr is not None:
                    unc_lines.append(
                        f"{el} [calib]: CF = {active_cf:.4f} ± {cr.cf_uncertainty:.4f}"
                    )
                elif src == "self":
                    unc_lines.append(
                        f"{el} [self]: CF = {active_cf:.4f}  "
                        f"(self CF = {r.self_cf:.4f} ± {r.self_cf_uncertainty:.4f})"
                    )
                else:
                    unc_lines.append(f"{el} [custom]: CF = {active_cf:.4f}  |  ref calib CF = {ref_cf:.4f}")
            if not math.isnan(r.self_cf):
                unc_lines.append(
                    f"<br>Sheet self CF = {r.self_cf:.4f} ± {r.self_cf_uncertainty:.4f}  "
                    f"(σ = {r.self_cf_std:.4f})"
                )
            if sigs:
                unc_lines.append(
                    f"Mean σ_corrected = {sum(sigs)/len(sigs):.4f} mg/cm²  "
                    f"(CF uncertainty + 2% XRF reading)"
                )
            self.unc_label.setText("<br>".join(unc_lines))

    def _populate_stat_table(self, blocks: dict):
        cols = ["Metric", "n", "Mean", "Std", "Min", "Max", "Median", "CV%"]
        self.stat_table.setColumnCount(len(cols))
        self.stat_table.setHorizontalHeaderLabels(cols)
        self.stat_table.setRowCount(len(blocks))
        for r, (name, s) in enumerate(blocks.items()):
            if not s:
                self._cell(r, 0, name)
                for c in range(1, len(cols)):
                    self._cell(r, c, "—")
                continue
            self._cell(r, 0, name)
            self._cell(r, 1, str(s["n"]))
            self._cell(r, 2, f"{s['mean']:.4f}")
            self._cell(r, 3, f"{s['std']:.4f}")
            self._cell(r, 4, f"{s['min']:.4f}")
            self._cell(r, 5, f"{s['max']:.4f}")
            self._cell(r, 6, f"{s['median']:.4f}")
            self._cell(r, 7, f"{s['cv_pct']:.2f}")

    def _cell(self, row, col, value):
        item = QTableWidgetItem(value)
        item.setTextAlignment(Qt.AlignCenter)
        self.stat_table.setItem(row, col, item)

    def _run_fit(self):
        if self.project is None or self.sheet is None:
            return

        if isinstance(self.sheet, CalibrationSheet):
            r = compute_calibration_sheet(self.sheet, self.project)
            xs = [sr.mass_loading for sr in r.sample_results]
            ys = [sr.corr_factor  for sr in r.sample_results]
            y_name = "CF"
        else:
            calib_results = {cs.element: compute_calibration_sheet(cs, self.project)
                             for cs in self.project.calibration_sheets}
            r = compute_analysis_sheet(self.sheet, calib_results, self.project)
            xs = [sr.mass_loading for sr in r.sample_results]
            ys = [sr.pct_error    for sr in r.sample_results]
            y_name = "% Error"

        fit = fit_correction_factors(xs, ys, self.model_combo.currentText())
        self._last_fit = fit
        if fit is None:
            self.fit_label.setText("Fit failed (need ≥ 2 samples).")
            return
        params_str = ", ".join(
            f"{p:.4g} ± {e:.2g}" for p, e in zip(fit.params, fit.param_errors)
        )
        self.fit_label.setText(
            f"<b>{y_name}</b> vs. Mass Loading — model: <b>{fit.model}</b>  |  "
            f"R² = {fit.r_squared:.4f}<br>Parameters: {params_str}"
        )
