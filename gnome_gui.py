#!/usr/bin/env python3
"""GNOME-интерфейс DreamUX. Работает с DRXFS через VFS."""

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

if KERNEL_DIR not in sys.path:
    sys.path.insert(0, KERNEL_DIR)
if PLUGIN_DIR not in sys.path:
    sys.path.insert(0, PLUGIN_DIR)

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
    QTabWidget, QMenu, QInputDialog, QComboBox,
)


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


_VFS = None


def _get_vfs():
    global _VFS
    if _VFS is not None:
        return _VFS
    try:
        from plugins import vfs as _v
        _VFS = _v
        return _VFS
    except ImportError:
        pass
    try:
        import importlib.util
        vfs_path = os.path.join(PLUGIN_DIR, "vfs.py")
        if os.path.isfile(vfs_path):
            spec = importlib.util.spec_from_file_location("vfs", vfs_path)
            _v = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(_v)
            _VFS = _v
            return _VFS
    except Exception as e:
        log_write("errors", "ERROR", f"vfs import: {e}")
    return None


def _kernel_call(cmd, timeout=60):
    import socket
    addr = os.environ.get("DREAMUX_GUI_SERVER", "127.0.0.1:54325")
    token = os.environ.get("DREAMUX_GUI_TOKEN", "dreamux_gui_secret_2024")
    try:
        host, port = addr.split(":")
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((host, int(port)))
        s.sendall(json.dumps({"token": token, "cmd": cmd}).encode("utf-8") + b"\n")
        data = b""
        while b"\n" not in data:
            chunk = s.recv(65536)
            if not chunk:
                break
            data += chunk
        s.close()
        if not data:
            return {"ok": False, "error": "пустой ответ ядра"}
        return json.loads(data.decode("utf-8").strip())
    except ConnectionRefusedError:
        return {"ok": False, "error": "ядро не отвечает"}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


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
QComboBox { background-color: #1a1a1a; border: 1px solid #3a3a3a;
    border-radius: 6px; padding: 4px 8px; color: #ffffff; }
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
QMenu { background-color: #2b2b2b; color: #ffffff;
    border-radius: 10px; padding: 6px; border: 1px solid #3a3a3a; }
QMenu::item { padding: 8px 32px 8px 24px; border-radius: 6px; }
QMenu::item:selected { background-color: #3584e4; }
QMenu::separator { height: 1px; background-color: #3a3a3a;
                    margin: 4px 8px; }
"""


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


class DesktopIcon(QFrame):
    def __init__(self, parent, icon, label, callback):
        super().__init__(parent)
        self.callback = callback
        self.setFixedSize(90, 100)
        self.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(4)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ic = QLabel(icon)
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ic.setStyleSheet("font-size: 40pt; background: transparent;")
        lay.addWidget(ic)
        nm = QLabel(label)
        nm.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nm.setWordWrap(True)
        nm.setStyleSheet("color: white; font-size: 9pt; "
                         "background: transparent; font-weight: bold;")
        lay.addWidget(nm)
        self.setToolTip(label)

    def mouseDoubleClickEvent(self, event):
        if self.callback:
            self.callback()

    def enterEvent(self, event):
        self.setStyleSheet("background: rgba(255,255,255,30); border-radius: 8px;")

    def leaveEvent(self, event):
        self.setStyleSheet("background: transparent;")


class WallpaperWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.desktop = None
        self.icons_layer = None

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

    def setup_icons(self, desktop):
        self.desktop = desktop
        self.icons_layer = QWidget(self)
        self.icons_layer.setStyleSheet("background: transparent;")
        self.icons_layer.setGeometry(20, 40, 200, self.height() - 60)
        grid = QVBoxLayout(self.icons_layer)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(10)
        grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        base_apps = [
            ("📁", "Файлы",     desktop.open_files),
            ("🌐", "Браузер",   desktop.open_browser),
            ("🖥", "Терминал",  desktop.open_terminal),
            ("⚙", "Настройки", desktop.open_settings),
        ]
        for icon, label, cb in base_apps:
            ic = DesktopIcon(self.icons_layer, icon, label, cb)
            grid.addWidget(ic)
        try:
            _v = _get_vfs()
            if _v:
                items = _v.list_dir("disk2", "apps")
                for kind, name, size in items:
                    if kind == "dir":
                        ic = DesktopIcon(
                            self.icons_layer, "📦", name,
                            lambda n=name: desktop.launch_app_from_vfs(n),
                        )
                        grid.addWidget(ic)
        except Exception:
            pass

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.icons_layer:
            self.icons_layer.setGeometry(20, 40, 200, self.height() - 60)


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
        self._drag = None

    def closeEvent(self, event):
        if hasattr(self.desktop, "windows") and self in self.desktop.windows:
            self.desktop.windows.remove(self)
        super().closeEvent(event)


def open_files(desktop):
    log_write("actions", "INFO", "Открыто Files (DRXFS)")
    _v = _get_vfs()
    if _v is None:
        win = GnomeWindow(desktop, "Файлы", 600, 300, 200, 200)
        win.body_lay.addWidget(QLabel("⛔ VFS недоступен\nСмотри логи"))
        return

    win = GnomeWindow(desktop, "Файлы", 1100, 700, 80, 40)
    state = {"disk": "disk0", "path": "", "history": [], "index": -1}

    top = QHBoxLayout()
    top.setSpacing(6)
    top.setContentsMargins(4, 4, 4, 4)
    b_back = QPushButton("←")
    b_back.setObjectName("WinBtn")
    b_back.setFixedSize(34, 34)
    top.addWidget(b_back)
    b_fwd = QPushButton("→")
    b_fwd.setObjectName("WinBtn")
    b_fwd.setFixedSize(34, 34)
    top.addWidget(b_fwd)
    b_up = QPushButton("↑")
    b_up.setObjectName("WinBtn")
    b_up.setFixedSize(34, 34)
    top.addWidget(b_up)
    breadcrumb = QLabel("disk0:/")
    breadcrumb.setObjectName("H2")
    breadcrumb.setStyleSheet("padding: 8px 12px; background: #2a2a2a; "
                             "border-radius: 8px; color: #ffffff;")
    top.addWidget(breadcrumb, 1)
    disk_combo = QComboBox()
    disk_combo.addItems(["disk0 (СИСТЕМА)", "disk1 (ЗАГРУЗОЧНЫЙ)",
                         "disk2 (ОСТАЛЬНОЕ)"])
    disk_combo.setFixedWidth(200)
    top.addWidget(disk_combo)
    win.body_lay.addLayout(top)

    main = QHBoxLayout()
    main.setSpacing(0)
    sidebar = QListWidget()
    sidebar.setObjectName("Sidebar")
    sidebar.setFixedWidth(220)
    sidebar_paths = {}

    def add_section(title):
        it = QListWidgetItem(title)
        it.setFlags(Qt.ItemFlag.NoItemFlags)
        it.setForeground(QColor("#888888"))
        f = it.font()
        f.setBold(True)
        f.setPointSize(9)
        it.setFont(f)
        sidebar.addItem(it)

    def add_item(label, disk, path, icon="📁"):
        it = QListWidgetItem(f"{icon}  {label}")
        it.setToolTip(f"{disk}:/{path}")
        sidebar.addItem(it)
        sidebar_paths[sidebar.count() - 1] = (disk, path)

    add_section("БЫСТРЫЙ ДОСТУП")
    add_item("Система", "disk0", "system", "💽")
    add_item("Ядро", "disk0", "system/kernel", "⚙")
    add_item("Плагины", "disk0", "system/plugins", "🧩")
    add_item("Логи", "disk0", "system/logs", "📋")
    add_item("Пользователи", "disk0", "system/users", "👥")
    add_item("Загрузка", "disk1", "boot", "🚀")
    add_item("Домой", "disk2", "home", "🏠")
    add_item("Приложения", "disk2", "apps", "📦")
    add_item("Пакеты", "disk2", "packages", "🗜")
    add_item("Песочница", "disk2", "sandbox", "🧪")
    add_item("Загрузки", "disk2", "downloads", "⬇")
    main.addWidget(sidebar)

    right = QWidget()
    rl = QVBoxLayout(right)
    rl.setContentsMargins(16, 16, 16, 16)
    rl.setSpacing(8)
    stack = QStackedWidget()
    grid_w = QWidget()
    grid = QGridLayout(grid_w)
    grid.setSpacing(24)
    grid.setContentsMargins(8, 8, 8, 8)
    grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setWidget(grid_w)
    scroll.setStyleSheet("border: none; background: transparent;")
    stack.addWidget(scroll)

    viewer = QWidget()
    vl = QVBoxLayout(viewer)
    vhead = QHBoxLayout()
    vname = QLabel("")
    vname.setObjectName("H2")
    vhead.addWidget(vname, 1)
    vback = QPushButton("← Назад")
    vback.setObjectName("WinBtn")
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
    stack.addWidget(viewer)
    rl.addWidget(stack, 1)
    main.addWidget(right, 1)
    win.body_lay.addLayout(main)

    TEXT_EXT = {"txt", "md", "log", "json", "xml", "yml", "yaml", "ini",
                "cfg", "toml", "env", "html", "htm", "css", "sql", "csv",
                "tsv", "dupfi", "py", "js", "sh", "bat", "c", "h", "cpp"}
    IMG_EXT = {"png", "jpg", "jpeg", "gif", "bmp", "webp", "tiff", "ico", "svg"}
    FOLDER_COLOR = "#62a0ea"
    FILE_COLOR = "#ffffff"

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
            "duap": "🗜", "dupfi": "📦",
            "py": "🐍", "js": "📜", "html": "🌐", "css": "🎨",
            "exe": "⚙", "sh": "⚙", "bat": "⚙",
        }.get(ext, "📄")

    def join_path(*parts):
        return "/".join(p.strip("/") for p in parts if p).strip("/")

    def safe_read_text(data):
        if data is None:
            return ""
        if len(data) > 2 * 1024 * 1024:
            return f"Файл слишком большой: {len(data):,} байт"
        try:
            return data.decode("utf-8", errors="replace")
        except Exception as e:
            return f"Ошибка: {e}"

    def open_file_internal(disk, path):
        ext = path.rsplit(".", 1)[-1].lower() if "." in os.path.basename(path) else ""
        name = os.path.basename(path)
        vname.setText(f"{disk}:/{path}")
        data = _v.read(disk, path)
        if data is None:
            vtext.setPlainText("Не удалось прочитать")
            vbody.setCurrentWidget(vtext)
            stack.setCurrentWidget(viewer)
            return
        if ext == "dupfi":
            resp = _kernel_call(f"/dupfi install {path}")
            vtext.setPlainText(resp.get("output", resp.get("error", "")))
            vbody.setCurrentWidget(vtext)
        elif ext in TEXT_EXT or ext == "":
            vtext.setPlainText(safe_read_text(data))
            vbody.setCurrentWidget(vtext)
        elif ext in IMG_EXT:
            pix = QPixmap()
            if pix.loadFromData(data):
                vimg.setPixmap(pix)
                vbody.setCurrentWidget(vimg_scroll)
            else:
                vtext.setPlainText(f"Не удалось: {name}")
                vbody.setCurrentWidget(vtext)
        else:
            raw = data[:512]
            lines = []
            for off in range(0, len(raw), 16):
                chunk = raw[off:off + 16]
                hs = " ".join(f"{b:02x}" for b in chunk)
                asc = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
                lines.append(f"{off:08x}  {hs:<47}  {asc}")
            vtext.setPlainText(f"Бинарный: {name}\n\n" + "\n".join(lines))
            vbody.setCurrentWidget(vtext)
        stack.setCurrentWidget(viewer)

    def show_grid():
        stack.setCurrentWidget(scroll)
    vback.clicked.connect(show_grid)

    def render_dir(disk, path):
        state["disk"] = disk
        state["path"] = path
        breadcrumb.setText(f"💾 {disk}:/{path}" if path else f"💾 {disk}:/")
        breadcrumb.setToolTip(f"{disk}:/{path}")
        while grid.count():
            it = grid.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()
        try:
            items = _v.list_dir(disk, path)
        except Exception as e:
            err = QLabel(f"⚠ Ошибка: {e}")
            err.setStyleSheet("color:#e01b24; font-size:12pt;")
            grid.addWidget(err, 0, 0)
            return
        if not items:
            empty = QLabel("(пусто)")
            empty.setStyleSheet("color:#6a6a6a; font-size:12pt;")
            grid.addWidget(empty, 0, 0)
            return
        col = r = 0
        for kind, name, size in items:
            is_dir = (kind == "dir")
            full_path = join_path(path, name)
            cell = QWidget()
            cell.setFixedSize(110, 110)
            cl = QVBoxLayout(cell)
            cl.setContentsMargins(4, 4, 4, 4)
            cl.setSpacing(4)
            cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ic = QLabel(icon_for(name, is_dir))
            ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ic.setStyleSheet(
                f"font-size:44pt; color:{FOLDER_COLOR if is_dir else FILE_COLOR};"
            )
            cl.addWidget(ic)
            nm = QLabel(name)
            nm.setAlignment(Qt.AlignmentFlag.AlignCenter)
            nm.setWordWrap(True)
            nm.setStyleSheet("color:#ffffff; font-size:9pt;")
            nm.setFixedHeight(30)
            cl.addWidget(nm)

            def mh(is_dir=is_dir, full_path=full_path, disk=disk):
                def _h(ev):
                    if is_dir:
                        navigate(disk, full_path)
                    else:
                        open_file_internal(disk, full_path)
                return _h
            cell.mouseDoubleClickEvent = mh()

            def cm(name=name, is_dir=is_dir, full_path=full_path,
                   disk=disk, size=size):
                def _h(ev):
                    menu = QMenu(cell)
                    menu.setStyleSheet(CONTEXT_MENU_QSS)
                    menu.addAction(
                        "📂  Открыть",
                        lambda: (navigate(disk, full_path) if is_dir
                                 else open_file_internal(disk, full_path))
                    )
                    if not is_dir:
                        menu.addAction(
                            "💾  Извлечь на Windows",
                            lambda: extract_to_local(disk, full_path, name)
                        )
                    menu.addSeparator()
                    menu.addAction(
                        "📋  Копировать путь",
                        lambda: QApplication.clipboard().setText(
                            f"{disk}:/{full_path}")
                    )
                    menu.addAction(
                        "🗑  Удалить",
                        lambda: delete_item(disk, full_path, name)
                    )
                    menu.exec(ev.globalPosition().toPoint())
                return _h
            cell.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            cell.customContextMenuRequested = cm()
            grid.addWidget(cell, r, col)
            col += 1
            if col >= 7:
                col = 0
                r += 1

    def navigate(disk, path, add_history=True):
        if add_history:
            state["history"] = state["history"][:state["index"] + 1]
            state["history"].append((disk, path))
            state["index"] = len(state["history"]) - 1
        render_dir(disk, path)
        show_grid()

    def go_back():
        if state["index"] > 0:
            state["index"] -= 1
            d, p = state["history"][state["index"]]
            render_dir(d, p)
            show_grid()

    def go_fwd():
        if state["index"] < len(state["history"]) - 1:
            state["index"] += 1
            d, p = state["history"][state["index"]]
            render_dir(d, p)
            show_grid()

    def go_up():
        d = state["disk"]
        p = state["path"]
        parent = "/".join(p.split("/")[:-1]) if p else ""
        if parent != p:
            navigate(d, parent)

    def extract_to_local(disk, path, name):
        target, _ = QFileDialog.getSaveFileName(
            win, "Сохранить", name, "Все файлы (*)"
        )
        if not target:
            return
        data = _v.read(disk, path)
        if data is None:
            QMessageBox.warning(win, "Ошибка", "Не удалось прочитать")
            return
        try:
            with open(target, "wb") as f:
                f.write(data)
            Toast(desktop.wallpaper, f"✅ {os.path.basename(target)}")
        except Exception as e:
            QMessageBox.critical(win, "Ошибка", str(e))

    def delete_item(disk, path, name):
        r = QMessageBox.question(win, "Удаление", f"Удалить '{name}'?")
        if r != QMessageBox.StandardButton.Yes:
            return
        if _v.delete(disk, path):
            Toast(desktop.wallpaper, f"🗑 {name}")
            render_dir(disk, state["path"] if disk == state["disk"] else "")
        else:
            QMessageBox.warning(win, "Ошибка", "Не удалось удалить")

    b_back.clicked.connect(go_back)
    b_fwd.clicked.connect(go_fwd)
    b_up.clicked.connect(go_up)

    def on_sidebar(item):
        idx = sidebar.row(item)
        target = sidebar_paths.get(idx)
        if target:
            navigate(target[0], target[1])
    sidebar.itemClicked.connect(on_sidebar)

    def on_disk_change(idx):
        disk = ["disk0", "disk1", "disk2"][idx]
        navigate(disk, "")
    disk_combo.currentIndexChanged.connect(on_disk_change)

    navigate("disk0", "system")


def open_terminal(desktop):
    log_write("actions", "INFO", "Открыт Терминал")
    win = GnomeWindow(desktop, "Терминал", 780, 520, 160, 120)
    out = QTextEdit()
    out.setReadOnly(True)
    out.setStyleSheet("background:#0d0d0d; color:#e0e0e0; "
                      "font-family:'Consolas','Monospace'; font-size:10pt;")
    out.append("DreamUX Terminal")
    out.append("Все команды выполняются ядром DreamUX.")
    out.append("Введите 'help' для списка.")
    out.append("Примеры: /vfs info, /disks, /dupfi list, ls, cat\n")
    win.body_lay.addWidget(out, 1)
    inp = QLineEdit()
    inp.setPlaceholderText("dreamux>")
    win.body_lay.addWidget(inp)

    def on_enter():
        raw = inp.text().strip()
        if not raw:
            return
        inp.clear()
        out.append(f"dreamux> {raw}")
        resp = _kernel_call(raw)
        if resp.get("output"):
            for line in resp["output"].rstrip().splitlines():
                out.append(line)
        if not resp.get("ok") and resp.get("error"):
            out.append(f"[error] {resp['error']}")
        sb = out.verticalScrollBar()
        sb.setValue(sb.maximum())

    inp.returnPressed.connect(on_enter)
    inp.setFocus()


def open_clocks(desktop):
    win = GnomeWindow(desktop, "Часы", 380, 260, 380, 180)
    t = QLabel()
    t.setStyleSheet("font-size:42pt; font-weight:200; color:#3584e4;")
    t.setAlignment(Qt.AlignmentFlag.AlignCenter)
    win.body_lay.addWidget(t)
    d = QLabel()
    d.setStyleSheet("color:#9a9a9a; font-size:11pt;")
    d.setAlignment(Qt.AlignmentFlag.AlignCenter)
    win.body_lay.addWidget(d)

    def tick():
        now = datetime.datetime.now()
        t.setText(now.strftime("%H:%M:%S"))
        d.setText(now.strftime("%A, %d %B %Y"))
        QTimer.singleShot(500, tick)
    tick()


def open_about(desktop):
    win = GnomeWindow(desktop, "О системе", 420, 320, 340, 200)
    l1 = QLabel("DreamUX")
    l1.setStyleSheet("font-size:24pt; font-weight:700;")
    l1.setAlignment(Qt.AlignmentFlag.AlignCenter)
    win.body_lay.addWidget(l1)
    l2 = QLabel("IDEAS INTO EXPERIENCES")
    l2.setStyleSheet("color:#9a9a9a; letter-spacing:3px;")
    l2.setAlignment(Qt.AlignmentFlag.AlignCenter)
    win.body_lay.addWidget(l2)
    l3 = QLabel("Версия 2.5.0\nDRXFS + VHD")
    l3.setStyleSheet("color:#9a9a9a; font-size:9pt;")
    l3.setAlignment(Qt.AlignmentFlag.AlignCenter)
    win.body_lay.addWidget(l3)


def open_settings(desktop):
    win = GnomeWindow(desktop, "Настройки", 780, 500, 130, 80)
    tabs = QTabWidget()
    win.body_lay.addWidget(tabs)
    tab = QWidget()
    lay = QVBoxLayout(tab)
    lay.addWidget(QLabel("<h2>DreamUX 2.5.0</h2>"))
    lay.addWidget(QLabel("VFS: DRXFS в 3 VHD"))
    lay.addWidget(QLabel("Файловая система: собственная (DRXFS)"))
    lay.addWidget(QLabel("Монтирование: не требуется"))
    lay.addStretch()
    tabs.addTab(tab, "О системе")
    tab2 = QWidget()
    lay2 = QVBoxLayout(tab2)
    info = QTextEdit()
    info.setReadOnly(True)
    info.setStyleSheet("background:#0d0d0d; color:#e0e0e0; "
                       "font-family:'Consolas','Monospace'; font-size:10pt;")
    _v = _get_vfs()
    if _v:
        try:
            info.setPlainText(_v.format_info())
        except Exception as e:
            info.setPlainText(f"Ошибка: {e}")
    else:
        info.setPlainText("⛔ VFS недоступен")
    lay2.addWidget(info)
    tabs.addTab(tab2, "Диски")


def open_browser(desktop, url=None):
    log_write("actions", "INFO", "Открыто Browser")
    try:
        from PyQt6.QtWebEngineWidgets import QWebEngineView
        from PyQt6.QtCore import QUrl
        HAS_WEB = True
    except ImportError:
        HAS_WEB = False
    win = GnomeWindow(desktop, "Браузер", 1200, 800, 60, 30)
    top = QHBoxLayout()
    top.setSpacing(6)
    b_back = QPushButton("←")
    b_back.setObjectName("WinBtn")
    b_back.setFixedSize(34, 34)
    top.addWidget(b_back)
    b_fwd = QPushButton("→")
    b_fwd.setObjectName("WinBtn")
    b_fwd.setFixedSize(34, 34)
    top.addWidget(b_fwd)
    b_rel = QPushButton("⟳")
    b_rel.setObjectName("WinBtn")
    b_rel.setFixedSize(34, 34)
    top.addWidget(b_rel)
    b_home = QPushButton("🏠")
    b_home.setObjectName("WinBtn")
    b_home.setFixedSize(34, 34)
    top.addWidget(b_home)
    url_edit = QLineEdit()
    url_edit.setPlaceholderText("Поиск или адрес...")
    top.addWidget(url_edit, 1)
    b_go = QPushButton("→")
    b_go.setObjectName("WinBtn")
    b_go.setFixedSize(34, 34)
    top.addWidget(b_go)
    win.body_lay.addLayout(top)
    if not HAS_WEB:
        msg = QLabel("⚠ PyQt6-WebEngine не установлен.\n"
                     "pip install PyQt6-WebEngine")
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        win.body_lay.addWidget(msg, 1)
        return
    browser = QWebEngineView()
    win.body_lay.addWidget(browser, 1)
    HOME = url or "https://www.google.com"
    browser.setUrl(QUrl(HOME))

    def on_url(qurl):
        url_edit.setText(qurl.toString())
    browser.urlChanged.connect(on_url)
    b_back.clicked.connect(browser.back)
    b_fwd.clicked.connect(browser.forward)
    b_rel.clicked.connect(browser.reload)
    b_home.clicked.connect(lambda: browser.setUrl(QUrl(HOME)))

    def go():
        t = url_edit.text().strip()
        if not t:
            return
        if "." not in t or " " in t:
            t = f"https://www.google.com/search?q={t}"
        if not t.startswith("http"):
            t = "https://" + t
        browser.setUrl(QUrl(t))

    b_go.clicked.connect(go)
    url_edit.returnPressed.connect(go)
    url_edit.setFocus()


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
    resp = _kernel_call("/av status")
    info.setPlainText(resp.get("output") or resp.get("error") or "нет данных")


def open_vpn(desktop):
    win = GnomeWindow(desktop, "VPN", 620, 460, 200, 120)
    info = QTextEdit()
    info.setReadOnly(True)
    info.setStyleSheet("background:#0d0d0d; color:#e0e0e0; "
                       "font-family:'Consolas','Monospace'; font-size:10pt;")
    win.body_lay.addWidget(info)
    resp = _kernel_call("/vpn status")
    info.setPlainText(resp.get("output") or resp.get("error") or "нет данных")


def open_remote(desktop):
    try:
        from remote_tools_gui import remote_tools_open
        remote_tools_open(desktop)
    except Exception as e:
        log_write("errors", "ERROR", f"remote: {e}")


class GnomeDesktop(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DreamUX")
        screen = None
        try:
            from PyQt6.QtWidgets import QApplication
            screen = QApplication.primaryScreen().availableGeometry()
        except Exception:
            pass
        if screen:
            self.resize(screen.width(), screen.height())
        else:
            self.resize(1920, 1080)
        self.windows = []
        self.wallpaper = WallpaperWidget()
        self.wallpaper.desktop = self
        self.wallpaper.setup_icons(self)
        self.setCentralWidget(self.wallpaper)
        self.panel = TopPanel(self.wallpaper)
        self.panel.setGeometry(0, 0, self.width(), 32)
        self.panel.raise_()
        self.dock = Dock(self, self.wallpaper)
        self.dock.adjustSize()
        self._position_dock()
        self.dock.raise_()
        QShortcut(QKeySequence("F12"), self).activated.connect(self._on_screenshot)
        QShortcut(QKeySequence("F11"), self).activated.connect(self._toggle_fullscreen)
        QShortcut(QKeySequence("Esc"), self).activated.connect(self._toggle_fullscreen)
        log_write("actions", "INFO", "DreamUX GUI запущен")

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showMaximized()
        else:
            self.showFullScreen()

    def _show_desktop_menu(self, pos):
        menu = QMenu(self.wallpaper)
        menu.setStyleSheet(CONTEXT_MENU_QSS)
        menu.addAction("📁  Открыть Files", self.open_files)
        menu.addAction("📦  Paket Installer", self.open_installers)
        menu.addAction("🌐  Открыть Browser", self.open_browser)
        menu.addAction("▶  Открыть Terminal", self.open_terminal)
        menu.addSeparator()
        menu.addAction("💽  Диски VFS", self.open_disks)
        menu.addSeparator()
        menu.addAction("⚙  Настройки", self.open_settings)
        menu.addAction("ℹ  О системе", self.open_about)
        menu.addSeparator()
        menu.addAction("🔄  Обновить", self.repaint)
        menu.addAction("🚪  Выход", self.close)
        menu.exec(pos)

    def open_disks(self):
        win = GnomeWindow(self, "Диски", 700, 500, 200, 120)
        info = QTextEdit()
        info.setReadOnly(True)
        info.setStyleSheet("background:#0d0d0d; color:#e0e0e0; "
                           "font-family:'Consolas','Monospace'; font-size:10pt;")
        _v = _get_vfs()
        if _v:
            try:
                info.setPlainText(_v.format_info())
            except Exception as e:
                info.setPlainText(str(e))
        else:
            info.setPlainText("⛔ VFS недоступен")
        win.body_lay.addWidget(info)

    def launch_app_from_vfs(self, app_name):
        _v = _get_vfs()
        if _v is None:
            QMessageBox.warning(self, "Ошибка", "VFS недоступен")
            return
        try:
            items = _v.list_dir("disk2", f"apps/{app_name}")
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"list: {e}")
            return
        entry = None
        for kind, name, size in items:
            if kind == "file" and name.endswith(".py"):
                entry = f"apps/{app_name}/{name}"
                break
        if not entry:
            QMessageBox.warning(self, "Ошибка", "Нет .py в приложении")
            return
        import tempfile
        import subprocess
        data = _v.read("disk2", entry)
        if data is None:
            return
        tmp_dir = os.path.join(KERNEL_DIR, "tmp")
        os.makedirs(tmp_dir, exist_ok=True)
        tmp = tempfile.NamedTemporaryFile(suffix=".py", delete=False, dir=tmp_dir)
        tmp.close()
        with open(tmp.name, "wb") as f:
            f.write(data)
        try:
            subprocess.Popen([sys.executable, tmp.name])
            Toast(self.wallpaper, f"▶ {app_name}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.panel.setGeometry(0, 0, self.width(), 32)
        self._position_dock()
        self.panel.raise_()
        self.dock.raise_()

    def _position_dock(self):
        self.dock.adjustSize()
        x = (self.width() - self.dock.width()) // 2
        y = self.height() - self.dock.height() - 12
        self.dock.move(x, y)
        self.dock.raise_()

    def _on_screenshot(self):
        os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
        name = datetime.datetime.now().strftime("screenshot_%Y-%m-%d_%H-%M-%S.png")
        path = os.path.join(SCREENSHOTS_DIR, name)
        if self.grab().save(path, "PNG"):
            log_write("actions", "INFO", "Скриншот", path=path)
            Toast(self.wallpaper, f"{os.path.basename(path)}")

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


def main():
    from PyQt6.QtCore import qInstallMessageHandler
    def _qt_msg_handler(mode, ctx, msg):
        if "Unknown property" in msg:
            return
        try:
            print(msg, file=sys.stderr)
        except Exception:
            pass
    qInstallMessageHandler(_qt_msg_handler)
    try:
        from PyQt6.QtCore import Qt as QtCore
        QApplication.setAttribute(QtCore.ApplicationAttribute.AA_ShareOpenGLContexts)
    except Exception:
        pass
    app = QApplication(sys.argv)
    app.setStyleSheet(ADWAITA_DARK_QSS)
    win = GnomeDesktop()

    def on_unlock(username):
        log_write("actions", "INFO", f"Пользователь '{username}' вошёл")
        win.showFullScreen()
        win.raise_()
        win.activateWindow()

    forced_user = os.environ.get("SIMPLEOS_USERNAME")
    if forced_user:
        on_unlock(forced_user)
        sys.exit(app.exec())

    lock = None
    try:
        sys.path.insert(0, HERE)
        from lock_screen import LockScreen
        lock = LockScreen(on_unlock=on_unlock)
    except Exception as e:
        log_write("errors", "ERROR", f"lock_screen (init): {e}")

    def show_lock_or_desktop():
        if lock is not None:
            try:
                lock.show_fullscreen()
                return
            except Exception as e:
                log_write("errors", "ERROR", f"lock_screen show: {e}")
        on_unlock("unknown")

    splash_ok = False
    try:
        sys.path.insert(0, HERE)
        from splash import SplashScreen
        splash = SplashScreen(on_finished=show_lock_or_desktop, duration_ms=2500)
        splash.start()
        splash_ok = True
    except Exception as e:
        log_write("errors", "ERROR", f"splash: {e}")

    if not splash_ok:
        show_lock_or_desktop()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
