from functools import partial
import re
import sys
import os
import hashlib
import time
import shutil

import requests
from platformdirs import user_data_dir
from loguru import logger

from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QPushButton,
    QLabel,
    QMessageBox,
    QHBoxLayout,
    QFrame,
    QProgressBar,
    QStackedWidget,
    QGroupBox,
    QScrollArea,
)
from PySide6.QtCore import (
    QThread,
    QThreadPool,
    Signal,
    Qt,
    QRunnable,
    QObject,
    QSize,
    QUrl,
)
from PySide6.QtGui import QFont, QDesktopServices

import qtawesome as qta



class QWidgetList(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWidgetResizable(True)
        self.container = QWidget()
        self.root_layout = QVBoxLayout(self.container)
        self.root_layout.setSpacing(5)
        self.root_layout.setContentsMargins(0, 0, 0, 0)

        self.stack = QStackedWidget()
        self.root_layout.addWidget(self.stack)
        self.setWidget(self.container)

        self.list_widget = QWidget()
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setSpacing(5)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.stack.addWidget(self.list_widget)

        self.loading_widget = QWidget()
        self.loading_layout = QVBoxLayout(self.loading_widget)
        self.loading_label = QLabel("Please Wait...")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_spinner = qta.IconWidget()
        self.animation = qta.Spin(self.loading_spinner)
        self.loading_spinner.setIconSize(QSize(128, 128))
        self.loading_spinner.setIcon(qta.icon("msc.loading", animation=self.animation))
        self.loading_spinner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_layout.addWidget(self.loading_spinner)
        self.loading_layout.addWidget(self.loading_label)
        self.loading_widget.setLayout(self.loading_layout)
        self.stack.addWidget(self.loading_widget)

        self.list_layout.addStretch()

    def add_widget(self, widget: QWidget):
        """Add a widget to the list."""
        self.list_layout.insertWidget(self.list_layout.count() - 1, widget)

    def remove_widget(self, widget: QWidget):
        """Remove a specific widget from the list."""
        self.list_layout.removeWidget(widget)
        widget.setParent(None)

    def clear_widgets(self):
        """Remove all widgets from the list."""
        while self.list_layout.count() - 1:
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

    def set_spacing(self, spacing: int):
        """Set spacing between widgets."""
        self.list_layout.setSpacing(spacing)

    def set_loading(self, loading: bool):
        """Show or hide the loading screen."""
        if loading:
            self.stack.setCurrentWidget(self.loading_widget)
        else:
            self.stack.setCurrentWidget(self.list_widget)


class ApkDownloadWorker(QRunnable):
    def __init__(self, url, path, version, name) -> None:
        super().__init__()
        self.url = url
        self.path = path
        self.version = version
        self.name = name
        self.signals = ApkDownloadSignals()

    def run(self):
        try:
            response = requests.get(self.url, stream=True, timeout=5)
            total_length = response.headers.get("content-length")
            if total_length is None:
                self.signals.finished.emit([self.version, self.name, False])
                return

            total_length = int(total_length)
            downloaded = 0

            with open(self.path, "wb") as file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        file.write(chunk)
                        downloaded += len(chunk)
                        self.signals.progress.emit(int(100 * downloaded / total_length))

            self.signals.finished.emit([self.version, self.name, True])
        except Exception as e:
            self.signals.finished.emit([self.version, self.name, False])
        time.sleep(0.1)  # not sure why this is needed


class CheckSumDownloadWorker(QRunnable):
    def __init__(self, url, path, version, name) -> None:
        super().__init__()
        self.url = url
        self.path = path
        self.version = version
        self.name = name
        self.signals = ChecksumDownloadSignals()

    def run(self):
        try:
            response = requests.get(self.url, stream=True, timeout=5)
            with open(self.path, "wb") as file:
                file.write(response.content)

            self.signals.finished.emit([self.version, self.name, True])
        except Exception as e:
            self.signals.finished.emit([self.version, self.name, False])


class ApkDownloadSignals(QObject):
    finished = Signal(list)
    error = Signal(str)
    progress = Signal(int)


class ChecksumDownloadSignals(QObject):
    finished = Signal(list)
    error = Signal(str)
    progress = Signal(int)


class FetchSignals(QObject):
    finished = Signal(list)
    error = Signal(str)
    progress = Signal(int)


class FetchReleasesWorker(QRunnable):
    def __init__(self) -> None:
        super().__init__()
        self.signals = FetchSignals()

    def run(self):
        repo = "Mercs-MSA/2024_ScoutingDataCollection"
        logger.debug(f"Fetching releases from {repo}")
        try:
            releases_url = f"https://api.github.com/repos/{repo}/releases"
            response = requests.get(releases_url, timeout=5)
            releases = response.json()
            valid_releases = []

            for release in releases:
                version = release["tag_name"]
                title = release["name"]
                pre_release = release["prerelease"]
                assets = release["assets"]
                apk_url = None
                sha1_url = None
                for asset in assets:
                    if asset["name"] == "app-release.apk":
                        apk_url = asset["browser_download_url"]
                    elif asset["name"] == "app-release.apk.sha1":
                        sha1_url = asset["browser_download_url"]
                if (not apk_url) or (not sha1_url):
                    logger.warning(f"Invalid release tag: {version}")


                if apk_url and sha1_url:
                    release_info = {
                        "version": version,
                        "title": title,
                        "prerelease": pre_release,
                        "apk_url": apk_url,
                        "sha1_url": sha1_url,
                    }
                    valid_releases.append(release_info)
                    logger.info(f"Found release tag: {version}")

            self.signals.finished.emit(valid_releases)
        except Exception as e:
            self.signals.error.emit(repr(e))
            self.signals.finished.emit([])
            logger.error(f"Error fetching releases: {repr(e)}")


class Chip(QWidget):
    # Small widget that displays a single piece of data
    def __init__(self, label, color: str = "#FFB3A9"):
        super().__init__()
        self.label = label
        self.color = color
        self.initUI()
        self.setFixedWidth(self.sizeHint().width())
        self.setFixedHeight(40)

    def initUI(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        self.label = QLabel(self.label)
        layout.addWidget(self.label)

        self.label.setStyleSheet("font-weight: bold;")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # background color, rounded corners, padding, etc.
        r, g, b = tuple(int(self.color.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4))
        self.setStyleSheet(
            f"background-color: rgba({r}, {g}, {b}, 0.5); border-radius: 11px; padding: 2px;"
        )


class Downloader(QWidget):
    def __init__(self):
        super().__init__()

        self.releases = []
        self.downloads: dict[str, dict] = {}
        self.app_dir = user_data_dir("scouting_transfer", "mercs")
        logger.info(f"Download path: {self.app_dir}")

        self.worker_pool = QThreadPool()
        self.worker_pool.setMaxThreadCount(16)
        self.worker: QThread | None = None

        self.initUI()

        self.refresh_downloaded()

    def initUI(self):
        layout = QVBoxLayout()

        self.download_button = QPushButton("Fetch Release List", self)
        self.download_button.clicked.connect(self.fetch_releases)
        layout.addWidget(self.download_button)

        self.releases_layout = QHBoxLayout()
        layout.addLayout(self.releases_layout)

        downloadable_group = QGroupBox("Downloadable Releases", self)
        self.releases_layout.addWidget(downloadable_group)

        downloadable_layout = QVBoxLayout()
        downloadable_group.setLayout(downloadable_layout)

        self.downloadable_releases = QWidgetList(self)
        self.downloadable_releases.set_spacing(4)
        downloadable_layout.addWidget(self.downloadable_releases)

        downloaded_group = QGroupBox("Downloaded Releases", self)
        self.releases_layout.addWidget(downloaded_group)

        downloaded_layout = QVBoxLayout()
        downloaded_group.setLayout(downloaded_layout)

        self.downloaded_releases = QWidgetList(self)
        self.downloaded_releases.set_spacing(4)
        downloaded_layout.addWidget(self.downloaded_releases)

        self.setLayout(layout)

    def fetch_releases(self):
        if not self.worker or not self.worker.isRunning():
            self.downloadable_releases.clear_widgets()
            self.downloadable_releases.set_loading(True)
            worker = FetchReleasesWorker()
            worker.signals.error.connect(
                lambda error: QMessageBox.warning(
                    self, "Error", f"Error fetching releases: {error}"
                )
            )
            worker.signals.finished.connect(self.on_releases_fetched)
            self.worker_pool.start(worker)

    def on_releases_fetched(self, releases):
        self.releases = releases
        self.downloadable_releases.clear_widgets()
        self.downloadable_releases.set_loading(False)
        for release in releases:
            release_item = ReleaseItem(
                False,
                release["title"],
                release["version"],
                release["prerelease"],
                release["apk_url"],
                release["sha1_url"],
            )
            release_item.download.connect(
                partial(self.download_release, release, release_item.progress_bar)
            )
            self.downloadable_releases.add_widget(release_item)

    def download_release(self, release: dict, progress_bar: QProgressBar | None):
        if release["version"] in [dl.rsplit("-", 1)[0] for dl in self.downloads.keys()]:
            QMessageBox.warning(
                self,
                "Download",
                f"Another download is running for tag: {release['version']}",
            )
            return

        logger.info(f"Downloading release {release['version']}")
        os.makedirs(os.path.join(self.app_dir, release["version"]), exist_ok=True)
        self.download_apk(
            release["version"],
            release["apk_url"],
            os.path.join(self.app_dir, release["version"], "app-release.apk"),
            "apk",
            progress_bar,
        )
        self.download_checksum(
            release["version"],
            release["sha1_url"],
            os.path.join(self.app_dir, release["version"], "app-release.apk.sha1"),
            "checksum",
            None,
        )
        self.downloads[release["version"] + "-checksum"] = {
            "progress": 0,
            "path": os.path.join(
                self.app_dir, release["version"], "app-release.apk.sha1"
            ),
        }
        self.downloads[release["version"] + "-apk"] = {
            "progress": 0,
            "path": os.path.join(self.app_dir, release["version"], "app-release.apk"),
        }

    def download_apk(self, version, url, path, name, progressbar: QProgressBar | None):
        worker = ApkDownloadWorker(url, path, version, name)
        worker.signals.progress.connect(
            lambda prog: self.update_progress(version, prog, name)
        )

        if progressbar:
            worker.signals.progress.connect(progressbar.setValue)
            worker.signals.progress.connect(progressbar.show)
            worker.signals.finished.connect(progressbar.hide)

        worker.signals.finished.connect(
            lambda result: self.on_download_finished(result[0], result[1], result[2])
        )
        self.worker_pool.start(worker)

    def download_checksum(
        self, version, url, path, name, progressbar: QProgressBar | None
    ):
        worker = CheckSumDownloadWorker(url, path, version, name)
        worker.signals.progress.connect(
            lambda prog: self.update_progress(version, prog, name)
        )

        if progressbar:
            worker.signals.progress.connect(progressbar.setValue)
            worker.signals.progress.connect(progressbar.show)
            worker.signals.finished.connect(progressbar.hide)

        worker.signals.finished.connect(
            lambda result: self.on_download_finished(result[0], result[1], result[2])
        )
        self.worker_pool.start(worker)

    def update_progress(self, version, value, name):
        self.downloads[f"{version}-{name}"]["progress"] = value
        # logger.debug(f"Download progress of {name}:{version} -> {value}")
        pass

    def on_download_finished(self, version, name, success):
        if not success:
            logger.error(f"Download failed for tag {version}, {name}")
            QMessageBox.critical(
                self, "Error", f"Download failed for {version} - {name}"
            )
            return

        logger.info(f"Download finished for tag {version}, {name}")
        self.downloads.pop(f"{version}-{name}")
        for download in self.downloads.keys():
            if download.rsplit("-", 1)[0] == version:
                return
        # at this stage, all reqd downloads are done

        self.refresh_downloaded()

        # verify checksum
        ok = self.verify_sha1(
            os.path.join(self.app_dir, version, "app-release.apk"),
            os.path.join(self.app_dir, version, "app-release.apk.sha1"),
        )
        if ok:
            logger.success(
                f"Checksum OK for {os.path.join(self.app_dir, version, 'app-release.apk')}"
            )
            self.refresh_downloaded()
        else:
            logger.error(
                f"Checksum FAILED for {os.path.join(self.app_dir, version, 'app-release.apk')}"
            )
            QMessageBox.critical(
                self,
                "Error",
                f"Checksum FAILED for {os.path.join(self.app_dir, version, 'app-release.apk')}",
            )

    def refresh_downloaded(self):
        self.downloaded_releases.clear_widgets()
        for version in os.listdir(self.app_dir):
            version_path = os.path.join(self.app_dir, version)
            if os.path.isdir(version_path):
                apk_path = os.path.join(version_path, "app-release.apk")
                if os.path.isfile(apk_path):
                    release_item = ReleaseItem(True, version, version, False, "", "")
                    release_item.show_file.connect(partial(self.show_file, version_path))
                    release_item.delete.connect(partial(self.delete_version, version))
                    self.downloaded_releases.add_widget(release_item)

    def show_file(self, path: str):
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def delete_version(self, version: str):
        reply = QMessageBox.question(
            self,
            "Delete Version",
            f"Are you sure you want to delete version {version}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                shutil.rmtree(os.path.join(self.app_dir, version))
                logger.info(f"Deleted version {version}")
                self.refresh_downloaded()
            except Exception as e:
                logger.error(f"Failed to delete version {version}: {repr(e)}")
                QMessageBox.critical(
                    self, "Error", f"Failed to delete version {version}: {repr(e)}"
                )
        self.refresh_downloaded()

    def verify_sha1(self, file_path, sha1_path):
        with open(sha1_path, "r") as sha1_file:
            expected_sha1 = sha1_file.read().strip()

        sha1 = hashlib.sha1()
        with open(file_path, "rb") as file:
            while chunk := file.read(8192):
                sha1.update(chunk)

        return sha1.hexdigest() == expected_sha1


class ReleaseItem(QFrame):
    download = Signal()
    install = Signal()
    delete = Signal()
    show_file = Signal()

    def __init__(
        self,
        downloaded: bool,
        title: str,
        tag: str,
        prerelease: bool,
        apk_url: str,
        sha1_url: str,
    ):
        super().__init__()
        self.tag = tag
        self.title = title
        self.apk_url = apk_url
        self.sha1_url = sha1_url

        self.setFrameShape(QFrame.Shape.Box)

        layout = QVBoxLayout()
        self.setLayout(layout)

        self.release_title = QLabel(title)
        self.release_title.setFont(QFont(self.release_title.font().family(), 13))
        layout.addWidget(self.release_title)

        self.release_chips = QHBoxLayout()
        self.release_chips.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self.release_chips)

        if not downloaded:
            self.version_chip = Chip(tag, "#8bc34a")
            self.release_chips.addWidget(self.version_chip)

            if prerelease:
                self.pre_chip = Chip("Pre-Release", "#ffeb3b")
                self.release_chips.addWidget(self.pre_chip)

            self.download_button = QPushButton("Download")
            self.download_button.clicked.connect(self.download.emit)
            self.download_button.setMinimumHeight(48)
            layout.addWidget(self.download_button)

            self.progress_bar = QProgressBar()
            self.progress_bar.hide()
            layout.addWidget(self.progress_bar)
        else:
            self.progress_bar = None
            self.release_chips.addWidget(Chip("local", "#8bc34a"))

            button_layout = QHBoxLayout()
            layout.addLayout(button_layout)

            self.install_button = QPushButton("Install to Android")
            self.install_button.clicked.connect(self.install.emit)
            self.install_button.setMinimumHeight(48)
            button_layout.addWidget(self.install_button)

            self.show_file_button = QPushButton()
            self.show_file_button.setIcon(qta.icon("mdi6.file-eye-outline"))
            self.show_file_button.setIconSize(QSize(32, 32))
            self.show_file_button.setFixedSize(QSize(48, 48))
            self.show_file_button.clicked.connect(self.show_file.emit)
            button_layout.addWidget(self.show_file_button)

            self.delete_button = QPushButton()
            self.delete_button.setIcon(qta.icon("mdi6.delete"))
            self.delete_button.setIconSize(QSize(32, 32))
            self.delete_button.setFixedSize(QSize(48, 48))
            self.delete_button.clicked.connect(self.delete.emit)
            button_layout.addWidget(self.delete_button)

        self.release_chips.addStretch()


if __name__ == "__main__":
    import qdarktheme

    app = QApplication(sys.argv)
    qdarktheme.setup_theme("dark")
    main_window = Downloader()
    main_window.resize(640, 480)
    main_window.show()
    sys.exit(app.exec())
