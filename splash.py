"""Заставка DreamUX при запуске GUI."""

import os
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRect
from PyQt6.QtGui import QPixmap, QPainter, QColor
from PyQt6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout,
)


HERE = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(HERE, "assets", "dreamux.png")


class SplashScreen(QWidget):
    """Заставка: тёмный фон, логотип DreamUX по центру, плавное появление/исчезновение."""

    def __init__(self, on_finished=None, duration_ms=2500):
        super().__init__()
        self._on_finished = on_finished
        self._duration_ms = duration_ms

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.SplashScreen
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Размер окна под экран
        screen = None
        try:
            from PyQt6.QtWidgets import QApplication
            screen = QApplication.primaryScreen().availableGeometry()
        except Exception:
            pass

        w = min(720, (screen.width() if screen else 720) - 80)
        h = min(540, (screen.height() if screen else 540) - 80)
        if screen:
            x = screen.x() + (screen.width() - w) // 2
            y = screen.y() + (screen.height() - h) // 2
        else:
            x, y = 200, 200
        self.setGeometry(x, y, w, h)

        # Контейнер
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(16)

        # Логотип
        self.logo = QLabel()
        self.logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if os.path.isfile(LOGO_PATH):
            pix = QPixmap(LOGO_PATH)
            if not pix.isNull():
                pix = pix.scaledToWidth(
                    int(w * 0.75),
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.logo.setPixmap(pix)
        if self.logo.pixmap() is None or self.logo.pixmap().isNull():
            self.logo.setText("DreamUX")
            self.logo.setStyleSheet(
                "color: #ffffff; font-size: 48pt; font-weight: 700; "
                "letter-spacing: 4px;"
            )
        layout.addWidget(self.logo, 1)

        # Подпись
        subtitle = QLabel("IDEAS INTO EXPERIENCES")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet(
            "color: #9a9a9a; font-size: 11pt; "
            "letter-spacing: 6px; font-weight: 300;"
        )
        layout.addWidget(subtitle)

        # Прогресс-полоска
        self.bar = QWidget(self)
        self.bar.setStyleSheet(
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            "stop:0 #3a7bfb, stop:1 #a25af5); border-radius: 2px;"
        )
        self.bar.setFixedHeight(3)
        self.bar.setGeometry(40, h - 30, 0, 3)
        self._bar_full_width = w - 80

        # Анимации
        self.setWindowOpacity(0.0)
        self._fade_in = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_in.setDuration(500)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)
        self._fade_in.setEasingCurve(QEasingCurve.Type.InOutQuad)

        self._fade_out = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_out.setDuration(500)
        self._fade_out.setStartValue(1.0)
        self._fade_out.setEndValue(0.0)
        self._fade_out.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._fade_out.finished.connect(self._finish)

        self._bar_anim = QPropertyAnimation(self.bar, b"geometry", self)
        self._bar_anim.setDuration(duration_ms)
        self._bar_anim.setStartValue(QRect(40, h - 30, 0, 3))
        self._bar_anim.setEndValue(QRect(40, h - 30, self._bar_full_width, 3))
        self._bar_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(20, 20, 28, 245))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(self.rect(), 16, 16)

    def start(self):
        self.show()
        self.raise_()
        self.activateWindow()
        self._fade_in.start()
        self._bar_anim.start()
        QTimer.singleShot(self._duration_ms + 400, self._fade_out.start)

    def _finish(self):
        self.close()
        if self._on_finished:
            self._on_finished()
