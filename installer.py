from functools import partial
import re
import sys
import os
import hashlib
import requests
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QPushButton,
    QLabel,
    QTabWidget,
    QListWidget,
    QMessageBox,
    QHBoxLayout,
    QFrame,
    QListWidgetItem,
    QProgressBar,
)
from platformdirs import user_data_dir
from PySide6.QtCore import QThread, QThreadPool, Signal, Qt, QRunnable, QObject, QSize
from PySide6.QtGui import QFont

from loguru import logger
from PySide6.QtWidgets import QGroupBox


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
            response = requests.get(self.url, stream=True)
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
            response = requests.get(self.url, stream=True)
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
        try:
            releases_url = f"https://api.github.com/repos/{repo}/releases"
            response = requests.get(releases_url)
            releases = response.json()
            valid_releases = []

            for release in releases:
                version = release["tag_name"]
                title = release["name"]
                pre_release = release["prerelease"]
                if re.match(r"^\d{4}\.\d+\.\d+", version):
                    assets = release["assets"]
                    apk_url = None
                    sha1_url = None
                    for asset in assets:
                        if asset["name"] == "app-release.apk":
                            apk_url = asset["browser_download_url"]
                        elif asset["name"] == "app-release.apk.sha1":
                            sha1_url = asset["browser_download_url"]

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
                else:
                    logger.warning(f"Invalid release tag: {version}")

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
        self.setFixedHeight(24)

    def initUI(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(4, 0, 4, 0)
        self.setLayout(layout)

        self.label = QLabel(self.label)
        layout.addWidget(self.label)

        # determine text color based on bg
        if sum(int(self.color.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4)) > 382:
            text_color = "#000000"
        else:
            text_color = "#ffffff"
        self.label.setStyleSheet(f"color: {text_color}; font-weight: bold;")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # background color, rounded corners, padding, etc.
        self.setStyleSheet(
            f"background-color: {self.color}; border-radius: 11px; padding: 2px;"
        )


class Downloader(QWidget):
    def __init__(self):
        super().__init__()

        self.releases = []
        self.downloads: dict[str, dict] = {}
        self.app_dir = user_data_dir("scouting_transfer", "mercs")
        logger.info(f"Download path: {self.app_dir}")

        self.worker_pool = QThreadPool()
        self.worker_pool.setMaxThreadCount(4)
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

        self.downloadable_releases = QListWidget(self)
        downloadable_layout.addWidget(self.downloadable_releases)

        downloaded_group = QGroupBox("Downloaded Releases", self)
        self.releases_layout.addWidget(downloaded_group)

        downloaded_layout = QVBoxLayout()
        downloaded_group.setLayout(downloaded_layout)

        self.downloaded_releases = QListWidget(self)
        downloaded_layout.addWidget(self.downloaded_releases)

        self.setLayout(layout)

    def fetch_releases(self):
        if not self.worker or not self.worker.isRunning():
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
        self.downloadable_releases.clear()
        for release in releases:
            release_item = ReleaseItem(
                False,
                release["version"],
                release["title"],
                release["prerelease"],
                release["apk_url"],
                release["sha1_url"],
            )
            release_item.download.connect(
                partial(self.download_release, release, release_item.progress_bar)
            )
            release_item.download.connect(
                lambda: item.setSizeHint(QSize(release_item.sizeHint().width(), release_item.sizeHint().height()+30))
            )
            item = QListWidgetItem()
            self.downloadable_releases.addItem(item)
            self.downloadable_releases.setItemWidget(item, release_item)
            item.setSizeHint(release_item.sizeHint())

    def download_release(self, release: dict, progress_bar: QProgressBar | None):
        if release["version"] in [dl.rsplit("-", 1)[0] for dl in self.downloads.keys()]:
            QMessageBox.warning(self, "Download", f"Another download is running for tag: {release['version']}")
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

    def download_checksum(self, version, url, path, name, progressbar: QProgressBar | None):
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
        logger.debug(f"Download progress of {name}:{version} -> {value}")
        pass

    def on_download_finished(self, version, name, success):
        if not success:
            logger.error(f"Download failed for tag {version}, {name}")
            QMessageBox.critical(self, "Error", f"Download failed for {version} - {name}")
            return

        logger.info(f"Download finished for tag {version}, {name}")
        self.downloads.pop(f"{version}-{name}")
        for download in self.downloads.keys():
            if download.rsplit("-", 1)[0] == version:
                return
        # at this stage, all reqd downloads are done

        self.fetch_releases()

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
        self.downloaded_releases.clear()
        for version in os.listdir(self.app_dir):
            version_path = os.path.join(self.app_dir, version)
            if os.path.isdir(version_path):
                apk_path = os.path.join(version_path, "app-release.apk")
                if os.path.isfile(apk_path):
                    release_item = ReleaseItem(True, version, version, False, "", "")
                    item = QListWidgetItem()
                    self.downloaded_releases.addItem(item)
                    self.downloaded_releases.setItemWidget(item, release_item)
                    item.setSizeHint(QSize(release_item.sizeHint().width(), release_item.sizeHint().height() + 40))

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
            self.version_chip = Chip(tag, "#4caf50")
            self.release_chips.addWidget(self.version_chip)

            if prerelease:
                self.pre_chip = Chip("Pre-Release")
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
            self.release_chips.addWidget(Chip("local", "#4caf50"))

            self.install_button = QPushButton("Install")
            self.install_button.clicked.connect(self.install.emit)
            self.install_button.setMinimumHeight(48)
            layout.addWidget(self.install_button)

        self.release_chips.addStretch()

if __name__ == "__main__":
    import qdarktheme

    app = QApplication(sys.argv)
    qdarktheme.setup_theme("dark")
    main_window = Downloader()
    main_window.resize(640, 480)
    main_window.show()
    sys.exit(app.exec())
