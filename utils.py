"""
Various utilities used by the program
"""

# https://stackoverflow.com/questions/12523586/python-format-size-application-converting-b-to-kb-mb-gb-tb
def format_bytes(size: int) -> str:
    """Convert bytes to str of KB, MB, etc

    Args:
        size (int): bytes

    Returns:
        str: Size string
    """
    power = 2**10
    n = 0
    power_labels = {0: "", 1: "K", 2: "M", 3: "G", 4: "T"}
    while size > power:
        size /= power
        n += 1
    return f"{size:.1f}{power_labels[n] + 'B'}"
