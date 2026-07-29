from __future__ import annotations


def format_file_size(value: int | float) -> str:
    """Format a logical byte count using binary (1024-based) units."""
    size = max(0.0, float(value))
    units = ("B", "KB", "MB", "GB", "TB")
    for index, unit in enumerate(units):
        if size < 1024.0 or index == len(units) - 1:
            if unit == "B":
                return f"{int(size)} B"
            precision = 2 if size < 10 else 1 if size < 100 else 0
            return f"{size:.{precision}f} {unit}"
        size /= 1024.0
    return "0 B"


def sort_resources(resources, key: str = "TYPE", descending: bool = True):
    items = list(resources)
    if key == "SIZE":
        available = [item for item in items if item.status not in {"MISSING", "GENERATED"}]
        unavailable = [item for item in items if item.status in {"MISSING", "GENERATED"}]
        available.sort(key=lambda item: item.name.casefold())
        available.sort(key=lambda item: item.size, reverse=descending)
        unavailable.sort(key=lambda item: item.name.casefold())
        return available + unavailable
    if key == "STATUS":
        return sorted(items, key=lambda item: (item.status, item.name.casefold()))
    if key == "LIBRARY":
        return sorted(items, key=lambda item: (item.library_path, item.name.casefold()))
    return sorted(items, key=lambda item: (item.kind, item.name.casefold()))
