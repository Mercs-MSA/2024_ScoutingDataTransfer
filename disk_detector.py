"""
Wrapper for psutil disk partitions
"""

import os
import json

from dataclasses import dataclass

import psutil

import utils


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


class DiskDetector:  # pylint: disable=too-few-public-methods
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
            disks.append(
                Disk(
                    disk.device,
                    disk.mountpoint,
                    disk.fstype,
                    disk.opts,
                    disk.maxfile,
                    disk.maxpath,
                    psutil.disk_usage(disk.mountpoint).total,
                )
            )
        return disks


def scouting_disk_predicate(disk: Disk) -> tuple[bool, str, str]:
    """Disk detection predicate

    Args:
        disk (disk_detector.Disk): Disk to attempt search

    Returns:
        tuple[bool, str, str]: Output from predicate (Visible, Name, Icon)
    """
    if os.path.isfile(os.path.join(disk.mountpoint, "scout_disk_opts.json")):
        with open(
            os.path.join(disk.mountpoint, "scout_disk_opts.json"), "r", encoding="utf-8"
        ) as file:
            opts = json.load(file)
    else:
        opts = {}

    if "display" in opts:
        if "id" in opts:
            return (
                True,
                f"ID: {opts['id']} {disk.mountpoint} fs:{disk.fstype} "
                f"cap:{utils.format_bytes(disk.capacity)}",
                str(opts["id"]),
            )
        if opts["display"]:
            return (
                True,
                f"ID: ?? {disk.mountpoint} fs:{disk.fstype} "
                "cap:{utils.format_bytes(disk.capacity)}",
                "0",
            )

    return False, "", "??"


if __name__ == "__main__":
    print(DiskDetector().get_disks())
