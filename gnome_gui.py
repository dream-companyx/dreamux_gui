#!/usr/bin/env python3
"""GNOME-подобный интерфейс на PyQt6 с песочницей, логами и скриншотами."""

import os
import sys
import json
import string
import platform
import datetime
import shutil

from PyQt6.QtCore import (
    Qt, QTimer, QPoint, QPropertyAnimation, QEasingCurve,
)
from PyQt6.QtGui import (
    QColor, QPainter, QLinearGradient, QShortcut, QKeySequence, QPixmap,
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QListWidget, QListWidgetItem,
    QGridLayout, QScrollArea, QSizePolicy, QLineEdit, QTextEdit,
    QGraphicsOpacityEffect, QStackedWidget, QFileDialog, QMessageBox,
    QTabWidget, QCheckBox,
)

# --- Пути ---
HERE = os.path.dirname(os.path.abspath(__file__))
KERNEL_DIR = os.path.dirname(HERE)
SANDBOX_ROOT = os.path.join(KERNEL_DIR, "sandbox")
LOGS_ROOT = os.path.join(KERNEL_DIR, "logs")
SCREENSHOTS_DIR = os.path.join(HERE, "screenshots")
sys.path.insert(0, os.path.join(KERNEL_DIR, "plugins"))

os.makedirs(SANDBOX_ROOT, exist_ok=True)
os.makedirs(LOGS_ROOT, exist_ok=True)
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

# --- Песочница ---
SANDBOX_DIRS = {
    "home":       os.path.join(SANDBOX_ROOT, "home"),
    "system":     os.path.join(SANDBOX_ROOT, "system"),
    "apps":       os.path.join(SANDBOX_ROOT, "apps"),
    "media":      os.path.join(SANDBOX_ROOT, "media"),
    "import":     os.path.join(SANDBOX_ROOT, "import"),
    "quarantine": os.path.join(SANDBOX_ROOT, "quarantine"),
    "tmp":        os.path.join(SANDBOX_ROOT, "tmp"),
    "games":      os.path.join(SANDBOX_ROOT, "games"),
    "installers": os.path.join(SANDBOX_ROOT, "installers"),
}
for p in SANDBOX_DIRS.values():
    os.makedirs(p, exist_ok=True)

SANDBOX_ROOTS = [SANDBOX_ROOT]
MAX_TEXT_SIZE = 2 * 1024 * 1024
MAX_HEX_SIZE = 512

DANGEROUS_EXT = {
    "exe", "msi", "bat", "cmd", "com", "scr", "pif",
    "sh", "run", "bin", "app", "apk", "ipa",
    "dll", "so", "dylib", "vbs", "vbe", "js", "jse",
    "wsf", "wsh", "ps1", "psm1", "jar", "class",
    "py", "pyc", "pyo", "rb", "pl", "php",
}

# --- Логи ---
LOG_FILES = {
    "actions":    os.path.join(LOGS_ROOT, "actions.log"),
    "sandbox":    os.path.join(LOGS_ROOT, "sandbox.log"),
    "quarantine": os.path.join(LOGS_ROOT, "quarantine.log"),
    "errors":     os.path.join(LOGS_ROOT, "errors.log"),
    "games":      os.path.join(LOGS_ROOT, "games.log"),
    "browser":    os.path.join(LOGS_ROOT, "browser.log"),
    "network":    os.path.join(LOGS_ROOT, "network.log"),
    "installers": os.path.join(LOGS_ROOT, "installers.log"),
    "antivirus":  os.path.join(LOGS_ROOT, "antivirus.log"),
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
    print(f"[LOG/{category}] {line.rstrip()}")


def log_tail(category, n=200):
    p = LOG_FILES.get(category)
    if not p or not os.path.exists(p):
        return "(пусто)"
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            return "".join(f.readlines()[-n:])
    except Exception as e:
        return f"(ошибка: {e})"


# --- Песочница: утилиты ---
def is_path_allowed(path):
    try:
        real = os.path.realpath(path)
    except Exception:
        return False
    for root in SANDBOX_ROOTS:
        try:
            r = os.path.realpath(root)
            if real == r or real.startswith(r + os.sep):
                return True
        except Exception:
            continue
    return False


def safe_read_text(path):
    if not is_path_allowed(path):
        return "⛔ Файл вне песочницы."
    try:
        size = os.path.getsize(path)
    except OSError:
        size = 0
    if size > MAX_TEXT_SIZE:
        return f"⚠ Файл слишком большой: {size:,} байт"
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read(MAX_TEXT_SIZE)
    except Exception as e:
        return f"⚠ Ошибка чтения: {e}"


def safe_read_bytes(path):
    if not is_path_allowed(path):
        return b""
    try:
        with open(path, "rb") as f:
            return f.read(MAX_HEX_SIZE)
    except Exception:
        return b""


def sandbox_quarantine(path):
    if not os.path.isfile(path):
        return None
    dst = os.path.join(SANDBOX_DIRS["quarantine"], os.path.basename(path))
    base, ext = os.path.splitext(dst)
    i = 1
    while os.path.exists(dst):
        dst = f"{base}_{i}{ext}"
        i += 1
    shutil.move(path, dst)
    log_write("quarantine", "DANGER", "Файл в карантине",
              src=path, dst=dst)
    return dst


# --- QSS ---
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
QFrame#Window { background-color: #242424; border: 1px solid #1a1a1a;
    border-radius: 12px; }
QFrame#HeaderBar { background-color: #303030;
    border-top-left-radius: 12px; border-top-right-radius: 12px;
    border-bottom: 1px solid #1a1a1a; }
QLabel#WindowTitle { color: #ffffff; font-weight: 600; padding: 6px; }
QPushButton#WinBtn { background: transparent; border: none;
    color: #cccccc; border-radius: 6px; padding: 4px 8px; font-weight: 700; }
QPushButton#WinBtn:hover { background-color: rgba(255,255,255,30); }
QPushButton#WinClose:hover { background-color: #e01b24; color: white; }
QListWidget#Sidebar { background-color: #1e1e1e; border: none;
    outline: 0; padding: 6px; }
QListWidget#Sidebar::item { padding: 8px 10px; border-radius: 6px;
    color: #dddddd; }
QListWidget#Sidebar::item:selected { background-color: #3584e4;
    color: #ffffff; }
QListWidget#Sidebar::item:hover { background-color: rgba(255,255,255,25); }
QLabel#FileIcon { font-size: 30pt; }
QLabel#FileName { color: #ffffff; font-size: 9pt; }
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


# --- Скриншоты ---
def take_screenshot(window):
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
    name = datetime.datetime.now().strftime("screenshot_%Y-%m-%d_%H-%M-%S.png")
    path = os.path.join(SCREENSHOTS_DIR, name)
    pix = window.grab()
    if pix.save(path, "PNG"):
        log_write("actions", "INFO", "Скриншот окна", path=path)
        return path
    return None


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


class WallpaperWidget(QWidget):
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
        lbl = QLabel("SimpleOS")
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
            ("📁", "Files",      self.desktop.open_files),
            ("🌐", "Browser",    self.desktop.open_browser),
            ("🎮", "Games",      self.desktop.open_games),
            ("📦", "Installers", self.desktop.open_installers),
            ("🛡", "AV",         self.desktop.open_av),
            ("🔒", "VPN",        self.desktop.open_vpn),
            ("▶",  "Terminal",   self.desktop.open_terminal),
            ("🕒", "Clocks",     self.desktop.open_clocks),
            ("⚙",  "Settings",   self.desktop.open_settings),
            ("ℹ",  "About",      self.desktop.open_about),
        ]
        for icon, name, cb in apps:
            b = QPushButton(f"{icon}\n{name}")
            b.setObjectName("DockButton")
            b.clicked.connect(cb)
            lay.addWidget(b)


class GnomeWindow(QFrame):
    def __init__(self, desktop, title, w=560, h=400, x=120, y=100):
        super().__init__(desktop.desktop_area)
        self.desktop = desktop
        self.setObjectName("Window")
        self.setGeometry(x, y, w, h)
        self.raise_()
        self._drag = None

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
        self._drag = None


# --- Приложения ---
def icon_for(name, is_dir):
    if is_dir:
        return "📁"
    ext = name.lower().rsplit(".", 1)[-1] if "." in name else ""
    return {
        "txt": "📄", "md": "📝", "log": "📋", "json": "📋", "xml": "📋",
        "png": "🖼", "jpg": "🖼", "jpeg": "🖼", "gif": "🖼", "svg": "🖼",
        "mp3": "🎵", "wav": "🎵", "flac": "🎵",
        "mp4": "🎬", "mkv": "🎬", "avi": "🎬",
        "pdf": "📕", "doc": "📘", "docx": "📘",
        "xls": "📗", "xlsx": "📗", "ppt": "📙", "pptx": "📙",
        "zip": "🗜", "rar": "🗜", "7z": "🗜",
        "py": "🐍", "js": "📜", "html": "🌐", "css": "🎨",
        "exe": "⚙", "sh": "⚙", "bat": "⚙",
        "apk": "📱", "iso": "💿",
    }.get(ext, "📄")


def open_files(desktop):
    log_write("actions", "INFO", "Открыто Files")
    win = GnomeWindow(desktop, "Файлы", 900, 560, 100, 60)
    state = {"history": [], "index": -1}

    row = QHBoxLayout()
    sidebar = QListWidget()
    sidebar.setObjectName("Sidebar")
    sidebar.setFixedWidth(240)
    locs = [
        ("🏠 Домашняя папка",        SANDBOX_DIRS["home"],       "linux"),
        ("📥 Импорт из главной ОС",  SANDBOX_DIRS["import"],     "linux"),
        ("⚙ Система",                SANDBOX_DIRS["system"],     "linux"),
        ("📦 Приложения",            SANDBOX_DIRS["apps"],       "linux"),
        ("💾 Диски",                 SANDBOX_DIRS["media"],      "linux"),
        ("🗑 Временные",             SANDBOX_DIRS["tmp"],        "linux"),
        ("⛔ Карантин",              SANDBOX_DIRS["quarantine"], "android"),
    ]
    loc_by_item = {}
    for label, path, grp in locs:
        it = QListWidgetItem(label)
        it.setToolTip(path)
        sidebar.addItem(it)
        loc_by_item[it] = path
    row.addWidget(sidebar)

    right = QWidget()
    rl = QVBoxLayout(right)
    rl.setContentsMargins(12, 12, 12, 12)
    rl.setSpacing(8)

    bar = QHBoxLayout()
    bar.setSpacing(6)
    b_back = QPushButton("◀"); b_back.setObjectName("WinBtn")
    b_fwd = QPushButton("▶"); b_fwd.setObjectName("WinBtn")
    b_up = QPushButton("▲"); b_up.setObjectName("WinBtn")
    b_ref = QPushButton("⟳"); b_ref.setObjectName("WinBtn")
    for b in (b_back, b_fwd, b_up, b_ref):
        bar.addWidget(b)

    b_import = QPushButton("📥 Импорт"); b_import.setObjectName("WinBtn")
    bar.addWidget(b_import)
    b_reset = QPushButton("🔄 Сброс ОС"); b_reset.setObjectName("WinBtn")
    bar.addWidget(b_reset)
    b_logs = QPushButton("📜 Логи"); b_logs.setObjectName("WinBtn")
    bar.addWidget(b_logs)

    path_lbl = QLabel("/")
    path_lbl.setObjectName("H2")
    path_lbl.setStyleSheet("padding: 4px 10px; background: #1a1a1a; border-radius: 6px;")
    bar.addWidget(path_lbl, 1)
    rl.addLayout(bar)

    stack = QStackedWidget()

    # --- сетка ---
    grid_w = QWidget()
    grid = QGridLayout(grid_w)
    grid.setSpacing(16)
    grid.setContentsMargins(8, 8, 8, 8)
    grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setWidget(grid_w)
    stack.addWidget(scroll)

    # --- просмотрщик ---
    viewer = QWidget()
    vl = QVBoxLayout(viewer)
    vl.setContentsMargins(0, 0, 0, 0)
    vhead = QHBoxLayout()
    vname = QLabel(""); vname.setObjectName("H2")
    vhead.addWidget(vname, 1)
    vback = QPushButton("← К файлам"); vback.setObjectName("WinBtn")
    vhead.addWidget(vback)
    vl.addLayout(vhead)

    vbody = QStackedWidget()
    vl.addWidget(vbody, 1)

    vtext = QTextEdit()
    vtext.setReadOnly(True)
    vtext.setStyleSheet("background:#0d0d0d; color:#e0e0e0; "
                        "font-family:'Consolas','Monospace'; font-size:10pt;")
    vbody.addWidget(vtext)

    vimg = QLabel()
    vimg.setAlignment(Qt.AlignmentFlag.AlignCenter)
    vimg.setStyleSheet("background:#0d0d0d;")
    vimg_scroll = QScrollArea()
    vimg_scroll.setWidgetResizable(True)
    vimg_scroll.setWidget(vimg)
    vbody.addWidget(vimg_scroll)

    vmedia = QLabel()
    vmedia.setAlignment(Qt.AlignmentFlag.AlignCenter)
    vmedia.setStyleSheet("background:#0d0d0d; color:#9a9a9a; font-size:12pt;")
    vmedia.setWordWrap(True)
    vbody.addWidget(vmedia)

    stack.addWidget(viewer)
    rl.addWidget(stack, 1)
    row.addWidget(right, 1)
    win.body_lay.addLayout(row)

    TEXT_EXT = {"txt","md","log","json","xml","yml","yaml","ini","cfg",
                "toml","env","html","htm","css","sql","csv","tsv","rtf","tex"}
    IMG_EXT = {"png","jpg","jpeg","gif","bmp","webp","tiff","ico","svg"}
    MEDIA_EXT = {"mp3","wav","flac","ogg","m4a","aac","mp4","mkv","avi","mov"}

    def open_file_internal(path):
        if not is_path_allowed(path):
            log_write("sandbox", "DANGER", "Открытие вне песочницы", path=path)
            vname.setText(os.path.basename(path))
            vmedia.setText("⛔ Файл вне песочницы.")
            vbody.setCurrentWidget(vmedia)
            stack.setCurrentWidget(viewer)
            return
        ext = path.rsplit(".", 1)[-1].lower() if "." in os.path.basename(path) else ""
        name = os.path.basename(path)
        vname.setText(name)
        try:
            size = os.path.getsize(path)
        except OSError:
            size = 0
        log_write("actions", "INFO", "Открыт файл", path=path, ext=ext)

        if ext in DANGEROUS_EXT:
            log_write("quarantine", "DANGER", "Опасный файл", path=path, ext=ext)
            q = sandbox_quarantine(path)
            vtext.setPlainText(
                f"⚠ Опасный файл: {name}\n"
                f"🔒 В песочнице такие файлы НЕ запускаются.\n\n"
                f"Перемещён в карантин:\n{q}"
            )
            vbody.setCurrentWidget(vtext)
            stack.setCurrentWidget(viewer)
            refresh_current()
            return

        if ext in TEXT_EXT or ext == "":
            vtext.setPlainText(safe_read_text(path))
            vbody.setCurrentWidget(vtext)
        elif ext in IMG_EXT:
            pix = QPixmap(path)
            if not pix.isNull():
                vimg.setPixmap(pix)
                vbody.setCurrentWidget(vimg_scroll)
            else:
                vmedia.setText(f"⚠ Не удалось: {name}")
                vbody.setCurrentWidget(vmedia)
        elif ext in MEDIA_EXT:
            vmedia.setText(f"🎬 {name}\n\nРазмер: {size:,} байт\n"
                           f"🔒 Медиа в песочнице не воспроизводится.")
            vbody.setCurrentWidget(vmedia)
        else:
            raw = safe_read_bytes(path)
            lines = []
            for off in range(0, len(raw), 16):
                chunk = raw[off:off+16]
                hs = " ".join(f"{b:02x}" for b in chunk)
                asc = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
                lines.append(f"{off:08x}  {hs:<47}  {asc}")
            vtext.setPlainText(f"Бинарный: {name}\nРазмер: {size:,}\n\n"
                               + "\n".join(lines))
            vbody.setCurrentWidget(vtext)
        stack.setCurrentWidget(viewer)

    def show_grid():
        stack.setCurrentWidget(scroll)
    vback.clicked.connect(show_grid)

    def refresh_current():
        if state["history"]:
            render_dir(state["history"][state["index"]])

    def navigate(path, add_history=True):
        path = os.path.abspath(path)
        if not os.path.isdir(path):
            return
        if not is_path_allowed(path):
            log_write("sandbox", "DANGER", "Попытка выйти из песочницы", path=path)
            return
        if add_history:
            state["history"] = state["history"][:state["index"]+1]
            state["history"].append(path)
            state["index"] = len(state["history"]) - 1
        render_dir(path)
        show_grid()

    def render_dir(path):
        path_lbl.setText(path if len(path) < 70 else "..." + path[-67:])
        path_lbl.setToolTip(path)
        while grid.count():
            it = grid.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()
        try:
            entries = sorted(
                os.scandir(path),
                key=lambda e: (not e.is_dir(follow_symlinks=False), e.name.lower()),
            )
        except PermissionError:
            err = QLabel("⛔ Доступ запрещён")
            err.setStyleSheet("color:#e01b24; font-size:12pt;")
            grid.addWidget(err, 0, 0); return
        except Exception as e:
            err = QLabel(f"⚠ {e}")
            err.setStyleSheet("color:#e01b24; font-size:12pt;")
            grid.addWidget(err, 0, 0); return

        col = r = 0
        for entry in entries:
            try:
                is_dir = entry.is_dir(follow_symlinks=False)
            except OSError:
                is_dir = False
            cell = QWidget()
            cell.setFixedSize(110, 100)
            cl = QVBoxLayout(cell)
            cl.setContentsMargins(4, 4, 4, 4)
            cl.setSpacing(2)
            ic = QLabel(icon_for(entry.name, is_dir))
            ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ic.setStyleSheet("font-size:30pt;")
            cl.addWidget(ic)
            nm = QLabel(entry.name)
            nm.setAlignment(Qt.AlignmentFlag.AlignCenter)
            nm.setWordWrap(True)
            nm.setStyleSheet(
                f"color:{'#3584e4' if is_dir else '#ffffff'}; font-size:9pt;"
            )
            cl.addWidget(nm)
            def mh(e=entry, is_dir=is_dir):
                def _h(ev):
                    p = os.path.join(path, e.name)
                    if is_dir:
                        navigate(p)
                    else:
                        open_file_internal(p)
                return _h
            cell.mouseDoubleClickEvent = mh()
            grid.addWidget(cell, r, col)
            col += 1
            if col >= 6:
                col = 0; r += 1

    def go_back():
        if state["index"] > 0:
            state["index"] -= 1
            render_dir(state["history"][state["index"]])
            show_grid()
    def go_fwd():
        if state["index"] < len(state["history"]) - 1:
            state["index"] += 1
            render_dir(state["history"][state["index"]])
            show_grid()
    def go_up():
        cur = state["history"][state["index"]] if state["history"] else "/"
        parent = os.path.dirname(cur.rstrip(os.sep)) or os.sep
        if parent != cur:
            navigate(parent)

    b_back.clicked.connect(go_back)
    b_fwd.clicked.connect(go_fwd)
    b_up.clicked.connect(go_up)
    b_ref.clicked.connect(refresh_current)

    def on_sidebar(item):
        p = loc_by_item.get(item)
        if p:
            navigate(p)
    sidebar.itemClicked.connect(on_sidebar)

    def on_import():
        path, _ = QFileDialog.getOpenFileName(
            win, "Импорт файла в песочницу", os.path.expanduser("~")
        )
        if not path:
            return
        log_write("actions", "INFO", "Импорт запрошен", src=path)
        try:
            from av_bridge import AVBridge
            av = AVBridge(log_fn=lambda m: log_write("antivirus", "INFO", m))
            report = av.scan(path)
            verdict = report.get("verdict", "unknown")
            log_write("antivirus", "INFO", "Импорт проверен",
                      file=os.path.basename(path), verdict=verdict,
                      source=report.get("source"))
            if verdict == "malicious":
                QMessageBox.warning(win, "Импорт",
                    f"⛔ Антивирус хоста: MALICIOUS\n\n{report.get('issues')}")
                return
        except Exception as e:
            log_write("antivirus", "WARN", f"AV недоступен: {e}")
        dst = os.path.join(SANDBOX_DIRS["import"], os.path.basename(path))
        base, ext = os.path.splitext(dst)
        i = 1
        while os.path.exists(dst):
            dst = f"{base}_{i}{ext}"; i += 1
        shutil.copy2(path, dst)
        log_write("actions", "INFO", "Импортировано", src=path, dst=dst)
        QMessageBox.information(win, "Импорт",
            f"✅ Скопировано в песочницу:\n{dst}\n\nОригинал:\n{path}")
        refresh_current()

    def on_reset():
        r = QMessageBox.question(win, "Сброс второстепенной ОС",
            "Все файлы в песочнице будут удалены.\nГлавная ОС не пострадает.")
        if r != QMessageBox.StandardButton.Yes:
            return
        log_write("sandbox", "RESET", "Сброс песочницы")
        shutil.rmtree(SANDBOX_ROOT, ignore_errors=True)
        for p in SANDBOX_DIRS.values():
            os.makedirs(p, exist_ok=True)
        os.makedirs(SANDBOX_ROOT, exist_ok=True)
        state["history"].clear()
        state["index"] = -1
        navigate(SANDBOX_DIRS["home"])
        QMessageBox.information(win, "Сброс", "Песочница пересоздана.")

    def on_logs():
        log_write("actions", "INFO", "Открыт просмотр логов")
        lw = GnomeWindow(desktop, "Логи", 780, 480, 160, 100)
        tabs = QTabWidget()
        for key, title in [
            ("actions","Действия"), ("sandbox","Песочница"),
            ("quarantine","Карантин"), ("errors","Ошибки"),
            ("games","Игры"), ("browser","Браузер"),
            ("network","Сеть"), ("installers","Установщики"),
            ("antivirus","Антивирус"),
        ]:
            t = QTextEdit()
            t.setReadOnly(True)
            t.setStyleSheet("background:#0d0d0d; color:#e0e0e0; "
                            "font-family:'Consolas','Monospace'; font-size:9pt;")
            t.setPlainText(log_tail(key, 500))
            tabs.addTab(t, title)
        lw.body_lay.addWidget(tabs)

    b_import.clicked.connect(on_import)
    b_reset.clicked.connect(on_reset)
    b_logs.clicked.connect(on_logs)

    home = SANDBOX_DIRS["home"]
    if os.path.isdir(home):
        navigate(home)


def open_settings(desktop):
    win = GnomeWindow(desktop, "Настройки", 780, 500, 130, 80)
    row = QHBoxLayout()
    sb = QListWidget()
    sb.setObjectName("Sidebar")
    sb.setFixedWidth(200)
    for it in ["🔍 Поиск","🌐 Wi-Fi","🔵 Bluetooth","🖥 Дисплей","🔊 Звук",
               "🔋 Питание","🖱 Мышь","⌨ Клавиатура","🖨 Принтеры","🎨 Цвет",
               "🌍 Регион","♿ Спец. возможности","👥 Пользователи",
               "🕒 Дата и время","ℹ О системе"]:
        sb.addItem(QListWidgetItem(it))
    sb.setCurrentRow(14)
    row.addWidget(sb)

    right = QWidget()
    rl = QVBoxLayout(right)
    t = QLabel("О системе"); t.setObjectName("H2")
    t.setAlignment(Qt.AlignmentFlag.AlignCenter)
    rl.addWidget(t)
    logo = QLabel("GNOME")
    logo.setStyleSheet("font-size:32pt; font-weight:200; color:#dddddd;")
    logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
    rl.addWidget(logo)
    cols = QHBoxLayout()
    for title, items in [
        ("Аппаратная информация", [
            ("Модель","QEMU Standard PC"),("Память","4,0 ГиБ"),
            ("Процессор","Intel Core i5-9400F × 6"),
            ("Графика","Software Rendering"),("Диск","107,4 ГБ")]),
        ("Программная информация", [
            ("Название ОС","SimpleOS (Nightly)"),("Тип ОС","64-бит"),
            ("Версия GNOME","45.0"),("Оконный","Wayland"),
            ("Ядро","Linux 6.5.0")]),
    ]:
        c = QVBoxLayout()
        h = QLabel(title); h.setObjectName("H2"); c.addWidget(h)
        for k, v in items:
            w = QWidget(); wl = QHBoxLayout(w); wl.setContentsMargins(0,2,0,2)
            lk = QLabel(k); lk.setStyleSheet("color:#9a9a9a;"); lk.setFixedWidth(150)
            lv = QLabel(v)
            wl.addWidget(lk); wl.addWidget(lv, 1)
            c.addWidget(w)
        c.addStretch()
        cols.addLayout(c)
    rl.addLayout(cols)
    rl.addStretch()
    row.addWidget(right, 1)
    win.body_lay.addLayout(row)


def open_terminal(desktop):
    win = GnomeWindow(desktop, "Терминал", 640, 400, 160, 120)
    out = QTextEdit()
    out.setReadOnly(True)
    out.setStyleSheet("background:#0d0d0d; color:#e0e0e0; "
                      "font-family:'Consolas','Monospace'; font-size:10pt;")
    out.append("SimpleOS Terminal — 'help'\n")
    win.body_lay.addWidget(out, 1)
    inp = QLineEdit()
    inp.setPlaceholderText("user@simpleos:~$")
    win.body_lay.addWidget(inp)
    def on_enter():
        cmd = inp.text().strip()
        if not cmd: return
        inp.clear()
        out.append(f"<span style='color:#33d17a'>user@simpleos:~$</span> {cmd}")
        if cmd == "help":
            out.append("help, whoami, date, uname, clear, screenshot")
        elif cmd == "whoami": out.append("user")
        elif cmd == "date": out.append(datetime.datetime.now().strftime("%c"))
        elif cmd == "uname": out.append("SimpleOS 1.0 x86_64")
        elif cmd == "clear": out.clear()
        elif cmd == "screenshot":
            p = take_screenshot(desktop)
            out.append(f"Скриншот: {p}" if p else "Ошибка")
        else: out.append(f"command not found: {cmd}")
    inp.returnPressed.connect(on_enter)
    inp.setFocus()


def open_clocks(desktop):
    win = GnomeWindow(desktop, "Часы", 380, 260, 380, 180)
    t = QLabel(); t.setStyleSheet("font-size:42pt; font-weight:200; color:#3584e4;")
    t.setAlignment(Qt.AlignmentFlag.AlignCenter)
    win.body_lay.addWidget(t)
    d = QLabel(); d.setStyleSheet("color:#9a9a9a; font-size:11pt;")
    d.setAlignment(Qt.AlignmentFlag.AlignCenter)
    win.body_lay.addWidget(d)
    def tick():
        now = datetime.datetime.now()
        t.setText(now.strftime("%H:%M:%S"))
        d.setText(now.strftime("%A, %d %B %Y"))
        QTimer.singleShot(500, tick)
    tick()


def open_about(desktop):
    win = GnomeWindow(desktop, "О системе", 420, 300, 340, 200)
    l1 = QLabel("SimpleOS"); l1.setStyleSheet("font-size:24pt; font-weight:700;")
    l1.setAlignment(Qt.AlignmentFlag.AlignCenter)
    win.body_lay.addWidget(l1)
    l2 = QLabel("GNOME-like Desktop"); l2.setStyleSheet("color:#9a9a9a;")
    l2.setAlignment(Qt.AlignmentFlag.AlignCenter)
    win.body_lay.addWidget(l2)
    l3 = QLabel("Версия 1.0\nPyQt6 · Adwaita dark\nF12 — скриншот")
    l3.setStyleSheet("color:#9a9a9a; font-size:9pt;")
    l3.setAlignment(Qt.AlignmentFlag.AlignCenter)
    win.body_lay.addWidget(l3)


# --- Главное окно ---
class GnomeDesktop(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SimpleOS — GNOME")
        self.resize(1280, 800)
        self.wallpaper = WallpaperWidget()
        self.setCentralWidget(self.wallpaper)
        self.desktop_area = QWidget(self.wallpaper)
        self.desktop_area.setGeometry(0, 32, 1280, 800 - 32)
        self.desktop_area.setStyleSheet("background: transparent;")
        self.panel = TopPanel(self.wallpaper)
        self.panel.setGeometry(0, 0, self.width(), 32)
        self.dock = Dock(self, self.wallpaper)
        self.dock.adjustSize()
        self._position_dock()
        QShortcut(QKeySequence("F12"), self).activated.connect(self._on_screenshot)
        QShortcut(QKeySequence("F11"), self).activated.connect(self._on_screen)
        log_write("actions", "INFO", "GNOME запущен")

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.panel.setGeometry(0, 0, self.width(), 32)
        self.desktop_area.setGeometry(0, 32, self.width(), self.height() - 32)
        self._position_dock()

    def _position_dock(self):
        self.dock.adjustSize()
        x = (self.width() - self.dock.width()) // 2
        y = self.height() - self.dock.height() - 12
        self.dock.move(x, y)
        self.dock.raise_()

    def _on_screenshot(self):
        p = take_screenshot(self)
        if p:
            Toast(self.wallpaper, f"📸 {os.path.basename(p)}")

    def _on_screen(self):
        screen = QApplication.primaryScreen()
        if not screen:
            return
        name = datetime.datetime.now().strftime("screen_%Y-%m-%d_%H-%M-%S.png")
        path = os.path.join(SCREENSHOTS_DIR, name)
        if screen.grabWindow(0).save(path, "PNG"):
            log_write("actions", "INFO", "Скриншот экрана", path=path)
            Toast(self.wallpaper, f"📸 {name}")

    def closeEvent(self, e):
        log_write("actions", "INFO", "GNOME закрыт")
        super().closeEvent(e)

    # --- Приложения ---
    def open_files(self):      open_files(self)
    def open_settings(self):   open_settings(self)
    def open_terminal(self):   open_terminal(self)
    def open_clocks(self):     open_clocks(self)
    def open_about(self):      open_about(self)

    def open_browser(self):
        try:
            from browser import browser_open
            browser_open(self)
        except Exception as e:
            log_write("errors", "ERROR", f"browser: {e}")
            GnomeWindow(self, "Браузер", 400, 200, 300, 200)

    def open_games(self):
        try:
            from games import games_open
            games_open(self)
        except Exception as e:
            log_write("errors", "ERROR", f"games: {e}")
            GnomeWindow(self, "Игры", 400, 200, 300, 200)

    def open_installers(self):
        try:
            from installers import installers_open
            installers_open(self)
        except Exception as e:
            log_write("errors", "ERROR", f"installers: {e}")
            GnomeWindow(self, "Установщики", 400, 200, 300, 200)

    def open_av(self):
        win = GnomeWindow(self, "Антивирус хоста", 680, 480, 200, 120)
        info = QTextEdit()
        info.setReadOnly(True)
        info.setStyleSheet("background:#0d0d0d; color:#e0e0e0; "
                           "font-family:'Consolas','Monospace'; font-size:10pt;")
        win.body_lay.addWidget(info)
        try:
            from av_bridge import AVBridge
            av = AVBridge(log_fn=lambda m: log_write("antivirus", "INFO", m))
            st = av.status()
            info.setPlainText(
                f"Антивирус главной ОС\n"
                f"─────────────────────\n"
                f"Активен:  {'да' if st['active'] else 'нет'}\n"
                f"Название: {st.get('name','—')}\n"
                f"Тип:      {st.get('type','—')}\n"
                f"Путь:     {st.get('path','—')}\n\n"
                f"Все файлы проверяются ДО попадания в песочницу."
            )
        except Exception as e:
            info.setPlainText(f"Ошибка: {e}")
        btn = QPushButton("🔄 Обновить")
        btn.setObjectName("WinBtn")
        win.body_lay.addWidget(btn)

    def open_vpn(self):
        win = GnomeWindow(self, "VPN", 620, 460, 200, 120)
        info = QTextEdit()
        info.setReadOnly(True)
        info.setStyleSheet("background:#0d0d0d; color:#e0e0e0; "
                           "font-family:'Consolas','Monospace'; font-size:10pt;")
        win.body_lay.addWidget(info)
        try:
            from ovpn import OVPNClient
            ovpn = OVPNClient(log_fn=lambda m: log_write("ovpn", "INFO", m))
            st = ovpn.status()
            info.setPlainText(
                f"OpenVPN-туннель ядра\n"
                f"─────────────────────\n"
                f"OpenVPN:      {st['openvpn'] or 'НЕ найден'}\n"
                f"Конфиг:       {st['config'] or '—'}\n"
                f"Auth:         {st['auth'] or '—'}\n"
                f"Папка файлов: {st['files_dir']}\n"
                f"Папка логов:  {st['logs_dir']}\n"
                f"Лог:          {st['log_file']}\n"
                f"Debug:        {st['debug_log']}\n"
                f"Подключение:  {'✅ АКТИВНО' if st['connected'] else '❌ нет'}\n"
                f"Kill-switch:  {'вкл' if st['kill_switch'] else 'выкл'}\n"
            )
        except Exception as e:
            info.setPlainText(f"Ошибка: {e}")


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(ADWAITA_DARK_QSS)
    win = GnomeDesktop()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()