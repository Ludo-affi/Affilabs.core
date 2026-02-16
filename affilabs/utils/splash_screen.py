"""Modern animated splash screen for application startup.

This module provides a beautiful splash screen that appears instantly
before heavy module imports, giving immediate visual feedback to users.
"""

import math

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import (
    QPainter, QPixmap, QFont, QColor, QPen, QBrush,
    QLinearGradient, QRadialGradient, QPainterPath,
)
from PySide6.QtWidgets import QSplashScreen
from pathlib import Path

from affilabs.utils.resource_path import get_affilabs_resource


def _draw_protein_decorations(painter):
    """Draw stylized, semi-transparent molecular silhouettes as background art.

    Three structures relevant to SPR biosensing:
    - IgG antibody (Y-shape) on the left
    - Globular protein cluster on the upper right
    - DNA double helix segment on the lower right
    """
    painter.save()

    # --- 1. IgG Antibody (Y-shape) - left side ---
    ab_fill = QColor(120, 180, 255, 25)
    ab_edge = QColor(140, 200, 255, 40)
    cx, cy = 75, 185

    # Fc stem
    painter.setPen(QPen(ab_edge, 1.5))
    painter.setBrush(QBrush(ab_fill))
    stem = QPainterPath()
    stem.addRoundedRect(cx - 6, cy + 5, 12, 30, 4, 4)
    painter.drawPath(stem)

    # Hinge
    painter.drawEllipse(QPointF(cx, cy + 5), 5, 5)

    # Left Fab arm + binding site
    painter.setPen(QPen(ab_edge, 2.5))
    painter.setBrush(Qt.NoBrush)
    arm_l = QPainterPath()
    arm_l.moveTo(cx, cy + 5)
    arm_l.lineTo(cx - 22, cy - 25)
    painter.drawPath(arm_l)
    painter.setBrush(QBrush(QColor(150, 210, 255, 30)))
    painter.drawEllipse(QPointF(cx - 22, cy - 25), 7, 9)

    # Right Fab arm + binding site
    painter.setBrush(Qt.NoBrush)
    arm_r = QPainterPath()
    arm_r.moveTo(cx, cy + 5)
    arm_r.lineTo(cx + 22, cy - 25)
    painter.drawPath(arm_r)
    painter.setBrush(QBrush(QColor(150, 210, 255, 30)))
    painter.drawEllipse(QPointF(cx + 22, cy - 25), 7, 9)

    # --- 2. Globular Protein (BSA-like) - upper right ---
    glob_fill = QColor(180, 140, 255, 20)
    glob_edge = QColor(200, 160, 255, 35)
    painter.setPen(QPen(glob_edge, 1.0))
    painter.setBrush(QBrush(glob_fill))
    gx, gy = 630, 100
    for dx, dy, r in [
        (0, 0, 14), (-12, -8, 10), (10, -10, 11),
        (-10, 10, 9), (12, 8, 10), (0, -16, 8), (0, 15, 8),
    ]:
        painter.drawEllipse(QPointF(gx + dx, gy + dy), r, r)

    # --- 3. DNA Double Helix - lower right ---
    dna_edge1 = QColor(120, 240, 200, 40)
    dna_edge2 = QColor(255, 200, 140, 40)
    rung_color = QColor(200, 200, 255, 20)
    hx, hy = 645, 320
    helix_h, helix_w, n = 70, 16, 30

    strand1, strand2 = [], []
    for i in range(n):
        t = i / (n - 1)
        y = hy - helix_h / 2 + t * helix_h
        strand1.append(QPointF(hx + helix_w * math.sin(t * 3 * math.pi), y))
        strand2.append(QPointF(hx + helix_w * math.sin(t * 3 * math.pi + math.pi), y))

    painter.setBrush(Qt.NoBrush)
    for strand, color in [(strand1, dna_edge1), (strand2, dna_edge2)]:
        painter.setPen(QPen(color, 2.0))
        path = QPainterPath()
        path.moveTo(strand[0])
        for pt in strand[1:]:
            path.lineTo(pt)
        painter.drawPath(path)

    painter.setPen(QPen(rung_color, 1.0))
    for i in range(0, n, 4):
        painter.drawLine(strand1[i], strand2[i])

    painter.restore()


def create_splash_screen():
    """Create and return modern splash screen with update function.

    Returns:
        tuple: (splash, pixmap, update_function)
    """
    # Create splash screen with larger size and frameless
    splash = QSplashScreen()
    splash.setFixedSize(700, 400)

    # Create custom splash with modern design
    splash_pixmap = QPixmap(700, 400)
    splash_pixmap.fill(QColor(0, 0, 0, 0))  # Transparent

    painter = QPainter(splash_pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)

    # Main gradient - deep blue to purple
    gradient = QLinearGradient(0, 0, 700, 400)
    gradient.setColorAt(0, QColor(15, 32, 96))      # Deep navy blue
    gradient.setColorAt(0.5, QColor(32, 64, 128))   # Rich blue
    gradient.setColorAt(1, QColor(48, 25, 107))     # Deep purple

    # Draw rounded rectangle background
    painter.setPen(Qt.NoPen)
    painter.setBrush(QBrush(gradient))
    painter.drawRoundedRect(0, 0, 700, 400, 20, 20)

    # Add subtle glow effect
    radial = QRadialGradient(350, 200, 300)
    radial.setColorAt(0, QColor(100, 150, 255, 30))
    radial.setColorAt(1, QColor(0, 0, 0, 0))
    painter.setBrush(radial)
    painter.drawRoundedRect(0, 0, 700, 400, 20, 20)

    # Draw molecular decorations (IgG antibody, globular protein, DNA helix)
    _draw_protein_decorations(painter)

    # Try to load and draw icon
    try:
        icon_path = get_affilabs_resource("ui/img/affinite2.ico")
        if icon_path.exists():
            icon_pixmap = QPixmap(str(icon_path))
            # Draw icon at top left
            icon_size = 64
            painter.drawPixmap(20, 20, icon_size, icon_size, icon_pixmap)
    except Exception:
        pass  # Skip icon if not found

    # Draw title with modern font
    title_font = QFont("Segoe UI Light", 42, QFont.Thin)
    painter.setFont(title_font)
    painter.setPen(QColor(255, 255, 255, 255))
    painter.drawText(0, 130, 700, 70, Qt.AlignCenter, "AffiLabs.core")

    # Draw subtitle with accent color
    subtitle_font = QFont("Segoe UI", 14)
    painter.setFont(subtitle_font)
    painter.setPen(QColor(150, 200, 255, 230))
    painter.drawText(0, 200, 700, 30, Qt.AlignCenter, "Surface Plasmon Resonance Analysis")

    # Draw inspiring slogan
    slogan_font = QFont("Segoe UI", 13, QFont.Medium)
    painter.setFont(slogan_font)
    painter.setPen(QColor(255, 215, 100, 255))  # Gold accent for inspiration
    painter.drawText(0, 250, 700, 30, Qt.AlignCenter, "Where Light Meets Matter - Science Revealed")

    # Draw initial status message
    status_font = QFont("Segoe UI", 11)
    painter.setFont(status_font)
    painter.setPen(QColor(200, 220, 255, 200))
    painter.drawText(0, 310, 700, 30, Qt.AlignCenter, "Initializing...")

    # Draw version and copyright
    version_font = QFont("Segoe UI", 9)
    painter.setFont(version_font)
    painter.setPen(QColor(150, 180, 220, 150))
    painter.drawText(0, 360, 700, 20, Qt.AlignCenter, "Version 2.0.4  •  © 2026 Affinite Instruments")

    painter.end()

    splash.setPixmap(splash_pixmap)
    splash.setWindowFlags(Qt.SplashScreen | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)

    def update_splash(message: str, app=None):
        """Update splash screen message with smooth animation.

        Args:
            message: Status message to display
            app: QApplication instance for processEvents (optional)
        """
        if not splash.isVisible():
            return

        # Recreate pixmap with new message (optimized - reuse gradient)
        new_pixmap = QPixmap(700, 400)
        new_pixmap.fill(QColor(0, 0, 0, 0))

        painter = QPainter(new_pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        # Main gradient
        gradient = QLinearGradient(0, 0, 700, 400)
        gradient.setColorAt(0, QColor(15, 32, 96))
        gradient.setColorAt(0.5, QColor(32, 64, 128))
        gradient.setColorAt(1, QColor(48, 25, 107))

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(gradient))
        painter.drawRoundedRect(0, 0, 700, 400, 20, 20)

        # Glow effect
        radial = QRadialGradient(350, 200, 300)
        radial.setColorAt(0, QColor(100, 150, 255, 30))
        radial.setColorAt(1, QColor(0, 0, 0, 0))
        painter.setBrush(radial)
        painter.drawRoundedRect(0, 0, 700, 400, 20, 20)

        # Draw molecular decorations (IgG antibody, globular protein, DNA helix)
        _draw_protein_decorations(painter)

        # Icon
        try:
            icon_path = get_affilabs_resource("ui/img/affinite2.ico")
            if icon_path.exists():
                icon_pixmap = QPixmap(str(icon_path))
                painter.drawPixmap(20, 20, 64, 64, icon_pixmap)
        except Exception:
            pass

        # Title
        title_font = QFont("Segoe UI Light", 42, QFont.Thin)
        painter.setFont(title_font)
        painter.setPen(QColor(255, 255, 255, 255))
        painter.drawText(0, 130, 700, 70, Qt.AlignCenter, "AffiLabs.core")

        # Subtitle
        subtitle_font = QFont("Segoe UI", 14)
        painter.setFont(subtitle_font)
        painter.setPen(QColor(150, 200, 255, 230))
        painter.drawText(0, 200, 700, 30, Qt.AlignCenter, "Surface Plasmon Resonance Analysis")

        # Inspiring slogan
        slogan_font = QFont("Segoe UI", 13, QFont.Medium)
        painter.setFont(slogan_font)
        painter.setPen(QColor(255, 215, 100, 255))  # Gold accent for inspiration
        painter.drawText(0, 250, 700, 30, Qt.AlignCenter, "Where Light Meets Matter - Science Revealed")

        # Status message (UPDATED - highlighted)
        status_font = QFont("Segoe UI Semibold", 11, QFont.DemiBold)
        painter.setFont(status_font)
        painter.setPen(QColor(120, 220, 255, 255))  # Brighter for active status
        painter.drawText(0, 310, 700, 30, Qt.AlignCenter, message)

        # Version
        version_font = QFont("Segoe UI", 9)
        painter.setFont(version_font)
        painter.setPen(QColor(150, 180, 220, 150))
        painter.drawText(0, 360, 700, 20, Qt.AlignCenter, "Version 2.0.4  •  © 2026 Affinite Instruments")

        painter.end()

        splash.setPixmap(new_pixmap)

        # Process events to ensure splash updates
        if app:
            app.processEvents()

    return splash, splash_pixmap, update_splash
