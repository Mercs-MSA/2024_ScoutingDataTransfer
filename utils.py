"""
Various utilities used by the program
"""

import json
import math


def convert_types(data_list):
    for i in data_list:
        try:
            yield json.loads(i)
        except Exception:
            yield i


def chunk_into_n(lst, n):
    size = math.ceil(len(lst) / n)
    return list(map(lambda x: lst[x * size : x * size + size], list(range(n))))
