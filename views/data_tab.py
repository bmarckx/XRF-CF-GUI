import math
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QHeaderView, QMessageBox, QDoubleSpinBox, QComboBox,
    QCheckBox, QGroupBox, QGridLayout, QFrame, QSizePolicy, QInputDialog,
)
from PySide6.QtCore import Signal, Qt, QTimer

from models.project import (
    CalibrationSample, AnalysisSample, CalibrationSheet, AnalysisSheet,
    INPUT_MASS, INPUT_LOADING, CF_SOURCE_CALIBRATION, CF_SOURCE_SELF,
)
from models.calculations import compute_calibration_sheet, compute_analysis_sheet
from views.diameter_input import DiameterInput


class DataTab(QWidget):
    data_changed    = Signal()
    samples_moved   = Signal()   # emitted after samples move to another sheet

    def __init__(self, parent=None):
        super().__init__(parent)
        self.sheet = None
        self.project = None
        self._suppress_signal = False
        self._cf_row_widgets = []   # (combo, spin, calib_lbl, self_lbl) per element row

        layout = QVBoxLayout(self)

        self.header_label = QLabel("No sheet selected")
        self.header_label.setStyleSheet("font-weight: bold; font-size: 13px; padding: 4px;")
        layout.addWidget(self.header_label)

        # ── geometry & input-mode controls ──
        cfg_row = QHBoxLayout()
        self.diam_cb = QCheckBox("Override project diameter:")
        self.diam_input = DiameterInput()
        self.area_label = QLabel()
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Mass (mg)",             INPUT_MASS)
        self.mode_combo.addItem("Mass Loading (mg/cm²)", INPUT_LOADING)

        cfg_row.addWidget(self.diam_cb)
        cfg_row.addWidget(self.diam_input)
        cfg_row.addWidget(self.area_label)
        cfg_row.addSpacing(20)
        cfg_row.addWidget(QLabel("Input column:"))
        cfg_row.addWidget(self.mode_combo)
        cfg_row.addStretch()
        layout.addLayout(cfg_row)

        self.diam_cb.toggled.connect(self._on_diam_toggle)
        self.diam_input.value_changed.connect(self._on_diam_changed)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)

        # ── per-element CF configuration (analysis sheets only) ──
        self.cf_group = QGroupBox("Correction Factor Configuration")
        self.cf_group.setVisible(False)
        cf_outer = QVBoxLayout(self.cf_group)

        # Header row
        cf_hdr = QGridLayout()
        for col, txt in enumerate(["Element", "Source", "Calib CF", "Self CF", "Custom value"]):
            lbl = QLabel(f"<b>{txt}</b>")
            lbl.setAlignment(Qt.AlignCenter)
            cf_hdr.addWidget(lbl, 0, col)
        cf_outer.addLayout(cf_hdr)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine); sep.setFrameShadow(QFrame.Sunken)
        cf_outer.addWidget(sep)

        self.cf_grid = QGridLayout()
        cf_outer.addLayout(self.cf_grid)
        layout.addWidget(self.cf_group)

        # ── per-element capacity configuration (analysis sheets only) ──
        self.cap_group = QGroupBox("Capacity Configuration")
        self.cap_group.setVisible(False)
        cap_outer = QVBoxLayout(self.cap_group)

        # Per-element header
        cap_hdr = QGridLayout()
        for col, txt in enumerate(["Element", "Active", "Expected SC (mAh/g)"]):
            lbl = QLabel(f"<b>{txt}</b>"); lbl.setAlignment(Qt.AlignCenter)
            cap_hdr.addWidget(lbl, 0, col)
        cap_outer.addLayout(cap_hdr)

        self.cap_grid = QGridLayout()
        cap_outer.addLayout(self.cap_grid)
        layout.addWidget(self.cap_group)

        self._cap_row_widgets = []   # (checkbox, exp_spinbox) per element row
        self._suppress_cap = False

        # ── data table ──
        self.table = QTableWidget()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        self.btn_add    = QPushButton("+ Add sample")
        self.btn_remove = QPushButton("− Remove selected")
        self.btn_move   = QPushButton("Move selected to…")
        self.btn_add.clicked.connect(self._add_row)
        self.btn_remove.clicked.connect(self._remove_row)
        self.btn_move.clicked.connect(self._move_rows)
        btn_row.addWidget(self.btn_add); btn_row.addWidget(self.btn_remove)
        btn_row.addWidget(self.btn_move); btn_row.addStretch()
        layout.addLayout(btn_row)

    # ── public API ───────────────────────────────────────────────────────────
    def set_context(self, project, sheet):
        self.project = project
        self.sheet = sheet
        self._refresh_config_controls()
        self._rebuild_cf_panel()
        self._rebuild_cap_panel()
        self._populate()

    # ── geometry / mode controls ─────────────────────────────────────────────
    def _refresh_config_controls(self):
        self._suppress_signal = True
        enabled = self.sheet is not None and self.project is not None
        for w in (self.diam_cb, self.mode_combo):
            w.setEnabled(enabled)

        if not enabled:
            self.diam_cb.setChecked(False)
            self.diam_input.setEnabled(False)
            self.area_label.setText("")
            self._suppress_signal = False
            return

        override = self.sheet.diameter_cm is not None
        self.diam_cb.setChecked(override)
        self.diam_input.setEnabled(override)
        d = self.sheet.effective_diameter(self.project)
        self.diam_input.set_value_cm(d)
        area = self.sheet.effective_area_cm2(self.project)
        suffix = "  (project default)" if not override else ""
        self.area_label.setText(f"Area: {area:.4f} cm²{suffix}")

        idx = 1 if self.sheet.input_mode == INPUT_LOADING else 0
        self.mode_combo.setCurrentIndex(idx)
        self._suppress_signal = False

    def _on_diam_toggle(self, checked):
        if self._suppress_signal or self.sheet is None:
            return
        if checked:
            d = self.diam_input.value_cm()
            self.sheet.diameter_cm = d if d is not None else self.project.diameter_cm
        else:
            self.sheet.diameter_cm = None
        self._refresh_config_controls()
        self.data_changed.emit()

    def _on_diam_changed(self):
        if self._suppress_signal or self.sheet is None or self.sheet.diameter_cm is None:
            return
        d = self.diam_input.value_cm()
        if d is None:
            return
        self.sheet.diameter_cm = d
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
        factor = 1.0 / area if old_mode == INPUT_MASS else area
        for s in self.sheet.samples:
            s.mass_mg *= factor
            if hasattr(s, "mass_uncertainty"):
                s.mass_uncertainty *= factor

        self.sheet.input_mode = new_mode
        self._populate()
        self.data_changed.emit()

    # ── per-element CF panel ──────────────────────────────────────────────────
    def _rebuild_cf_panel(self):
        # Always defer so the method is safe to call from within signal handlers
        # (deleting a widget that is currently emitting a signal is unsafe).
        QTimer.singleShot(0, self._do_rebuild_cf_panel)

    def _do_rebuild_cf_panel(self):
        """Recreate the per-element CF configuration rows."""
        # Remove old rows
        self._suppress_signal = True
        for combo, spin, cl, sl in self._cf_row_widgets:
            for w in (combo, spin, cl, sl):
                self.cf_grid.removeWidget(w)
                w.deleteLater()
        self._cf_row_widgets = []

        is_analysis = isinstance(self.sheet, AnalysisSheet) and self.project is not None
        self.cf_group.setVisible(is_analysis)
        if not is_analysis:
            self._suppress_signal = False
            return

        # Compute current CFs for reference display
        calib_results = {cs.element: compute_calibration_sheet(cs, self.project)
                         for cs in self.project.calibration_sheets}
        r = compute_analysis_sheet(self.sheet, calib_results, self.project)

        element_cf_sources = self.sheet.element_cf_sources

        for row_i, el in enumerate(self.sheet.elements):
            src = element_cf_sources.get(el, CF_SOURCE_CALIBRATION)

            el_lbl = QLabel(f"<b>{el}</b>")
            el_lbl.setAlignment(Qt.AlignCenter)
            self.cf_grid.addWidget(el_lbl, row_i, 0)

            combo = QComboBox()
            combo.addItem("Calibration", CF_SOURCE_CALIBRATION)
            combo.addItem("Self",        CF_SOURCE_SELF)
            combo.addItem("Custom",      "custom")
            if src == CF_SOURCE_CALIBRATION:
                combo.setCurrentIndex(0)
            elif src == CF_SOURCE_SELF:
                combo.setCurrentIndex(1)
            else:
                combo.setCurrentIndex(2)
            combo.setProperty("element", el)
            combo.currentIndexChanged.connect(self._on_element_cf_source_changed)
            self.cf_grid.addWidget(combo, row_i, 1)

            calib_cf = r.ref_correction_factors.get(el, float("nan"))
            calib_lbl = QLabel(f"{calib_cf:.4f}" if not math.isnan(calib_cf) else "N/A")
            calib_lbl.setAlignment(Qt.AlignCenter)
            self.cf_grid.addWidget(calib_lbl, row_i, 2)

            self_cf = r.self_cf
            self_lbl = QLabel(f"{self_cf:.4f}" if not math.isnan(self_cf) else "N/A")
            self_lbl.setAlignment(Qt.AlignCenter)
            self.cf_grid.addWidget(self_lbl, row_i, 3)

            spin = QDoubleSpinBox()
            spin.setRange(0.0001, 1000.0); spin.setDecimals(4)
            spin.setEnabled(src not in (CF_SOURCE_CALIBRATION, CF_SOURCE_SELF))
            if src not in (CF_SOURCE_CALIBRATION, CF_SOURCE_SELF):
                try:
                    spin.setValue(float(src))
                except (ValueError, TypeError):
                    spin.setValue(1.0)
            else:
                spin.setValue(1.0)
            spin.setProperty("element", el)
            spin.valueChanged.connect(self._on_element_cf_custom_changed)
            self.cf_grid.addWidget(spin, row_i, 4)

            self._cf_row_widgets.append((combo, spin, calib_lbl, self_lbl))

        self._suppress_signal = False

    def _on_element_cf_source_changed(self, _idx):
        if self._suppress_signal or not isinstance(self.sheet, AnalysisSheet):
            return
        combo = self.sender()
        el = combo.property("element")
        src = combo.currentData()
        row_i = self.sheet.elements.index(el)
        _, spin, _, _ = self._cf_row_widgets[row_i]

        if src == "custom":
            spin.setEnabled(True)
            self.sheet.element_cf_sources[el] = str(spin.value())
        else:
            spin.setEnabled(False)
            self.sheet.element_cf_sources[el] = src

        self.data_changed.emit()

    def _on_element_cf_custom_changed(self, value):
        if self._suppress_signal or not isinstance(self.sheet, AnalysisSheet):
            return
        spin = self.sender()
        el = spin.property("element")
        row_i = self.sheet.elements.index(el)
        combo, _, _, _ = self._cf_row_widgets[row_i]
        if combo.currentData() == "custom":
            self.sheet.element_cf_sources[el] = str(value)
            self.data_changed.emit()

    # ── capacity configuration panel ─────────────────────────────────────────
    def _rebuild_cap_panel(self):
        is_analysis = isinstance(self.sheet, AnalysisSheet) and self.project is not None
        self.cap_group.setVisible(is_analysis)
        if not is_analysis:
            return

        self._suppress_cap = True

        # Clear old element rows — _cap_row_widgets is list of (cb, exp_sp)
        for widgets in self._cap_row_widgets:
            for w in widgets:
                self.cap_grid.removeWidget(w); w.deleteLater()
        self._cap_row_widgets = []

        esc = self.sheet.element_specific_capacities

        for row_i, el in enumerate(self.sheet.elements):
            el_lbl = QLabel(f"<b>{el}</b>"); el_lbl.setAlignment(Qt.AlignCenter)
            self.cap_grid.addWidget(el_lbl, row_i, 0)

            active = el in esc
            cb = QCheckBox()
            cb.setChecked(active)
            cb.setProperty("element", el)
            cb.stateChanged.connect(self._on_cap_active_changed)
            self.cap_grid.addWidget(cb, row_i, 1)

            exp_sp = QDoubleSpinBox()
            exp_sp.setRange(0.0, 100000.0); exp_sp.setDecimals(2); exp_sp.setSuffix(" mAh/g")
            exp_sp.setEnabled(active)
            exp_sp.setValue(esc.get(el, 0.0) or 0.0)
            exp_sp.setProperty("element", el)
            exp_sp.valueChanged.connect(self._on_cap_sc_changed)
            self.cap_grid.addWidget(exp_sp, row_i, 2)

            self._cap_row_widgets.append((cb, exp_sp))

        self._suppress_cap = False

    def _on_cap_active_changed(self, _state):
        if self._suppress_cap or not isinstance(self.sheet, AnalysisSheet):
            return
        cb = self.sender()
        el = cb.property("element")
        row_i = self.sheet.elements.index(el)
        _, exp_sp = self._cap_row_widgets[row_i]
        if cb.isChecked():
            exp_sp.setEnabled(True)
            if exp_sp.value() > 0:
                self.sheet.element_specific_capacities[el] = exp_sp.value()
        else:
            exp_sp.setEnabled(False)
            self.sheet.element_specific_capacities.pop(el, None)
        # Active set changed → the "Mass utilized" column depends on it; repopulate.
        self._populate()
        self.data_changed.emit()

    def _on_cap_sc_changed(self, value):
        if self._suppress_cap or not isinstance(self.sheet, AnalysisSheet):
            return
        sp = self.sender()
        el = sp.property("element")
        row_i = self.sheet.elements.index(el)
        cb, _ = self._cap_row_widgets[row_i]
        if cb.isChecked():
            if value > 0:
                self.sheet.element_specific_capacities[el] = value
            else:
                self.sheet.element_specific_capacities.pop(el, None)
            self.data_changed.emit()

    # ── data table ────────────────────────────────────────────────────────────
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
            cols = ["Sample ID", mass_lbl, "XRF Loading (mg/cm²)", unc_lbl, "Excl."]
            self.table.setColumnCount(len(cols))
            self.table.setHorizontalHeaderLabels(cols)
            self.table.setRowCount(len(self.sheet.samples))
            for r, s in enumerate(self.sheet.samples):
                self._set_cell(r, 0, s.sample_id)
                self._set_cell(r, 1, s.mass_mg)
                self._set_cell(r, 2, s.xrf_loading)
                self._set_cell(r, 3, s.mass_uncertainty)
                self._set_excl_cell(r, 4, getattr(s, "is_excluded", False))
        elif isinstance(self.sheet, AnalysisSheet):
            self.header_label.setText(
                f"Analysis: {self.sheet.name}   (elements: {', '.join(self.sheet.elements)})"
            )
            n_el = len(self.sheet.elements)
            cols = (["Sample ID", mass_lbl]
                    + [f"XRF {el} (mg/cm²)" for el in self.sheet.elements]
                    + ["Practical SC (mAh/g)", "Cap basis", "Mass utilized (mg/cm²)",
                       "Notes", "Excl."])
            self.table.setColumnCount(len(cols))
            self.table.setHorizontalHeaderLabels(cols)
            self.table.setRowCount(len(self.sheet.samples))
            for r, s in enumerate(self.sheet.samples):
                self._set_cell(r, 0, s.sample_id)
                self._set_cell(r, 1, s.mass_mg)
                for ei, el in enumerate(self.sheet.elements):
                    self._set_cell(r, 2 + ei, s.xrf_loadings.get(el, ""))
                prac = getattr(s, "practical_specific_capacity", float("nan"))
                self._set_cell(r, 2 + n_el, "" if math.isnan(prac) else prac)
                self._set_basis_combo(r, 3 + n_el, getattr(s, "cap_mass_basis", "measured"))
                mu = self._active_utilized(s)
                self._set_cell(r, 4 + n_el, "" if not mu else round(mu, 6))
                self._set_cell(r, 5 + n_el, s.notes)
                self._set_excl_cell(r, 6 + n_el, getattr(s, "is_excluded", False))

        self._suppress_signal = False

    def _set_cell(self, row, col, value):
        item = QTableWidgetItem("" if value == "" or value is None else str(value))
        self.table.setItem(row, col, item)

    def _set_excl_cell(self, row, col, excluded: bool):
        item = QTableWidgetItem()
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked if excluded else Qt.Unchecked)
        self.table.setItem(row, col, item)

    def _set_basis_combo(self, row, col, current):
        combo = QComboBox()
        combo.addItems(["measured", "calibration", "self", "active", "custom"])
        idx = combo.findText(current if current in
                             ("measured", "calibration", "self", "active", "custom") else "measured")
        combo.setCurrentIndex(max(0, idx))
        combo.setProperty("row", row)
        combo.currentTextChanged.connect(self._on_cap_basis_changed)
        self.table.setCellWidget(row, col, combo)

    def _basis_loadings_for(self, basis):
        """Per-sample, per-element loadings for the given basis regime (for snapshotting)."""
        try:
            calib = {cs.element: compute_calibration_sheet(cs, self.project)
                     for cs in self.project.calibration_sheets}
            r = compute_analysis_sheet(self.sheet, calib, self.project)
        except Exception:
            return None
        rows = []
        for j, sr in enumerate(r.sample_results):
            s = self.sheet.samples[j]
            per_el = {}
            for el in self.sheet.elements:
                xrf_el = s.xrf_loadings.get(el, 0.0)
                if   basis == "calibration":
                    cf = r.ref_correction_factors.get(el, 1.0)
                    per_el[el] = xrf_el * (cf if not math.isnan(cf) else 1.0)
                elif basis == "self":
                    per_el[el] = xrf_el * (r.self_cf if not math.isnan(r.self_cf) else 1.0)
                elif basis == "active":
                    per_el[el] = (sr.corrected_per_element or {}).get(el, 0.0)
                else:  # measured: split whole-electrode measured by XRF proportion
                    per_el[el] = sr.mass_loading * (xrf_el / sr.xrf_total) if sr.xrf_total > 0 else 0.0
            rows.append(per_el)
        return rows

    def _on_cap_basis_changed(self, basis):
        if self._suppress_signal or not isinstance(self.sheet, AnalysisSheet):
            return
        combo = self.sender()
        row = combo.property("row")
        if row is None or row >= len(self.sheet.samples):
            return
        s = self.sheet.samples[row]
        s.cap_mass_basis = basis
        if basis != "custom":
            snaps = self._basis_loadings_for(basis)
            if snaps and row < len(snaps):
                s.cap_frozen_loadings = dict(snaps[row])    # freeze per-element loadings
        self._populate()
        self.data_changed.emit()

    def _active_utilized(self, s):
        """Active-only pre-scale sum from a sample's frozen loadings (the 'mass utilized')."""
        frozen = getattr(s, "cap_frozen_loadings", None) or {}
        esc = self.sheet.element_specific_capacities
        active = [el for el in self.sheet.elements if el in esc]
        return sum(float(frozen.get(el, 0.0)) for el in active)

    def _set_active_utilized(self, s, target):
        """Set the active 'mass utilized' total by scaling the active frozen loadings to match.

        Inactive frozen loadings are left untouched. Sets basis to 'custom'.
        """
        row = self.sheet.samples.index(s)
        frozen = dict(getattr(s, "cap_frozen_loadings", None) or {})
        if not frozen:
            snaps = self._basis_loadings_for(getattr(s, "cap_mass_basis", "measured"))
            if snaps and row < len(snaps):
                frozen = dict(snaps[row])
        esc = self.sheet.element_specific_capacities
        active = [el for el in self.sheet.elements if el in esc]
        cur = sum(float(frozen.get(el, 0.0)) for el in active)
        if math.isnan(target):
            # clear → revert to live basis
            s.cap_frozen_loadings = {}
            return
        if cur > 0:
            scale = target / cur
            for el in active:
                frozen[el] = float(frozen.get(el, 0.0)) * scale
        elif active:
            for el in active:
                frozen[el] = target / len(active)
        s.cap_frozen_loadings = frozen
        s.cap_mass_basis = "custom"

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

    # ── move samples to another sheet ─────────────────────────────────────────
    def _candidate_targets(self):
        """Sheets of the same type as the current one, excluding it."""
        if self.project is None or self.sheet is None:
            return []
        if isinstance(self.sheet, CalibrationSheet):
            pool = self.project.calibration_sheets
        else:
            pool = self.project.analysis_sheets
        return [s for s in pool if s is not self.sheet]

    @staticmethod
    def _sheet_label(sheet):
        if isinstance(sheet, CalibrationSheet):
            return f"{sheet.element} on {sheet.substrate}" if sheet.substrate else sheet.element
        return sheet.name

    def _move_rows(self):
        if self.sheet is None:
            return
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        rows = [r for r in rows if 0 <= r < len(self.sheet.samples)]
        if not rows:
            QMessageBox.information(self, "Move samples", "Select one or more sample rows first.")
            return

        targets = self._candidate_targets()
        if not targets:
            QMessageBox.information(
                self, "Move samples",
                "There is no other sheet of the same type to move samples to.")
            return

        labels = [self._sheet_label(t) for t in targets]
        choice, ok = QInputDialog.getItem(
            self, "Move samples",
            f"Move {len(rows)} sample(s) to:", labels, 0, False)
        if not ok:
            return
        target = targets[labels.index(choice)]

        for r in rows:
            self.sheet.samples[r] = self._adapt_sample(self.sheet.samples[r], target)
        # collect moved samples, then remove from source (reverse order)
        moved = [self.sheet.samples[r] for r in rows]
        for r in sorted(rows, reverse=True):
            del self.sheet.samples[r]
        target.samples.extend(moved)

        self._populate()
        self.data_changed.emit()
        self.samples_moved.emit()

    def _adapt_sample(self, sample, target):
        """Return a sample compatible with `target`'s type/elements (no-op if already so)."""
        # Calibration → Calibration, or Analysis → Analysis with element remapping.
        if isinstance(target, AnalysisSheet) and isinstance(sample, AnalysisSample):
            new_loadings = {el: sample.xrf_loadings.get(el, 0.0) for el in target.elements}
            sample.xrf_loadings = new_loadings
        return sample

    def _on_item_changed(self, item):
        if self._suppress_signal or self.sheet is None:
            return
        r, c = item.row(), item.column()
        if r >= len(self.sheet.samples):
            return
        s = self.sheet.samples[r]
        text = item.text().strip()
        # Handle Excl. checkbox (not a text cell)
        if isinstance(self.sheet, CalibrationSheet) and c == 4:
            s.is_excluded = (item.checkState() == Qt.Checked)
            self.data_changed.emit()
            return
        if isinstance(self.sheet, AnalysisSheet) and c == 6 + len(self.sheet.elements):
            s.is_excluded = (item.checkState() == Qt.Checked)
            self.data_changed.emit()
            return

        try:
            if isinstance(self.sheet, CalibrationSheet):
                if   c == 0: s.sample_id = text
                elif c == 1: s.mass_mg = float(text) if text else 0.0
                elif c == 2: s.xrf_loading = float(text) if text else 0.0
                elif c == 3: s.mass_uncertainty = float(text) if text else 0.0
            elif isinstance(self.sheet, AnalysisSheet):
                n_el = len(self.sheet.elements)
                if   c == 0: s.sample_id = text
                elif c == 1: s.mass_mg = float(text) if text else 0.0
                elif c < 2 + n_el:
                    s.xrf_loadings[self.sheet.elements[c - 2]] = float(text) if text else 0.0
                elif c == 2 + n_el:
                    s.practical_specific_capacity = float(text) if text else float("nan")
                elif c == 4 + n_el:                       # edit "Mass utilized" (active) → custom
                    self._set_active_utilized(s, float(text) if text else float("nan"))
                elif c == 5 + n_el:
                    s.notes = text
        except ValueError:
            QMessageBox.warning(self, "Invalid input", f"Could not parse '{text}' as a number.")
            self._populate()
            return
        self.data_changed.emit()
