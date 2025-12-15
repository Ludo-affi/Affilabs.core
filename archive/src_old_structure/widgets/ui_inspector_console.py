"""Interactive UI Inspector Console - Access dev tools while app is running."""

import sys
from io import StringIO

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)


class UIInspectorConsole(QDialog):
    """Interactive Python console for inspecting and adjusting UI in real-time.
    Access with Ctrl+Shift+I or from Advanced menu.
    """

    def __init__(self, mainwindow, parent=None):
        super().__init__(parent)
        self.mainwindow = mainwindow
        self.setWindowTitle("UI Inspector Console")
        self.setWindowFlags(Qt.WindowType.Window)  # Normal window, not modal
        self.resize(800, 600)

        # Store command history
        self.history = []
        self.history_index = -1

        self._setup_ui()
        self._setup_namespace()
        self._print_welcome()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Title bar with instructions
        header = QLabel("🔧 UI Inspector Console - Interactive Dev Tools")
        header_font = QFont()
        header_font.setPointSize(11)
        header_font.setBold(True)
        header.setFont(header_font)
        header.setStyleSheet(
            "padding: 5px; background: rgb(46, 48, 227); color: white;",
        )
        layout.addWidget(header)

        # Output display
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setStyleSheet("""
            QTextEdit {
                background-color: rgb(30, 30, 30);
                color: rgb(220, 220, 220);
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 10pt;
                padding: 10px;
            }
        """)
        layout.addWidget(self.output, stretch=1)

        # Input area
        input_layout = QVBoxLayout()

        input_label = QLabel(">>> Python Command:")
        input_label.setStyleSheet("color: rgb(100, 100, 100); font-size: 9pt;")
        input_layout.addWidget(input_label)

        # Command input
        command_row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText(
            "e.g., inspect(mw.sidebar.device_widget, 'device')",
        )
        self.input.setStyleSheet("""
            QLineEdit {
                background-color: rgb(50, 50, 50);
                color: rgb(220, 220, 220);
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 10pt;
                padding: 8px;
                border: 2px solid rgb(100, 100, 100);
                border-radius: 3px;
            }
            QLineEdit:focus {
                border: 2px solid rgb(46, 48, 227);
            }
        """)
        self.input.returnPressed.connect(self._execute_command)
        command_row.addWidget(self.input)

        # Run button
        run_btn = QPushButton("▶ Run")
        run_btn.setStyleSheet("""
            QPushButton {
                background-color: rgb(46, 227, 111);
                color: black;
                font-weight: bold;
                padding: 8px 15px;
                border: none;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: rgb(66, 247, 131);
            }
        """)
        run_btn.clicked.connect(self._execute_command)
        command_row.addWidget(run_btn)

        input_layout.addLayout(command_row)
        layout.addLayout(input_layout)

        # Quick commands
        quick_layout = QHBoxLayout()
        quick_label = QLabel("Quick:")
        quick_layout.addWidget(quick_label)

        self._add_quick_btn(quick_layout, "Help", "help()")
        self._add_quick_btn(quick_layout, "Tree", "tree(mw)")
        self._add_quick_btn(
            quick_layout,
            "Device",
            "inspect(mw.sidebar.device_widget.device_status_widget, 'device_status')",
        )
        self._add_quick_btn(quick_layout, "Sidebar", "inspect(mw.sidebar, 'sidebar')")
        self._add_quick_btn(quick_layout, "Clear", "clear()")

        quick_layout.addStretch()
        layout.addLayout(quick_layout)

    def _add_quick_btn(self, layout, text, command):
        btn = QPushButton(text)
        btn.setStyleSheet("""
            QPushButton {
                background-color: rgb(240, 240, 240);
                border: 1px solid rgb(171, 171, 171);
                padding: 4px 8px;
                border-radius: 2px;
                font-size: 9pt;
            }
            QPushButton:hover {
                background-color: rgb(46, 48, 227);
                color: white;
            }
        """)
        btn.clicked.connect(lambda: self._run_quick_command(command))
        layout.addWidget(btn)

    def _run_quick_command(self, command):
        self.input.setText(command)
        self._execute_command()

    def _setup_namespace(self):
        """Setup the execution namespace with useful imports and references."""
        from widgets.ui_dev_helpers import (
            adjust,
            compare,
            find_and_inspect,
            find_widget_by_name,
            get_all_widgets_of_type,
            inspect,
            inspect_layout,
            print_widget_tree,
        )

        self.namespace = {
            # Main window reference
            "mw": self.mainwindow,
            # UI dev helpers
            "inspect": inspect,
            "inspect_layout": inspect_layout,
            "compare": compare,
            "adjust": adjust,
            "tree": print_widget_tree,
            "find": find_widget_by_name,
            "find_all": get_all_widgets_of_type,
            "fi": find_and_inspect,  # Shortcut: fi(mw, 'widget_name')
            # Common Qt widgets
            "QPushButton": __import__(
                "PySide6.QtWidgets",
                fromlist=["QPushButton"],
            ).QPushButton,
            "QLabel": __import__("PySide6.QtWidgets", fromlist=["QLabel"]).QLabel,
            "QWidget": __import__("PySide6.QtWidgets", fromlist=["QWidget"]).QWidget,
            # Helper functions
            "help": self._show_help,
            "clear": self._clear_output,
        }

    def _print_welcome(self):
        welcome = """
╔══════════════════════════════════════════════════════════════════╗
║           UI Inspector Console - Interactive Dev Tools            ║
╚══════════════════════════════════════════════════════════════════╝

Quick Start:
  • Type Python commands to inspect/adjust UI
  • 'mw' = mainwindow reference
  • Use arrow keys for command history
  • Type 'help()' for available commands

Examples:
  inspect(mw.sidebar.device_widget.device_status_widget, 'device')
  tree(mw.sidebar)
  adjust.resize_widget(mw.sidebar, 350, 600)
  find(mw, 'spr_connect_btn')

Type 'help()' for full command list.
────────────────────────────────────────────────────────────────────
"""
        self._append_output(welcome, "info")

    def _show_help(self):
        help_text = """
═══════════════════════════════════════════════════════════════════
                      AVAILABLE COMMANDS
═══════════════════════════════════════════════════════════════════

INSPECTION:
  inspect(widget, "name")        - Get widget properties + code
  tree(widget)                   - Print widget hierarchy tree
  inspect_layout(layout, "name") - Get layout properties
  find(parent, "objectName")     - Find widget by name
  find_all(parent, WidgetType)   - Find all widgets of type

ADJUSTMENT (prints code for you):
  adjust.move_widget(w, x, y)
  adjust.resize_widget(w, width, height)
  adjust.set_fixed_size(w, width, height)
  adjust.set_min_size(w, width, height)
  adjust.set_layout_margins(layout, l, t, r, b)
  adjust.set_layout_spacing(layout, spacing)

NAVIGATION:
  mw                             - Main window
  mw.sidebar                     - Sidebar widget
  mw.sidebar.device_widget       - Device widget
  mw.sensorgram                  - Sensorgram window
  mw.settings_panel              - Settings panel

UTILITY:
  clear()                        - Clear console output
  help()                         - Show this help

EXAMPLES:
  # See device status properties
  inspect(mw.sidebar.device_widget.device_status_widget, 'device_status')

  # Adjust sidebar width
  adjust.set_min_size(mw.sidebar, 350, 600)

  # Find a button
  btn = find(mw, 'spr_connect_btn')
  inspect(btn, 'connect_btn')

  # See widget tree
  tree(mw.sidebar)

═══════════════════════════════════════════════════════════════════
"""
        self._append_output(help_text, "info")

    def _execute_command(self):
        command = self.input.text().strip()
        if not command:
            return

        # Add to history
        self.history.append(command)
        self.history_index = len(self.history)

        # Show command
        self._append_output(f">>> {command}", "command")

        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()

        try:
            # Execute in namespace
            result = eval(command, self.namespace)

            # Get any printed output
            output = captured_output.getvalue()
            if output:
                self._append_output(output, "output")

            # Show result if not None and not a widget object
            # (suppress widget object representations)
            if result is not None:
                # Don't print widget objects directly - they show ugly repr
                from PySide6.QtWidgets import QWidget

                if not isinstance(result, QWidget):
                    self._append_output(str(result), "result")

        except SyntaxError:
            # Try as statement instead of expression
            try:
                exec(command, self.namespace)
                output = captured_output.getvalue()
                if output:
                    self._append_output(output, "output")
            except Exception as e:
                self._append_output(f"Error: {e}", "error")
        except Exception as e:
            self._append_output(f"Error: {e}", "error")
        finally:
            sys.stdout = old_stdout

        # Clear input
        self.input.clear()

        # Scroll to bottom
        self.output.moveCursor(QTextCursor.MoveOperation.End)

    def _clear_output(self):
        self.output.clear()
        self._print_welcome()

    def _append_output(self, text, style="normal"):
        """Append text with color coding."""
        colors = {
            "command": "#4A9EFF",  # Blue
            "output": "#A8E6CF",  # Green
            "result": "#FFD93D",  # Yellow
            "error": "#FF6B6B",  # Red
            "info": "#C3C3C3",  # Gray
        }

        color = colors.get(style, "#FFFFFF")

        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml(
            f'<span style="color: {color};">{text.replace("<", "&lt;").replace(">", "&gt;")}</span><br>',
        )

    def keyPressEvent(self, event):
        """Handle arrow keys for command history."""
        if event.key() == Qt.Key.Key_Up:
            if self.history and self.history_index > 0:
                self.history_index -= 1
                self.input.setText(self.history[self.history_index])
        elif event.key() == Qt.Key.Key_Down:
            if self.history and self.history_index < len(self.history) - 1:
                self.history_index += 1
                self.input.setText(self.history[self.history_index])
            else:
                self.history_index = len(self.history)
                self.input.clear()
        else:
            super().keyPressEvent(event)


def install_inspector_shortcut(mainwindow):
    """Install Ctrl+Shift+I shortcut to open UI inspector console.
    Call this in mainwindow.__init__()
    """
    from PySide6.QtGui import QKeySequence, QShortcut

    def open_inspector():
        if (
            not hasattr(mainwindow, "_inspector_console")
            or mainwindow._inspector_console is None
        ):
            mainwindow._inspector_console = UIInspectorConsole(mainwindow)
        mainwindow._inspector_console.show()
        mainwindow._inspector_console.raise_()
        mainwindow._inspector_console.activateWindow()
        mainwindow._inspector_console.input.setFocus()

    shortcut = QShortcut(QKeySequence("Ctrl+Shift+I"), mainwindow)
    shortcut.activated.connect(open_inspector)

    return open_inspector
