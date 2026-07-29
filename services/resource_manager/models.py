from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional


PathWriter = Callable[[str], None]


@dataclass
class ReferenceRecord:
    resource_id: str
    owner_type: str
    owner_name: str
    property_path: str
    object_name: str = ""
    library_path: str = ""


@dataclass
class ReferenceNode:
    id: str
    kind: str
    name: str
    library_path: str = ""
    data_name: str = ""
    owner_name: str = ""
    tree_name: str = ""
    tree_type: str = ""
    tree_id: str = ""
    tree_owner_kind: str = ""
    tree_owner_name: str = ""
    tree_library_path: str = ""
    node_name: str = ""
    slot_index: int = -1
    scene_name: str = ""
    view_layer_name: str = ""
    linked: bool = False
    locatable: bool = True


@dataclass(frozen=True)
class ReferenceEdge:
    source_id: str
    target_id: str
    relation: str


@dataclass(frozen=True)
class ReferencePath:
    id: str
    node_ids: tuple[str, ...]
    relations: tuple[str, ...]
    cyclic: bool = False


@dataclass(frozen=True)
class ReferenceHost:
    id: str
    node_id: str
    kind: str
    name: str
    detail: str = ""


@dataclass(frozen=True)
class ReferenceUsage:
    id: str
    node_id: str
    category: str
    name: str
    hosts: tuple[ReferenceHost, ...] = ()
    path_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReferenceUsageGroup:
    category: str
    label: str
    usages: tuple[ReferenceUsage, ...]

    @property
    def count(self) -> int:
        return len(self.usages)


@dataclass(frozen=True)
class ReferenceOverview:
    direct_nodes: int = 0
    materials: int = 0
    modifiers: int = 0
    objects: int = 0
    scenes: int = 0
    primary_users: int = 0


@dataclass(frozen=True)
class ReferenceFlowCard:
    node_id: str
    kind: str
    type_label: str
    name: str
    relation: str = ""
    icon: str = "DOT"
    locatable: bool = True
    cyclic: bool = False


@dataclass(frozen=True)
class ReferenceFlowStep:
    node_id: str
    step_index: int
    kind: str
    type_label: str
    name: str
    relation: str = ""
    icon: str = "DOT"
    locatable: bool = True
    cyclic: bool = False
    path_id: str = ""


@dataclass
class ReferenceGraph:
    nodes: dict[str, ReferenceNode] = field(default_factory=dict)
    edges: list[ReferenceEdge] = field(default_factory=list)
    _outgoing: dict[str, list[ReferenceEdge]] = field(default_factory=dict, repr=False)
    usage_index: dict[str, ReferenceUsage] = field(default_factory=dict, repr=False)
    path_index: dict[str, ReferencePath] = field(default_factory=dict, repr=False)

    def add_node(self, node: ReferenceNode) -> ReferenceNode:
        return self.nodes.setdefault(node.id, node)

    def add_edge(self, source_id: str, target_id: str, relation: str) -> None:
        if source_id == target_id:
            return
        edge = ReferenceEdge(source_id, target_id, relation)
        bucket = self._outgoing.setdefault(source_id, [])
        if edge not in bucket:
            bucket.append(edge)
            self.edges.append(edge)

    def children(self, node_id: str) -> tuple[ReferenceEdge, ...]:
        return tuple(self._outgoing.get(node_id, ()))


@dataclass
class ResourceRecord:
    id: str
    kind: str
    name: str
    original_path: str
    absolute_path: str
    status: str
    size: int = 0
    member_paths: tuple[str, ...] = ()
    file_count: int = 0
    modified_time: float = 0.0
    content_hash: str = ""
    packed: bool = False
    generated: bool = False
    library_path: str = ""
    root_node_id: str = ""
    references: list[ReferenceRecord] = field(default_factory=list)
    path_writer: Optional[PathWriter] = field(default=None, repr=False, compare=False)

    @property
    def reference_count(self) -> int:
        return len(self.references)

    @property
    def is_missing(self) -> bool:
        return self.status == "MISSING"


@dataclass
class LibraryNode:
    path: str
    depth: int = 0
    parent_path: str = ""
    status: str = "OK"
    children: list[str] = field(default_factory=list)


@dataclass
class ScanIssue:
    severity: str
    message: str
    resource_id: str = ""
    path: str = ""


@dataclass
class ResourceGraph:
    resources: dict[str, ResourceRecord] = field(default_factory=dict)
    libraries: dict[str, LibraryNode] = field(default_factory=dict)
    issues: list[ScanIssue] = field(default_factory=list)
    references_graph: ReferenceGraph = field(default_factory=ReferenceGraph)

    def add_resource(self, resource: ResourceRecord) -> ResourceRecord:
        existing = self.resources.get(resource.id)
        if existing is None:
            self.resources[resource.id] = resource
            return resource
        existing.references.extend(resource.references)
        if existing.path_writer is None:
            existing.path_writer = resource.path_writer
        return existing

    @property
    def missing_count(self) -> int:
        return sum(item.is_missing for item in self.resources.values())

    @property
    def reference_count(self) -> int:
        return sum(item.reference_count for item in self.resources.values())


@dataclass
class ScanOptions:
    full_scan: bool = False
    hash_files: bool = False
    recursive_libraries: bool = False
    max_depth: int = 0


@dataclass
class PackageItem:
    resource_id: str
    source: Path
    destination: Path
    relative_path: str
    size: int
    content_hash: str = ""
    action: str = "COPY"


@dataclass
class PackagePlan:
    blend_path: Path
    assets_root: Path
    items: list[PackageItem] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)


@dataclass
class PackageResult:
    copied: int = 0
    reused: int = 0
    updated: int = 0
    skipped: int = 0
    failed: list[str] = field(default_factory=list)
