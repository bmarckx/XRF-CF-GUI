from PySide6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QDoubleSpinBox, QDialogButtonBox, QVBoxLayout, QLabel
)
import math

from models.project import Project


class NewProjectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Project")
        self.resize(360, 160)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit("Untitled Project")
        form.addRow("Project name:", self.name_edit)

        self.diam_spin = QDoubleSpinBox()
        self.diam_spin.setRange(0.01, 100.0)
        self.diam_spin.setDecimals(4)
        self.diam_spin.setValue(1.27)
        self.diam_spin.setSuffix(" cm")
        form.addRow("Disk diameter:", self.diam_spin)

        self.area_label = QLabel()
        form.addRow("Area:", self.area_label)
        self.diam_spin.valueChanged.connect(self._update_area)
        self._update_area()

        layout.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _update_area(self):
        d = self.diam_spin.value()
        self.area_label.setText(f"{math.pi * (d / 2) ** 2:.4f} cm²")

    def build_project(self) -> Project:
        return Project(name=self.name_edit.text().strip() or "Untitled",
                       diameter_cm=self.diam_spin.value())
