import math
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QLabel, QHeaderView
)
from PySide6.QtGui import QColor, QBrush
from PySide6.QtCore import Qt

from models.project import CalibrationSheet, AnalysisSheet, CF_SOURCE_CALIBRATION
from models.calculations import compute_calibration_sheet, compute_analysis_sheet


_OUTLIER_BG = QBrush(QColor(255, 235, 130))
_OUTLIER_FG = QBrush(QColor(40, 40, 40))


def _fmt(v, decimals=4):
    return f"{v:.{decimals}f}" if not math.isnan(v) else "—"


class ResultsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.project = None
        self.sheet = None

        layout = QVBoxLayout(self)

        self.summary_label = QLabel()
        self.summary_label.setStyleSheet(
            "font-weight: bold; padding: 6px; "
            "background: #eaf2fb; color: #1a1a1a; "
            "border-radius: 4px; border: 1px solid #b6c8df;"
        )
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        self.table = QTableWidget()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)

    def set_context(self, project, sheet):
        self.project = project
        self.sheet = sheet
        self.refresh()

    def refresh(self):
        self.table.clear()
        if self.project is None or self.sheet is None:
            self.summary_label.setText("No sheet selected.")
            self.table.setRowCount(0); self.table.setColumnCount(0)
            return

        if isinstance(self.sheet, CalibrationSheet):
            self._refresh_calibration()
        elif isinstance(self.sheet, AnalysisSheet):
            self._refresh_analysis()

    # ── calibration ───────────────────────────────────────────────────────────
    def _refresh_calibration(self):
        r = compute_calibration_sheet(self.sheet, self.project)
        self.summary_label.setText(
            f"<b>{r.element} on {r.substrate or '—'}</b>  |  "
            f"CF = {_fmt(r.correction_factor)} ± {_fmt(r.cf_uncertainty)}  |  "
            f"σ_CF = {_fmt(r.cf_std)}  |  mean error = {_fmt(r.mean_pct_error, 2)}%  |  "
            f"area = {_fmt(r.area_cm2)} cm²  |  outliers: {len(r.outlier_indices)}"
        )
        cols = ["Sample ID", "Mass Loading (mg/cm²)", "XRF Loading (mg/cm²)",
                "Corr. Factor", "Corr. Loading (mg/cm²)", "% Error"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.setRowCount(len(r.sample_results))
        for i, sr in enumerate(r.sample_results):
            self._set(i, 0, sr.sample_id)
            self._set(i, 1, _fmt(sr.mass_loading))
            self._set(i, 2, _fmt(sr.xrf_loading))
            self._set(i, 3, _fmt(sr.corr_factor))
            self._set(i, 4, _fmt(sr.corrected_loading))
            self._set(i, 5, _fmt(sr.pct_error, 2))
            if sr.is_outlier:
                self._highlight_row(i)

    # ── analysis ──────────────────────────────────────────────────────────────
    def _refresh_analysis(self):
        calib_results = {cs.element: compute_calibration_sheet(cs, self.project)
                         for cs in self.project.calibration_sheets}
        r = compute_analysis_sheet(self.sheet, calib_results, self.project)

        # Determine if active regime differs from reference (all-calibration)
        ecs = self.sheet.element_cf_sources
        has_override = any(ecs.get(el, CF_SOURCE_CALIBRATION) != CF_SOURCE_CALIBRATION
                           for el in self.sheet.elements)

        # ── summary label ──
        active_cf_str = "  ".join(
            f"{el}={_fmt(cf)}" for el, cf in r.correction_factors.items()
        )
        src_notes = []
        for el in self.sheet.elements:
            src = ecs.get(el, CF_SOURCE_CALIBRATION)
            if src == CF_SOURCE_CALIBRATION:
                src_notes.append(f"{el}:calib")
            elif src == "self":
                src_notes.append(f"{el}:self")
            else:
                src_notes.append(f"{el}:custom")
        summary = (
            f"<b>{r.name}</b>  |  "
            f"Active CFs: {active_cf_str}  ({', '.join(src_notes)})  |  "
            f"mean error = {_fmt(r.mean_pct_error, 2)}%"
        )
        if has_override:
            summary += f"  |  Ref. mean error (calib only) = {_fmt(r.ref_mean_pct_error, 2)}%"
        if not math.isnan(r.mean_practical_sc):
            summary += (f"  |  mean prac. SC = {_fmt(r.mean_practical_sc, 2)} ± "
                        f"{_fmt(r.practical_sc_std, 2)} mAh/g")
        if r.cap_correction_factors:
            cap_cf_str = "  ".join(f"{el}={_fmt(cf)}" for el, cf in r.cap_correction_factors.items())
            summary += (f"  |  Cap. CFs: {cap_cf_str}"
                        f"  (cap mean error = {_fmt(r.cap_mean_pct_error, 2)}%)")
        summary += (f"  |  self CF = {_fmt(r.self_cf)}  |  "
                    f"area = {_fmt(r.area_cm2)} cm²  |  outliers: {len(r.outlier_indices)}")
        self.summary_label.setText(summary)

        # ── columns ──
        # Fixed: Sample ID, Mass Loading, Measured Mass
        # Per element: XRF (loading), Corr. (loading), Corr. (mass)
        # Totals: XRF Total, Corr. Total (loading), Corr. Total (mass)
        # Comparison (if has_override): Ref. Total (loading), Ref. Total (mass), Ref. % Error
        # Errors: % Error, σ_corr
        cols = ["Sample ID", "Mass Loading\n(mg/cm²)", "Meas. Mass\n(mg)"]
        for el in self.sheet.elements:
            cols += [f"XRF {el}\n(mg/cm²)", f"Corr. {el}\n(mg/cm²)", f"Corr. {el}\n(mg)"]
        cols += ["XRF Total\n(mg/cm²)", "Corr. Total\n(mg/cm²)", "Corr. Total\n(mg)"]
        if has_override:
            cols += ["Ref. Total\n(mg/cm²)", "Ref. Total\n(mg)", "Ref. % Error"]
        cols += ["% Error", "σ_corr\n(mg/cm²)"]

        # Capacity-regime columns (shown when practical SC data and a capacity CF exist)
        has_cap_regime = (any(not math.isnan(getattr(s, "practical_specific_capacity", float("nan")))
                              for s in self.sheet.samples)
                          and bool(r.cap_correction_factors))
        if has_cap_regime:
            cols += ["Prac. SC\n(mAh/g)"]
            for el in self.sheet.elements:
                cols.append(f"Cap. {el}\n(mg/cm²)")
            cols += ["Cap.-regime\nloading (mg/cm²)", "Cap.-regime\nmass (mg)", "Cap. % Error"]

        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.setRowCount(len(r.sample_results))

        for i, sr in enumerate(r.sample_results):
            col = 0
            self._set(i, col, sr.sample_id);                        col += 1
            self._set(i, col, _fmt(sr.mass_loading));               col += 1
            self._set(i, col, _fmt(sr.measured_mass));              col += 1
            for el in self.sheet.elements:
                self._set(i, col, _fmt(sr.xrf_per_element.get(el, 0)));       col += 1
                self._set(i, col, _fmt(sr.corrected_per_element.get(el, 0))); col += 1
                self._set(i, col, _fmt(sr.corrected_mass_per_element.get(el, 0))); col += 1
            self._set(i, col, _fmt(sr.xrf_total));                 col += 1
            self._set(i, col, _fmt(sr.corrected_total));           col += 1
            self._set(i, col, _fmt(sr.corrected_mass_total));      col += 1
            if has_override:
                self._set(i, col, _fmt(sr.ref_corrected_total));       col += 1
                self._set(i, col, _fmt(sr.ref_corrected_mass_total));  col += 1
                self._set(i, col, _fmt(sr.ref_pct_error, 2));          col += 1
            self._set(i, col, _fmt(sr.pct_error, 2));              col += 1
            self._set(i, col, _fmt(sr.sigma_corrected));           col += 1
            if has_cap_regime:
                psc = getattr(self.sheet.samples[i], "practical_specific_capacity", float("nan"))
                self._set(i, col, _fmt(psc, 2));                           col += 1
                cpe = sr.cap_regime_per_element or {}
                for el in self.sheet.elements:
                    self._set(i, col, _fmt(cpe.get(el, float("nan"))));    col += 1
                self._set(i, col, _fmt(sr.cap_regime_loading));            col += 1
                self._set(i, col, _fmt(sr.cap_regime_mass));               col += 1
                ml_i = sr.mass_loading
                cap_err = (abs(sr.cap_regime_loading - ml_i) / ml_i * 100
                           if ml_i > 0 and not math.isnan(sr.cap_regime_loading) else float("nan"))
                self._set(i, col, _fmt(cap_err, 2));                       col += 1
            if sr.is_outlier:
                self._highlight_row(i)

    # ── helpers ───────────────────────────────────────────────────────────────
    def _set(self, row, col, value):
        item = QTableWidgetItem(str(value))
        item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, col, item)

    def _highlight_row(self, row):
        for c in range(self.table.columnCount()):
            it = self.table.item(row, c)
            if it is not None:
                it.setBackground(_OUTLIER_BG)
                it.setForeground(_OUTLIER_FG)
