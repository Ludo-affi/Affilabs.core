"""OEM Issue Tracker Dialog — internal GitHub Issues UI.

Opens from Device Status sidebar button or Ctrl+Shift+I.
Requires GITHUB_TOKEN + GITHUB_REPO in .env.
"""

import threading
import webbrowser
from datetime import datetime

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from affilabs.utils.logger import logger

# ── Style constants ───────────────────────────────────────────────────────────
_FONT = "-apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif"

_DIALOG_STYLE = f"""
QDialog {{
    background: #F5F5F7;
    font-family: {_FONT};
}}
QTabWidget::pane {{
    border: 1px solid #D2D2D7;
    border-radius: 8px;
    background: #FFFFFF;
}}
QTabBar::tab {{
    background: transparent;
    color: #6E6E73;
    font-size: 12px;
    font-weight: 600;
    padding: 8px 18px;
    border-bottom: 2px solid transparent;
    font-family: {_FONT};
}}
QTabBar::tab:selected {{
    color: #1D1D1F;
    border-bottom: 2px solid #0071E3;
}}
QLabel {{
    color: #1D1D1F;
    font-family: {_FONT};
}}
QLineEdit, QTextEdit, QComboBox {{
    background: #FFFFFF;
    border: 1px solid #D2D2D7;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
    color: #1D1D1F;
    font-family: {_FONT};
}}
QLineEdit:focus, QTextEdit:focus {{
    border-color: #0071E3;
}}
QTableWidget {{
    background: #FFFFFF;
    border: none;
    gridline-color: #F0F0F5;
    font-size: 12px;
    font-family: {_FONT};
}}
QTableWidget::item {{
    padding: 6px 8px;
    color: #1D1D1F;
}}
QTableWidget::item:selected {{
    background: #E8F0FF;
    color: #1D1D1F;
}}
QHeaderView::section {{
    background: #F5F5F7;
    color: #6E6E73;
    font-size: 11px;
    font-weight: 600;
    padding: 6px 8px;
    border: none;
    border-bottom: 1px solid #D2D2D7;
    font-family: {_FONT};
}}
"""

_BTN_PRIMARY = """
QPushButton {{
    background: #0071E3;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 7px 18px;
    font-size: 13px;
    font-weight: 600;
    font-family: {font};
}}
QPushButton:hover {{ background: #0077ED; }}
QPushButton:pressed {{ background: #005BB5; }}
QPushButton:disabled {{ background: #C7C7CC; color: #8E8E93; }}
""".format(font=_FONT)

_BTN_SECONDARY = """
QPushButton {{
    background: #FFFFFF;
    color: #1D1D1F;
    border: 1px solid #D2D2D7;
    border-radius: 6px;
    padding: 7px 18px;
    font-size: 13px;
    font-weight: 500;
    font-family: {font};
}}
QPushButton:hover {{ background: #F0F0F5; }}
QPushButton:pressed {{ background: #E5E5EA; }}
""".format(font=_FONT)

_SEVERITY_COLORS = {
    "critical": "#D73A4A",
    "high":     "#E4606D",
    "medium":   "#FBCA04",
    "low":      "#0075CA",
}
_SEVERITY_TEXT_COLORS = {
    "critical": "white",
    "high":     "white",
    "medium":   "#1D1D1F",
    "low":      "white",
}
SEVERITIES   = ["critical", "high", "medium", "low"]
COMPONENTS   = ["spark", "pump", "calibration", "ui", "hardware", "acquisition", "recording", "other"]


# ── Dialog ────────────────────────────────────────────────────────────────────

class IssueTrackerDialog(QDialog):
    """Internal OEM issue tracker backed by GitHub Issues."""

    # Emitted (issue_number, url) after successful creation
    issue_created = Signal(int, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🐛  Issue Tracker — OEM Internal")
        self.setModal(False)   # non-modal so app stays usable
        self.resize(900, 620)
        self.setStyleSheet(_DIALOG_STYLE)

        self._issues_cache: list[dict] = []
        self._creating = False

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # Header
        hdr = QHBoxLayout()
        title_lbl = QLabel("Issue Tracker")
        title_lbl.setStyleSheet("font-size: 20px; font-weight: 700; color: #1D1D1F;")
        hdr.addWidget(title_lbl)
        hdr.addStretch()

        self._cfg_badge = QLabel()
        self._cfg_badge.setStyleSheet("font-size: 11px; padding: 3px 10px; border-radius: 10px;")
        hdr.addWidget(self._cfg_badge)
        root.addLayout(hdr)

        # Tabs
        self._tabs = QTabWidget()
        root.addWidget(self._tabs)

        self._build_list_tab()
        self._build_create_tab()

        # Bottom bar
        bar = QHBoxLayout()
        bar.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(_BTN_SECONDARY)
        close_btn.clicked.connect(self.accept)
        bar.addWidget(close_btn)
        root.addLayout(bar)

        self._check_config()
        self._refresh_issues()

    # ── List tab ──────────────────────────────────────────────────────────────

    def _build_list_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Toolbar
        toolbar = QHBoxLayout()
        self._state_combo = QComboBox()
        self._state_combo.addItems(["open", "closed", "all"])
        self._state_combo.setFixedWidth(100)
        self._state_combo.currentTextChanged.connect(self._refresh_issues)
        toolbar.addWidget(QLabel("Show:"))
        toolbar.addWidget(self._state_combo)
        toolbar.addStretch()

        self._issue_count_lbl = QLabel("")
        self._issue_count_lbl.setStyleSheet("color: #6E6E73; font-size: 12px;")
        toolbar.addWidget(self._issue_count_lbl)

        self._refresh_btn = QPushButton("⟳  Refresh")
        self._refresh_btn.setStyleSheet(_BTN_SECONDARY)
        self._refresh_btn.setFixedHeight(30)
        self._refresh_btn.clicked.connect(self._refresh_issues)
        toolbar.addWidget(self._refresh_btn)
        layout.addLayout(toolbar)

        # Table
        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(["#", "Title", "Severity", "Component", "State", "Created"])
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(0, 55)
        self._table.setColumnWidth(2, 90)
        self._table.setColumnWidth(3, 110)
        self._table.setColumnWidth(4, 70)
        self._table.setColumnWidth(5, 110)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.doubleClicked.connect(self._open_issue_in_browser)
        layout.addWidget(self._table)

        hint = QLabel("Double-click a row to open in GitHub")
        hint.setStyleSheet("color: #8E8E93; font-size: 11px;")
        layout.addWidget(hint)

        # Close / reopen selected
        action_bar = QHBoxLayout()
        action_bar.addStretch()
        close_sel_btn = QPushButton("Close Selected")
        close_sel_btn.setStyleSheet(_BTN_SECONDARY)
        close_sel_btn.setFixedHeight(30)
        close_sel_btn.clicked.connect(self._close_selected)
        action_bar.addWidget(close_sel_btn)

        reopen_sel_btn = QPushButton("Reopen Selected")
        reopen_sel_btn.setStyleSheet(_BTN_SECONDARY)
        reopen_sel_btn.setFixedHeight(30)
        reopen_sel_btn.clicked.connect(self._reopen_selected)
        action_bar.addWidget(reopen_sel_btn)
        layout.addLayout(action_bar)

        self._tabs.addTab(tab, "📋  Open Issues")

    def _populate_table(self, issues: list[dict]):
        self._issues_cache = issues
        self._table.setRowCount(0)
        for issue in issues:
            row = self._table.rowCount()
            self._table.insertRow(row)

            num_item = QTableWidgetItem(str(issue.get("number", "")))
            num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 0, num_item)

            self._table.setItem(row, 1, QTableWidgetItem(issue.get("title", "")))

            labels = [lbl["name"] for lbl in issue.get("labels", [])]
            severity = next((l.split(":")[1] for l in labels if l.startswith("severity:")), "")
            component = next((l.split(":")[1] for l in labels if l.startswith("comp:")), "")

            sev_item = QTableWidgetItem(severity)
            sev_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if severity in _SEVERITY_COLORS:
                sev_item.setForeground(Qt.GlobalColor.white if _SEVERITY_TEXT_COLORS.get(severity) == "white" else Qt.GlobalColor.black)
                sev_item.setBackground(__import__("PySide6.QtGui", fromlist=["QColor"]).QColor(_SEVERITY_COLORS[severity]))
            self._table.setItem(row, 2, sev_item)

            self._table.setItem(row, 3, QTableWidgetItem(component))

            state_item = QTableWidgetItem(issue.get("state", ""))
            state_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 4, state_item)

            created = issue.get("created_at", "")[:10]  # YYYY-MM-DD
            self._table.setItem(row, 5, QTableWidgetItem(created))

        count = len(issues)
        self._issue_count_lbl.setText(f"{count} issue{'s' if count != 1 else ''}")

    def _refresh_issues(self):
        self._refresh_btn.setEnabled(False)
        self._refresh_btn.setText("Loading…")
        state = self._state_combo.currentText()

        def _fetch():
            try:
                from affilabs.services.github_issue_tracker import list_issues
                issues = list_issues(state=state)
            except Exception as e:
                issues = None
                err = str(e)
                QTimer.singleShot(0, lambda: self._on_fetch_error(err))
                return
            QTimer.singleShot(0, lambda: self._on_issues_fetched(issues))

        threading.Thread(target=_fetch, daemon=True).start()

    def _on_issues_fetched(self, issues: list[dict]):
        self._refresh_btn.setEnabled(True)
        self._refresh_btn.setText("⟳  Refresh")
        self._populate_table(issues)

    def _on_fetch_error(self, err: str):
        self._refresh_btn.setEnabled(True)
        self._refresh_btn.setText("⟳  Refresh")
        self._issue_count_lbl.setText("⚠ Load failed")
        logger.warning(f"Issue fetch failed: {err}")

    def _open_issue_in_browser(self, index):
        row = index.row()
        if 0 <= row < len(self._issues_cache):
            url = self._issues_cache[row].get("html_url", "")
            if url:
                webbrowser.open(url)

    def _close_selected(self):
        self._change_state_selected("closed")

    def _reopen_selected(self):
        self._change_state_selected("open")

    def _change_state_selected(self, new_state: str):
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.information(self, "No Selection", "Select one or more issues first.")
            return
        for idx in rows:
            row = idx.row()
            if 0 <= row < len(self._issues_cache):
                number = self._issues_cache[row]["number"]
                def _do(n=number, s=new_state):
                    try:
                        from affilabs.services.github_issue_tracker import close_issue, reopen_issue
                        if s == "closed":
                            close_issue(n)
                        else:
                            reopen_issue(n)
                    except Exception as e:
                        logger.warning(f"State change failed for #{n}: {e}")
                    QTimer.singleShot(0, self._refresh_issues)
                threading.Thread(target=_do, daemon=True).start()

    # ── Create tab ────────────────────────────────────────────────────────────

    def _build_create_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        def _field_label(text):
            lbl = QLabel(text)
            lbl.setStyleSheet("font-size: 12px; font-weight: 600; color: #6E6E73;")
            return lbl

        # Title
        layout.addWidget(_field_label("TITLE *"))
        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText("Short summary of the issue")
        self._title_edit.setFixedHeight(36)
        layout.addWidget(self._title_edit)

        # Description
        layout.addWidget(_field_label("DESCRIPTION *"))
        self._desc_edit = QTextEdit()
        self._desc_edit.setPlaceholderText(
            "Steps to reproduce, expected vs actual behaviour, any errors seen…"
        )
        self._desc_edit.setFixedHeight(120)
        layout.addWidget(self._desc_edit)

        # Severity + Component row
        meta_row = QHBoxLayout()
        meta_row.setSpacing(16)

        sev_col = QVBoxLayout()
        sev_col.addWidget(_field_label("SEVERITY"))
        self._severity_combo = QComboBox()
        self._severity_combo.addItems(SEVERITIES)
        self._severity_combo.setCurrentText("medium")
        self._severity_combo.setFixedHeight(34)
        sev_col.addWidget(self._severity_combo)
        meta_row.addLayout(sev_col)

        comp_col = QVBoxLayout()
        comp_col.addWidget(_field_label("COMPONENT"))
        self._component_combo = QComboBox()
        self._component_combo.addItems(COMPONENTS)
        self._component_combo.setFixedHeight(34)
        comp_col.addWidget(self._component_combo)
        meta_row.addLayout(comp_col)

        meta_row.addStretch()
        layout.addLayout(meta_row)

        # Auto-attach options
        attach_row = QHBoxLayout()
        self._attach_log_chk = QCheckBox("Attach log tail")
        self._attach_log_chk.setChecked(True)
        self._attach_screenshot_chk = QCheckBox("Take screenshot (saves locally)")
        self._attach_screenshot_chk.setChecked(True)
        attach_row.addWidget(self._attach_log_chk)
        attach_row.addSpacing(16)
        attach_row.addWidget(self._attach_screenshot_chk)
        attach_row.addStretch()
        layout.addLayout(attach_row)

        layout.addStretch()

        # Submit row
        submit_row = QHBoxLayout()
        submit_row.addStretch()
        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet("font-size: 12px; color: #6E6E73;")
        submit_row.addWidget(self._status_lbl)

        self._submit_btn = QPushButton("Create Issue")
        self._submit_btn.setStyleSheet(_BTN_PRIMARY)
        self._submit_btn.setFixedHeight(36)
        self._submit_btn.clicked.connect(self._on_submit)
        submit_row.addWidget(self._submit_btn)
        layout.addLayout(submit_row)

        self._tabs.addTab(tab, "➕  New Issue")

    def _on_submit(self):
        if self._creating:
            return
        title = self._title_edit.text().strip()
        desc = self._desc_edit.toPlainText().strip()
        if not title:
            QMessageBox.warning(self, "Missing Title", "Please enter a title.")
            return
        if not desc:
            QMessageBox.warning(self, "Missing Description", "Please enter a description.")
            return

        severity = self._severity_combo.currentText()
        component = self._component_combo.currentText()
        include_log = self._attach_log_chk.isChecked()
        do_screenshot = self._attach_screenshot_chk.isChecked()

        # Take screenshot synchronously before switching threads (needs Qt main thread)
        screenshot_path = None
        if do_screenshot:
            try:
                from affilabs.services.github_issue_tracker import take_screenshot_to_file
                screenshot_path = take_screenshot_to_file()
            except Exception as e:
                logger.debug(f"Screenshot step skipped: {e}")

        self._creating = True
        self._submit_btn.setEnabled(False)
        self._submit_btn.setText("Creating…")
        self._status_lbl.setText("")

        def _do():
            try:
                from affilabs.services.github_issue_tracker import create_issue, ensure_labels
                ensure_labels()
                number, url = create_issue(
                    title=title,
                    description=desc,
                    severity=severity,
                    component=component,
                    include_log=include_log,
                    screenshot_path=screenshot_path,
                )
                QTimer.singleShot(0, lambda: self._on_created(number, url))
            except Exception as e:
                err = str(e)
                QTimer.singleShot(0, lambda: self._on_create_error(err))

        threading.Thread(target=_do, daemon=True).start()

    def _on_created(self, number: int, url: str):
        self._creating = False
        self._submit_btn.setEnabled(True)
        self._submit_btn.setText("Create Issue")
        self._status_lbl.setText(f"✅  Created #{number}")
        self._title_edit.clear()
        self._desc_edit.clear()
        self.issue_created.emit(number, url)
        # Switch to list tab and refresh
        self._tabs.setCurrentIndex(0)
        self._refresh_issues()
        logger.info(f"Issue #{number} created: {url}")

    def _on_create_error(self, err: str):
        self._creating = False
        self._submit_btn.setEnabled(True)
        self._submit_btn.setText("Create Issue")
        self._status_lbl.setText(f"❌  {err}")
        QMessageBox.critical(self, "Create Failed", f"Could not create issue:\n\n{err}")

    # ── Config check ──────────────────────────────────────────────────────────

    def _check_config(self):
        from affilabs.services.github_issue_tracker import ensure_configured
        ok, err = ensure_configured()
        if ok:
            from affilabs.services.github_issue_tracker import GITHUB_REPO
            self._cfg_badge.setText(f"● {GITHUB_REPO}")
            self._cfg_badge.setStyleSheet(
                "font-size: 11px; font-weight: 600; color: #34C759; "
                "background: #E3FAEC; border-radius: 10px; padding: 3px 10px;"
            )
        else:
            self._cfg_badge.setText("⚠ Not configured")
            self._cfg_badge.setStyleSheet(
                "font-size: 11px; font-weight: 600; color: #FF9500; "
                "background: #FFF3CD; border-radius: 10px; padding: 3px 10px;"
            )
            self._submit_btn.setEnabled(False)
            self._status_lbl.setText(f"⚠ {err} — add to .env")
