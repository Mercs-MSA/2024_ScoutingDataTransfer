from dataclasses import dataclass

import psutil


@dataclass
class Disk:
    device: str
    mountpoint: str
    fstype: str
    opts: str
    maxfile: int
    maxpath: int
    capacity: int = 0


class DiskDetector:
    @staticmethod
    def get_disks():
        disks = []
        for disk in psutil.disk_partitions():
            disks.append(Disk(disk.device, disk.mountpoint, disk.fstype, disk.opts, disk.maxfile,
                              disk.maxpath, psutil.disk_usage(disk.mountpoint).total))
        return disks


if __name__ == "__main__":
    print(DiskDetector().get_disks())
