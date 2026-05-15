from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QLabel, QHeaderView
)
from PySide6.QtGui import QColor, QBrush
from PySide6.QtCore import Qt

from models.project import CalibrationSheet, AnalysisSheet
from models.calculations import compute_calibration_sheet, compute_analysis_sheet


_OUTLIER_BG = QBrush(QColor(255, 235, 130))
_OUTLIER_FG = QBrush(QColor(40, 40, 40))


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
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
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
            r = compute_calibration_sheet(self.sheet, self.project)
            self.summary_label.setText(
                f"<b>{r.element} on {r.substrate or '—'}</b>  |  "
                f"CF = {r.correction_factor:.4f} ± {r.cf_uncertainty:.4f}  |  "
                f"σ_CF = {r.cf_std:.4f}  |  mean error = {r.mean_pct_error:.2f}%  |  "
                f"area = {r.area_cm2:.4f} cm²  |  "
                f"outliers: {len(r.outlier_indices)}"
            )
            cols = ["Sample ID", "Mass Loading (mg/cm²)", "XRF Loading (mg/cm²)",
                    "Corr. Factor", "Corr. Loading (mg/cm²)", "% Error"]
            self.table.setColumnCount(len(cols))
            self.table.setHorizontalHeaderLabels(cols)
            self.table.setRowCount(len(r.sample_results))
            for i, sr in enumerate(r.sample_results):
                self._set(i, 0, sr.sample_id)
                self._set(i, 1, f"{sr.mass_loading:.4f}")
                self._set(i, 2, f"{sr.xrf_loading:.4f}")
                self._set(i, 3, f"{sr.corr_factor:.4f}")
                self._set(i, 4, f"{sr.corrected_loading:.4f}")
                self._set(i, 5, f"{sr.pct_error:.2f}")
                if sr.is_outlier:
                    self._highlight_row(i)

        elif isinstance(self.sheet, AnalysisSheet):
            calib_results = {cs.element: compute_calibration_sheet(cs, self.project)
                             for cs in self.project.calibration_sheets}
            r = compute_analysis_sheet(self.sheet, calib_results, self.project)
            cf_str = ", ".join(f"{el}={cf:.4f}" for el, cf in r.correction_factors.items())
            self.summary_label.setText(
                f"<b>{r.name}</b>  |  CFs: {cf_str}  |  "
                f"mean error = {r.mean_pct_error:.2f}%  |  "
                f"area = {r.area_cm2:.4f} cm²  |  "
                f"outliers: {len(r.outlier_indices)}"
            )
            cols = ["Sample ID", "Mass Loading (mg/cm²)"] + \
                   [f"XRF {el}" for el in self.sheet.elements] + \
                   ["XRF Total", "Corr. Total", "% Error", "σ_corr"]
            self.table.setColumnCount(len(cols))
            self.table.setHorizontalHeaderLabels(cols)
            self.table.setRowCount(len(r.sample_results))
            for i, sr in enumerate(r.sample_results):
                self._set(i, 0, sr.sample_id)
                self._set(i, 1, f"{sr.mass_loading:.4f}")
                for ei, el in enumerate(self.sheet.elements):
                    self._set(i, 2 + ei, f"{sr.xrf_per_element.get(el, 0):.4f}")
                base = 2 + len(self.sheet.elements)
                self._set(i, base + 0, f"{sr.xrf_total:.4f}")
                self._set(i, base + 1, f"{sr.corrected_total:.4f}")
                self._set(i, base + 2, f"{sr.pct_error:.2f}")
                self._set(i, base + 3, f"{sr.sigma_corrected:.4f}")
                if sr.is_outlier:
                    self._highlight_row(i)

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
