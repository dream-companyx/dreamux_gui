"""Менеджер игр второстепенной ОС. Токен, allowlist, AV хоста."""

import os
import sys
import json
import subprocess
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
KERNEL_DIR = os.path.dirname(HERE)
SANDBOX_ROOT = os.path.join(KERNEL_DIR, "sandbox")
GAMES_DIR = os.path.join(SANDBOX_ROOT, "games")

log_write = lambda *a, **k: None


def list_games():
    if not os.path.isdir(GAMES_DIR):
        return []
    out = []
    for entry in sorted(os.scandir(GAMES_DIR), key=lambda e: e.name):
        if not entry.is_dir():
            continue
        info = {"dir": entry.name, "path": entry.path}
        m = os.path.join(entry.path, "game.json")
        if os.path.isfile(m):
            try:
                with open(m, "r", encoding="utf-8") as f:
                    info.update(json.load(f))
            except Exception as e:
                info["error"] = str(e)
        out.append(info)
    return out


def launch_game(game_dir_name, netd, av=None):
    game_path = os.path.join(GAMES_DIR, game_dir_name)
    if not os.path.isdir(game_path):
        return {"error": "game not found"}
    m_path = os.path.join(game_path, "game.json")
    if not os.path.isfile(m_path):
        return {"error": "game.json не найден"}
    with open(m_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # Проверка AV
    if av is not None:
        for fname in os.listdir(game_path):
            fpath = os.path.join(game_path, fname)
            if os.path.isfile(fpath) and fname.endswith((".py", ".exe", ".dll", ".so")):
                r = av.scan(fpath)
                log_write("games", "INFO", "AV", file=fname,
                          verdict=r.get("verdict"))
                if r.get("verdict") == "malicious":
                    return {"error": f"{fname} — MALICIOUS", "report": r}

    perms = manifest.get("permissions", {})
    if not perms.get("network", False):
        return {"error": "Игра не запрашивает сеть"}

    entry = manifest.get("entry", "main.py")
    entry_path = os.path.join(game_path, entry)
    if not os.path.isfile(entry_path):
        return {"error": f"Нет точки входа: {entry}"}

    token = netd.issue_session(
        f"game:{manifest.get('name', game_dir_name)}",
        allowlist=manifest.get("allowlist", []),
        require_vpn=True,
    )
    if token is None:
        return {"error": "Ядро отказало"}

    env = os.environ.copy()
    env["SIMPLEOS_GAME_TOKEN"] = token
    env["SIMPLEOS_GAME_DIR"] = game_path
    env["PYTHONPATH"] = os.pathsep.join(
        [os.path.join(KERNEL_DIR, "plugins"), env.get("PYTHONPATH", "")]
    )
    try:
        proc = subprocess.Popen([sys.executable, entry_path],
                                cwd=game_path, env=env)
    except Exception as e:
        netd.revoke_session(token)
        return {"error": str(e)}

    log_write("games", "INFO", "Игра запущена",
              name=manifest.get("name"), pid=proc.pid)
    return {"proc": proc, "token": token, "manifest": manifest}


def games_open(desktop):
    global log_write
    from gnome_gui import GnomeWindow, log_write as lw
    log_write = lw
    from netd import get_global_daemon

    win = GnomeWindow(desktop, "Игры", 780, 520, 160, 100)
    from PyQt6.QtWidgets import (
        QHBoxLayout, QVBoxLayout, QListWidget, QListWidgetItem,
        QLabel, QTextEdit, QPushButton, QWidget,
    )
    from PyQt6.QtCore import Qt

    row = QHBoxLayout()
    sb = QListWidget()
    sb.setObjectName("Sidebar")
    sb.setFixedWidth(260)
    games = list_games()
    for g in games:
        it = QListWidgetItem(f"🎮 {g.get('name', g['dir'])}")
        it.setToolTip(g["path"])
        sb.addItem(it)
    row.addWidget(sb)

    right = QWidget()
    rl = QVBoxLayout(right)
    title = QLabel("Выберите игру"); title.setObjectName("H2")
    rl.addWidget(title)
    info = QTextEdit()
    info.setReadOnly(True)
    info.setStyleSheet("background:#0d0d0d; color:#e0e0e0; "
                       "font-family:'Consolas','Monospace'; font-size:9pt;")
    rl.addWidget(info, 1)
    btn = QPushButton("▶ Запустить игру"); btn.setObjectName("WinBtn")
    rl.addWidget(btn)
    row.addWidget(right, 1)
    win.body_lay.addLayout(row)

    cur = {"g": None}

    def on_select(item):
        idx = sb.row(item)
        if idx < 0 or idx >= len(games):
            return
        g = games[idx]
        cur["g"] = g
        title.setText(f"🎮 {g.get('name', g['dir'])}")
        info.setPlainText(json.dumps(g, indent=2, ensure_ascii=False))

    sb.itemClicked.connect(on_select)

    def on_launch():
        g = cur["g"]
        if not g:
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
        r = launch_game(g["dir"], netd, av)
        info.setPlainText(json.dumps(r, indent=2, ensure_ascii=False,
                                     default=str))

    btn.clicked.connect(on_launch)