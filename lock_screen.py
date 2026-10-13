"""
DreamUX Lock Screen — экран блокировки.
Показывается при старте GUI. Требует пароль аккаунта.

Ключевое:
  - show_fullscreen() перекрывает панель задач Windows через SetWindowPos.
  - Пароль берётся из users.json (уровень 0 = СИСТЕМА).
"""

import os
import json
import hashlib
import datetime
import getpass

from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QPoint
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame,
)


HERE = os.path.dirname(os.path.abspath(__file__))
KERNEL_DIR = os.path.dirname(os.path.dirname(HERE))
USERS_FILE = os.path.join(KERNEL_DIR, "users.json")


class LockScreen(QWidget):
    def __init__(self, on_unlock=None):
        super().__init__()
        self.on_unlock = on_unlock

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )

        try:
            from PyQt6.QtWidgets import QApplication
            screen = QApplication.primaryScreen().geometry()
            self.setGeometry(screen)
        except Exception:
            self.resize(1280, 800)

        self.setStyleSheet("background-color: #0a0a12;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Часы
        top = QVBoxLayout()
        top.setContentsMargins(0, 80, 0, 0)
        top.setSpacing(8)

        self.time_lbl = QLabel()
        self.time_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_lbl.setStyleSheet(
            "color: #ffffff; font-size: 72pt; font-weight: 200; "
            "letter-spacing: 4px;"
        )
        top.addWidget(self.time_lbl)

        self.date_lbl = QLabel()
        self.date_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.date_lbl.setStyleSheet(
            "color: #cccccc; font-size: 16pt; font-weight: 300;"
        )
        top.addWidget(self.date_lbl)

        layout.addLayout(top)
        layout.addStretch(1)

        # Центр
        center = QVBoxLayout()
        center.setSpacing(12)
        center.setAlignment(Qt.AlignmentFlag.AlignCenter)

        username = self._get_username()

        self.avatar_lbl = QLabel()
        self.avatar_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar_lbl.setFixedSize(100, 100)
        self.avatar_lbl.setStyleSheet(
            "font-size: 48pt; color: #ffffff; "
            "background-color: #3584e4; "
            "border-radius: 50px;"
        )
        self.avatar_lbl.setText(username[0].upper() if username else "?")
        center.addWidget(self.avatar_lbl, alignment=Qt.AlignmentFlag.AlignCenter)

        self.name_lbl = QLabel(username)
        self.name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_lbl.setStyleSheet(
            "color: #ffffff; font-size: 18pt; font-weight: 600;"
        )
        center.addWidget(self.name_lbl)

        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("Введите пароль...")
        self.password.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.password.setFixedWidth(320)
        self.password.setFixedHeight(44)
        self.password.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255,255,255,25);
                color: #ffffff;
                border: 2px solid rgba(255,255,255,60);
                border-radius: 10px;
                padding: 6px 12px;
                font-size: 14pt;
            }
            QLineEdit:focus {
                border: 2px solid #3584e4;
                background-color: rgba(255,255,255,40);
            }
        """)
        self.password.returnPressed.connect(self._try_unlock)
        center.addWidget(self.password, alignment=Qt.AlignmentFlag.AlignCenter)

        self.error_lbl = QLabel("")
        self.error_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_lbl.setStyleSheet(
            "color: #e01b24; font-size: 11pt; min-height: 20px;"
        )
        center.addWidget(self.error_lbl)

        btn = QPushButton("Войти")
        btn.setFixedWidth(320)
        btn.setFixedHeight(44)
        btn.setStyleSheet("""
            QPushButton {
                background-color: #3584e4;
                color: #ffffff;
                border: none;
                border-radius: 10px;
                font-size: 14pt;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #4a90e2; }
            QPushButton:pressed { background-color: #2c6fc7; }
        """)
        btn.clicked.connect(self._try_unlock)
        center.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addLayout(center)
        layout.addStretch(1)

        # Низ
        bottom = QHBoxLayout()
        bottom.setContentsMargins(40, 0, 40, 40)
        bottom.setSpacing(12)
        bottom.addStretch(1)

        for icon in ["🔄", "⏻"]:
            b = QPushButton(icon)
            b.setFixedSize(64, 64)
            b.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255,255,255,25);
                    color: #ffffff;
                    border: none;
                    border-radius: 32px;
                    font-size: 22pt;
                }
                QPushButton:hover {
                    background-color: rgba(255,255,255,50);
                }
            """)
            bottom.addWidget(b)

        layout.addLayout(bottom)

        self._tick()
        self.password.setFocus()

    def _get_username(self):
        if os.path.isfile(USERS_FILE):
            try:
                with open(USERS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for name, info in data.items():
                    if info.get("level") == 0:
                        return name
                if data:
                    return list(data.keys())[0]
            except Exception:
                pass
        return getpass.getuser()

    def _tick(self):
        now = datetime.datetime.now()
        self.time_lbl.setText(now.strftime("%H:%M"))
        self.date_lbl.setText(now.strftime("%A, %d %B %Y"))
        QTimer.singleShot(1000, self._tick)

    def _try_unlock(self):
        password = self.password.text()
        if not password:
            self.error_lbl.setText("Введите пароль")
            return

        if not os.path.isfile(USERS_FILE):
            if self.on_unlock:
                self.on_unlock(getpass.getuser())
            self.close()
            return

        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                users = json.load(f)
        except Exception as e:
            self.error_lbl.setText(f"Ошибка: {e}")
            return

        pwd_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()

        for name, info in users.items():
            if info.get("level") == 0:
                if info.get("password_hash") == pwd_hash:
                    if self.on_unlock:
                        self.on_unlock(name)
                    self.close()
                    return

        self.error_lbl.setText("Неверный пароль")
        self.password.clear()
        self.password.setFocus()
        self._shake()

    def _shake(self):
        try:
            original = self.pos()
            anim = QPropertyAnimation(self, b"pos", self)
            anim.setDuration(300)
            anim.setStartValue(original)
            anim.setKeyValueAt(0.25, QPoint(original.x() - 10, original.y()))
            anim.setKeyValueAt(0.50, QPoint(original.x() + 10, original.y()))
            anim.setKeyValueAt(0.75, QPoint(original.x() - 5, original.y()))
            anim.setEndValue(original)
            anim.start()
            self._shake_anim = anim
        except Exception:
            pass

    def show_fullscreen(self):
        """Fullscreen поверх всего, включая панель задач Windows."""
        # Флаги Qt
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )

        # Геометрия — весь экран
        try:
            from PyQt6.QtWidgets import QApplication
            screen = QApplication.primaryScreen().geometry()
            self.setGeometry(screen)
        except Exception:
            pass

        # Показ на весь экран
        self.showFullScreen()
        self.raise_()
        self.activateWindow()
        self.password.setFocus()

        # WinAPI — поверх панели задач
        if os.name == "nt":
            self._make_topmost_windows()
            # Повторный вызов через 100мс (для надёжности на медленных системах)
            QTimer.singleShot(100, self._make_topmost_windows)

    def _make_topmost_windows(self):
        """Жёстко поднимает окно поверх всех, включая панель задач."""
        try:
            import ctypes

            user32 = ctypes.windll.user32

            HWND_TOPMOST = -1
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_SHOWWINDOW = 0x0040

            hwnd = int(self.winId())
            user32.SetWindowPos(
                hwnd,
                HWND_TOPMOST,
                0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW,
            )
        except Exception as e:
            try:
                print(f"[LockScreen] WinAPI: {e}", flush=True)
            except Exception:
                pass
