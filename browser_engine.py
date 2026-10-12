"""
Встроенный браузер DreamUX на PyQt6 + QtWebEngine.
Вкладки, загрузки через wget, кнопка «открыть в системном браузере».
"""

import sys
import os
from pathlib import Path
import threading
import time

try:
    import wget
    WGET_OK = True
except ImportError:
    WGET_OK = False
    print("[BROWSER] wget не установлен — загрузки работать не будут",
          file=sys.stderr)


from PyQt6.QtCore import (
    Qt, pyqtSignal, pyqtSlot, QObject, QUrl, QTimer, QSize,
)
from PyQt6.QtGui import (
    QAction, QColor, QIcon, QPixmap,
)
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QLabel, QTabBar, QStackedWidget,
    QFileDialog, QProgressBar, QToolBar, QMainWindow,
    QListWidget, QAbstractItemView, QSizePolicy, QToolButton,
    QListWidgetItem,
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import (
    QWebEngineDownloadRequest, QWebEngineProfile, QWebEnginePage,
)


# ============================================================
# Кастомная страница — открывает ссылки в новой вкладке
# ============================================================
class CustomWebEnginePage(QWebEnginePage):
    def __init__(self, browser_window, parent=None):
        super().__init__(parent)
        self.browser_window = browser_window

    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        if nav_type == QWebEnginePage.NavigationType.NavigationTypeLinkClicked:
            self.browser_window.add_new_tab(url)
            return False
        return True


# ============================================================
# Загрузчик через wget
# ============================================================
class YandexStyleDownloader(QObject):
    download_started = pyqtSignal(str)
    progress_changed = pyqtSignal(str, int)
    status_changed = pyqtSignal(str, str)
    finished = pyqtSignal(str)

    def __init__(self, url: QUrl, save_path: Path, item_id: str):
        super().__init__()
        self.url = url.toString()
        self.save_path = save_path
        self.item_id = item_id
        self._is_paused = False
        self._is_cancelled = False
        self._thread = None
        self._is_running = False

    @pyqtSlot()
    def start(self):
        if self._is_cancelled:
            return
        if not self._thread or not self._thread.is_alive():
            self._is_running = True
            self._thread = threading.Thread(target=self._run_wget, daemon=True)
            self._thread.start()
            self.download_started.emit(self.save_path.name)

    @pyqtSlot()
    def pause(self):
        if self._is_running:
            self._is_paused = True
            self.status_changed.emit(self.item_id, "Пауза")

    @pyqtSlot()
    def resume(self):
        if self._is_running:
            self._is_paused = False
            self.status_changed.emit(self.item_id, "Возобновлено")
            self.start()

    @pyqtSlot()
    def cancel(self):
        self._is_cancelled = True
        self._is_paused = True
        self._is_running = False
        try:
            if self.save_path.exists():
                self.save_path.unlink()
        except Exception:
            pass
        finally:
            self.finished.emit(self.item_id)

    def _run_wget(self):
        if self._is_cancelled or not WGET_OK:
            self.status_changed.emit(self.item_id, "wget не установлен")
            self.finished.emit(self.item_id)
            return

        try:
            temp_path = self.save_path.parent / f"{self.save_path.name}.part"
            downloaded_size = 0
            if temp_path.exists():
                downloaded_size = temp_path.stat().st_size

            def progress_bar(current, total, width=50):
                if self._is_cancelled:
                    raise KeyboardInterrupt("Cancelled")
                if self._is_paused:
                    while self._is_paused and not self._is_cancelled:
                        time.sleep(0.1)
                    if self._is_cancelled:
                        raise KeyboardInterrupt("Cancelled")
                if total > 0:
                    percent = int((current + downloaded_size) / total * 100)
                    if percent > 100:
                        percent = 100
                    self.progress_changed.emit(self.item_id, percent)

            if not self._is_cancelled:
                wget.download(self.url, out=str(temp_path), bar=progress_bar)

                if not self._is_cancelled and not self._is_paused:
                    if temp_path.exists():
                        if self.save_path.exists():
                            self.save_path.unlink()
                        temp_path.rename(self.save_path)
                    self.status_changed.emit(self.item_id, "Готово")
                    self.progress_changed.emit(self.item_id, 100)
                else:
                    if temp_path.exists():
                        temp_path.unlink()

        except KeyboardInterrupt:
            self.status_changed.emit(self.item_id, "Остановлено")
            temp_file = self.save_path.parent / f"{self.save_path.name}.part"
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass
        except Exception as e:
            self.status_changed.emit(self.item_id, f"Ошибка: {str(e)[:30]}")

        finally:
            self._is_running = False
            self.finished.emit(self.item_id)


# ============================================================
# Строка загрузки
# ============================================================
class DownloadItemWidget(QWidget):
    def __init__(self, downloader, file_name):
        super().__init__()
        self.downloader = downloader

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        self.state_icon = QLabel("🔄")
        f = self.state_icon.font()
        f.setPointSize(12)
        self.state_icon.setFont(f)
        self.state_icon.setFixedWidth(30)
        layout.addWidget(self.state_icon)

        display_name = file_name[:30] + ("..." if len(file_name) > 30 else "")
        self.file_label = QLabel(display_name)
        self.file_label.setStyleSheet("color: white; font-weight: bold;")
        layout.addWidget(self.file_label, 1)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar { background-color: rgba(255, 255, 255, 0.1);
                border-radius: 3px; }
            QProgressBar::chunk { background-color: qlineargradient(
                x1:0, y1:0, x2:1, y2:0, stop:0 #00a9f4, stop:1 #0078d7);
                border-radius: 3px; }
        """)
        layout.addWidget(self.progress_bar)

        self.btn_open = QPushButton("Открыть")
        self.btn_open.setEnabled(False)
        self.btn_open.clicked.connect(self._open_file)

        self.btn_folder = QPushButton("📁")
        self.btn_folder.setFixedWidth(30)
        self.btn_folder.setEnabled(False)
        self.btn_folder.clicked.connect(self._show_in_folder)

        self.btn_action = QPushButton("❚❚")
        self.btn_action.setFixedWidth(30)
        self.btn_action.setStyleSheet("border: none; color: white;")
        self.btn_action.clicked.connect(self._toggle_pause)

        self.btn_cancel = QPushButton("✖")
        self.btn_cancel.setFixedWidth(30)
        self.btn_cancel.setStyleSheet("border: none; color: #ff6b6b;")
        self.btn_cancel.clicked.connect(self.cancel_download)

        layout.addWidget(self.btn_open)
        layout.addWidget(self.btn_folder)
        layout.addWidget(self.btn_action)
        layout.addWidget(self.btn_cancel)

        downloader.progress_changed.connect(self._update_progress)
        downloader.status_changed.connect(self._update_status)
        downloader.finished.connect(self._on_finished)

        downloader.start()

    def _update_progress(self, item_id, percent):
        self.progress_bar.setValue(percent)

    def _update_status(self, item_id, status):
        if "Готово" in status:
            self.state_icon.setText("✅")
            self.progress_bar.setValue(100)
        elif "Ошибка" in status:
            self.state_icon.setText("❌")
        elif "Пауза" in status or "Остановлено" in status:
            self.state_icon.setText("🛑")
        else:
            self.state_icon.setText("🔄")

        is_done = "Готово" in status
        is_error = "Ошибка" in status
        self.btn_open.setEnabled(is_done)
        self.btn_folder.setEnabled(is_done or is_error)

        if "Пауза" in status or "Остановлено" in status:
            self.btn_action.setText("▶")
        elif is_done or is_error:
            self.btn_action.setEnabled(False)
            self.btn_cancel.setEnabled(False)
        else:
            self.btn_action.setText("❚❚")

    def _toggle_pause(self):
        if self.btn_action.text() == "❚❚":
            self.downloader.pause()
        else:
            self.downloader.resume()

    def cancel_download(self):
        self.downloader.cancel()

    def _open_file(self):
        p = str(self.downloader.save_path)
        if sys.platform == "win32":
            os.startfile(p)
        elif sys.platform == "darwin":
            os.system(f'open "{p}"')
        else:
            os.system(f'xdg-open "{p}"')

    def _show_in_folder(self):
        folder = str(Path(self.downloader.save_path).parent)
        if sys.platform == "win32":
            os.startfile(folder)
        elif sys.platform == "darwin":
            os.system(f'open -R "{folder}"')
        else:
            os.system(f'xdg-open "{folder}"')

    def _on_finished(self):
        QTimer.singleShot(15000, self.deleteLater)


# ============================================================
# Главное окно браузера
# ============================================================
class Browser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DreamUX Browser")
        self.resize(1280, 720)

        self.browser_process = None

        central = QWidget()
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.setCentralWidget(central)

        QWebEngineProfile.defaultProfile().downloadRequested.connect(
            self.on_download_requested
        )

        # ---- Вкладки ----
        top_container = QWidget()
        top_container.setFixedHeight(84)
        top_layout = QVBoxLayout(top_container)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(0)

        tab_strip = QWidget()
        tab_strip.setObjectName("tab_strip")
        tab_strip.setFixedHeight(34)
        ts_layout = QHBoxLayout(tab_strip)
        ts_layout.setContentsMargins(0, 0, 0, 0)
        ts_layout.setSpacing(0)

        self.tab_bar = QTabBar()
        self.tab_bar.setDocumentMode(True)
        self.tab_bar.setTabsClosable(True)
        self.tab_bar.setExpanding(False)
        self.tab_bar.setFixedHeight(34)
        self.tab_bar.tabCloseRequested.connect(self.close_tab)
        self.tab_bar.currentChanged.connect(self.on_tab_changed)
        ts_layout.addWidget(self.tab_bar)

        self.plus_btn = QToolButton()
        self.plus_btn.setText("+")
        self.plus_btn.setFixedSize(28, 28)
        self.plus_btn.setStyleSheet("""
            QToolButton { color: white; background: transparent;
                border: none; font-size: 16px; font-weight: bold; }
            QToolButton:hover { background: rgba(255,255,255,0.1);
                border-radius: 6px; }
        """)
        self.plus_btn.clicked.connect(lambda: self.add_new_tab())
        ts_layout.addWidget(self.plus_btn)
        ts_layout.addStretch(1)

        indicator_btn = QPushButton()
        indicator_btn.setFlat(True)
        indicator_btn.setFixedSize(24, 24)
        indicator_btn.clicked.connect(self.toggle_download_panel)
        ts_layout.addWidget(indicator_btn)
        self.indicator_corner = indicator_btn

        top_layout.addWidget(tab_strip)

        # ---- Тулбар ----
        toolbar = QToolBar("Навигация")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setIconSize(QSize(24, 24))
        toolbar.setFixedHeight(50)

        search_container = QWidget()
        search_container.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(0)

        self.url_bar = QLineEdit()
        self.url_bar.returnPressed.connect(self.navigate_to_url)
        self.url_bar.setPlaceholderText("Поиск в Google или адрес сайта...")
        self.url_bar.setStyleSheet(
            "QLineEdit { background: transparent; border: none; "
            "padding-left: 10px; color: white; }"
        )
        search_layout.addWidget(self.url_bar, 1)

        open_in_browser_btn = QPushButton("🌐")
        open_in_browser_btn.setToolTip("Открыть в системном браузере")
        open_in_browser_btn.setFixedSize(30, 30)
        open_in_browser_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; "
            "font-size: 18px; } "
            "QPushButton:hover { background: rgba(255,255,255,0.1); "
            "border-radius: 4px; }"
        )
        open_in_browser_btn.clicked.connect(self.open_in_real_browser)
        search_layout.addWidget(open_in_browser_btn)

        spacer_left = QWidget()
        spacer_left.setSizePolicy(QSizePolicy.Policy.Expanding,
                                  QSizePolicy.Policy.Preferred)

        self.back_btn = QAction(QIcon.fromTheme("go-previous"), "", self)
        self.back_btn.triggered.connect(
            lambda: self._current_browser() and self._current_browser().back()
        )
        toolbar.addAction(self.back_btn)

        self.forward_btn = QAction(QIcon.fromTheme("go-next"), "", self)
        self.forward_btn.triggered.connect(
            lambda: self._current_browser() and self._current_browser().forward()
        )
        toolbar.addAction(self.forward_btn)

        self.reload_action = QAction(QIcon.fromTheme("view-refresh"), "", self)
        self.reload_action.triggered.connect(
            lambda: self._current_browser() and self._current_browser().reload()
        )
        toolbar.addAction(self.reload_action)

        self.home_action = QAction(QIcon.fromTheme("go-home"), "", self)
        self.home_action.triggered.connect(
            lambda: self._current_browser() and self._current_browser().load(
                QUrl("https://www.google.com")
            )
        )
        toolbar.addAction(self.home_action)

        toolbar.addSeparator()
        toolbar.addWidget(spacer_left)
        toolbar.addWidget(search_container)

        spacer_right = QWidget()
        spacer_right.setSizePolicy(QSizePolicy.Policy.Expanding,
                                   QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer_right)

        top_dl_action = QAction(QIcon.fromTheme("folder-downloads"),
                                "📥 Загрузки", self)
        top_dl_action.triggered.connect(self.toggle_download_panel)
        toolbar.addAction(top_dl_action)

        top_layout.addWidget(toolbar)
        main_layout.addWidget(top_container)

        self.stacked_widget = QStackedWidget()
        main_layout.addWidget(self.stacked_widget, 1)

        # ---- Панель загрузок ----
        self.download_panel = QWidget()
        self.download_panel.setMaximumHeight(0)
        self.download_panel.setMinimumHeight(0)
        self.download_panel.setStyleSheet(
            "QWidget { background-color: #1E1F23; "
            "border-top: 1px solid #2a2b30; }"
        )
        dl_layout = QVBoxLayout(self.download_panel)
        dl_layout.setContentsMargins(10, 10, 10, 10)

        title = QLabel("Активные загрузки")
        title.setStyleSheet("color: white; font-size: 14px; font-weight: bold;")
        dl_layout.addWidget(title)

        self.download_list = QListWidget()
        self.download_list.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        self.download_list.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.download_list.setStyleSheet(
            "QListWidget { background: transparent; border: none; outline: none; }"
            "QListWidget::item { background: rgba(10,10,10,0.5); "
            "border-radius: 10px; margin-bottom: 8px; padding: 0; }"
        )
        dl_layout.addWidget(self.download_list)

        main_layout.addWidget(self.download_panel)

        self.setStyleSheet("""
            QMainWindow { background-color: #141519; }
            #tab_strip { background-color: #141519; }
            QTabBar::tab {
                background: #16171A; color: #cccccc;
                border-top-left-radius: 8px; border-top-right-radius: 8px;
                padding: 2px 15px; min-width: 120px; }
            QTabBar::tab:selected { background: #1E1F23; color: white; }
            QTabBar::tab:hover { background: #232429; }
            QToolBar { background-color: #1E1F23; border: none;
                padding-left: 10px; spacing: 5px; }
            QToolBar QToolButton { background: transparent; border: none;
                padding: 4px; border-radius: 4px; }
            QToolBar QToolButton:hover { background: rgba(255,255,255,0.1); }
            QLineEdit { background: transparent; border: none;
                padding-left: 10px; color: white; }
            QLineEdit:focus { outline: none; border: none; }
        """)

        self.active_downloads_count = 0
        self._download_counter = 0

        self.add_new_tab(QUrl("https://www.google.com"))

    # ---- Системный браузер ----
    def open_in_real_browser(self):
        browser = self._current_browser()
        if browser is None:
            return
        url = browser.url().toString()
        if sys.platform == "win32":
            os.startfile(url)
        elif sys.platform == "darwin":
            os.system(f'open "{url}"')
        else:
            os.system(f'xdg-open "{url}"')

    def _current_browser(self):
        return self.stacked_widget.currentWidget()

    def navigate_to_url(self):
        browser = self._current_browser()
        if browser is None:
            return
        user_input = self.url_bar.text().strip()
        url = QUrl.fromUserInput(user_input)
        if not url.scheme():
            url.setScheme("https")
        browser.load(url)

    def update_navigation_buttons(self):
        browser = self._current_browser()
        if browser is None:
            return
        h = browser.history()
        self.back_btn.setEnabled(h.canGoBack())
        self.forward_btn.setEnabled(h.canGoForward())

    def on_tab_changed(self, index):
        if index < 0:
            return
        self.stacked_widget.setCurrentIndex(index)
        browser = self.stacked_widget.widget(index)
        if browser is None:
            return
        self.url_bar.setText(browser.url().toDisplayString())
        self.update_navigation_buttons()
        self.setWindowTitle(self.tab_bar.tabText(index) + " — DreamUX Browser")

    def add_new_tab(self, url=None):
        browser = QWebEngineView()
        page = CustomWebEnginePage(self, browser)
        browser.setPage(page)

        if url is None:
            url = QUrl("https://www.google.com")
        elif isinstance(url, str):
            url = QUrl(url)
        browser.load(url)

        browser.titleChanged.connect(
            lambda title, b=browser: self._on_title_changed(b, title)
        )
        browser.iconChanged.connect(
            lambda icon, b=browser: self._on_icon_changed(b, icon)
        )
        browser.urlChanged.connect(
            lambda qurl, b=browser: self._on_url_changed(b, qurl)
        )
        browser.loadFinished.connect(
            lambda ok, b=browser: self._on_load_finished(b)
        )

        self.stacked_widget.addWidget(browser)
        index = self.tab_bar.addTab("Новая вкладка")
        self.tab_bar.setCurrentIndex(index)
        self.on_tab_changed(index)

    def close_tab(self, index):
        if self.tab_bar.count() <= 1:
            return
        widget = self.stacked_widget.widget(index)
        self.stacked_widget.removeWidget(widget)
        if widget is not None:
            widget.deleteLater()
        self.tab_bar.removeTab(index)

    def _on_title_changed(self, browser, title):
        idx = self.stacked_widget.indexOf(browser)
        if idx == -1:
            return
        short = title[:30] + ("..." if len(title) > 30 else "")
        self.tab_bar.setTabText(idx, short)
        if idx == self.stacked_widget.currentIndex():
            self.setWindowTitle(short + " — DreamUX Browser")

    def _on_icon_changed(self, browser, icon):
        idx = self.stacked_widget.indexOf(browser)
        if idx != -1:
            self.tab_bar.setTabIcon(idx, icon)

    def _on_url_changed(self, browser, qurl):
        if self.stacked_widget.currentWidget() is browser:
            self.url_bar.setText(qurl.toDisplayString())

    def _on_load_finished(self, browser):
        if self.stacked_widget.currentWidget() is browser:
            self.update_navigation_buttons()

    # ---- Скачивание ----
    def on_download_requested(self, request: QWebEngineDownloadRequest):
        suggested_name = request.suggestedFileName()
        if not suggested_name:
            url = request.url().toString()
            suggested_name = url.split('/')[-1] or "download"

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Куда сохранить?", suggested_name, "Все файлы (*)"
        )
        if not file_path:
            request.cancel()
            return

        request.cancel()

        save_path = Path(file_path)
        self._download_counter += 1
        item_id = f"id_{self._download_counter}"

        downloader = YandexStyleDownloader(request.url(), save_path, item_id)
        widget = DownloadItemWidget(downloader, save_path.name)
        list_item = QListWidgetItem(self.download_list)
        list_item.setSizeHint(widget.sizeHint())
        self.download_list.setItemWidget(list_item, widget)

        self.active_downloads_count += 1
        self.update_indicator_on_tab()
        if self.download_panel.maximumHeight() == 0:
            self.toggle_download_panel()

        downloader.finished.connect(lambda i=item_id: self._cleanup_download(i))

    def toggle_download_panel(self):
        if self.download_panel.maximumHeight() > 0:
            self.download_panel.setMaximumHeight(0)
            self.download_panel.setMinimumHeight(0)
        else:
            self.download_panel.setMaximumHeight(200)
            self.download_panel.setMinimumHeight(120)

    def update_indicator_on_tab(self):
        icon = QIcon.fromTheme("folder-downloads") if self.active_downloads_count > 0 else QIcon()
        if self.indicator_corner:
            self.indicator_corner.setIcon(icon)

    def _cleanup_download(self, item_id):
        self.active_downloads_count = max(0, self.active_downloads_count - 1)
        self.update_indicator_on_tab()

        for row in range(self.download_list.count()):
            item = self.download_list.item(row)
            widget = self.download_list.itemWidget(item)
            if widget is not None and hasattr(widget, 'downloader') and \
                    widget.downloader.item_id == item_id:
                widget.deleteLater()
                self.download_list.takeItem(row)
                break

        if self.active_downloads_count == 0:
            self.download_panel.setMaximumHeight(0)
            self.download_panel.setMinimumHeight(0)


# ============================================================
# Запуск
# ============================================================
def main():
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = Browser()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
