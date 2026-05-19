#!/usr/bin/env python3
import sys
import os
from PyQt6.QtWidgets import QApplication, QLabel, QWidget
from PyQt6.QtCore import Qt

os.environ['QT_QPA_PLATFORM'] = 'xcb' # Try forcing XCB backend

if __name__ == '__main__':
    app = QApplication(sys.argv)

    window = QWidget()
    window.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
    window.setWindowTitle("Minimal PyQt6 Test")
    window.setGeometry(100, 100, 200, 50)

    label = QLabel("Hello World!", window)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setGeometry(0, 0, 200, 50)
    label.setStyleSheet("background-color: #333; color: white; border-radius: 10px;")

    window.show()

    sys.exit(app.exec())
