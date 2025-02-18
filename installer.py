from functools import partial
import os
import hashlib
import time
import shutil
import subprocess

import ppadb.client
import ppadb.device
import requests
from platformdirs import user_data_dir
from loguru import logger

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QPushButton,
    QLabel,
    QMessageBox,
    QHBoxLayout,
    QFrame,
    QProgressBar,
    QGroupBox,
    QWizard,
    QWizardPage,
    QListWidget,
    QListWidgetItem,
    QTextEdit,
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
    QPoint,
)
from PySide6.QtGui import (
    QFont,
    QDesktopServices,
    QPixmap,
    QLinearGradient,
    QPainter,
    QColor,
)

import qtawesome as qta

import constants
import shared_resources
from widgets import QWidgetList, Chip


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
            self.signals.error.emit(repr(e))
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
            self.signals.error.emit(repr(e))
        time.sleep(0.1)  # not sure why this is needed


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


class AdbSpinupSignals(QObject):
    finished = Signal(ppadb.client.Client)
    error = Signal(str)


class AdbDeviceSearchSignals(QObject):
    finished = Signal(list)
    error = Signal(str)


class InstallerSignals(QObject):
    finished = Signal(bool)
    log = Signal(str)


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


class AdbSpinupWorker(QRunnable):
    def __init__(
        self,
        resources: shared_resources.InstallerSharedResources,
        host: str = "127.0.0.1",
        port: int = 5037,
    ) -> None:
        super().__init__()
        self.host = host
        self.port = port
        self.resources = resources
        self.signals = AdbSpinupSignals()

    def run(self):
        try:
            if not self.resources.debug_client:
                logger.debug(f"Starting ADB client {self.host}:{self.port}")
                result = subprocess.run(
                    ["adb", "start-server"], capture_output=True, text=True
                )
                if result.returncode != 0:
                    raise RuntimeError(f"Failed to start adb server: {result.stderr}")
                self.resources.debug_client = ppadb.client.Client(self.host, self.port)
                self.resources.debug_client.create_connection()
                self.signals.finished.emit(self.resources.debug_client)
            else:
                logger.debug(
                    f"Client already exists {self.host}:{self.port}, reconnecting"
                )
                self.resources.debug_client.create_connection()
                self.signals.finished.emit(self.resources.debug_client)
        except Exception as e:
            self.signals.error.emit(repr(e))
            logger.error(f"Failed to start ADB client, {repr(e)}")


class AdbDeviceSearchWorker(QRunnable):
    def __init__(self, resources: shared_resources.InstallerSharedResources) -> None:
        super().__init__()
        self.resources = resources
        self.signals = AdbDeviceSearchSignals()

    def run(self):
        if not self.resources.debug_client:
            self.signals.error.emit("ADB client is null")
            self.signals.finished.emit([])
            return
        output = []
        try:
            devices = self.resources.debug_client.devices()
            logger.debug(f"Found {len(devices)} devices")
            device: ppadb.device.Device
            for device in devices:
                appver = device.get_package_version_name(constants.COLLECTION_APP_ID)
                output.append(
                    {"device": device, "serial": device.serial, "app": appver}
                )
            self.signals.finished.emit(output)
        except Exception as e:
            self.signals.error.emit(repr(e))


class ApkInstallWorker(QRunnable):
    def __init__(self, devices: list[dict], apk_path: str) -> None:
        super().__init__()
        self.devices = devices
        self.apk_path = apk_path
        self.signals = InstallerSignals()

    def run(self):
        success = True
        for device_info in self.devices:
            device: ppadb.device.Device = device_info["device"]
            try:
                logger.info(f"Installing APK on device {device.serial}")
                self.signals.log.emit(f"Installing on {device.serial}...")
                if device.get_package_version_name(constants.COLLECTION_APP_ID):
                    self.signals.log.emit(
                        f"Device contains app {constants.COLLECTION_APP_ID}, uninstalling first"
                    )
                    device.uninstall(constants.COLLECTION_APP_ID)
                    self.signals.log.emit("App uninstalled")
                result = device.install(self.apk_path, downgrade=True)
                if result:
                    self.signals.log.emit(f"Successfully installed on {device.serial}")
                else:
                    self.signals.log.emit(f"Failed to install on {device.serial}")
                    success = False
            except Exception as e:
                self.signals.log.emit(f"Error installing on {device.serial}: {repr(e)}")
                success = False
        self.signals.finished.emit(success)


class InstallerWizard(QWizard):
    class InitPage(QWizardPage):
        def __init__(
            self, resources: shared_resources.InstallerSharedResources, parent=None
        ):
            super().__init__(parent)
            self.resources = resources

            self.setTitle("ADB Server Setup")
            self.setSubTitle("Startup a new ADB server instance")
            self.setCommitPage(True)

            # spinup ADB client
            self.spinup_worker = AdbSpinupWorker(self.resources)
            self.spinup_worker.signals.finished.connect(self.set_client)
            self.spinup_worker.signals.error.connect(self.on_error)
            if self.resources.worker_pool:
                self.resources.worker_pool.start(self.spinup_worker)
            else:
                logger.critical("Worker Pool is null, can't spinup ADB client")

            layout = QVBoxLayout()
            self.setLayout(layout)

            self.spinner = qta.IconWidget()
            self.spinner.setIconSize(QSize(64, 64))
            self.animation = qta.Spin(self.spinner)
            self.spinner.setIcon(qta.icon("msc.loading", animation=self.animation))
            self.spinner.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(self.spinner)

            self.wait_label = QLabel("Please wait for ADB connection...")
            self.wait_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(self.wait_label)

        def set_client(self, client: ppadb.client.Client):
            self.resources.debug_client = client
            logger.debug(f"Client started, {client}")
            self.wizard().next()

        def on_error(self, error: str):
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to spin up ADB client: {error}",
                QMessageBox.StandardButton.Ok,
                QMessageBox.StandardButton.Ok,
            )
            self.wizard().reject()

    class TabletSelectPage(QWizardPage):
        def __init__(
            self,
            resources: shared_resources.InstallerSharedResources,
            parent: QWidget | None = None,
        ) -> None:
            super().__init__(parent)

            self.setTitle("Select a Tablet")
            self.setSubTitle("Select a target for the application")

            self.resources = resources

            layout = QVBoxLayout()
            self.setLayout(layout)

            self.device_list = QListWidget(self)
            self.device_list.setSelectionBehavior(
                QListWidget.SelectionBehavior.SelectItems
            )
            self.device_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
            self.device_list.itemSelectionChanged.connect(self.completeChanged)
            self.device_list.setSpacing(2)
            layout.addWidget(self.device_list)

            self.refresh_button = QPushButton("Refresh Device List")
            self.refresh_button.clicked.connect(self.refresh_devices)
            layout.addWidget(self.refresh_button)

            self.refresh_devices()

        def refresh_devices(self):
            if not self.resources.debug_client:
                return

            self.device_list.clear()
            try:
                self.device_search_worker = AdbDeviceSearchWorker(self.resources)
                self.device_search_worker.signals.finished.connect(
                    self.populate_device_list
                )
                self.device_search_worker.signals.error.connect(self.on_error)
                if self.resources.worker_pool:
                    self.resources.worker_pool.start(self.device_search_worker)
                else:
                    logger.critical("Worker Pool is null, can't search for devices")
            except Exception as e:
                QMessageBox.critical(
                    self, "Error", f"Failed to list devices: {repr(e)}"
                )

        def on_error(self, error: str):
            QMessageBox.critical(
                self,
                "Error",
                f"An error occured during an ADB action: {error}",
                QMessageBox.StandardButton.Ok,
                QMessageBox.StandardButton.Ok,
            )
            self.wizard().reject()

        def populate_device_list(self, devices: list[dict]):
            for device in devices:
                item = QListWidgetItem(
                    f"{device['serial']} - Scouting App {device['app']}"
                )
                item.setData(Qt.ItemDataRole.UserRole, device)
                self.device_list.addItem(item)

        def get_devices(self) -> list[dict]:
            output = []
            for selection in self.device_list.selectedItems():
                output.append(selection.data(Qt.ItemDataRole.UserRole))
            return output

        def isComplete(self) -> bool:
            return len(self.device_list.selectedIndexes()) > 0

    class InstallerPage(QWizardPage):
        def __init__(
            self,
            resources: shared_resources.InstallerSharedResources,
            parent: QWidget | None,
        ) -> None:
            super().__init__(parent)
            self.setTitle("Android Install")
            self.setSubTitle("Install apps on target(s)")
            self.setCommitPage(True)

            self.resources = resources
            self.devices = []

            layout = QVBoxLayout()
            self.setLayout(layout)

            self.device_list = QListWidget(self)
            self.device_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
            layout.addWidget(self.device_list)

            self.install_button = QPushButton("Install to Above Devices")
            self.install_button.setFont(QFont(self.install_button.font().family(), 14))
            self.install_button.setMinimumHeight(48)
            self.install_button.clicked.connect(self.on_install)
            layout.addWidget(self.install_button)

        def set_devices(self, devices: list[dict]):
            self.devices = devices
            self.device_list.clear()
            for device in devices:
                item = QListWidgetItem(
                    f"{device['serial']} - Scouting App {device['app']}"
                )
                self.device_list.addItem(item)

        def on_install(self):
            self.wizard().next()

    class InstallingPage(QWizardPage):
        def __init__(
            self,
            resources: shared_resources.InstallerSharedResources,
            apk: str,
            devices: list[dict],
            parent: QWidget | None = None,
        ) -> None:
            super().__init__(parent)
            self.resources = resources
            self.devices = []
            self.apk = apk
            self.setTitle("Installing")
            self.setSubTitle("Installing App")

            self.root_layout = QVBoxLayout()
            self.setLayout(self.root_layout)

            self.top_layout = QHBoxLayout()
            self.root_layout.addLayout(self.top_layout)

            self.top_spinner = qta.IconWidget()
            self.animation = qta.Spin(self.top_spinner)
            self.top_spinner.setIconSize(QSize(32, 32))
            self.top_spinner.setIcon(qta.icon("msc.loading", animation=self.animation))
            self.top_layout.addWidget(self.top_spinner)

            self.top_label = QLabel("Installing on Devices")
            self.top_layout.addWidget(self.top_label)

            self.top_layout.addStretch()

            self.logs = QTextEdit()
            self.logs.setStyleSheet("background: #0d0d0d")
            self.logs.setReadOnly(True)
            self.root_layout.addWidget(self.logs)

        def on_install_finished(self, success: bool):
            if success:
                self.top_spinner.setIcon(qta.icon("mdi6.check", color="green"))
                self.top_label.setText("Install complete!")
            else:
                self.top_spinner.setIcon(qta.icon("mdi6.alert", color="red"))
                self.top_label.setText("Install failed!")
            logger.info("Install completed")

        def set_devices(self, devs: list[dict]):
            self.devices = devs

        def start(self):
            # start up install worker
            self.install_worker = ApkInstallWorker(self.devices, self.apk)
            self.install_worker.signals.log.connect(self.logs.append)
            self.install_worker.signals.finished.connect(self.on_install_finished)
            if self.resources.worker_pool:
                self.resources.worker_pool.start(self.install_worker)
            else:
                logger.critical("Worker Pool is null, can't start install worker")

    def __init__(
        self,
        resources: shared_resources.InstallerSharedResources,
        apk: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setWindowTitle("Installer")

        self.setPixmap(QWizard.WizardPixmap.BannerPixmap, self.generate_banner())
        self.setPixmap(
            QWizard.WizardPixmap.LogoPixmap,
            qta.icon("mdi.android-debug-bridge").pixmap(64, 64),
        )

        self.selector = self.TabletSelectPage(resources, self)
        self.installer = self.InstallerPage(resources, self)
        self.installing = self.InstallingPage(
            resources, apk, self.selector.get_devices(), self
        )

        self.setPage(0, self.InitPage(resources, self))
        self.setPage(1, self.selector)
        self.setPage(2, self.installer)
        self.setPage(3, self.installing)
        self.currentIdChanged.connect(self.on_page_change)

    def on_page_change(self, page: int):
        self.installer.set_devices(self.selector.get_devices())
        self.installing.set_devices(self.selector.get_devices())
        if page == 3:
            self.installing.start()

    def generate_banner(self):
        px = QPixmap(QSize(self.width(), 84))
        px.fill(Qt.GlobalColor.transparent)

        g = QLinearGradient(QPoint(0, 0), QPoint(self.width(), 84))
        g.setColorAt(0, QColor("#A91717"))
        g.setColorAt(1, Qt.GlobalColor.transparent)

        painter = QPainter(px)
        painter.fillRect(px.rect(), g)
        painter.end()

        return px


class Downloader(QWidget):
    def __init__(self):
        super().__init__()

        self.releases = []
        self.downloads: dict[str, dict] = {}
        self.app_dir = user_data_dir("scouting_transfer", "mercs", ensure_exists=True)
        logger.info(f"Download path: {self.app_dir}")

        self.resources = shared_resources.InstallerSharedResources()
        self.resources.worker_pool = QThreadPool()

        self.resources.worker_pool.setMaxThreadCount(16)
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
            if self.resources.worker_pool:
                self.resources.worker_pool.start(worker)

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
        if self.resources.worker_pool:
            self.resources.worker_pool.start(worker)

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
        if self.resources.worker_pool:
            self.resources.worker_pool.start(worker)

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
                    release_item.show_file.connect(
                        partial(self.show_file, version_path)
                    )
                    release_item.delete.connect(partial(self.delete_version, version))
                    release_item.install.connect(partial(self.install_adb, version))
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

    def install_adb(self, version: str):
        wizard = InstallerWizard(
            self.resources, os.path.join(self.app_dir, version, "app-release.apk")
        )
        wizard.exec()

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
