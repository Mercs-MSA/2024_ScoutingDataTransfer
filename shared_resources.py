from ppadb.client import Client as AdbClient
from PySide6.QtCore import QThreadPool


class InstallerSharedResources:
    debug_client: AdbClient | None = None
    worker_pool: QThreadPool | None = None
