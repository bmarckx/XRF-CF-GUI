from PySide6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QDialogButtonBox, QVBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QMessageBox
)
from PySide6.QtCore import Qt

from models.project import CalibrationSheet, AnalysisSheet


class AddCalibrationDialog(QDialog):
    def __init__(self, existing_elements: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Calibration Sheet")
        self.resize(360, 180)
        self.existing = set(existing_elements)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.element_edit = QLineEdit()
        self.element_edit.setPlaceholderText("e.g. Pb")
        form.addRow("Element:", self.element_edit)

        self.substrate_edit = QLineEdit()
        self.substrate_edit.setPlaceholderText("e.g. Al (XRF-silent substrate)")
        form.addRow("Substrate:", self.substrate_edit)

        layout.addLayout(form)
        layout.addWidget(QLabel("<i>The correction factor for this element will be derived from these samples.</i>"))

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _accept(self):
        el = self.element_edit.text().strip()
        if not el:
            QMessageBox.warning(self, "Missing element", "Element name is required.")
            return
        if el in self.existing:
            QMessageBox.warning(self, "Duplicate element", f"Calibration for '{el}' already exists.")
            return
        self.accept()

    def build_sheet(self) -> CalibrationSheet:
        return CalibrationSheet(
            element=self.element_edit.text().strip(),
            substrate=self.substrate_edit.text().strip(),
            samples=[],
        )


class AddAnalysisDialog(QDialog):
    def __init__(self, calibrated_elements: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Analysis Sheet")
        self.resize(360, 320)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. Pb on Cu")
        form.addRow("Sheet name:", self.name_edit)

        layout.addLayout(form)

        layout.addWidget(QLabel("Select elements present (must have calibration sheets):"))
        self.list = QListWidget()
        for el in calibrated_elements:
            item = QListWidgetItem(el)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.list.addItem(item)
        layout.addWidget(self.list)

        if not calibrated_elements:
            layout.addWidget(QLabel("<i>No calibration sheets exist yet — add at least one first.</i>"))

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _accept(self):
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Missing name", "Sheet name is required.")
            return
        if not self._selected_elements():
            QMessageBox.warning(self, "No elements", "Select at least one element.")
            return
        self.accept()

    def _selected_elements(self):
        out = []
        for i in range(self.list.count()):
            it = self.list.item(i)
            if it.checkState() == Qt.Checked:
                out.append(it.text())
        return out

    def build_sheet(self) -> AnalysisSheet:
        return AnalysisSheet(
            name=self.name_edit.text().strip(),
            elements=self._selected_elements(),
            samples=[],
        )
