"""
Wrapper for psutil disk partitions
"""

from dataclasses import dataclass

import psutil


@dataclass
class Disk:
    """
    Custom disk class
    """
    device: str
    mountpoint: str
    fstype: str
    opts: str
    maxfile: int
    maxpath: int
    capacity: int = 0


class DiskDetector: # pylint: disable=too-few-public-methods
    """
    Detect disk partitions
    """
    @staticmethod
    def get_disks() -> list[Disk]:
        """
        Get disk partitiond

        Returns:
            list[Disk]: List of currently available disk partitions
        """
        disks = []
        for disk in psutil.disk_partitions():
            disks.append(Disk(disk.device, disk.mountpoint, disk.fstype, disk.opts, disk.maxfile,
                              disk.maxpath, psutil.disk_usage(disk.mountpoint).total))
        return disks


if __name__ == "__main__":
    print(DiskDetector().get_disks())
