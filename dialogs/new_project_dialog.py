from PySide6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QDialogButtonBox, QVBoxLayout, QLabel, QMessageBox
)
import math

from models.project import Project
from views.diameter_input import DiameterInput


class NewProjectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Project")
        self.resize(360, 160)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit("Untitled Project")
        form.addRow("Project name:", self.name_edit)

        self.diam_input = DiameterInput()
        self.diam_input.set_value_cm(1.27)
        form.addRow("Disk diameter:", self.diam_input)

        self.area_label = QLabel()
        form.addRow("Area:", self.area_label)
        self.diam_input.value_changed.connect(self._update_area)
        self._update_area()

        layout.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _update_area(self):
        d = self.diam_input.value_cm()
        if d is None:
            self.area_label.setText("—")
        else:
            self.area_label.setText(f"{math.pi * (d / 2) ** 2:.4f} cm²")

    def _on_accept(self):
        if self.diam_input.value_cm() is None:
            QMessageBox.warning(self, "Invalid diameter",
                                "Enter a valid diameter (decimal cm, or decimal/fractional inches).")
            return
        self.accept()

    def build_project(self) -> Project:
        return Project(name=self.name_edit.text().strip() or "Untitled",
                       diameter_cm=self.diam_input.value_cm() or 1.27)
