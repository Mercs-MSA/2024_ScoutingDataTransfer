"""
Various utilities used by the program
"""

import json
import math
import sys
import loguru

from PySide6.QtCore import qVersion
from PIL import _version as pil_version
from pillow_heif import _version as pillow_heif_version
from jinja2 import __version__ as jinja2_version


def convert_types(data_list):
    for i in data_list:
        try:
            yield json.loads(i)
        except Exception:
            yield i


def chunk_into_n(lst, n):
    size = math.ceil(len(lst) / n)
    return list(map(lambda x: lst[x * size : x * size + size], list(range(n))))


def report_versions(logger: "loguru.Logger"):
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Qt version: {qVersion()}")
    logger.info(f"Pillow version: {pil_version.__version__}")
    logger.info(f"Pillow-Heif version: {pillow_heif_version.__version__}")
    logger.info(f"Jinja2 version: {jinja2_version}")
