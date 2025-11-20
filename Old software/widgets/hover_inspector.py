"""Hover Inspector - Shows widget info when you hover over it."""

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QObject, QEvent


class HoverInspector(QObject):
    """
    Shows widget information in status bar when hovering with Ctrl pressed.
    Click while Ctrl+hovering to copy inspect command to UI Inspector Console.
    """

    def __init__(self, mainwindow):
        super().__init__()
        self.mainwindow = mainwindow
        self.enabled = False
        self.ctrl_pressed = False
        self.last_hover_widget = None
        self.last_hover_command = None

    def enable(self):
        """Enable hover inspection on all widgets."""
        self.enabled = True
        QApplication.instance().installEventFilter(self)

    def disable(self):
        """Disable hover inspection."""
        self.enabled = False
        QApplication.instance().removeEventFilter(self)

    def eventFilter(self, watched, event):
        """Show widget info on hover when Ctrl is pressed."""
        if not self.enabled:
            return super().eventFilter(watched, event)

        try:
            # Track Ctrl key state
            if event.type() == QEvent.Type.KeyPress:
                if event.key() == Qt.Key.Key_Control:
                    self.ctrl_pressed = True
            elif event.type() == QEvent.Type.KeyRelease:
                if event.key() == Qt.Key.Key_Control:
                    self.ctrl_pressed = False
                    self.last_hover_widget = None
                    self.last_hover_command = None

            # Show info on hover when Ctrl is pressed
            if event.type() == QEvent.Type.Enter and self.ctrl_pressed:
                if hasattr(watched, 'objectName'):
                    widget_info = self._get_widget_info(watched)
                    if widget_info:
                        self.last_hover_widget = watched
                        # Show in status bar instead of tooltip (no crashes)
                        if hasattr(self.mainwindow, 'ui') and hasattr(self.mainwindow.ui, 'status'):
                            self.mainwindow.ui.status.setText(widget_info)

            # Click while Ctrl+hovering to copy to inspector
            # Use MouseButtonRelease to avoid conflicts with button handlers
            if event.type() == QEvent.Type.MouseButtonRelease and self.ctrl_pressed:
                if self.last_hover_command:
                    # Open inspector if not open
                    if not hasattr(self.mainwindow, '_inspector_console') or self.mainwindow._inspector_console is None:
                        self.mainwindow.open_ui_inspector()

                    # Set command in console
                    console = self.mainwindow._inspector_console
                    if console and hasattr(console, 'input'):
                        console.input.setText(self.last_hover_command)
                        console.input.setFocus()
                        console.show()
                        console.raise_()
                        console.activateWindow()
                        # Show feedback
                        if hasattr(self.mainwindow, 'ui') and hasattr(self.mainwindow.ui, 'status'):
                            self.mainwindow.ui.status.setText(f"✓ Command ready: {self.last_hover_command}")

                    # Don't consume the event - let normal click handling continue
                    return False

        except Exception as e:
            # Silently handle any errors to prevent crashes
            pass

        return super().eventFilter(watched, event)

    def _get_widget_info(self, widget):
        """Get displayable widget information."""
        widget_name = widget.objectName() or type(widget).__name__
        widget_type = type(widget).__name__

        # Try to find path from mainwindow
        path = self._find_widget_path(widget)

        if not path:
            if widget_name and widget_name != widget_type:
                path = f"find(mw, '{widget_name}')"
            else:
                return None  # Skip widgets we can't identify

        # Store command for click-to-copy
        self.last_hover_command = f"inspect({path})"

        # Return status bar message
        info = f"🔍 {widget_name} ({widget_type}) | Path: {path} | Click to inspect"

        return info

    def _find_widget_path(self, target):
        """Find the Python path to access this widget from mainwindow."""
        mw = self.mainwindow

        # First priority: check if widget has a name - use fi() function
        if target.objectName():
            return f"fi(mw, '{target.objectName()}')"

        # Second priority: check common direct paths
        paths_to_check = [
            ('mw.sidebar', getattr(mw, 'sidebar', None)),
            ('mw.sensorgram', getattr(mw, 'sensorgram', None)),
            ('mw.spectroscopy', getattr(mw, 'spectroscopy', None)),
            ('mw.data_processing', getattr(mw, 'data_processing', None)),
            ('mw.data_analysis', getattr(mw, 'data_analysis', None)),
        ]

        for path, obj in paths_to_check:
            if obj is target:
                return path

        # Third priority: check sidebar children
        if hasattr(mw, 'sidebar'):
            sidebar_paths = [
                ('mw.sidebar.device_widget', getattr(mw.sidebar, 'device_widget', None)),
                ('mw.sidebar.kinetic_widget', getattr(mw.sidebar, 'kinetic_widget', None)),
            ]
            for path, obj in sidebar_paths:
                if obj is target:
                    return path

        # Last resort: try recursive search
        found = self._search_widget(target, mw, 'mw', max_depth=3)
        if found:
            return found

        return None

    def _search_widget(self, target, current, path, max_depth=4, depth=0):
        """Recursively search for widget."""
        if depth >= max_depth or current is None:
            return None

        if current is target:
            return path

        # Common attributes to search
        attrs = ['sidebar', 'device_widget', 'sensorgram', 'spectroscopy',
                'data_processing', 'data_analysis', 'kinetic_widget', 'ui']

        for attr in attrs:
            if hasattr(current, attr):
                try:
                    child = getattr(current, attr)
                    result = self._search_widget(target, child, f"{path}.{attr}", max_depth, depth + 1)
                    if result:
                        return result
                except:
                    pass

        return None


def install_hover_inspector(mainwindow):
    """
    Install hover inspector (shows widget info when you Ctrl+hover).
    Click while Ctrl+hovering to copy inspect command to UI Inspector Console.
    Returns the inspector object. Call .enable() to activate.
    """
    inspector = HoverInspector(mainwindow)
    return inspector

