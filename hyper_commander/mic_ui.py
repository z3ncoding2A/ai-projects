import sys
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPainter, QColor, QPainterPath
import os
import time
import math

class MicOverlay(QWidget):
    def __init__(self):
        super().__init__()
        
        # Essential flags for a floating, non-tiling overlay
        self.setWindowFlags(
            Qt.FramelessWindowHint | 
            Qt.WindowStaysOnTopHint | 
            Qt.Tool | 
            Qt.WindowTransparentForInput |
            Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Exact title for Hyprland rules
        self.setWindowTitle("HyperCommanderMicUI")
        
        # 300x60 wide pill, matching hyprwhspr's default dimensions
        self.setFixedSize(300, 60)
        
        # For simple animation
        self.start_time = time.time()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(30)  # ~30 fps

    def showEvent(self, event):
        super().showEvent(event)
        
        # Move window via hyprctl immediately
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = screen.height() - self.height() - 40 # 40px margin from bottom
        
        import threading
        def move_window():
            import subprocess
            time.sleep(0.05)
            # Make sure it floats, pins, and moves to exact pixel coordinates
            subprocess.Popen(['hyprctl', 'dispatch', 'setfloating', 'title:^HyperCommanderMicUI$'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.Popen(['hyprctl', 'dispatch', 'pin', 'title:^HyperCommanderMicUI$'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.Popen(['hyprctl', 'dispatch', 'movewindowpixel', f'exact {x} {y},title:^HyperCommanderMicUI$'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
        threading.Thread(target=move_window, daemon=True).start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 1. Background (Dark rounded pill like hyprwhspr)
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), self.height() // 2, self.height() // 2)
        
        # Hyprwhspr uses a dark translucent background
        bg_color = QColor(30, 30, 30, 230)
        painter.fillPath(path, bg_color)
        
        # Subtle border
        pen = painter.pen()
        pen.setColor(QColor(100, 100, 100, 100))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawPath(path)
        
        # 2. Draw a simple animated "Waveform" or pulsing circle in the center
        # For simplicity and style, we draw an animated pulsing mic icon or dots
        elapsed = time.time() - self.start_time
        
        painter.setPen(Qt.NoPen)
        
        # Let's draw 5 pulsing dots
        dot_count = 5
        spacing = 20
        start_x = (self.width() - (dot_count - 1) * spacing) / 2
        cy = self.height() / 2
        
        for i in range(dot_count):
            # Pulse math
            pulse = math.sin(elapsed * 4 + i) * 0.5 + 0.5
            radius = 3 + pulse * 4
            
            # Bright cyan/blue accent color
            color = QColor(0, 255, 204)
            color.setAlpha(int(100 + pulse * 155))
            painter.setBrush(color)
            
            painter.drawEllipse(int(start_x + i * spacing - radius), int(cy - radius), int(radius * 2), int(radius * 2))

if __name__ == '__main__':
    app = QApplication(sys.argv)
    os.environ["QT_QPA_PLATFORM"] = "wayland;xcb"
    overlay = MicOverlay()
    overlay.show()
    sys.exit(app.exec_())
