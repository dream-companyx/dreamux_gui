"""RemoteTools GUI — панель управления компонентами DreamUX."""

import os
import sys
import datetime
import shutil
import zipfile

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QListWidget, QListWidgetItem, QMessageBox,
    QTabWidget, QInputDialog,
)
from PyQt6.QtCore import Qt


HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(HERE)
KERNEL_DIR = os.path.dirname(PLUGIN_DIR)
SNAPSHOTS_DIR = os.path.join(KERNEL_DIR, "snapshots")
SANDBOX_DIR = os.path.join(KERNEL_DIR, "sandbox")
LOGS_DIR = os.path.join(HERE, "logs")
CONFIG_DIR = os.path.join(KERNEL_DIR, "config")
AVDB_DIR = os.path.join(KERNEL_DIR, "avdb")

COMPONENTS = {
    "sandbox":   SANDBOX_DIR,
    "logs":      LOGS_DIR,
    "config":    CONFIG_DIR,
    "avdb":      AVDB_DIR,
    "gnome_gui": HERE,
}


def _human_size(n):
    for u in ["Б", "КБ", "МБ", "ГБ"]:
        if n < 1024:
            return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} ТБ"


def _dir_size(path):
    total = 0
    if not os.path.isdir(path):
        return 0
    for root, _, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def _ensure():
    os.makedirs(SNAPSHOTS_DIR, exist_ok=True)


def remote_tools_open(desktop):
    try:
        from gnome_gui import GnomeWindow, log_write
    except ImportError:
        from .gnome_gui import GnomeWindow, log_write

    win = GnomeWindow(desktop, "RemoteTools", 780, 540, 180, 90)
    tabs = QTabWidget()
    win.body_lay.addWidget(tabs)

    # --- Вкладка 1: Компоненты ---
    tab1 = QWidget()
    t1 = QVBoxLayout(tab1)

    info = QTextEdit()
    info.setReadOnly(True)
    info.setStyleSheet(
        "background:#0d0d0d; color:#e0e0e0; "
        "font-family:'Consolas','Monospace'; font-size:10pt;"
    )
    t1.addWidget(info, 1)

    def refresh_info():
        lines = ["RemoteTools — состояние DreamUX", "=" * 50, ""]
        lines.append(f"Корень:    {KERNEL_DIR}")
        lines.append(f"Снапшоты:  {SNAPSHOTS_DIR}")
        lines.append("")
        lines.append(f"{'Компонент':<14} {'Размер':<12} {'Статус'}")
        lines.append("-" * 40)
        for name, path in COMPONENTS.items():
            if os.path.isdir(path):
                size = _human_size(_dir_size(path))
                lines.append(f"{name:<14} {size:<12} OK")
            else:
                lines.append(f"{name:<14} {'—':<12} НЕТ")
        lines.append("")
        _ensure()
        snaps = sorted(os.listdir(SNAPSHOTS_DIR))
        lines.append(f"Снапшоты ({len(snaps)}):")
        if not snaps:
            lines.append("  (нет)")
        else:
            for s in snaps[-10:]:
                p = os.path.join(SNAPSHOTS_DIR, s)
                lines.append(f"  • {s}  ({_human_size(_dir_size(p))})")
        info.setPlainText("\n".join(lines))

    refresh_info()

    def _backup():
        _ensure()
        ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        dst = os.path.join(SNAPSHOTS_DIR, f"full_{ts}")
        os.makedirs(dst, exist_ok=True)
        for name, path in COMPONENTS.items():
            if os.path.isdir(path):
                try:
                    shutil.copytree(path, os.path.join(dst, name))
                except Exception:
                    pass
        log_write("actions", "INFO", "RemoteTools: полный снапшот", dst=dst)
        QMessageBox.information(win, "RemoteTools", f"Снапшот создан:\n{dst}")
        refresh_info()

    def _reset_full():
        r = QMessageBox.question(win, "RemoteTools",
            "Сбросить ВСЕ компоненты?\n"
            "sandbox, logs, config, avdb — будут пересозданы.\n"
            "Снапшоты НЕ удаляются.")
        if r != QMessageBox.StandardButton.Yes:
            return
        for name, path in COMPONENTS.items():
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
            os.makedirs(path, exist_ok=True)
        log_write("sandbox", "RESET", "RemoteTools: полный сброс")
        QMessageBox.information(win, "RemoteTools", "Все компоненты сброшены.")
        refresh_info()

    def _reset_one():
        name, ok = QInputDialog.getItem(
            win, "RemoteTools", "Компонент для сброса:",
            list(COMPONENTS.keys()), 0, False,
        )
        if not ok:
            return
        path = COMPONENTS[name]
        shutil.rmtree(path, ignore_errors=True)
        os.makedirs(path, exist_ok=True)
        log_write("sandbox", "RESET", f"RemoteTools: сброс {name}")
        QMessageBox.information(win, "RemoteTools", f"{name} сброшен.")
        refresh_info()

    def _export():
        _ensure()
        ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        zip_path = os.path.join(SNAPSHOTS_DIR, f"dreamux_backup_{ts}.zip")
        try:
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for name, path in COMPONENTS.items():
                    if os.path.isdir(path):
                        for root, _, files in os.walk(path):
                            for f in files:
                                full = os.path.join(root, f)
                                rel = os.path.relpath(full, KERNEL_DIR)
                                zf.write(full, rel)
            log_write("actions", "INFO", "RemoteTools: экспорт", zip_path=zip_path)
            QMessageBox.information(win, "RemoteTools",
                f"Экспортировано:\n{zip_path}")
        except Exception as e:
            QMessageBox.warning(win, "RemoteTools", f"Ошибка: {e}")

    b1 = QPushButton("Снапшот (full)")
    b1.setObjectName("WinBtn")
    b1.clicked.connect(_backup)
    t1.addWidget(b1)

    btns = QHBoxLayout()
    b2 = QPushButton("Сброс компонента"); b2.setObjectName("WinBtn")
    b2.clicked.connect(_reset_one); btns.addWidget(b2)
    b3 = QPushButton("Сброс ВСЕГО"); b3.setObjectName("WinBtn")
    b3.clicked.connect(_reset_full); btns.addWidget(b3)
    b4 = QPushButton("Экспорт в ZIP"); b4.setObjectName("WinBtn")
    b4.clicked.connect(_export); btns.addWidget(b4)
    b5 = QPushButton("Обновить"); b5.setObjectName("WinBtn")
    b5.clicked.connect(refresh_info); btns.addWidget(b5)
    t1.addLayout(btns)
    tabs.addTab(tab1, "Компоненты")

    # --- Вкладка 2: Снапшоты ---
    tab2 = QWidget()
    t2 = QVBoxLayout(tab2)
    t2.addWidget(QLabel("Снапшоты:"))

    list_w = QListWidget()
    list_w.setObjectName("Sidebar")
    t2.addWidget(list_w, 1)

    def refresh_snaps():
        list_w.clear()
        _ensure()
        for s in sorted(os.listdir(SNAPSHOTS_DIR), reverse=True):
            list_w.addItem(QListWidgetItem(s))

    refresh_snaps()

    def _restore():
        it = list_w.currentItem()
        if not it:
            return
        snap_name = it.text()
        name, ok = QInputDialog.getItem(
            win, "Восстановить", "Компонент:",
            list(COMPONENTS.keys()), 0, False,
        )
        if not ok:
            return
        snap_dir = os.path.join(SNAPSHOTS_DIR, snap_name)
        if snap_name.startswith("full_"):
            src = os.path.join(snap_dir, name)
        else:
            src = snap_dir
        if not os.path.isdir(src):
            QMessageBox.warning(win, "RemoteTools",
                f"В снапшоте нет '{name}'.")
            return
        dst = COMPONENTS[name]
        shutil.rmtree(dst, ignore_errors=True)
        try:
            shutil.copytree(src, dst)
            log_write("actions", "INFO", "RemoteTools: восстановление",
                      component=name, snapshot=snap_name)
            QMessageBox.information(win, "RemoteTools",
                f"{name} восстановлен из {snap_name}")
            refresh_info()
        except Exception as e:
            QMessageBox.warning(win, "RemoteTools", f"Ошибка: {e}")

    def _delete_snap():
        it = list_w.currentItem()
        if not it:
            return
        snap_name = it.text()
        r = QMessageBox.question(win, "RemoteTools",
            f"Удалить снапшот?\n{snap_name}")
        if r != QMessageBox.StandardButton.Yes:
            return
        shutil.rmtree(os.path.join(SNAPSHOTS_DIR, snap_name), ignore_errors=True)
        refresh_snaps()
        refresh_info()

    def _clean():
        snaps = sorted(os.listdir(SNAPSHOTS_DIR))
        if len(snaps) <= 5:
            QMessageBox.information(win, "RemoteTools", "Нечего чистить.")
            return
        for s in snaps[:-5]:
            shutil.rmtree(os.path.join(SNAPSHOTS_DIR, s), ignore_errors=True)
        refresh_snaps()
        refresh_info()
        QMessageBox.information(win, "RemoteTools",
            "Оставлено 5 последних снапшотов.")

    rb = QHBoxLayout()
    br = QPushButton("Восстановить"); br.setObjectName("WinBtn")
    br.clicked.connect(_restore); rb.addWidget(br)
    bd = QPushButton("Удалить"); bd.setObjectName("WinBtn")
    bd.clicked.connect(_delete_snap); rb.addWidget(bd)
    bc = QPushButton("Оставить 5"); bc.setObjectName("WinBtn")
    bc.clicked.connect(_clean); rb.addWidget(bc)
    bu = QPushButton("Обновить"); bu.setObjectName("WinBtn")
    bu.clicked.connect(refresh_snaps); rb.addWidget(bu)
    t2.addLayout(rb)
    tabs.addTab(tab2, "Снапшоты")

    log_write("actions", "INFO", "RemoteTools открыт")
