"""Обёртка для запуска browser_engine.py из DreamUX."""

import os
import sys
import subprocess


HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(HERE, "browser_engine.py")


def browser_open(desktop):
    """Запускает browser_engine.py отдельным процессом."""
    try:
        from gnome_gui import GnomeWindow, log_write
        from PyQt6.QtWidgets import QLabel
    except ImportError:
        return

    if not os.path.isfile(ENGINE):
        win = GnomeWindow(desktop, "Браузер", 600, 300, 200, 150)
        lbl = QLabel(f"browser_engine.py не найден:\n{ENGINE}")
        lbl.setWordWrap(True)
        win.body_lay.addWidget(lbl)
        return

    try:
        proc = subprocess.Popen(
            [sys.executable, ENGINE],
            cwd=HERE,
        )
        log_write("browser", "INFO", "Browser запущен (PID)",
                  pid=proc.pid)

        win = GnomeWindow(desktop, "Браузер", 520, 240, 300, 200)
        lbl = QLabel(
            f"🌐 DreamUX Browser запущен отдельным окном.\n\n"
            f"PID: {proc.pid}\n\n"
            f"Если окно не появилось — проверь cmd, откуда запущено ядро."
        )
        lbl.setWordWrap(True)
        lbl.setAlignment(lbl.alignment())
        win.body_lay.addWidget(lbl)
    except Exception as e:
        log_write("errors", "ERROR", f"browser: {e}")
        win = GnomeWindow(desktop, "Браузер", 520, 240, 300, 200)
        lbl = QLabel(f"Не удалось запустить браузер:\n{e}")
        lbl.setWordWrap(True)
        win.body_lay.addWidget(lbl)
