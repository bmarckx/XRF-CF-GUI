"""Entry point for the XRF Correction Factor GUI."""

import sys
import os

# Make package imports work whether run as script or module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from views.main_window import MainWindow
from models import settings


def _first_run_setup(parent=None):
    """On first launch, ask the user for the default folder for file browsers."""
    if settings.is_configured():
        return
    QMessageBox.information(
        parent, "Welcome to the XRF Correction Factor Tool",
        "Choose the default folder where your project files will be opened and "
        "saved. You can change this later by opening or saving from a different "
        "location.")
    folder = QFileDialog.getExistingDirectory(
        parent, "Select default project folder", os.path.expanduser("~"))
    # If the user cancels, fall back to the home directory but still mark configured.
    settings.set_default_dir(folder or os.path.expanduser("~"))


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("XRF-CF-GUI")
    _first_run_setup()
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
