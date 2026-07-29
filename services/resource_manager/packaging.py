from __future__ import annotations

import os
import shutil
from pathlib import Path

from .models import PackageItem, PackagePlan, PackageResult, ResourceGraph
from .paths import file_hash, folder_for_kind
from .tasks import ResourceTask, TaskUpdate


def build_package_plan(
    graph: ResourceGraph,
    selection: set[str] | None,
    blend_path: str,
    assets_folder: str = "assets",
) -> PackagePlan:
    if not blend_path:
        raise ValueError("请先保存 .blend 工程，再执行相对路径打包。")
    blend = Path(blend_path).resolve()
    root = blend.parent / assets_folder
    plan = PackagePlan(blend, root)
    reserved: dict[Path, str] = {}
    for resource in graph.resources.values():
        if selection and resource.id not in selection:
            continue
        if resource.status != "OK" or not resource.absolute_path:
            plan.skipped.append(resource.id)
            continue
        source = Path(resource.absolute_path)
        if not source.is_file():
            plan.skipped.append(resource.id)
            continue
        digest = resource.content_hash if resource.file_count <= 1 and resource.content_hash else file_hash(source)
        destination = root / folder_for_kind(resource.kind) / source.name
        existing_hash = reserved.get(destination)
        reserved_same_content = existing_hash == digest
        if existing_hash and existing_hash != digest:
            destination = destination.with_name(f"{destination.stem}_{digest[:8]}{destination.suffix}")
            plan.conflicts.append(resource.id)
        elif destination.exists() and destination.resolve() != source.resolve():
            destination_hash = file_hash(destination)
            if destination_hash != digest:
                destination = destination.with_name(f"{destination.stem}_{digest[:8]}{destination.suffix}")
                plan.conflicts.append(resource.id)
        reserved[destination] = digest
        relative = "//" + destination.relative_to(blend.parent).as_posix()
        action = "REUSE" if reserved_same_content or (destination.exists() and file_hash(destination) == digest) else "COPY"
        plan.items.append(PackageItem(resource.id, source, destination, relative, source.stat().st_size, digest, action))
    return plan


def _package_work(plan: PackagePlan, graph: ResourceGraph):
    result = PackageResult(skipped=len(plan.skipped))
    total = len(plan.items) * 3
    copied_bytes = 0
    total_bytes = sum(item.size for item in plan.items if item.action == "COPY")
    staged: list[tuple[PackageItem, Path]] = []
    for index, item in enumerate(plan.items, 1):
        item.destination.parent.mkdir(parents=True, exist_ok=True)
        if item.action == "REUSE":
            result.reused += 1
            staged.append((item, item.destination))
        else:
            temporary = item.destination.with_name(item.destination.name + ".caintool-tmp")
            shutil.copy2(item.source, temporary)
            copied_bytes += item.size
            staged.append((item, temporary))
        yield TaskUpdate("复制资源", str(item.source), index, total, index / max(1, len(plan.items)), copied_bytes, total_bytes)
    verified: list[PackageItem] = []
    for index, (item, staged_path) in enumerate(staged, 1):
        if file_hash(staged_path) != item.content_hash:
            result.failed.append(f"校验失败：{item.source}")
            if staged_path != item.destination:
                staged_path.unlink(missing_ok=True)
        else:
            if staged_path != item.destination:
                os.replace(staged_path, item.destination)
                result.copied += 1
            verified.append(item)
        yield TaskUpdate("校验资源", str(item.destination), len(plan.items) + index, total, index / max(1, len(staged)))
    for index, item in enumerate(verified, 1):
        resource = graph.resources[item.resource_id]
        if resource.path_writer:
            resource.path_writer(item.relative_path)
            resource.original_path = item.relative_path
            resource.absolute_path = str(item.destination)
            result.updated += 1
        yield TaskUpdate("回写相对路径", item.relative_path, len(plan.items) * 2 + index, total, index / max(1, len(verified)))
    return result


def execute_package_plan(plan: PackagePlan, graph: ResourceGraph) -> ResourceTask:
    return ResourceTask("规范化打包外部资源", _package_work(plan, graph))
