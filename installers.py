"""Менеджер установщиков второстепенной ОС. Токен, AV хоста, allowlist."""

import os
import sys
import json
import shutil
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
KERNEL_DIR = os.path.dirname(HERE)
SANDBOX_ROOT = os.path.join(KERNEL_DIR, "sandbox")
INSTALLERS_DIR = os.path.join(SANDBOX_ROOT, "installers")
INSTALLED_DIR = os.path.join(SANDBOX_ROOT, "apps")

log_write = lambda *a, **k: None

INSTALLER_ALLOWLIST = [
    "flathub.org", "dl.flathub.org", "snapcraft.io", "api.snapcraft.io",
    "github.com", "objects.githubusercontent.com", "raw.githubusercontent.com",
    "sourceforge.net", "downloads.sourceforge.net",
    "apps.microsoft.com", "f-droid.org",
    "deb.debian.org", "archive.ubuntu.com", "packages.microsoft.com",
]


def list_installers():
    if not os.path.isdir(INSTALLERS_DIR):
        return []
    out = []
    for entry in sorted(os.scandir(INSTALLERS_DIR), key=lambda e: e.name):
        if not entry.is_dir():
            continue
        info = {"dir": entry.name, "path": entry.path}
        m = os.path.join(entry.path, "installer.json")
        if os.path.isfile(m):
            try:
                with open(m, "r", encoding="utf-8") as f:
                    info.update(json.load(f))
            except Exception as e:
                info["error"] = str(e)
        out.append(info)
    return out


def run_installer(installer_dir_name, netd, av=None):
    inst_path = os.path.join(INSTALLERS_DIR, installer_dir_name)
    if not os.path.isdir(inst_path):
        return {"error": "installer not found"}
    m_path = os.path.join(inst_path, "installer.json")
    if not os.path.isfile(m_path):
        return {"error": "installer.json не найден"}
    with open(m_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    allow = manifest.get("allowlist") or INSTALLER_ALLOWLIST
    token = netd.issue_session(
        f"installer:{manifest.get('name', installer_dir_name)}",
        allowlist=allow, require_vpn=True,
    )
    if not token:
        return {"error": "Ядро отказало"}

    dl_dir = os.path.join(inst_path, "downloads")
    os.makedirs(dl_dir, exist_ok=True)

    entry = manifest.get("entry", "download.py")
    entry_path = os.path.join(inst_path, entry)
    if not os.path.isfile(entry_path):
        netd.revoke_session(token)
        return {"error": f"Нет точки входа: {entry}"}

    env = os.environ.copy()
    env["SIMPLEOS_INSTALLER_TOKEN"] = token
    env["SIMPLEOS_INSTALLER_DIR"] = inst_path
    env["SIMPLEOS_DOWNLOADS_DIR"] = dl_dir
    env["PYTHONPATH"] = os.pathsep.join(
        [os.path.join(KERNEL_DIR, "plugins"), env.get("PYTHONPATH", "")]
    )
    try:
        proc = subprocess.Popen([sys.executable, entry_path],
                                cwd=inst_path, env=env)
        proc.wait(timeout=600)
    except Exception as e:
        netd.revoke_session(token)
        return {"error": str(e)}

    results = []
    for fname in sorted(os.listdir(dl_dir)):
        fpath = os.path.join(dl_dir, fname)
        if not os.path.isfile(fpath):
            continue
        if av is not None:
            r = av.scan(fpath)
            log_write("installers", "INFO", "AV",
                      file=fname, verdict=r.get("verdict"))
            results.append({"file": fname, "report": r})
            if r.get("verdict") == "malicious":
                qdir = os.path.join(SANDBOX_ROOT, "quarantine")
                os.makedirs(qdir, exist_ok=True)
                q = os.path.join(qdir, fname)
                try:
                    shutil.move(fpath, q)
                except Exception:
                    pass
                netd.revoke_session(token)
                return {"error": "MALICIOUS", "file": fname,
                        "report": r, "results": results}

    app_name = manifest.get("name", installer_dir_name)
    app_dir = os.path.join(INSTALLED_DIR, app_name)
    os.makedirs(app_dir, exist_ok=True)
    for fname in os.listdir(dl_dir):
        src = os.path.join(dl_dir, fname)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(app_dir, fname))

    netd.revoke_session(token)
    log_write("installers", "INFO", "Установлено", app=app_name)
    return {"ok": True, "app": app_name, "results": results}


def installers_open(desktop):
    global log_write
    from gnome_gui import GnomeWindow, log_write as lw
    log_write = lw
    from netd import get_global_daemon
    from PyQt6.QtWidgets import (
        QHBoxLayout, QVBoxLayout, QListWidget, QListWidgetItem,
        QLabel, QTextEdit, QPushButton, QWidget,
    )

    win = GnomeWindow(desktop, "Установщики", 860, 560, 140, 90)
    row = QHBoxLayout()
    sb = QListWidget()
    sb.setObjectName("Sidebar")
    sb.setFixedWidth(260)
    ins = list_installers()
    for i in ins:
        it = QListWidgetItem(f"📦 {i.get('name', i['dir'])}")
        it.setToolTip(i["path"])
        sb.addItem(it)
    row.addWidget(sb)

    right = QWidget()
    rl = QVBoxLayout(right)
    title = QLabel("Выберите установщик"); title.setObjectName("H2")
    rl.addWidget(title)
    info = QTextEdit()
    info.setReadOnly(True)
    info.setStyleSheet("background:#0d0d0d; color:#e0e0e0; "
                       "font-family:'Consolas','Monospace'; font-size:9pt;")
    rl.addWidget(info, 1)
    btn = QPushButton("📥 Установить"); btn.setObjectName("WinBtn")
    rl.addWidget(btn)
    row.addWidget(right, 1)
    win.body_lay.addLayout(row)

    cur = {"i": None}

    def on_select(item):
        idx = sb.row(item)
        if idx < 0 or idx >= len(ins):
            return
        cur["i"] = ins[idx]
        title.setText(f"📦 {ins[idx].get('name', ins[idx]['dir'])}")
        info.setPlainText(json.dumps(ins[idx], indent=2, ensure_ascii=False))

    sb.itemClicked.connect(on_select)

    def on_install():
        i = cur["i"]
        if not i:
            return
        netd = get_global_daemon()
        if netd is None:
            info.setPlainText("⛔ Ядро недоступно")
            return
        try:
            from av_bridge import AVBridge
            av = AVBridge(log_fn=lambda m: log_write("antivirus", "INFO", m))
        except Exception:
            av = None
        info.setPlainText("⏳ Установка идёт...")
        r = run_installer(i["dir"], netd, av)
        info.setPlainText(json.dumps(r, indent=2, ensure_ascii=False,
                                     default=str))

    btn.clicked.connect(on_install)