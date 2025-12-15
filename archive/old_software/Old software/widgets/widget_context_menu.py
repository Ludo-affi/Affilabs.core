"""Widget Context Menu - Right-click any widget to inspect it."""

from PySide6.QtCore import QEvent, QObject
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu


class WidgetInspectorContextMenu(QObject):
    """Global event filter that adds right-click inspect to all widgets.
    Right-click any widget → "🔧 Inspect This Widget" appears.
    """

    def __init__(self, mainwindow):
        super().__init__()
        self.mainwindow = mainwindow
        self.enabled = False

    def enable(self):
        """Enable right-click inspect on all widgets."""
        self.enabled = True
        QApplication.instance().installEventFilter(self)

    def disable(self):
        """Disable right-click inspect."""
        self.enabled = False
        QApplication.instance().removeEventFilter(self)

    def eventFilter(self, watched, event):
        """Intercept right-click events to show inspect menu."""
        if not self.enabled:
            return super().eventFilter(watched, event)

        if event.type() == QEvent.Type.ContextMenuEvent:
            # Only for widgets, not the console itself
            if (
                hasattr(watched, "objectName")
                and watched is not self.mainwindow._inspector_console
                if hasattr(self.mainwindow, "_inspector_console")
                else True
            ):
                try:
                    self._show_inspect_menu(watched, event.globalPos())
                    return True  # Consume the event
                except:
                    pass  # If anything fails, let normal context menu work

        return super().eventFilter(watched, event)

    def _show_inspect_menu(self, widget, pos):
        """Show context menu with inspect option."""
        menu = QMenu()

        # Widget info
        widget_name = widget.objectName() or type(widget).__name__
        menu.addSection(f"🔧 {widget_name}")

        # Inspect action
        inspect_action = QAction("📋 Copy Inspect Command", menu)
        inspect_action.triggered.connect(lambda: self._copy_inspect_command(widget))
        menu.addAction(inspect_action)

        # Run inspect action
        run_action = QAction("▶ Inspect in Console", menu)
        run_action.triggered.connect(lambda: self._run_inspect(widget))
        menu.addAction(run_action)

        menu.addSeparator()

        # Quick info
        info_action = QAction(f"Size: {widget.width()}×{widget.height()}", menu)
        info_action.setEnabled(False)
        menu.addAction(info_action)

        pos_action = QAction(f"Pos: ({widget.x()}, {widget.y()})", menu)
        pos_action.setEnabled(False)
        menu.addAction(pos_action)

        menu.exec(pos)

    def _copy_inspect_command(self, widget):
        """Copy the inspect command to clipboard."""
        widget_path = self._get_widget_path(widget)
        command = f"inspect({widget_path}, '{widget.objectName() or 'widget'}')"

        clipboard = QApplication.clipboard()
        clipboard.setText(command)

        # Show feedback
        from widgets.message import show_message

        show_message(
            msg_type="Information",
            msg=f"Command copied to clipboard:\n\n{command}\n\nPaste into UI Inspector Console (Ctrl+Shift+I)",
            title="Inspect Command Copied",
        )

    def _run_inspect(self, widget):
        """Run inspect command directly in console."""
        # Open console if not open
        if (
            not hasattr(self.mainwindow, "_inspector_console")
            or self.mainwindow._inspector_console is None
        ):
            self.mainwindow.open_ui_inspector()

        # Generate and run command
        widget_path = self._get_widget_path(widget)
        command = f"inspect({widget_path}, '{widget.objectName() or 'widget'}')"

        # Set command in console and execute
        console = self.mainwindow._inspector_console
        console.input.setText(command)
        console._execute_command()

        # Bring console to front
        console.show()
        console.raise_()
        console.activateWindow()

    def _get_widget_path(self, widget):
        """Get the Python path to access this widget from mainwindow."""
        # Try to find the widget in common locations
        mw = self.mainwindow

        # Check common paths
        paths_to_check = [
            ("mw.sidebar", mw.sidebar if hasattr(mw, "sidebar") else None),
            (
                "mw.sidebar.device_widget",
                mw.sidebar.device_widget
                if hasattr(mw, "sidebar") and hasattr(mw.sidebar, "device_widget")
                else None,
            ),
            (
                "mw.sidebar.device_widget.device_status_widget",
                mw.sidebar.device_widget.device_status_widget
                if hasattr(mw, "sidebar")
                and hasattr(mw.sidebar, "device_widget")
                and hasattr(mw.sidebar.device_widget, "device_status_widget")
                else None,
            ),
            ("mw.sensorgram", mw.sensorgram if hasattr(mw, "sensorgram") else None),
            (
                "mw.spectroscopy",
                mw.spectroscopy if hasattr(mw, "spectroscopy") else None,
            ),
            (
                "mw.settings_panel",
                mw.settings_panel if hasattr(mw, "settings_panel") else None,
            ),
        ]

        # Check if widget matches any known path
        for path, obj in paths_to_check:
            if obj is widget:
                return path

        # Try to find by searching from mainwindow
        found_path = self._search_for_widget(widget, mw, "mw")
        if found_path:
            return found_path

        # Fallback: use find_widget_by_name if it has a name
        if widget.objectName():
            return f"find(mw, '{widget.objectName()}')"

        # Last resort
        return f"# Widget at ({widget.x()}, {widget.y()})"

    def _search_for_widget(self, target, current, path, max_depth=5, current_depth=0):
        """Recursively search for widget in object tree."""
        if current_depth >= max_depth:
            return None

        if current is target:
            return path

        # Check common attributes
        for attr_name in [
            "sidebar",
            "device_widget",
            "device_status_widget",
            "sensorgram",
            "spectroscopy",
            "settings_panel",
            "kinetic_widget",
        ]:
            if hasattr(current, attr_name):
                attr = getattr(current, attr_name)
                result = self._search_for_widget(
                    target,
                    attr,
                    f"{path}.{attr_name}",
                    max_depth,
                    current_depth + 1,
                )
                if result:
                    return result

        return None


def install_right_click_inspect(mainwindow):
    """Install right-click inspect functionality (disabled by default).
    Call this in mainwindow.__init__()

    Returns the context menu object. Call .enable() to activate.
    """
    context_menu = WidgetInspectorContextMenu(mainwindow)
    # Don't enable by default - caller can enable if needed
    return context_menu
