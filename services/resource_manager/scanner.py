from __future__ import annotations

import os
import hashlib
import re
from pathlib import Path
from typing import Callable, Iterable

from .models import ReferenceRecord, ResourceGraph, ResourceRecord, ScanIssue, ScanOptions
from .paths import canonical_path, classify_path, file_hash, resource_id
from .reference_graph import bind_resource_roots
from .tasks import ResourceTask, TaskUpdate


def _resolve_path(raw_path: str, blend_path: str = "", library_path: str = "") -> str:
    if not raw_path:
        return ""
    if raw_path.startswith("//"):
        anchor = Path(library_path or blend_path).parent if (library_path or blend_path) else Path.cwd()
        return canonical_path(str(anchor / raw_path[2:]))
    return canonical_path(os.path.expanduser(raw_path))


def _sequence_regex(filename: str, sequence_hint: bool) -> re.Pattern | None:
    escaped = re.escape(filename)
    if "<UDIM>" in filename:
        return re.compile("^" + escaped.replace(re.escape("<UDIM>"), r"\d{4}") + "$", re.IGNORECASE)
    percent = re.search(r"%0(\d+)d", filename)
    if percent:
        token = percent.group(0)
        return re.compile("^" + escaped.replace(re.escape(token), rf"\d{{{int(percent.group(1))}}}") + "$", re.IGNORECASE)
    hashes = re.search(r"#+", filename)
    if hashes:
        token = hashes.group(0)
        return re.compile("^" + escaped.replace(re.escape(token), rf"\d{{{len(token)}}}") + "$", re.IGNORECASE)
    if sequence_hint:
        stem, suffix = os.path.splitext(filename)
        digits = re.search(r"(\d+)$", stem)
        if digits:
            prefix = stem[:digits.start()]
            return re.compile(
                "^" + re.escape(prefix) + rf"\d{{{len(digits.group(1))}}}" + re.escape(suffix) + "$",
                re.IGNORECASE,
            )
    return None


def collect_resource_members(absolute_path: str, sequence_hint: bool = False) -> tuple[str, ...]:
    if not absolute_path:
        return ()
    path = Path(absolute_path)
    matcher = _sequence_regex(path.name, sequence_hint)
    if matcher and path.parent.is_dir():
        try:
            return tuple(sorted(
                (canonical_path(str(candidate)) for candidate in path.parent.iterdir()
                 if candidate.is_file() and matcher.match(candidate.name)),
                key=str.casefold,
            ))
        except OSError:
            return ()
    return (canonical_path(str(path)),) if path.is_file() else ()


def _group_hash(paths: tuple[str, ...]) -> str:
    if len(paths) == 1:
        return file_hash(Path(paths[0]))
    digest = hashlib.sha256()
    for member in paths:
        path = Path(member)
        digest.update(path.name.encode("utf-8", "surrogatepass"))
        digest.update(bytes.fromhex(file_hash(path)))
    return digest.hexdigest()


def record_from_path(
    raw_path: str,
    *,
    kind: str = "MISC",
    name: str = "",
    blend_path: str = "",
    library_path: str = "",
    owner_type: str = "",
    owner_name: str = "",
    property_path: str = "filepath",
    object_name: str = "",
    packed: bool = False,
    generated: bool = False,
    sequence_hint: bool = False,
    path_writer: Callable[[str], None] | None = None,
) -> ResourceRecord:
    absolute = _resolve_path(raw_path, blend_path, library_path)
    actual_kind = classify_path(absolute or raw_path, kind)
    members = () if packed or generated else collect_resource_members(absolute, sequence_hint)
    exists = bool(members)
    status = "PACKED" if packed else "GENERATED" if generated else "OK" if exists else "MISSING"
    stats = [Path(member).stat() for member in members]
    rid = resource_id(actual_kind, absolute or f"{owner_type}:{owner_name}:{raw_path}")
    reference = ReferenceRecord(rid, owner_type, owner_name, property_path, object_name, library_path)
    return ResourceRecord(
        id=rid, kind=actual_kind, name=name or Path(raw_path).name or owner_name,
        original_path=raw_path, absolute_path=absolute, status=status,
        size=sum(stat.st_size for stat in stats),
        member_paths=members, file_count=len(members),
        modified_time=max((stat.st_mtime for stat in stats), default=0.0),
        packed=packed, generated=generated, library_path=library_path,
        references=[reference], path_writer=path_writer,
    )


def _scan_work(records: Iterable[ResourceRecord], options: ScanOptions, reference_builder=None):
    records = list(records)
    graph = ResourceGraph()
    scan_units = sum(max(1, record.file_count) for record in records)
    total = scan_units + (len(records) if options.hash_files else 0)
    completed = 0
    scanned_bytes = 0
    total_scan_bytes = sum(record.size for record in records)
    for record in records:
        graph.add_resource(record)
        if record.is_missing:
            graph.issues.append(ScanIssue("ERROR", "找不到外部资源", record.id, record.absolute_path))
        members = record.member_paths or (record.absolute_path or record.name,)
        for member in members:
            completed += 1
            try:
                scanned_bytes += Path(member).stat().st_size if record.member_paths else 0
            except OSError:
                graph.issues.append(ScanIssue("WARNING", "无法读取资源成员", record.id, member))
            yield TaskUpdate(
                "解析资源组与文件大小", member, completed, total,
                completed / max(1, scan_units), scanned_bytes, total_scan_bytes,
            )
    if options.hash_files:
        hashed_bytes = 0
        total_bytes = sum(item.size for item in graph.resources.values() if item.status == "OK")
        for offset, record in enumerate(graph.resources.values(), 1):
            if record.status == "OK":
                record.content_hash = _group_hash(record.member_paths)
                hashed_bytes += record.size
            yield TaskUpdate(
                "计算内容哈希", record.absolute_path or record.name,
                scan_units + offset, total, offset / max(1, len(graph.resources)),
                hashed_bytes, total_bytes,
            )
    if reference_builder is not None:
        yield TaskUpdate("构建节点引用图", "扫描材质、节点组、物体、集合与场景", total, total + 2, 0.1)
        graph.references_graph = reference_builder()
        yield TaskUpdate(
            "生成引用路径", f"{len(graph.references_graph.nodes)} 个节点 / {len(graph.references_graph.edges)} 条关系",
            total + 1, total + 2, 0.8,
        )
        bind_resource_roots(graph)
        total += 2
    yield TaskUpdate("汇总", "生成资源状态和引用统计", total, total, 1.0)
    return graph


def scan_current_file(source, options: ScanOptions | None = None) -> ResourceTask:
    options = options or ScanOptions()
    records = source.iter_resource_records() if hasattr(source, "iter_resource_records") else source
    reference_builder = getattr(source, "build_reference_graph", None)
    return ResourceTask("完整资源扫描" if options.full_scan else "快速资源扫描", _scan_work(records, options, reference_builder))


def scan_library_tree(root, options: ScanOptions | None = None) -> ResourceTask:
    options = options or ScanOptions(full_scan=True, recursive_libraries=True)
    records = root.iter_resource_records() if hasattr(root, "iter_resource_records") else root
    return ResourceTask("递归扫描外链库", _scan_work(records, options))


def find_references(graph: ResourceGraph, resource_id_value: str) -> tuple[ReferenceRecord, ...]:
    resource = graph.resources.get(resource_id_value)
    return tuple(resource.references) if resource else ()
