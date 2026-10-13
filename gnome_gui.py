#!/usr/bin/env python3
"""GNOME-подобный интерфейс DreamUX. Fullscreen."""

import os
import sys
import json
import shutil
import datetime

HERE = os.environ.get("SIMPLEOS_GNOME_DIR") or \
       os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.environ.get("SIMPLEOS_PLUGIN_DIR") or \
             os.path.dirname(HERE)
LOGS_ROOT = os.environ.get("SIMPLEOS_LOGS_DIR") or \
            os.path.join(HERE, "logs")
SCREENSHOTS_DIR = os.environ.get("SIMPLEOS_SCREENSHOTS_DIR") or \
                  os.path.join(HERE, "screenshots")
ASSETS_DIR = os.environ.get("SIMPLEOS_ASSETS_DIR") or \
             os.path.join(HERE, "assets")
KERNEL_DIR = os.path.dirname(PLUGIN_DIR)

VFS_ROOT = os.path.join(KERNEL_DIR, "vfs")
DISK_0 = os.path.join(VFS_ROOT, "disk0.vhd.data")
DISK_0_SYSTEM = os.path.join(DISK_0, "system")
DISK_0_BOOT   = os.path.join(DISK_0, "boot")
DISK_1 = os.path.join(VFS_ROOT, "disk1.vhd.data")

for _p in (HERE, PLUGIN_DIR):
    if _p and _p not in sys.path:
        sys.path.insert(0, _p)

for _p in (LOGS_ROOT, SCREENSHOTS_DIR, ASSETS_DIR):
    try:
        os.makedirs(_p, exist_ok=True)
    except Exception:
        pass


from PyQt6.QtCore import Qt, QTimer, QPoint, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import (
    QColor, QPainter, QLinearGradient, QShortcut, QKeySequence, QPixmap,
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QListWidget, QListWidgetItem,
    QGridLayout, QScrollArea, QSizePolicy, QLineEdit, QTextEdit,
    QGraphicsOpacityEffect, QStackedWidget, QFileDialog, QMessageBox,
    QTabWidget, QMenu, QInputDialog,
)


# ============================================================
# Логи
# ============================================================
LOG_FILES = {
    "actions": os.path.join(LOGS_ROOT, "actions.log"),
    "errors":  os.path.join(LOGS_ROOT, "errors.log"),
}


def log_write(category, level, message, **fields):
    path = LOG_FILES.get(category)
    if not path:
        return
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    extra = ""
    if fields:
        extra = "  " + "  ".join(f"{k}={v!r}" for k, v in fields.items())
    line = f"{ts}  [{level:<6}]  {message}{extra}\n"
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass
    try:
        print(f"[LOG/{category}] {line.rstrip()}", flush=True)
    except Exception:
        pass


def log_tail(category, n=200):
    p = LOG_FILES.get(category)
    if not p or not os.path.exists(p):
        return "(пусто)"
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            return "".join(f.readlines()[-n:])
    except Exception as e:
        return f"(ошибка: {e})"


# ============================================================
# Утилиты
# ============================================================
MAX_TEXT_SIZE = 2 * 1024 * 1024
MAX_HEX_SIZE = 512


def safe_read_text(path):
    try:
        size = os.path.getsize(path)
    except OSError:
        size = 0
    if size > MAX_TEXT_SIZE:
        return f"Файл слишком большой: {size:,} байт"
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read(MAX_TEXT_SIZE)
    except Exception as e:
        return f"Ошибка чтения: {e}"


def safe_read_bytes(path):
    try:
        with open(path, "rb") as f:
            return f.read(MAX_HEX_SIZE)
    except Exception:
        return b""


# ============================================================
# QSS
# ============================================================
ADWAITA_DARK_QSS = """
* { font-family: "Segoe UI", "Cantarell", "Ubuntu", sans-serif;
    font-size: 10pt; color: #ffffff; }
QMainWindow, QWidget { background-color: #1e1e1e; }
QFrame#Panel { background-color: #303030; border: none; }
QFrame#Dock { background-color: rgba(40,40,40,220); border-radius: 16px; }
QLabel#PanelLabel { color: #ffffff; padding: 0 6px; }
QLabel#PanelClock { color: #ffffff; padding: 0 10px; font-weight: 600; }
QPushButton#PanelButton { background: transparent; border: none;
    color: #ffffff; padding: 4px 10px; border-radius: 6px; }
QPushButton#PanelButton:hover { background-color: rgba(255,255,255,30); }
QPushButton#DockButton { background-color: rgba(255,255,255,20);
    border: none; border-radius: 12px; color: #ffffff;
    padding: 8px 4px; min-width: 56px; }
QPushButton#DockButton:hover { background-color: rgba(255,255,255,50); }
QFrame#Window { background-color: #242424; border: 2px solid #1a1a1a;
    border-radius: 12px; }
QFrame#HeaderBar { background-color: #303030;
    border-top-left-radius: 10px; border-top-right-radius: 10px;
    border-bottom: 1px solid #1a1a1a; }
QLabel#WindowTitle { color: #ffffff; font-weight: 600; padding: 6px; }
QPushButton#WinBtn { background: transparent; border: none;
    color: #cccccc; border-radius: 6px; padding: 4px 8px; font-weight: 700; }
QPushButton#WinBtn:hover { background-color: rgba(255,255,255,30); }
QPushButton#WinClose:hover { background-color: #e01b24; color: white; }
QListWidget#Sidebar { background-color: #1e1e1e; border: none;
    outline: 0; padding: 8px; }
QListWidget#Sidebar::item { padding: 8px 12px; border-radius: 8px;
    color: #dddddd; }
QListWidget#Sidebar::item:selected { background-color: #3584e4;
    color: #ffffff; }
QListWidget#Sidebar::item:hover { background-color: rgba(255,255,255,25); }
QLabel#H2 { font-size: 12pt; font-weight: 600; color: #ffffff; }
QLineEdit, QTextEdit { background-color: #1a1a1a;
    border: 1px solid #3a3a3a; border-radius: 6px; padding: 6px;
    color: #ffffff; selection-background-color: #3584e4; }
QLineEdit:focus, QTextEdit:focus { border: 1px solid #3584e4; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 4px; }
QScrollBar::handle:vertical { background: rgba(255,255,255,60);
    border-radius: 4px; min-height: 20px; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
QTabWidget::pane { border: 1px solid #303030; }
QTabBar::tab { background: #2a2a2a; color: #dddddd;
    padding: 6px 12px; border: none; }
QTabBar::tab:selected { background: #3584e4; color: white; }
"""

CONTEXT_MENU_QSS = """
QMenu {
    background-color: #2b2b2b;
    color: #ffffff;
    border-radius: 10px;
    padding: 6px;
    border: 1px solid #3a3a3a;
}
QMenu::item {
    padding: 8px 32px 8px 24px;
    border-radius: 6px;
}
QMenu::item:selected { background-color: #3584e4; }
QMenu::separator { height: 1px; background-color: #3a3a3a;
                    margin: 4px 8px; }
"""


# ============================================================
# Toast
# ============================================================
class Toast(QLabel):
    def __init__(self, parent, text, timeout_ms=2200):
        super().__init__(parent)
        self.setText(text)
        self.setStyleSheet(
            "QLabel { background-color: rgba(40,40,40,235); color: #fff; "
            "padding: 10px 16px; border-radius: 10px; "
            "border: 1px solid #1a1a1a; font-size: 10pt; }"
        )
        self.adjustSize()
        self.move(parent.width() - self.width() - 20, 50)
        self.raise_()
        self.show()
        eff = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(eff)
        anim = QPropertyAnimation(eff, b"opacity", self)
        anim.setDuration(400)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        anim.finished.connect(self.deleteLater)
        QTimer.singleShot(timeout_ms, anim.start)


# ============================================================
# Wallpaper
# ============================================================
class WallpaperWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.desktop = None

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        grad = QLinearGradient(0, 0, w, h)
        grad.setColorAt(0.0, QColor("#3a0a2a"))
        grad.setColorAt(0.5, QColor("#6b1a1a"))
        grad.setColorAt(1.0, QColor("#c04a1a"))
        p.fillRect(self.rect(), grad)
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(-3, 8):
            for j in range(-2, 6):
                x = i * 220 + j * 60
                y = j * 180
                a = 18 + (i * j) % 25
                if a < 0:
                    a = -a
                p.setBrush(QColor(255, 90, 30, a))
                p.drawPolygon(QPoint(x, y), QPoint(x + 180, y + 40),
                              QPoint(x + 140, y + 180), QPoint(x - 40, y + 140))

    def contextMenuEvent(self, event):
        if self.desktop:
            self.desktop._show_desktop_menu(event.globalPos())


# ============================================================
# TopPanel
# ============================================================
class TopPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Panel")
        self.setFixedHeight(32)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 0, 8, 0)
        lay.setSpacing(4)
        b = QPushButton("Activities")
        b.setObjectName("PanelButton")
        lay.addWidget(b)
        lbl = QLabel("DreamUX")
        lbl.setObjectName("PanelLabel")
        lbl.setStyleSheet("font-weight: 700;")
        lay.addWidget(lbl)
        lay.addStretch()
        self.clock = QLabel()
        self.clock.setObjectName("PanelClock")
        lay.addWidget(self.clock)
        self._tick()
        lay.addStretch()
        for ic in ["🖧", "🔊", "🔋", "⏻"]:
            b = QPushButton(ic)
            b.setObjectName("PanelButton")
            lay.addWidget(b)

    def _tick(self):
        self.clock.setText(datetime.datetime.now().strftime("%a %H:%M"))
        QTimer.singleShot(1000, self._tick)


# ============================================================
# Dock
# ============================================================
class Dock(QFrame):
    def __init__(self, desktop, parent=None):
        super().__init__(parent)
        self.desktop = desktop
        self.setObjectName("Dock")
        self.setFixedHeight(74)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(6)
        apps = [
            ("📁", "Files",      desktop.open_files),
            ("📦", "Installers", desktop.open_installers),
            ("🌐", "Browser",    desktop.open_browser),
            ("🎮", "Games",      desktop.open_games),
            ("🛡", "AV",         desktop.open_av),
            ("🔒", "VPN",        desktop.open_vpn),
            ("▶",  "Terminal",   desktop.open_terminal),
            ("🕒", "Clocks",     desktop.open_clocks),
            ("⚙",  "Settings",   desktop.open_settings),
            ("🧰", "Remote",     desktop.open_remote),
            ("ℹ",  "About",      desktop.open_about),
        ]
        for icon, name, cb in apps:
            b = QPushButton(f"{icon}\n{name}")
            b.setObjectName("DockButton")
            b.clicked.connect(cb)
            lay.addWidget(b)


# ============================================================
# GnomeWindow
# ============================================================
class GnomeWindow(QFrame):
    def __init__(self, desktop, title, w=560, h=400, x=120, y=100):
        super().__init__(desktop.wallpaper)
        self.desktop = desktop
        self.setObjectName("Window")
        self.resize(w, h)
        self.move(x, y)
        self.show()
        self.raise_()

        self._drag = None
        if not hasattr(desktop, "windows"):
            desktop.windows = []
        desktop.windows.append(self)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        hb = QFrame()
        hb.setObjectName("HeaderBar")
        hb.setFixedHeight(40)
        hl = QHBoxLayout(hb)
        hl.setContentsMargins(8, 4, 8, 4)
        hl.setSpacing(6)
        t = QLabel(title)
        t.setObjectName("WindowTitle")
        hl.addWidget(t)
        hl.addStretch()

        bmin = QPushButton("—")
        bmin.setObjectName("WinBtn")
        bmin.clicked.connect(self.hide)
        hl.addWidget(bmin)

        bclose = QPushButton("✕")
        bclose.setObjectName("WinClose")
        bclose.setProperty("class", "WinBtn")
        bclose.clicked.connect(self.close)
        hl.addWidget(bclose)

        outer.addWidget(hb)

        self.body = QFrame()
        self.body.setStyleSheet("background: transparent;")
        self.body_lay = QVBoxLayout(self.body)
        self.body_lay.setContentsMargins(12, 12, 12, 12)
        self.body_lay.setSpacing(8)
        outer.addWidget(self.body, 1)

        hb.mousePressEvent = self._sd
        hb.mouseMoveEvent = self._md
        hb.mouseReleaseEvent = self._ed

    def _sd(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag = e.globalPosition().toPoint() - self.pos()
            self.raise_()

    def _md(self, e):
        if self._drag is not None:
            self.move(e.globalPosition().toPoint() - self._drag)

    def _ed(self, e):
        self._drag
