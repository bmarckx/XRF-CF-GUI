from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QTabWidget, QFileDialog, QMessageBox, QToolBar, QWidget
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction

from models.project import Project
from views.project_panel import ProjectPanel
from views.data_tab import DataTab
from views.results_tab import ResultsTab
from views.statistics_tab import StatisticsTab
from views.visualization_tab import VisualizationTab
from dialogs.new_project_dialog import NewProjectDialog
from dialogs.add_sheet_dialog import AddCalibrationDialog, AddAnalysisDialog
from xrf_io.excel_io import save_project, load_project
from xrf_io.pdf_export import export_pdf


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("XRF Correction Factor Tool")
        self.resize(1200, 720)

        self.project = None
        self.current_path = None

        self._build_toolbar()
        self._build_central()
        self._update_title()

    # ── construction ──────────────────────────────────────────────────────────
    def _build_toolbar(self):
        tb = QToolBar()
        tb.setMovable(False)
        self.addToolBar(tb)

        for name, slot in [
            ("New Project",   self.action_new),
            ("Open Excel…",   self.action_open),
            ("Save",          self.action_save),
            ("Save As…",      self.action_save_as),
            (None, None),
            ("Add Calibration", self.action_add_calib),
            ("Add Analysis",    self.action_add_analysis),
            (None, None),
            ("Export PDF…",  self.action_export_pdf),
        ]:
            if name is None:
                tb.addSeparator()
                continue
            act = QAction(name, self)
            act.triggered.connect(slot)
            tb.addAction(act)

    def _build_central(self):
        splitter = QSplitter(Qt.Horizontal)

        self.panel = ProjectPanel()
        self.panel.sheet_selected.connect(self._on_sheet_selected)
        self.panel.project_changed.connect(self._on_project_changed)
        self.panel.add_calib_requested.connect(self.action_add_calib)
        self.panel.add_analysis_requested.connect(self.action_add_analysis)
        splitter.addWidget(self.panel)

        self.tabs = QTabWidget()
        self.data_tab    = DataTab()
        self.results_tab = ResultsTab()
        self.stats_tab   = StatisticsTab()
        self.viz_tab     = VisualizationTab()

        self.data_tab.data_changed.connect(self._on_data_changed)

        self.tabs.addTab(self.data_tab,    "Data")
        self.tabs.addTab(self.results_tab, "Results")
        self.tabs.addTab(self.stats_tab,   "Statistics")
        self.tabs.addTab(self.viz_tab,     "Visualization")
        splitter.addWidget(self.tabs)

        splitter.setSizes([260, 940])
        self.setCentralWidget(splitter)

    # ── actions ──────────────────────────────────────────────────────────────
    def action_new(self):
        dlg = NewProjectDialog(self)
        if dlg.exec() == NewProjectDialog.Accepted:
            self.project = dlg.build_project()
            self.current_path = None
            self.panel.set_project(self.project)
            self._refresh_views(None)
            self._update_title()

    def action_open(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Excel project", "", "Excel (*.xlsx)")
        if not path:
            return
        try:
            self.project = load_project(path)
        except Exception as e:
            QMessageBox.critical(self, "Open failed", f"Could not load file:\n{e}")
            return
        self.current_path = path
        self.panel.set_project(self.project)
        self._refresh_views(None)
        self._update_title()

    def action_save(self):
        if self.project is None:
            return
        if not self.current_path:
            self.action_save_as()
            return
        try:
            save_project(self.project, self.current_path)
            self.statusBar().showMessage(f"Saved to {self.current_path}", 4000)
        except Exception as e:
            QMessageBox.critical(self, "Save failed", str(e))

    def action_save_as(self):
        if self.project is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Excel project",
            f"{self.project.name}.xlsx", "Excel (*.xlsx)"
        )
        if not path:
            return
        try:
            save_project(self.project, path)
            self.current_path = path
            self._update_title()
            self.statusBar().showMessage(f"Saved to {path}", 4000)
        except Exception as e:
            QMessageBox.critical(self, "Save failed", str(e))

    def action_add_calib(self):
        if self.project is None:
            QMessageBox.information(self, "No project", "Create a project first."); return
        existing = [c.element for c in self.project.calibration_sheets]
        dlg = AddCalibrationDialog(existing, self)
        if dlg.exec() == AddCalibrationDialog.Accepted:
            self.project.calibration_sheets.append(dlg.build_sheet())
            self.panel.refresh()
            self._refresh_views(self.project.calibration_sheets[-1])

    def action_add_analysis(self):
        if self.project is None:
            QMessageBox.information(self, "No project", "Create a project first."); return
        elements = [c.element for c in self.project.calibration_sheets]
        if not elements:
            QMessageBox.warning(self, "No calibrations", "Add at least one calibration sheet first."); return
        dlg = AddAnalysisDialog(elements, self)
        if dlg.exec() == AddAnalysisDialog.Accepted:
            self.project.analysis_sheets.append(dlg.build_sheet())
            self.panel.refresh()
            self._refresh_views(self.project.analysis_sheets[-1])

    def action_export_pdf(self):
        if self.project is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export PDF report", f"{self.project.name}_report.pdf", "PDF (*.pdf)"
        )
        if not path:
            return
        try:
            export_pdf(self.project, path)
            self.statusBar().showMessage(f"Exported {path}", 4000)
        except Exception as e:
            QMessageBox.critical(self, "Export failed", str(e))

    # ── signal handlers ──────────────────────────────────────────────────────
    def _on_sheet_selected(self, sheet):
        self._refresh_views(sheet)

    def _on_project_changed(self):
        self._refresh_views(None)

    def _on_data_changed(self):
        # Data edited → refresh results/stats/viz for current sheet
        self.results_tab.refresh()
        self.stats_tab.refresh()
        self.viz_tab.refresh()

    # ── helpers ──────────────────────────────────────────────────────────────
    def _refresh_views(self, sheet):
        self.data_tab.set_context(self.project, sheet)
        self.results_tab.set_context(self.project, sheet)
        self.stats_tab.set_context(self.project, sheet)
        self.viz_tab.set_context(self.project, sheet)

    def _update_title(self):
        suffix = self.project.name if self.project else "(no project)"
        if self.current_path:
            suffix += f"  —  {self.current_path}"
        self.setWindowTitle(f"XRF Correction Factor Tool  —  {suffix}")
