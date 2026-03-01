"""Modern animated splash screen for application startup.

This module provides a beautiful splash screen that appears instantly
before heavy module imports, giving immediate visual feedback to users.
Features SVG-based loading indicators and molecular visualizations.
"""

import math
import time

from PySide6.QtCore import Qt, QPointF, QTimer
from PySide6.QtGui import (
    QPainter, QPixmap, QFont, QColor, QPen, QBrush,
    QLinearGradient, QRadialGradient, QPainterPath,
)
from PySide6.QtWidgets import QSplashScreen
from pathlib import Path

from affilabs.utils.resource_path import get_affilabs_resource


def _draw_svg_loading_spinner(painter, x, y, size, rotation):
    """Draw an SVG-style animated loading spinner.
    
    Args:
        painter: QPainter instance
        x, y: Center position
        size: Diameter of spinner
        rotation: Rotation angle in degrees (0-360)
    """
    painter.save()
    painter.translate(x, y)
    painter.rotate(rotation)
    painter.translate(-x, -y)
    
    # Outer ring
    ring_pen = QPen(QColor(100, 180, 255, 200))
    ring_pen.setWidth(3)
    ring_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(ring_pen)
    painter.setBrush(Qt.NoBrush)
    
    # Draw arc (3/4 of circle)
    arc_rect = (x - size // 2, y - size // 2, size, size)
    painter.drawArc(*arc_rect, 0, 270 * 16)
    
    # Inner glow
    glow_pen = QPen(QColor(150, 210, 255, 80))
    glow_pen.setWidth(1)
    painter.setPen(glow_pen)
    inner_size = size - 8
    painter.drawEllipse(x - inner_size // 2, y - inner_size // 2, inner_size, inner_size)
    
    painter.restore()





def _draw_sparq_robot(painter, cx, cy, size=56):
    """Draw the Sparq AI robot face, matching sparq_icon.svg geometry.

    The SVG is a 24×24 design scaled to `size` px, centred at (cx, cy).
    Rendered in soft orange (#FF9500) with a translucent glow behind it.

    SVG geometry (scaled by factor = size / 24):
      head  : rounded rect x=5,y=6 w=14 h=12 rx=2
      eye L : circle cx=9,cy=10 r=1.5
      eye R : circle cx=15,cy=10 r=1.5
      mouth : line x1=9,y1=14 x2=15,y2=14
      ears  : left  line x=3,y=10..14   right line x=21,y=10..14
    """
    painter.save()

    scale = size / 24.0
    ox = cx - size / 2   # top-left origin of the 24×24 grid
    oy = cy - size / 2

    def sx(v): return ox + v * scale
    def sy(v): return oy + v * scale
    def ss(v): return v * scale

    orange = QColor(255, 149, 0, 210)     # #FF9500 at 82% opacity
    glow_c = QColor(255, 149, 0, 40)

    # --- glow halo ---
    radial = QRadialGradient(cx, cy, size * 0.75)
    radial.setColorAt(0, glow_c)
    radial.setColorAt(1, QColor(0, 0, 0, 0))
    painter.setPen(Qt.NoPen)
    painter.setBrush(QBrush(radial))
    painter.drawEllipse(int(cx - size), int(cy - size), int(size * 2), int(size * 2))

    pen = QPen(orange, max(1.0, scale * 1.25))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)

    # --- head (rounded rect) ---
    painter.setBrush(Qt.NoBrush)
    painter.setPen(pen)
    painter.drawRoundedRect(
        int(sx(5)), int(sy(6)), int(ss(14)), int(ss(12)),
        ss(2), ss(2)
    )

    # --- eyes (filled circles) ---
    painter.setBrush(QBrush(orange))
    painter.setPen(Qt.NoPen)
    r = max(1.5, ss(1.5))
    painter.drawEllipse(QPointF(sx(9), sy(10)), r, r)
    painter.drawEllipse(QPointF(sx(15), sy(10)), r, r)

    # --- mouth ---
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    painter.drawLine(QPointF(sx(9), sy(14)), QPointF(sx(15), sy(14)))

    # --- antenna ears (side lines) ---
    painter.drawLine(QPointF(sx(3), sy(10)), QPointF(sx(3), sy(14)))
    painter.drawLine(QPointF(sx(21), sy(10)), QPointF(sx(21), sy(14)))

    painter.restore()


def _draw_svg_logo_badge(painter, x, y, size):
    """Draw a professional badge-style logo using SVG-inspired drawing.
    
    Args:
        painter: QPainter instance
        x, y: Position
        size: Size of badge
    """
    painter.save()
    
    # Outer circle with gradient
    radial = QRadialGradient(x, y, size // 2)
    radial.setColorAt(0, QColor(150, 200, 255, 60))
    radial.setColorAt(1, QColor(100, 150, 255, 20))
    
    painter.setPen(QPen(QColor(120, 180, 255, 100), 1))
    painter.setBrush(QBrush(radial))
    painter.drawEllipse(x - size // 2, y - size // 2, size, size)
    
    # Inner circle with "A" letter (Affinite badge)
    inner_size = int(size * 0.6)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(QColor(100, 180, 255, 80)))
    painter.drawEllipse(x - inner_size // 2, y - inner_size // 2, inner_size, inner_size)
    
    # Draw stylized "A"
    font = QFont("Segoe UI", size // 4, QFont.Weight.Bold)
    painter.setFont(font)
    painter.setPen(QColor(200, 230, 255, 200))
    painter.drawText(x - size // 2, y - size // 2, size, size, 
                    Qt.AlignmentFlag.AlignCenter, "A")
    
    painter.restore()


def _draw_protein_decorations(painter):
    """Draw stylized, semi-transparent molecular silhouettes as background art.

    Three structures relevant to SPR biosensing:
    - IgG antibody (Y-shape) on the left
    - Globular protein cluster on the upper right
    - DNA double helix segment on the lower right
    """
    painter.save()

    # --- 1. IgG Antibody (Molecular Model Style) - left side ---
    painter.setRenderHint(QPainter.Antialiasing)
    
    cx, cy = 75, 185
    
    # Draw connectors first (so they appear behind spheres)
    connector_pen = QPen(QColor(100, 180, 255, 40), 1.5)
    painter.setPen(connector_pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    
    # Left Fab arm connector
    painter.drawLine(cx, cy, cx - 25, cy - 30)
    # Right Fab arm connector
    painter.drawLine(cx, cy, cx + 25, cy - 30)
    
    # --- Fc Region (large central sphere) ---
    fc_radius = 12
    fc_gradient = QRadialGradient(cx, cy + 10, fc_radius)
    fc_gradient.setColorAt(0, QColor(120, 200, 255, 50))
    fc_gradient.setColorAt(1, QColor(80, 160, 255, 25))
    painter.setPen(QPen(QColor(100, 180, 255, 70), 1))
    painter.setBrush(QBrush(fc_gradient))
    painter.drawEllipse(cx - fc_radius, cy - fc_radius + 10, fc_radius * 2, fc_radius * 2)
    
    # --- Hinge Region (connecting spheres) ---
    painter.setPen(QPen(QColor(130, 210, 255, 80), 1))
    hinge_gradient = QRadialGradient(cx, cy - 5, 4)
    hinge_gradient.setColorAt(0, QColor(150, 220, 255, 60))
    hinge_gradient.setColorAt(1, QColor(100, 190, 255, 30))
    painter.setBrush(QBrush(hinge_gradient))
    painter.drawEllipse(cx - 4, cy - 9, 8, 8)
    
    # --- LEFT FAB ARM (Fragment Antigen Binding) ---
    # Constant domain (Fc-like)
    left_fc_x, left_fc_y = cx - 20, cy - 18
    fc_gradient_l = QRadialGradient(left_fc_x, left_fc_y, 8)
    fc_gradient_l.setColorAt(0, QColor(120, 200, 255, 50))
    fc_gradient_l.setColorAt(1, QColor(80, 160, 255, 25))
    painter.setPen(QPen(QColor(100, 180, 255, 60), 1))
    painter.setBrush(QBrush(fc_gradient_l))
    painter.drawEllipse(left_fc_x - 8, left_fc_y - 8, 16, 16)
    
    # Variable domain 1 (Vl)
    vl_x, vl_y = cx - 28, cy - 32
    var_gradient = QRadialGradient(vl_x, vl_y, 6)
    var_gradient.setColorAt(0, QColor(150, 220, 255, 70))
    var_gradient.setColorAt(1, QColor(100, 190, 255, 35))
    painter.setPen(QPen(QColor(130, 210, 255, 70), 1))
    painter.setBrush(QBrush(var_gradient))
    painter.drawEllipse(vl_x - 6, vl_y - 6, 12, 12)
    
    # Variable domain 2 (Vh)
    vh_x, vh_y = cx - 23, cy - 38
    painter.setBrush(QBrush(var_gradient))
    painter.drawEllipse(vh_x - 6, vh_y - 6, 12, 12)
    
    # --- RIGHT FAB ARM (mirrored) ---
    # Constant domain
    right_fc_x, right_fc_y = cx + 20, cy - 18
    painter.setPen(QPen(QColor(100, 180, 255, 60), 1))
    painter.setBrush(QBrush(fc_gradient_l))
    painter.drawEllipse(right_fc_x - 8, right_fc_y - 8, 16, 16)
    
    # Variable domain 1
    vl_x_r, vl_y_r = cx + 28, cy - 32
    painter.setPen(QPen(QColor(130, 210, 255, 70), 1))
    painter.setBrush(QBrush(var_gradient))
    painter.drawEllipse(vl_x_r - 6, vl_y_r - 6, 12, 12)
    
    # Variable domain 2
    vh_x_r, vh_y_r = cx + 23, cy - 38
    painter.setBrush(QBrush(var_gradient))
    painter.drawEllipse(vh_x_r - 6, vh_y_r - 6, 12, 12)
    
    # --- 2. Protein Structure (BSA tertiary/quaternary) - upper right ---
    gx, gy = 630, 100
    
    # Draw interconnected subunits with SVG-style gradient fill
    subunits = [
        (0, 0, 16, QColor(180, 140, 255, 30)),      # Large central
        (-15, -12, 12, QColor(200, 150, 255, 25)),  # Top left
        (14, -14, 11, QColor(200, 160, 255, 28)),   # Top right
        (-16, 12, 10, QColor(190, 130, 255, 26)),   # Bottom left
        (15, 10, 11, QColor(210, 170, 255, 27)),    # Bottom right
        (0, -22, 8, QColor(180, 140, 255, 22)),     # Top cap
        (0, 20, 8, QColor(190, 150, 255, 24)),      # Bottom cap
    ]
    
    for dx, dy, radius, color in subunits:
        # Draw subunit with subtle gradient
        radial = QRadialGradient(gx + dx, gy + dy, radius // 2)
        radial.setColorAt(0, color)
        radial.setColorAt(1, QColor(color.red() - 30, color.green() - 30, color.blue() - 30, color.alpha() // 2))
        
        painter.setPen(QPen(QColor(160, 120, 255, 50), 1))
        painter.setBrush(QBrush(radial))
        painter.drawEllipse(gx + dx - radius, gy + dy - radius, radius * 2, radius * 2)

    # --- 3. DNA Double Helix - lower right, enhanced ---
    hx, hy = 645, 320
    helix_h, helix_w, n = 75, 20, 32
    
    # Calculate strand positions
    strand1, strand2 = [], []
    for i in range(n):
        t = i / (n - 1)
        y = hy - helix_h / 2 + t * helix_h
        strand1.append(QPointF(hx + helix_w * math.sin(t * 3.5 * math.pi), y))
        strand2.append(QPointF(hx + helix_w * math.sin(t * 3.5 * math.pi + math.pi), y))
    
    # Draw strands with gradient colors
    painter.setBrush(Qt.BrushStyle.NoBrush)
    for strand_idx, (strand, base_color) in enumerate([
        (strand1, QColor(100, 220, 200, 60)),  # Cyan
        (strand2, QColor(255, 180, 100, 60))   # Orange
    ]):
        painter.setPen(QPen(base_color, 2.5))
        path = QPainterPath()
        path.moveTo(strand[0])
        for pt in strand[1:]:
            path.lineTo(pt)
        painter.drawPath(path)
    
    # Draw base pair connections (rungs)
    painter.setPen(QPen(QColor(150, 200, 255, 40), 1.5))
    for i in range(0, n, 5):
        # Draw rung with slight curve
        rung = QPainterPath()
        rung.moveTo(strand1[i])
        rung.quadTo(
            (strand1[i].x() + strand2[i].x()) / 2,
            (strand1[i].y() + strand2[i].y()) / 2 - 2,
            strand2[i].x(),
            strand2[i].y()
        )
        painter.drawPath(rung)
    
    # Add base pair nucleotides (small circles)
    painter.setPen(QPen(QColor(200, 220, 255, 50), 0.5))
    painter.setBrush(QBrush(QColor(150, 200, 255, 30)))
    for i in range(0, n, 6):
        painter.drawEllipse(strand1[i].x() - 2, strand1[i].y() - 2, 4, 4)
        painter.drawEllipse(strand2[i].x() - 2, strand2[i].y() - 2, 4, 4)

    painter.restore()


def create_splash_screen():
    """Create and return modern splash screen with SVG elements and animation.

    Returns:
        tuple: (splash, pixmap, update_function)
    """
    # Create splash screen with larger size and frameless
    splash = QSplashScreen()
    splash.setFixedSize(700, 420)
    
    # Track animation state for loading spinner
    splash._animation_frame = 0
    splash._start_time = time.time()

    def _draw_main_content(message="Initializing..."):
        """Helper to draw splash content with animation."""
        # Create custom splash with modern design
        splash_pixmap = QPixmap(700, 420)
        splash_pixmap.fill(QColor(0, 0, 0, 0))  # Transparent

        painter = QPainter(splash_pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        # Main gradient - deep blue to purple with more depth
        gradient = QLinearGradient(0, 0, 700, 420)
        gradient.setColorAt(0, QColor(12, 25, 80))       # Deep navy
        gradient.setColorAt(0.4, QColor(28, 50, 120))    # Rich blue
        gradient.setColorAt(0.7, QColor(40, 35, 100))    # Blue-purple
        gradient.setColorAt(1, QColor(45, 20, 100))      # Deep purple

        # Draw rounded rectangle background
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(gradient))
        painter.drawRoundedRect(0, 0, 700, 420, 20, 20)

        # Add animated glow effect (pulsing)
        elapsed = (time.time() - splash._start_time) % 2.0
        pulse = 0.5 + 0.5 * math.sin(elapsed * math.pi)
        radial = QRadialGradient(350, 210, 350)
        radial.setColorAt(0, QColor(100, 150, 255, int(40 * pulse)))
        radial.setColorAt(1, QColor(0, 0, 0, 0))
        painter.setBrush(radial)
        painter.drawRoundedRect(0, 0, 700, 420, 20, 20)

        # Draw molecular decorations (IgG antibody, globular protein, DNA helix)
        _draw_protein_decorations(painter)

        # Sparq AI branding — bottom-left corner
        _draw_sparq_robot(painter, cx=52, cy=360, size=52)
        sparq_font = QFont("Segoe UI", 9)
        painter.setFont(sparq_font)
        painter.setPen(QColor(255, 149, 0, 180))
        painter.drawText(10, 382, 84, 20, Qt.AlignCenter, "Sparq AI")

        # Try to load and draw icon
        try:
            icon_path = get_affilabs_resource("ui/img/affinite2.ico")
            if icon_path.exists():
                icon_pixmap = QPixmap(str(icon_path))
                # Draw icon at top left with SVG-style badge glow
                _draw_svg_logo_badge(painter, 45, 45, 50)
                painter.drawPixmap(20, 20, 50, 50, icon_pixmap)
        except Exception:
            # Fallback: draw just the badge
            _draw_svg_logo_badge(painter, 45, 45, 50)

        # Draw title with modern font
        title_font = QFont("Segoe UI Light", 44, QFont.Thin)
        painter.setFont(title_font)
        painter.setPen(QColor(255, 255, 255, 255))
        painter.drawText(0, 125, 700, 70, Qt.AlignCenter, "AffiLabs.core")

        # Draw subtitle with accent color
        subtitle_font = QFont("Segoe UI", 13)
        painter.setFont(subtitle_font)
        painter.setPen(QColor(150, 200, 255, 230))
        painter.drawText(0, 195, 700, 30, Qt.AlignCenter, "Label-Free SPR · No Labels. Just Science.")

        # Draw inspiring slogan with glow effect
        slogan_font = QFont("Segoe UI", 12, QFont.Medium)
        painter.setFont(slogan_font)
        painter.setPen(QColor(255, 215, 100, 200))
        painter.drawText(0, 235, 700, 25, Qt.AlignCenter, "Real-time binding kinetics, simplified.")

        # Draw animated loading spinner
        rotation = (splash._animation_frame * 6) % 360
        _draw_svg_loading_spinner(painter, 350, 310, 28, rotation)

        # Draw status message with highlight
        status_font = QFont("Segoe UI Semibold", 11, QFont.DemiBold)
        painter.setFont(status_font)
        painter.setPen(QColor(120, 220, 255, 255))
        painter.drawText(0, 335, 700, 30, Qt.AlignCenter, message)

        # Draw version and copyright
        version_font = QFont("Segoe UI", 9)
        painter.setFont(version_font)
        painter.setPen(QColor(150, 180, 220, 150))
        try:
            from version import __version__
            _ver = __version__
        except Exception:
            _ver = ""
        _ver_str = f"Version {_ver}  •  © 2026 Affinite Instruments" if _ver else "© 2026 Affinite Instruments"
        painter.drawText(0, 375, 700, 20, Qt.AlignCenter, _ver_str)
        
        # Draw footer accent line
        painter.setPen(QPen(QColor(100, 150, 255, 100), 1))
        painter.drawLine(100, 405, 600, 405)

        painter.end()
        
        return splash_pixmap

    splash_pixmap = _draw_main_content()
    splash.setPixmap(splash_pixmap)
    splash.setWindowFlags(Qt.SplashScreen | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
    
    # Setup animation timer
    animation_timer = QTimer()
    def _animate():
        splash._animation_frame += 1
        if splash.isVisible():
            splash.setPixmap(_draw_main_content("Initializing..."))
    animation_timer.timeout.connect(_animate)
    animation_timer.start(50)  # Update every 50ms for smooth 20fps animation

    def update_splash(message: str, app=None):
        """Update splash screen message with animation.

        Args:
            message: Status message to display
            app: QApplication instance for processEvents (optional)
        """
        if not splash.isVisible():
            return

        splash_pixmap = _draw_main_content(message)
        splash.setPixmap(splash_pixmap)

        # Process events to ensure splash updates
        if app:
            app.processEvents()
    
    # Store timer reference to prevent garbage collection
    splash._animation_timer = animation_timer

    return splash, splash_pixmap, update_splash
