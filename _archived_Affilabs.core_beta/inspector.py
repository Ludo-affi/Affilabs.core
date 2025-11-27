"""UI element inspection utilities extracted from main prototype.

Provides contextual right-click copy of widget information for debugging.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QApplication, QMenu
from PySide6.QtGui import QAction

class ElementInspector:
    """Utility to inspect UI elements and copy their information."""

    @staticmethod
    def install_inspector(widget: QWidget):
        """Install context menu inspection on a widget and all descendants."""
        if widget is None:
            return
        widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        widget.customContextMenuRequested.connect(lambda pos: ElementInspector.show_inspector_menu(widget, pos))
        # Recursively attach to children
        for child in widget.findChildren(QWidget):
            child.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            child.customContextMenuRequested.connect(lambda pos, w=child: ElementInspector.show_inspector_menu(w, pos))

    @staticmethod
    def show_inspector_menu(widget: QWidget, pos):
        """Show context menu with copy element info action."""
        menu = QMenu(widget)
        inspect_action = QAction("🔍 Copy Element Info", menu)
        inspect_action.triggered.connect(lambda: ElementInspector.copy_element_info(widget))
        menu.addAction(inspect_action)
        menu.exec(widget.mapToGlobal(pos))

    @staticmethod
    def get_element_info(widget: QWidget) -> str:
        """Build formatted information string for a widget."""
        if widget is None:
            return "<None>"
        parts = []
        parts.append(f"Class: {widget.__class__.__name__}")
        name = widget.objectName()
        if name:
            parts.append(f"ObjectName: {name}")
        # Text if available
        if hasattr(widget, 'text') and callable(getattr(widget, 'text')):
            try:
                text_val = widget.text()
                if text_val:
                    parts.append(f"Text: {text_val}")
            except Exception:
                pass
        # Geometry
        try:
            g = widget.geometry()
            parts.append(f"Geometry: x={g.x()} y={g.y()} w={g.width()} h={g.height()}")
        except Exception:
            pass
        # Enabled / Visible
        parts.append(f"Enabled: {widget.isEnabled()}")
        parts.append(f"Visible: {widget.isVisible()}")
        # Parent chain (up to 3 levels)
        parent = widget.parentWidget()
        chain = []
        depth = 0
        while parent is not None and depth < 3:
            chain.append(parent.__class__.__name__)
            parent = parent.parentWidget()
            depth += 1
        if chain:
            parts.append("Parents: " + " > ".join(chain))
        return "\n".join(parts)

    @staticmethod
    def copy_element_info(widget: QWidget):
        """Copy widget info to clipboard and print for debug."""
        info = ElementInspector.get_element_info(widget)
        clipboard = QApplication.clipboard()
        clipboard.setText(info)
        print("\n📋 Element info copied to clipboard:\n" + info + "\n" + ("-" * 60))
