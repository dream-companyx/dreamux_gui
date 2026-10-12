"""Зашифрованный браузер второстепенной ОС. Работает через ядро по токену."""

import os
import sys

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QTextEdit, QLabel,
)

NETD = None
log_write = None


def browser_open(desktop):
    global NETD, log_write
    try:
        from netd import get_global_daemon
        NETD = get_global_daemon()
    except Exception:
        NETD = None
    try:
        from gnome_gui import GnomeWindow, log_write as lw
        log_write = lw
    except Exception:
        log_write = lambda *a, **k: None

    if NETD is None:
        from gnome_gui import GnomeWindow
        win = GnomeWindow(desktop, "Браузер", 620, 320, 200, 150)
        QLabel("⛔ Ядро недоступно.", win.body).pack(pady=30)
        return

    token = NETD.issue_session("browser", require_vpn=True)
    if not token:
        from gnome_gui import GnomeWindow
        win = GnomeWindow(desktop, "Браузер", 620, 320, 200, 150)
        QLabel("⛔ Ядро отказало в сессии.", win.body).pack(pady=30)
        return

    from gnome_gui import GnomeWindow
    win = GnomeWindow(desktop, "Браузер (зашифрованный)", 900, 620, 120, 60)

    bar = QHBoxLayout()
    back = QPushButton("◀"); back.setObjectName("WinBtn")
    fwd = QPushButton("▶"); fwd.setObjectName("WinBtn")
    rel = QPushButton("⟳"); rel.setObjectName("WinBtn")
    for b in (back, fwd, rel):
        bar.addWidget(b)
    url_edit = QLineEdit()
    url_edit.setPlaceholderText("https://example.com")
    bar.addWidget(url_edit, 1)
    go = QPushButton("→"); go.setObjectName("WinBtn")
    bar.addWidget(go)
    win.body_lay.addLayout(bar)

    status = QLabel("🔒 Зашифрованный канал · VPN · токен активен")
    status.setStyleSheet("color:#33d17a; padding:4px 8px;")
    win.body_lay.addWidget(status)

    view = QTextEdit()
    view.setReadOnly(True)
    view.setStyleSheet("background:#ffffff; color:#000; font-size:10pt;")
    win.body_lay.addWidget(view, 1)

    history = []
    hi = [-1]

    def do_request(url):
        if not url.startswith("http"):
            url = "https://" + url
        status.setText(f"🔒 Запрос: {url}")
        view.setPlainText("Загрузка...")
        if log_write:
            log_write("browser", "INFO", "Запрос", url=url)
        resp = NETD.request(token=token, method="GET", url=url,
                            headers={"User-Agent": "SimpleOS-Browser/1.0"})
        if "error" in resp:
            view.setPlainText(f"⚠ Ошибка: {resp['error']}")
            status.setText(f"⚠ {resp['error']}")
            if log_write:
                log_write("browser", "ERROR", "Ошибка",
                          url=url, error=resp["error"])
            return
        try:
            text = resp["body"].decode("utf-8", errors="replace")
        except Exception:
            text = f"(бинарный ответ, {len(resp['body'])} байт)"
        view.setPlainText(text)
        status.setText(f"🔒 {resp['status']} · {len(resp['body'])} байт")
        history.append(url)
        hi[0] = len(history) - 1
        if log_write:
            log_write("browser", "INFO", "Ответ",
                      url=url, status=resp["status"],
                      size=len(resp["body"]))

    def on_go():
        u = url_edit.text().strip()
        if u:
            do_request(u)

    url_edit.returnPressed.connect(on_go)
    go.clicked.connect(on_go)

    def on_back():
        if hi[0] > 0:
            hi[0] -= 1
            do_request(history[hi[0]])

    def on_fwd():
        if hi[0] < len(history) - 1:
            hi[0] += 1
            do_request(history[hi[0]])

    def on_rel():
        if history:
            do_request(history[hi[0]])

    back.clicked.connect(on_back)
    fwd.clicked.connect(on_fwd)
    rel.clicked.connect(on_rel)

    orig_close = win.closeEvent

    def on_close(e):
        NETD.revoke_session(token)
        status.setText("🔒 Токен отозван")
        return orig_close(e)

    win.closeEvent = on_close
    url_edit.setFocus()