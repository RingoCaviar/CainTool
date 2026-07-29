from __future__ import annotations

from collections.abc import Iterable

from .scanner import record_from_path
from .reference_graph import build_reference_graph


KNOWN_COLLECTIONS = (
    ("images", "IMAGE"), ("movieclips", "MOVIE_CLIP"), ("sounds", "SOUND"),
    ("fonts", "FONT"), ("cache_files", "ALEMBIC"), ("volumes", "VDB"),
    ("libraries", "LIBRARY"),
)


class BlenderResourceSource:
    def __init__(self, bpy_module):
        self.bpy = bpy_module
        self.blend_path = bpy_module.data.filepath

    def _writer(self, owner, property_name):
        return lambda value: setattr(owner, property_name, value)

    def build_reference_graph(self):
        return build_reference_graph(self.bpy.data)

    def _record(self, owner, property_name: str, kind: str, object_name: str = ""):
        raw_path = getattr(owner, property_name, "")
        library = getattr(owner, "library", None)
        library_path = getattr(library, "filepath", "") if library else ""
        packed = bool(getattr(owner, "packed_file", None))
        source = getattr(owner, "source", "")
        generated = kind == "IMAGE" and source in {"GENERATED", "VIEWER"}
        sequence_hint = source in {"SEQUENCE", "TILED"} or bool(getattr(owner, "is_sequence", False))
        return record_from_path(
            raw_path, kind=kind, name=getattr(owner, "name", ""),
            blend_path=self.blend_path, library_path=library_path,
            owner_type=owner.__class__.__name__, owner_name=getattr(owner, "name", ""),
            property_path=property_name, object_name=object_name,
            packed=packed, generated=generated,
            sequence_hint=sequence_hint,
            path_writer=self._writer(owner, property_name),
        )

    def iter_resource_records(self) -> Iterable:
        seen = set()
        for collection_name, kind in KNOWN_COLLECTIONS:
            for owner in getattr(self.bpy.data, collection_name, ()):
                if not hasattr(owner, "filepath"):
                    continue
                key = (id(owner), "filepath")
                seen.add(key)
                yield self._record(owner, "filepath", kind)

        # Discover add-on and node-defined file/directory paths exposed through RNA.
        datablock_collections = (
            "objects", "materials", "node_groups", "scenes", "worlds", "textures",
            "masks", "cameras", "lights", "meshes", "curves",
        )
        for collection_name in datablock_collections:
            for owner in getattr(self.bpy.data, collection_name, ()):
                yield from self._iter_rna_paths(owner, seen)
                node_tree = getattr(owner, "node_tree", None)
                if node_tree:
                    for node in getattr(node_tree, "nodes", ()):
                        yield from self._iter_rna_paths(node, seen, object_name=getattr(owner, "name", ""))

    def _iter_rna_paths(self, owner, seen: set, object_name: str = ""):
        rna = getattr(owner, "bl_rna", None)
        for prop in getattr(rna, "properties", ()):
            if getattr(prop, "type", "") != "STRING" or getattr(prop, "subtype", "") not in {"FILE_PATH", "DIR_PATH"}:
                continue
            prop_name = getattr(prop, "identifier", "")
            key = (id(owner), prop_name)
            if not prop_name or prop_name == "rna_type" or key in seen or getattr(prop, "is_readonly", False):
                continue
            try:
                value = getattr(owner, prop_name)
            except Exception:
                continue
            if not value:
                continue
            seen.add(key)
            yield self._record(owner, prop_name, "MISC", object_name)
