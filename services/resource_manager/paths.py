from __future__ import annotations

import hashlib
import os
from pathlib import Path


KIND_FOLDERS = {
    "IMAGE": "textures", "MOVIE_CLIP": "video", "VIDEO": "video",
    "SOUND": "audio", "FONT": "fonts", "ALEMBIC": "caches/alembic",
    "VDB": "caches/vdb", "SIMULATION": "caches/simulation",
    "LIBRARY": "libraries",
}


def canonical_path(path: str) -> str:
    if not path:
        return ""
    return os.path.normcase(os.path.realpath(os.path.abspath(path)))


def resource_id(kind: str, absolute_path: str) -> str:
    key = f"{kind}:{canonical_path(absolute_path)}".encode("utf-8", "surrogatepass")
    return hashlib.sha1(key).hexdigest()


def file_hash(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def classify_path(path: str, fallback: str = "MISC") -> str:
    suffix = Path(path).suffix.lower()
    if suffix == ".blend": return "LIBRARY"
    if suffix in {".abc"}: return "ALEMBIC"
    if suffix in {".vdb"}: return "VDB"
    if suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".exr", ".hdr", ".dds", ".webp"}: return "IMAGE"
    if suffix in {".mov", ".mp4", ".avi", ".mkv", ".webm"}: return "VIDEO"
    if suffix in {".wav", ".mp3", ".flac", ".ogg", ".aif", ".aiff"}: return "SOUND"
    if suffix in {".ttf", ".otf", ".woff", ".woff2"}: return "FONT"
    return fallback


def folder_for_kind(kind: str) -> Path:
    return Path(KIND_FOLDERS.get(kind, "misc"))
