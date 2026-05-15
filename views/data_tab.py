import math
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QHeaderView, QMessageBox, QDoubleSpinBox, QComboBox, QCheckBox
)
from PySide6.QtCore import Signal, Qt

from models.project import (
    CalibrationSample, AnalysisSample, CalibrationSheet, AnalysisSheet,
    INPUT_MASS, INPUT_LOADING,
)


class DataTab(QWidget):
    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.sheet = None
        self.project = None

        layout = QVBoxLayout(self)

        self.header_label = QLabel("No sheet selected")
        self.header_label.setStyleSheet("font-weight: bold; font-size: 13px; padding: 4px;")
        layout.addWidget(self.header_label)

        # ── per-sheet geometry & input-mode controls ──
        cfg_row = QHBoxLayout()
        self.diam_cb = QCheckBox("Override project diameter:")
        self.diam_spin = QDoubleSpinBox()
        self.diam_spin.setRange(0.01, 100.0); self.diam_spin.setDecimals(4)
        self.diam_spin.setSuffix(" cm")
        self.area_label = QLabel()
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Mass (mg)",          INPUT_MASS)
        self.mode_combo.addItem("Mass Loading (mg/cm²)", INPUT_LOADING)

        cfg_row.addWidget(self.diam_cb)
        cfg_row.addWidget(self.diam_spin)
        cfg_row.addWidget(self.area_label)
        cfg_row.addSpacing(20)
        cfg_row.addWidget(QLabel("Input column:"))
        cfg_row.addWidget(self.mode_combo)
        cfg_row.addStretch()
        layout.addLayout(cfg_row)

        self.diam_cb.toggled.connect(self._on_diam_toggle)
        self.diam_spin.valueChanged.connect(self._on_diam_changed)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)

        # ── data table ──
        self.table = QTableWidget()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("+ Add sample")
        self.btn_remove = QPushButton("− Remove selected")
        self.btn_add.clicked.connect(self._add_row)
        self.btn_remove.clicked.connect(self._remove_row)
        btn_row.addWidget(self.btn_add); btn_row.addWidget(self.btn_remove); btn_row.addStretch()
        layout.addLayout(btn_row)

        self._suppress_signal = False

    # ── public API ───────────────────────────────────────────────────────────
    def set_context(self, project, sheet):
        self.project = project
        self.sheet = sheet
        self._refresh_config_controls()
        self._populate()

    # ── internal helpers ─────────────────────────────────────────────────────
    def _refresh_config_controls(self):
        self._suppress_signal = True
        enabled = self.sheet is not None and self.project is not None
        for w in (self.diam_cb, self.mode_combo):
            w.setEnabled(enabled)

        if not enabled:
            self.diam_cb.setChecked(False)
            self.diam_spin.setEnabled(False)
            self.area_label.setText("")
            self._suppress_signal = False
            return

        # diameter override
        override = self.sheet.diameter_cm is not None
        self.diam_cb.setChecked(override)
        self.diam_spin.setEnabled(override)
        d = self.sheet.effective_diameter(self.project)
        self.diam_spin.setValue(d)
        area = self.sheet.effective_area_cm2(self.project)
        suffix = "  (project default)" if not override else ""
        self.area_label.setText(f"Area: {area:.4f} cm²{suffix}")

        # mode
        idx = 1 if self.sheet.input_mode == INPUT_LOADING else 0
        self.mode_combo.setCurrentIndex(idx)
        self._suppress_signal = False

    def _on_diam_toggle(self, checked):
        if self._suppress_signal or self.sheet is None:
            return
        if checked:
            self.sheet.diameter_cm = self.diam_spin.value()
        else:
            self.sheet.diameter_cm = None
        self._refresh_config_controls()
        self.data_changed.emit()

    def _on_diam_changed(self, value):
        if self._suppress_signal or self.sheet is None or self.sheet.diameter_cm is None:
            return
        self.sheet.diameter_cm = value
        area = self.sheet.effective_area_cm2(self.project)
        self.area_label.setText(f"Area: {area:.4f} cm²")
        self.data_changed.emit()

    def _on_mode_changed(self, idx):
        if self._suppress_signal or self.sheet is None:
            return
        new_mode = self.mode_combo.itemData(idx)
        old_mode = self.sheet.input_mode
        if new_mode == old_mode:
            return

        area = self.sheet.effective_area_cm2(self.project)
        if old_mode == INPUT_MASS and new_mode == INPUT_LOADING:
            factor = 1.0 / area     # mg → mg/cm²
        else:
            factor = area           # mg/cm² → mg

        for s in self.sheet.samples:
            s.mass_mg *= factor
            if hasattr(s, "mass_uncertainty"):
                s.mass_uncertainty *= factor

        self.sheet.input_mode = new_mode
        self._populate()
        self.data_changed.emit()

    def _mass_column_label(self):
        if self.sheet and self.sheet.input_mode == INPUT_LOADING:
            return "Mass Loading (mg/cm²)"
        return "Mass (mg)"

    def _populate(self):
        self._suppress_signal = True
        self.table.clear()
        if self.sheet is None:
            self.table.setRowCount(0); self.table.setColumnCount(0)
            self.header_label.setText("No sheet selected")
            self._suppress_signal = False
            return

        mass_lbl = self._mass_column_label()

        if isinstance(self.sheet, CalibrationSheet):
            self.header_label.setText(
                f"Calibration: {self.sheet.element} on {self.sheet.substrate or '(no substrate)'}"
            )
            unc_lbl = "σ_loading (mg/cm²)" if self.sheet.input_mode == INPUT_LOADING else "σ_mass (mg)"
            cols = ["Sample ID", mass_lbl, "XRF Loading (mg/cm²)", unc_lbl]
            self.table.setColumnCount(len(cols))
            self.table.setHorizontalHeaderLabels(cols)
            self.table.setRowCount(len(self.sheet.samples))
            for r, s in enumerate(self.sheet.samples):
                self._set_cell(r, 0, s.sample_id)
                self._set_cell(r, 1, s.mass_mg)
                self._set_cell(r, 2, s.xrf_loading)
                self._set_cell(r, 3, s.mass_uncertainty)
        elif isinstance(self.sheet, AnalysisSheet):
            self.header_label.setText(
                f"Analysis: {self.sheet.name}   (elements: {', '.join(self.sheet.elements)})"
            )
            cols = ["Sample ID", mass_lbl] + [f"XRF {el} (mg/cm²)" for el in self.sheet.elements] + ["Notes"]
            self.table.setColumnCount(len(cols))
            self.table.setHorizontalHeaderLabels(cols)
            self.table.setRowCount(len(self.sheet.samples))
            for r, s in enumerate(self.sheet.samples):
                self._set_cell(r, 0, s.sample_id)
                self._set_cell(r, 1, s.mass_mg)
                for ei, el in enumerate(self.sheet.elements):
                    self._set_cell(r, 2 + ei, s.xrf_loadings.get(el, ""))
                self._set_cell(r, 2 + len(self.sheet.elements), s.notes)

        self._suppress_signal = False

    def _set_cell(self, row, col, value):
        item = QTableWidgetItem("" if value == "" or value is None else str(value))
        self.table.setItem(row, col, item)

    def _add_row(self):
        if self.sheet is None:
            return
        if isinstance(self.sheet, CalibrationSheet):
            self.sheet.samples.append(CalibrationSample(sample_id="", mass_mg=0.0, xrf_loading=0.0))
        elif isinstance(self.sheet, AnalysisSheet):
            self.sheet.samples.append(AnalysisSample(
                sample_id="", mass_mg=0.0,
                xrf_loadings={el: 0.0 for el in self.sheet.elements},
            ))
        self._populate()
        self.data_changed.emit()

    def _remove_row(self):
        if self.sheet is None:
            return
        rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        for r in rows:
            if 0 <= r < len(self.sheet.samples):
                del self.sheet.samples[r]
        self._populate()
        self.data_changed.emit()

    def _on_item_changed(self, item):
        if self._suppress_signal or self.sheet is None:
            return
        r, c = item.row(), item.column()
        if r >= len(self.sheet.samples):
            return
        s = self.sheet.samples[r]
        text = item.text().strip()
        try:
            if isinstance(self.sheet, CalibrationSheet):
                if   c == 0: s.sample_id = text
                elif c == 1: s.mass_mg = float(text) if text else 0.0
                elif c == 2: s.xrf_loading = float(text) if text else 0.0
                elif c == 3: s.mass_uncertainty = float(text) if text else 0.0
            elif isinstance(self.sheet, AnalysisSheet):
                if   c == 0: s.sample_id = text
                elif c == 1: s.mass_mg = float(text) if text else 0.0
                elif c < 2 + len(self.sheet.elements):
                    s.xrf_loadings[self.sheet.elements[c - 2]] = float(text) if text else 0.0
                else:
                    s.notes = text
        except ValueError:
            QMessageBox.warning(self, "Invalid input", f"Could not parse '{text}' as a number.")
            self._populate()
            return
        self.data_changed.emit()
