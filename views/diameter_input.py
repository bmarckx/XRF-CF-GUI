"""Diameter entry widget: text field + unit selector (cm / in).

Stores the value internally in cm. Inch input accepts decimal or fractions
('1/2', '1 1/4'). Switching units re-displays the same physical value.
"""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QComboBox
from PySide6.QtCore import Signal

from models.units import parse_length_to_cm, INCH_TO_CM


class DiameterInput(QWidget):
    value_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cm = None
        self._suppress = False

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.edit = QLineEdit()
        self.edit.setMaximumWidth(90)
        self.edit.setPlaceholderText("e.g. 1.27 or 1/2")
        self.unit = QComboBox()
        self.unit.addItems(["cm", "in"])
        lay.addWidget(self.edit)
        lay.addWidget(self.unit)

        self.edit.editingFinished.connect(self._on_edit)
        self.unit.currentIndexChanged.connect(self._redisplay)

    # ── value API ──
    def value_cm(self):
        return self._cm

    def set_value_cm(self, cm):
        self._cm = cm if (cm is not None and cm > 0) else None
        self._redisplay()

    def setEnabled(self, on):
        self.edit.setEnabled(on)
        self.unit.setEnabled(on)
        super().setEnabled(on)

    # ── internals ──
    def _on_edit(self):
        if self._suppress:
            return
        cm = parse_length_to_cm(self.edit.text(), self.unit.currentText())
        if cm is not None and cm > 0:
            if cm != self._cm:
                self._cm = cm
                self.value_changed.emit()
        else:
            self._redisplay()   # revert invalid input

    def _redisplay(self, *_):
        self._suppress = True
        if self._cm is None:
            self.edit.setText("")
        elif self.unit.currentText() == "in":
            self.edit.setText(self._fmt(self._cm / INCH_TO_CM))
        else:
            self.edit.setText(self._fmt(self._cm))
        self._suppress = False

    @staticmethod
    def _fmt(v):
        return f"{v:.4f}".rstrip("0").rstrip(".")
