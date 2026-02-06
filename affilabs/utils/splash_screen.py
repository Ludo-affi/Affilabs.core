"""Modern animated splash screen for application startup.

This module provides a beautiful splash screen that appears instantly
before heavy module imports, giving immediate visual feedback to users.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPixmap, QFont, QColor, QPen, QBrush
from PySide6.QtWidgets import QSplashScreen
from pathlib import Path


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
    
    # Draw modern gradient background with rounded corners
    from PySide6.QtGui import QLinearGradient, QRadialGradient
    from PySide6.QtCore import QRectF
    
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
    
    # Draw outer border - subtle shine
    painter.setPen(QPen(QColor(100, 150, 255, 80), 2))
    painter.setBrush(Qt.NoBrush)
    painter.drawRoundedRect(1, 1, 698, 398, 20, 20)
    
    # Try to load and draw icon
    try:
        icon_path = Path(__file__).parent.parent / "ui" / "img" / "affinite2.ico"
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
    painter.drawText(0, 360, 700, 20, Qt.AlignCenter, "Version 2.0  •  © 2026 Affinite Instruments")
    
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
        from PySide6.QtGui import QLinearGradient, QRadialGradient
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
        
        # Border
        painter.setPen(QPen(QColor(100, 150, 255, 80), 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(1, 1, 698, 398, 20, 20)
        
        # Title
        title_font = QFont("Segoe UI", 28, QFont.Bold)
        painter.setFont(title_font)
        painter.setPen(QColor(20, 80, 150))
        painter.drawText(0, 80, 600, 60, Qt.AlignCenter, "AffiLabs.core")
        
        # Icon
        try:
            icon_path = Path(__file__).parent.parent / "ui" / "img" / "affinite2.ico"
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
        painter.drawText(0, 360, 700, 20, Qt.AlignCenter, "Version 2.0  •  © 2026 Affinite Instruments")
        
        painter.end()
        
        splash.setPixmap(new_pixmap)
        
        # Process events to ensure splash updates
        if app:
            app.processEvents()
    
    return splash, splash_pixmap, update_splash
