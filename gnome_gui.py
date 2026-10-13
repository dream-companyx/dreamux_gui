#!/usr/bin/env python3
"""GNOME-подобный интерфейс DreamUX. С интеграцией VFS."""

import os
import sys
import json
import shutil
import traceback
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

# VFS paths
VFS_ROOT = os.path.join(KERNEL_DIR, "vfs")
DISK_0 = os.path.join(VFS_ROOT, "disk0")
DISK_0_SYSTEM = os.path.join(DISK_0, "system")
DISK_0_BOOT   = os.path.join(DISK_0, "boot")
DISK_1 = os.path.join(VFS_ROOT, "disk1")

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
    QTabWidget,
)


# ============================================================
# Логи
# ============================================================
LOG_FILES = {
    "actions":    os.path.join(LOGS_ROOT, "actions.log"),
    "errors":     os.path.join(LOGS_ROOT, "errors.log"),
    "quarantine": os.path.join(LOGS_ROOT, "quarantine.log"),
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
# Песочница
# ============================================================
SANDBOX_ROOTS = [DISK_1] if os.path.isdir(DISK_1) else [KERNEL_DIR]


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


MAX_TEXT_SIZE = 2 * 1024 * 1024
MAX_HEX_SIZE = 512

DANGEROUS_EXT = {
    "exe", "msi", "bat", "cmd", "com", "scr", "pif",
    "sh", "run", "bin", "app", "apk", "ipa",
    "dll", "so", "dylib", "vbs", "vbe", "js", "jse",
    "wsf", "wsh", "ps1", "psm1", "jar", "class",
    "py", "pyc", "pyo", "rb", "pl", "php",
}


def safe_read_text(path):
    if not is_path_allowed(path):
        return "Файл вне песочницы."
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
    if not is_path_allowed(path):
        return b""
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


# ============================================================
# Toast / Скриншот
# ============================================================
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


# ============================================================
# Обои / панель / док / окно
# ============================================================
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
            ("🌐", "Browser",    desktop.open_browser),
            ("🎮", "Games",      desktop.open_games),
            ("📦", "Installers", desktop.open_installers),
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


class GnomeWindow(QFrame):
    def __init__(self, desktop, title, w=560, h=400, x=120, y=100):
        super().__init__(desktop.desktop_area)
        self.desktop = desktop
        self.setObjectName("Window")
        self.setGeometry(x, y, w, h)
        self.raise_()
        self._drag = None
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
        self._drag = None

    def closeEvent(self, event):
        if self in self.desktop.windows:
            self.desktop.windows.remove(self)
        super().closeEvent(event)


# ============================================================
# FILES — работает с VFS
# ============================================================
def open_files(desktop):
    log_write("actions", "INFO", "Открыто Files (VFS)")
    win = GnomeWindow(desktop, "Файлы", 900, 560, 100, 60)

    state = {"history": [], "index": -1}

    row = QHBoxLayout()
    sidebar = QListWidget()
    sidebar.setObjectName("Sidebar")
    sidebar.setFixedWidth(260)

    # ---- VFS локации ----
    locs = []

    if os.path.isdir(DISK_0):
        locs.append(("💽 Раздел 0 — СИСТЕМА", DISK_0))
        if os.path.isdir(DISK_0_SYSTEM):
            locs.append(("  ⚙ 0.0 — Система", DISK_0_SYSTEM))
        if os.path.isdir(DISK_0_BOOT):
            locs.append(("  🚀 0.5 — Загрузочный", DISK_0_BOOT))

    if os.path.isdir(DISK_1):
        locs.append(("💾 Раздел 1 — ОСТАЛЬНОЕ", DISK_1))
        for sub, icon, label in [
            ("home",      "🏠", "Домашняя папка"),
            ("apps",      "📦", "Приложения"),
            ("packages",  "📥", "Пакеты"),
            ("downloads", "⬇",  "Загрузки"),
            ("snapshots", "🗂", "Снапшоты"),
            ("documents", "📄", "Документы"),
            ("music",     "🎵", "Музыка"),
            ("pictures",  "🖼", "Изображения"),
            ("videos",    "🎬", "Видео"),
            ("media",     "💿", "Медиа"),
            ("data",      "📊", "Данные"),
            ("sandbox",   "🧪", "Песочница"),
        ]:
            p = os.path.join(DISK_1, sub)
            if os.path.isdir(p):
                locs.append((f"  {icon} {label}", p))

    # Если VFS не создана
    if not locs:
        locs.append(("⚠ VFS не создана — /disk 0 - 1 auto", KERNEL_DIR))

    loc_by_index = {}
    for label, path in locs:
        it = QListWidgetItem(label)
        it.setToolTip(path)
        sidebar.addItem(it)
        loc_by_index[sidebar.count() - 1] = path
    row.addWidget(sidebar)

    # ---- Правая часть ----
    right = QWidget()
    rl = QVBoxLayout(right)
    rl.setContentsMargins(12, 12, 12, 12)
    rl.setSpacing(8)

    bar = QHBoxLayout()
    bar.setSpacing(6)
    b_back = QPushButton("◀"); b_back.setObjectName("WinBtn")
    b_up = QPushButton("▲"); b_up.setObjectName("WinBtn")
    b_ref = QPushButton("⟳"); b_ref.setObjectName("WinBtn")
    for b in (b_back, b_up, b_ref):
        bar.addWidget(b)

    path_lbl = QLabel("/")
    path_lbl.setObjectName("H2")
    path_lbl.setStyleSheet("padding: 4px 10px; background: #1a1a1a; "
                           "border-radius: 6px;")
    bar.addWidget(path_lbl, 1)
    rl.addLayout(bar)

    stack = QStackedWidget()

    # Сетка
    grid_w = QWidget()
    grid = QGridLayout(grid_w)
    grid.setSpacing(16)
    grid.setContentsMargins(8, 8, 8, 8)
    grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setWidget(grid_w)
    stack.addWidget(scroll)

    # Просмотрщик
    viewer = QWidget()
    vl = QVBoxLayout(viewer)
    vl.setContentsMargins(0, 0, 0, 0)
    vhead = QHBoxLayout()
    vname = QLabel(""); vname.setObjectName("H2")
    vhead.addWidget(vname, 1)
    vback = QPushButton("← К списку"); vback.setObjectName("WinBtn")
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
                "toml","env","html","htm","css","sql","csv","tsv","rtf","tex",
                "dupfi"}
    IMG_EXT = {"png","jpg","jpeg","gif","bmp","webp","tiff","ico","svg"}
    MEDIA_EXT = {"mp3","wav","flac","ogg","m4a","aac","mp4","mkv","avi","mov"}

    def icon_for(name, is_dir):
        if is_dir:
            return "📁"
        ext = name.lower().rsplit(".", 1)[-1] if "." in name else ""
        return {
            "txt":"📄","md":"📝","log":"📋","json":"📋","xml":"📋",
            "png":"🖼","jpg":"🖼","jpeg":"🖼","gif":"🖼","svg":"🖼",
            "mp3":"🎵","wav":"🎵","flac":"🎵",
            "mp4":"🎬","mkv":"🎬","avi":"🎬",
            "pdf":"📕","doc":"📘","docx":"📘",
            "xls":"📗","xlsx":"📗","ppt":"📙","pptx":"📙",
            "zip":"🗜","rar":"🗜","7z":"🗜",
            "duap":"🗜","dupfi":"📦",
            "py":"🐍","js":"📜","html":"🌐","css":"🎨",
            "exe":"⚙","sh":"⚙","bat":"⚙",
            "apk":"📱","iso":"💿",
        }.get(ext, "📄")

    def open_file_internal(path):
        ext = path.rsplit(".", 1)[-1].lower() if "." in os.path.basename(path) else ""
        name = os.path.basename(path)
        vname.setText(name)

        # .dupfi → открыть Installer
        if ext == "dupfi":
            _open_with_installer(desktop, path, kind="dupfi")
            return

        # .duap → открыть Installer
        if ext == "duap":
            _open_with_installer(desktop, path, kind="duap")
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
                vmedia.setText(f"Не удалось: {name}")
                vbody.setCurrentWidget(vmedia)
        elif ext in MEDIA_EXT:
            vmedia.setText(f"{name}\n\nМедиа-файл.")
            vbody.setCurrentWidget(vmedia)
        else:
            raw = safe_read_bytes(path)
            lines = []
            for off in range(0, len(raw), 16):
                chunk = raw[off:off+16]
                hs = " ".join(f"{b:02x}" for b in chunk)
                asc = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
                lines.append(f"{off:08x}  {hs:<47}  {asc}")
            vtext.setPlainText(f"Бинарный: {name}\n\n" + "\n".join(lines))
            vbody.setCurrentWidget(vtext)
        stack.setCurrentWidget(viewer)

    def show_grid():
        stack.setCurrentWidget(scroll)
    vback.clicked.connect(show_grid)

    def navigate(path, add_history=True):
        path = os.path.abspath(path)
        if not os.path.isdir(path):
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
            err = QLabel("Доступ запрещён")
            err.setStyleSheet("color:#e01b24; font-size:12pt;")
            grid.addWidget(err, 0, 0); return
        except Exception as e:
            err = QLabel(f"Ошибка: {e}")
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
            def mh(e=entry, is_dir=is_dir, base=path):
                def _h(ev):
                    p = os.path.join(base, e.name)
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
    def go_up():
        cur = state["history"][state["index"]] if state["history"] else "/"
        parent = os.path.dirname(cur.rstrip(os.sep)) or os.sep
        if parent != cur:
            navigate(parent)
    def refresh():
        if state["history"] and os.path.isdir(state["history"][state["index"]]):
            render_dir(state["history"][state["index"]])

    b_back.clicked.connect(go_back)
    b_up.clicked.connect(go_up)
    b_ref.clicked.connect(refresh)

    def on_sidebar(item):
        row_idx = sidebar.row(item)
        p = loc_by_index.get(row_idx)
        if p:
            navigate(p)
    sidebar.itemClicked.connect(on_sidebar)

    # Стартовая — раздел 0
    if os.path.isdir(DISK_0):
        navigate(DISK_0)
    elif os.path.isdir(DISK_1):
        navigate(DISK_1)
    else:
        navigate(KERNEL_DIR)


def _open_with_installer(desktop, path, kind="dupfi"):
    """Открывает DreamUX Paket Installer с указанным файлом."""
    try:
        from plugins.dupfi import slash_dupfi
        class FakeKernel:
            slash_commands = {}
        fake = FakeKernel()
        if kind == "dupfi":
            slash_dupfi(fake, ["install", path])
        else:
            slash_dupfi(fake, ["info", path])
    except Exception as e:
        log_write("errors", "ERROR", f"installer: {e}")
        QMessageBox.warning(None, "Paket Installer", str(e))


# ============================================================
# Остальные приложения
# ============================================================
def open_terminal(desktop):
    win = GnomeWindow(desktop, "Терминал", 640, 400, 160, 120)
    out = QTextEdit()
    out.setReadOnly(True)
    out.setStyleSheet("background:#0d0d0d; color:#e0e0e0; "
                      "font-family:'Consolas','Monospace'; font-size:10pt;")
    out.append("DreamUX Terminal\n")
    win.body_lay.addWidget(out, 1)
    inp = QLineEdit()
    inp.setPlaceholderText("user@dreamux:~$")
    win.body_lay.addWidget(inp)

    def on_enter():
        cmd = inp.text().strip()
        if not cmd:
            return
        inp.clear()
        out.append(f"$ {cmd}")
        if cmd == "help":
            out.append("help, disks, whoami, date, clear")
        elif cmd == "disks":
            try:
                from plugins.vfs import format_info
                out.append(format_info())
            except Exception as e:
                out.append(str(e))
        elif cmd == "whoami":
            import getpass
            out.append(getpass.getuser())
        elif cmd == "date":
            out.append(datetime.datetime.now().strftime("%c"))
        elif cmd == "clear":
            out.clear()
        else:
            out.append(f"command not found: {cmd}")

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
    l1 = QLabel("DreamUX"); l1.setStyleSheet("font-size:24pt; font-weight:700;")
    l1.setAlignment(Qt.AlignmentFlag.AlignCenter)
    win.body_lay.addWidget(l1)
    l2 = QLabel("IDEAS INTO EXPERIENCES")
    l2.setStyleSheet("color:#9a9a9a; letter-spacing:3px;")
    l2.setAlignment(Qt.AlignmentFlag.AlignCenter)
    win.body_lay.addWidget(l2)
    l3 = QLabel("Версия 2.5.0\nPyQt6 · Adwaita dark")
    l3.setStyleSheet("color:#9a9a9a; font-size:9pt;")
    l3.setAlignment(Qt.AlignmentFlag.AlignCenter)
    win.body_lay.addWidget(l3)


def open_settings(desktop):
    win = GnomeWindow(desktop, "Настройки", 780, 500, 130, 80)
    tabs = QTabWidget()
    win.body_lay.addWidget(tabs)

    # О системе
    tab = QWidget()
    lay = QVBoxLayout(tab)
    lay.addWidget(QLabel("<h2>DreamUX 2.5.0</h2>"))
    lay.addWidget(QLabel("VFS: 2 раздела"))
    lay.addWidget(QLabel("PyQt6 · Adwaita dark"))
    lay.addStretch()
    tabs.addTab(tab, "О системе")

    # Диски
    tab2 = QWidget()
    lay2 = QVBoxLayout(tab2)
    info = QTextEdit()
    info.setReadOnly(True)
    info.setStyleSheet("background:#0d0d0d; color:#e0e0e0; "
                       "font-family:'Consolas','Monospace'; font-size:10pt;")
    try:
        from plugins.vfs import format_info
        info.setPlainText(format_info())
    except Exception as e:
        info.setPlainText(f"Ошибка: {e}")
    lay2.addWidget(info)
    tabs.addTab(tab2, "Диски")


def open_browser(desktop):
    try:
        from browser import browser_open
        browser_open(desktop)
    except Exception as e:
        log_write("errors", "ERROR", f"browser: {e}")


def open_games(desktop):
    try:
        from games import games_open
        games_open(desktop)
    except Exception as e:
        log_write("errors", "ERROR", f"games: {e}")


def open_installers(desktop):
    try:
        from installers import installers_open
        installers_open(desktop)
    except Exception as e:
        log_write("errors", "ERROR", f"installers: {e}")


def open_av(desktop):
    win = GnomeWindow(desktop, "Антивирус", 680, 480, 200, 120)
    info = QTextEdit()
    info.setReadOnly(True)
    info.setStyleSheet("background:#0d0d0d; color:#e0e0e0; "
                       "font-family:'Consolas','Monospace'; font-size:10pt;")
    win.body_lay.addWidget(info)
    try:
        from av_bridge import AVBridge
        av = AVBridge(log_fn=lambda m: log_write("actions", "INFO", m))
        st = av.status()
        info.setPlainText(
            f"Антивирус главной ОС\n"
            f"─────────────────────\n"
            f"Активен:  {'да' if st['active'] else 'нет'}\n"
            f"Название: {st.get('name','—')}\n"
            f"Тип:      {st.get('type','—')}\n"
        )
    except Exception as e:
        info.setPlainText(f"Ошибка: {e}")


def open_vpn(desktop):
    win = GnomeWindow(desktop, "VPN", 620, 460, 200, 120)
    info = QTextEdit()
    info.setReadOnly(True)
    info.setStyleSheet("background:#0d0d0d; color:#e0e0e0; "
                       "font-family:'Consolas','Monospace'; font-size:10pt;")
    win.body_lay.addWidget(info)
    try:
        from ovpn import OVPNClient
        ovpn = OVPNClient(log_fn=lambda m: log_write("actions", "INFO", m))
        st = ovpn.status()
        info.setPlainText(
            f"OpenVPN\n"
            f"─────────────────────\n"
            f"OpenVPN:      {st['openvpn'] or 'НЕ найден'}\n"
            f"Конфиг:       {st['config'] or '—'}\n"
            f"Подключение:  {'АКТИВНО' if st['connected'] else 'нет'}\n"
        )
    except Exception as e:
        info.setPlainText(f"Ошибка: {e}")


def open_remote(desktop):
    try:
        from remote_tools_gui import remote_tools_open
        remote_tools_open(desktop)
    except Exception as e:
        log_write("errors", "ERROR", f"remote: {e}")


# ============================================================
# Главное окно
# ============================================================
class GnomeDesktop(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DreamUX")
        self.resize(1280, 800)
        self.windows = []

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

        log_write("actions", "INFO", "DreamUX GUI запущен")

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
            Toast(self.wallpaper, f"{os.path.basename(p)}")

    def _on_screen(self):
        screen = QApplication.primaryScreen()
        if not screen:
            return
        name = datetime.datetime.now().strftime("screen_%Y-%m-%d_%H-%M-%S.png")
        path = os.path.join(SCREENSHOTS_DIR, name)
        if screen.grabWindow(0).save(path, "PNG"):
            log_write("actions", "INFO", "Скриншот экрана", path=path)
            Toast(self.wallpaper, f"{name}")

    def closeEvent(self, e):
        log_write("actions", "INFO", "DreamUX GUI закрыт")
        super().closeEvent(e)

    def open_files(self):      open_files(self)
    def open_settings(self):   open_settings(self)
    def open_terminal(self):   open_terminal(self)
    def open_clocks(self):     open_clocks(self)
    def open_about(self):      open_about(self)
    def open_browser(self):    open_browser(self)
    def open_games(self):      open_games(self)
    def open_installers(self): open_installers(self)
    def open_av(self):         open_av(self)
    def open_vpn(self):        open_vpn(self)
    def open_remote(self):     open_remote(self)


# ============================================================
# Запуск
# ============================================================
def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(ADWAITA_DARK_QSS)

    win = GnomeDesktop()
    win.setWindowOpacity(0.0)

    def on_splash_done():
        screen = app.primaryScreen().availableGeometry()
        w = min(1280, screen.width() - 40)
        h = min(800, screen.height() - 40)
        x = screen.x() + (screen.width() - w) // 2
        y = screen.y() + (screen.height() - h) // 2
        win.setGeometry(x, y, w, h)
        win.setWindowOpacity(1.0)
        win.show()
        win.raise_()
        win.activateWindow()

    try:
        from splash import SplashScreen
        splash = SplashScreen(on_finished=on_splash_done, duration_ms=2500)
        splash.start()
    except Exception as e:
        log_write("errors", "WARN", f"splash недоступен: {e}")
        on_splash_done()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
