import copy
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QMenu, QInputDialog, QMessageBox
)
from PySide6.QtCore import Qt, Signal


class ProjectPanel(QWidget):
    """Left-side tree showing calibration and analysis sheets."""

    sheet_selected   = Signal(object)            # emits the sheet object
    project_changed  = Signal()                  # emits when tree structure changes
    add_calib_requested    = Signal()
    add_analysis_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.project = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("Project")
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.tree)

    def set_project(self, project):
        self.project = project
        self.refresh()

    def refresh(self):
        self.tree.clear()
        if self.project is None:
            return

        root = QTreeWidgetItem([self.project.name])
        root.setData(0, Qt.UserRole, ("root", None))
        self.tree.addTopLevelItem(root)

        calib_hdr = QTreeWidgetItem(["Calibration Sheets"])
        calib_hdr.setData(0, Qt.UserRole, ("calib_hdr", None))
        root.addChild(calib_hdr)
        for cs in self.project.calibration_sheets:
            item = QTreeWidgetItem([f"{cs.element} on {cs.substrate}" if cs.substrate else cs.element])
            item.setData(0, Qt.UserRole, ("calib", cs))
            calib_hdr.addChild(item)

        ana_hdr = QTreeWidgetItem(["Analysis Sheets"])
        ana_hdr.setData(0, Qt.UserRole, ("ana_hdr", None))
        root.addChild(ana_hdr)
        for a in self.project.analysis_sheets:
            item = QTreeWidgetItem([a.name])
            item.setData(0, Qt.UserRole, ("ana", a))
            ana_hdr.addChild(item)

        self.tree.expandAll()

    def _on_selection_changed(self):
        items = self.tree.selectedItems()
        if not items:
            return
        kind, sheet = items[0].data(0, Qt.UserRole) or ("", None)
        if kind in ("calib", "ana") and sheet is not None:
            self.sheet_selected.emit(sheet)

    def _show_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        menu = QMenu(self)
        add_cal = menu.addAction("Add calibration sheet…")
        add_ana = menu.addAction("Add analysis sheet…")
        action_remove = None
        action_rename = None
        action_duplicate = None
        if item is not None:
            kind, sheet = item.data(0, Qt.UserRole) or ("", None)
            if kind in ("calib", "ana"):
                menu.addSeparator()
                action_rename = menu.addAction("Rename…")
                action_duplicate = menu.addAction("Duplicate")
                action_remove = menu.addAction("Remove")

        action = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if action == add_cal:
            self.add_calib_requested.emit()
        elif action == add_ana:
            self.add_analysis_requested.emit()
        elif action == action_rename and item is not None:
            self._rename_sheet(item)
        elif action == action_duplicate and item is not None:
            self._duplicate_sheet(item)
        elif action == action_remove and item is not None:
            self._remove_sheet(item)

    def _duplicate_sheet(self, item):
        kind, sheet = item.data(0, Qt.UserRole)
        dup = copy.deepcopy(sheet)
        if kind == "calib":
            dup.substrate = (dup.substrate + " copy").strip() if dup.substrate else "copy"
            idx = self.project.calibration_sheets.index(sheet)
            self.project.calibration_sheets.insert(idx + 1, dup)
        elif kind == "ana":
            dup.name = f"{dup.name} (copy)"
            idx = self.project.analysis_sheets.index(sheet)
            self.project.analysis_sheets.insert(idx + 1, dup)
        self.refresh()
        self.project_changed.emit()
        self._select_sheet(dup)

    def _select_sheet(self, sheet):
        """Select the tree item whose UserRole sheet matches `sheet`."""
        def walk(parent):
            for i in range(parent.childCount()):
                child = parent.child(i)
                data = child.data(0, Qt.UserRole) or ("", None)
                if data[1] is sheet:
                    self.tree.setCurrentItem(child)
                    return True
                if walk(child):
                    return True
            return False
        root = self.tree.topLevelItem(0)
        if root is not None:
            walk(root)

    def _rename_sheet(self, item):
        kind, sheet = item.data(0, Qt.UserRole)
        if kind == "calib":
            new, ok = QInputDialog.getText(self, "Rename", "Substrate:", text=sheet.substrate)
            if ok:
                sheet.substrate = new
                self.refresh()
                self.project_changed.emit()
        elif kind == "ana":
            new, ok = QInputDialog.getText(self, "Rename", "Analysis sheet name:", text=sheet.name)
            if ok and new.strip():
                sheet.name = new.strip()
                self.refresh()
                self.project_changed.emit()

    def _remove_sheet(self, item):
        kind, sheet = item.data(0, Qt.UserRole)
        if QMessageBox.question(self, "Remove sheet", f"Remove this sheet?") != QMessageBox.Yes:
            return
        if kind == "calib":
            self.project.calibration_sheets.remove(sheet)
        elif kind == "ana":
            self.project.analysis_sheets.remove(sheet)
        self.refresh()
        self.project_changed.emit()
