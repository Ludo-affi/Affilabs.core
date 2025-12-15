"""Quick UI Dev Helpers - Speed up UI iteration with Copilot."""

from PySide6.QtWidgets import QWidget


class UIInspector:
    """Quick inspection and code generation for UI elements.
    Helps you rapidly iterate on UI layouts with Copilot.
    """

    @staticmethod
    def inspect_widget(widget: QWidget, name: str = "widget"):
        """Get current widget properties as copy-paste code.

        Usage in Python console or debug:
            from widgets.ui_dev_helpers import UIInspector
            UIInspector.inspect_widget(self.device_status_widget, "device_status")
        """
        code_lines = [
            f"# Current properties of {name}:",
            f"# Type: {type(widget).__name__}",
            f"# Object Name: {widget.objectName() or '(none)'}",
            f"# Position: ({widget.x()}, {widget.y()})",
            f"# Size: {widget.width()}x{widget.height()}",
            f"# Min Size: {widget.minimumWidth()}x{widget.minimumHeight()}",
            f"# Max Size: {widget.maximumWidth()}x{widget.maximumHeight()}",
            f"# Visible: {widget.isVisible()}",
            "",
            "# Apply these settings:",
            f"{name}.move({widget.x()}, {widget.y()})",
            f"{name}.setFixedSize({widget.width()}, {widget.height()})",
            "# OR",
            f"{name}.setGeometry({widget.x()}, {widget.y()}, {widget.width()}, {widget.height()})",
            "",
            "# Quick adjustments:",
            f"adjust.move_widget({name}, {widget.x()}, {widget.y()})",
            f"adjust.resize_widget({name}, {widget.width()}, {widget.height()})",
        ]

        output = "\n".join(code_lines)
        print(output)
        return output

    @staticmethod
    def inspect_layout(layout, name: str = "layout") -> str:
        """Get layout properties and child widgets."""
        code_lines = [
            f"# Layout: {name}",
            f"# Type: {type(layout).__name__}",
            f"# Spacing: {layout.spacing() if hasattr(layout, 'spacing') else 'N/A'}",
            f"# Margins: {layout.contentsMargins().left()}, {layout.contentsMargins().top()}, "
            f"{layout.contentsMargins().right()}, {layout.contentsMargins().bottom()}",
            "",
            "# Child widgets:",
        ]

        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item.widget():
                w = item.widget()
                code_lines.append(
                    f"#   [{i}] {type(w).__name__} - {w.objectName() or 'unnamed'}",
                )

        return "\n".join(code_lines)

    @staticmethod
    def compare_widgets(
        widget1: QWidget,
        widget2: QWidget,
        name1="widget1",
        name2="widget2",
    ) -> str:
        """Compare two widgets to see differences."""
        code_lines = [
            f"# Comparison: {name1} vs {name2}",
            "",
            f"Position: ({widget1.x()}, {widget1.y()}) vs ({widget2.x()}, {widget2.y()})",
            f"Size: {widget1.width()}x{widget1.height()} vs {widget2.width()}x{widget2.height()}",
            f"Visible: {widget1.isVisible()} vs {widget2.isVisible()}",
            f"Enabled: {widget1.isEnabled()} vs {widget2.isEnabled()}",
        ]

        return "\n".join(code_lines)


class QuickLayoutAdjuster:
    """Quick layout adjustments without dialog boxes.
    Call these methods directly to adjust UI elements.
    """

    @staticmethod
    def set_widget_geometry(widget: QWidget, x: int, y: int, width: int, height: int):
        """Set widget position and size in one call."""
        widget.setGeometry(x, y, width, height)
        print(f"✓ Widget geometry set to: ({x}, {y}, {width}x{height})")
        print(f"  Code: widget.setGeometry({x}, {y}, {width}, {height})")

    @staticmethod
    def move_widget(widget: QWidget, x: int, y: int):
        """Move widget to new position."""
        widget.move(x, y)
        print(f"✓ Widget moved to: ({x}, {y})")
        print(f"  Code: widget.move({x}, {y})")

    @staticmethod
    def resize_widget(widget: QWidget, width: int, height: int):
        """Resize widget."""
        widget.resize(width, height)
        print(f"✓ Widget resized to: {width}x{height}")
        print(f"  Code: widget.resize({width}, {height})")

    @staticmethod
    def set_fixed_size(widget: QWidget, width: int, height: int):
        """Set fixed size (prevents resizing)."""
        widget.setFixedSize(width, height)
        print(f"✓ Widget fixed size set to: {width}x{height}")
        print(f"  Code: widget.setFixedSize({width}, {height})")

    @staticmethod
    def set_min_size(widget: QWidget, width: int, height: int):
        """Set minimum size."""
        widget.setMinimumSize(width, height)
        print(f"✓ Widget minimum size set to: {width}x{height}")
        print(f"  Code: widget.setMinimumSize({width}, {height})")

    @staticmethod
    def set_layout_margins(layout, left: int, top: int, right: int, bottom: int):
        """Set layout margins."""
        layout.setContentsMargins(left, top, right, bottom)
        print(f"✓ Layout margins set to: ({left}, {top}, {right}, {bottom})")
        print(f"  Code: layout.setContentsMargins({left}, {top}, {right}, {bottom})")

    @staticmethod
    def set_layout_spacing(layout, spacing: int):
        """Set layout spacing between widgets."""
        layout.setSpacing(spacing)
        print(f"✓ Layout spacing set to: {spacing}")
        print(f"  Code: layout.setSpacing({spacing})")


# Quick access aliases
inspect = UIInspector.inspect_widget
inspect_layout = UIInspector.inspect_layout
compare = UIInspector.compare_widgets

adjust = QuickLayoutAdjuster()


def find_and_inspect(parent: QWidget, name: str):
    """Find a widget by name and inspect it in one step."""
    widget = find_widget_by_name(parent, name)
    if widget:
        inspect(widget, name)
    else:
        print(f"[ERROR] Widget '{name}' not found")
    return widget


def print_widget_tree(widget: QWidget, indent: int = 0):
    """Print widget hierarchy tree.
    Helpful for understanding UI structure.
    """
    name = widget.objectName() or type(widget).__name__
    visible = "👁" if widget.isVisible() else "[ERROR]"
    print("  " * indent + f"{visible} {name} - {widget.width()}x{widget.height()}")

    for child in widget.children():
        if isinstance(child, QWidget):
            print_widget_tree(child, indent + 1)


def find_widget_by_name(parent: QWidget, name: str) -> QWidget:
    """Find a widget by its objectName."""
    if parent.objectName() == name:
        return parent

    for child in parent.children():
        if isinstance(child, QWidget):
            result = find_widget_by_name(child, name)
            if result:
                return result

    return None


def get_all_widgets_of_type(parent: QWidget, widget_type: type) -> list:
    """Get all widgets of a specific type in the hierarchy."""
    result = []

    if isinstance(parent, widget_type):
        result.append(parent)

    for child in parent.children():
        if isinstance(child, QWidget):
            result.extend(get_all_widgets_of_type(child, widget_type))

    return result


# ============================================================================
# COPILOT WORKFLOW EXAMPLES
# ============================================================================

"""
WORKFLOW 1: Inspect and adjust a widget
========================================

# In Python console or add to your code temporarily:
from affilabs.widgets.ui_dev_helpers import inspect, adjust

# 1. See current state
print(inspect(self.device_status_widget, "device_status"))

# 2. Try adjustments interactively
adjust.move_widget(self.device_status_widget, 10, 50)
adjust.resize_widget(self.device_status_widget, 340, 300)

# 3. Copy the printed code into your source file


WORKFLOW 2: Find and modify a widget
=====================================

from affilabs.widgets.ui_dev_helpers import find_widget_by_name, adjust

# Find widget
my_widget = find_widget_by_name(self, "spr_frame")

# Inspect it
print(inspect(my_widget, "spr_frame"))

# Adjust it
adjust.set_fixed_size(my_widget, 300, 150)


WORKFLOW 3: Understand widget hierarchy
========================================

from affilabs.widgets.ui_dev_helpers import print_widget_tree

# Print entire tree
print_widget_tree(self.sidebar)

# This shows you:
# - All widgets in the hierarchy
# - Which ones are visible (👁) or hidden ([ERROR])
# - Their current sizes


WORKFLOW 4: Find all widgets of a type
=======================================

from affilabs.widgets.ui_dev_helpers import get_all_widgets_of_type
from PySide6.QtWidgets import QPushButton

# Find all buttons
buttons = get_all_widgets_of_type(self, QPushButton)
for btn in buttons:
    print(f"{btn.objectName()}: {btn.text()}")


WORKFLOW 5: Compare before/after
=================================

from affilabs.widgets.ui_dev_helpers import compare, adjust

# Store original state
original_x = widget.x()
original_y = widget.y()

# Try new position
adjust.move_widget(widget, 50, 100)

# See what changed
print(f"Moved from ({original_x}, {original_y}) to ({widget.x()}, {widget.y()})")


WORKFLOW 6: Batch adjustments
==============================

from affilabs.widgets.ui_dev_helpers import adjust

# Adjust multiple related elements
adjust.set_layout_spacing(self.main_layout, 8)
adjust.set_layout_margins(self.main_layout, 12, 12, 12, 12)
adjust.set_min_size(self.device_status_widget, 300, 200)

# All commands print code you can copy


WORKFLOW 7: Debug layout issues
================================

from affilabs.widgets.ui_dev_helpers import inspect_layout, print_widget_tree

# See what's in a layout
print(inspect_layout(self.main_layout, "main_layout"))

# See widget hierarchy
print_widget_tree(self.main_container)

# Find hidden widgets
from affilabs.widgets.ui_dev_helpers import get_all_widgets_of_type
all_widgets = get_all_widgets_of_type(self, QWidget)
hidden = [w for w in all_widgets if not w.isVisible()]
print(f"Hidden widgets: {[w.objectName() for w in hidden]}")
"""
