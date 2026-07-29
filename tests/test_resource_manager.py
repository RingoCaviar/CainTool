import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from services.resource_manager.models import ResourceGraph, ScanOptions
from services.resource_manager.packaging import build_package_plan, execute_package_plan
from services.resource_manager.scanner import record_from_path, scan_current_file
from services.resource_manager.formatting import format_file_size, sort_resources
from services.resource_manager.tasks import ResourceTask, TaskState, TaskUpdate
from services.resource_manager.reference_graph import build_reference_graph, build_reference_paths
from services.resource_manager.usage_summary import get_paths_to_usage, summarize_reference_usage
from services.resource_manager.inspector import (
    build_flow_steps, build_reference_overview, choose_default_complete_path,
    choose_default_path, choose_default_usage, get_complete_usage_paths, get_display_path,
)


def finish(task):
    while task.tick(1.0):
        pass
    return task


class ResourceTaskTests(unittest.TestCase):
    def test_task_reports_progress_and_result(self):
        def work():
            yield TaskUpdate("扫描", "a", 1, 2, 0.5, 5, 10)
            yield TaskUpdate("扫描", "b", 2, 2, 1.0, 10, 10)
            return "done"

        task = finish(ResourceTask("test", work()))
        self.assertEqual(task.state, TaskState.COMPLETED)
        self.assertEqual(task.result, "done")
        self.assertEqual(task.progress, 1.0)
        self.assertEqual(task.bytes_completed, 10)

    def test_task_can_be_cancelled_before_work(self):
        task = ResourceTask("test", [TaskUpdate("扫描")])
        task.cancel()
        finish(task)
        self.assertEqual(task.state, TaskState.CANCELLED)


class ResourceScanTests(unittest.TestCase):
    def test_file_size_formatting_uses_adaptive_binary_units(self):
        self.assertEqual(format_file_size(824), "824 B")
        self.assertEqual(format_file_size(19_503_514), "18.6 MB")
        self.assertEqual(format_file_size(2.34 * 1024 ** 3), "2.34 GB")
        self.assertEqual(format_file_size(3 * 1024 ** 4), "3.00 TB")

    def test_sequence_members_are_summed_but_plain_numbered_files_are_not(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name, payload in (("fog.0001.vdb", b"a"), ("fog.0002.vdb", b"bb"), ("other.0001.vdb", b"xxx")):
                (root / name).write_bytes(payload)
            sequence = record_from_path(str(root / "fog.####.vdb"), kind="VDB")
            self.assertEqual(sequence.file_count, 2)
            self.assertEqual(sequence.size, 3)
            plain = record_from_path(str(root / "fog.0001.vdb"), kind="VDB")
            self.assertEqual(plain.file_count, 1)
            self.assertEqual(plain.size, 1)

    def test_size_sort_handles_large_values_and_places_unavailable_last(self):
        items = [
            SimpleNamespace(name="Small", size=1, status="OK", kind="IMAGE", library_path=""),
            SimpleNamespace(name="Huge", size=5 * 1024 ** 3, status="OK", kind="VDB", library_path=""),
            SimpleNamespace(name="Missing", size=0, status="MISSING", kind="IMAGE", library_path=""),
        ]
        self.assertEqual([item.name for item in sort_resources(items, "SIZE", True)], ["Huge", "Small", "Missing"])
        self.assertEqual([item.name for item in sort_resources(items, "SIZE", False)], ["Small", "Huge", "Missing"])

    def test_scan_deduplicates_path_and_preserves_references(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "shared.png"
            path.write_bytes(b"same")
            first = record_from_path(str(path), kind="IMAGE", owner_type="Image", owner_name="A")
            second = record_from_path(str(path), kind="IMAGE", owner_type="Node", owner_name="B")
            task = finish(scan_current_file([first, second], ScanOptions(hash_files=True)))
            graph = task.result
            self.assertEqual(len(graph.resources), 1)
            resource = next(iter(graph.resources.values()))
            self.assertEqual(resource.reference_count, 2)
            self.assertEqual(len(resource.content_hash), 64)

    def test_scan_marks_missing_file(self):
        record = record_from_path("definitely-missing.vdb", kind="VDB", owner_type="Volume", owner_name="Fog")
        graph = finish(scan_current_file([record])).result
        self.assertEqual(graph.missing_count, 1)
        self.assertEqual(graph.resources[record.id].kind, "VDB")


class ResourcePackagingTests(unittest.TestCase):
    def test_package_copies_verifies_and_updates_relative_path(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source" / "wood.png"
            source.parent.mkdir()
            source.write_bytes(b"texture")
            blend = root / "project" / "scene.blend"
            blend.parent.mkdir()
            blend.write_bytes(b"")
            written = []
            record = record_from_path(
                str(source), kind="IMAGE", owner_type="Image", owner_name="Wood",
                path_writer=written.append,
            )
            graph = ResourceGraph()
            graph.add_resource(record)
            plan = build_package_plan(graph, None, str(blend))
            task = finish(execute_package_plan(plan, graph))
            target = root / "project" / "assets" / "textures" / "wood.png"
            self.assertEqual(task.state, TaskState.COMPLETED)
            self.assertEqual(target.read_bytes(), b"texture")
            self.assertEqual(written, ["//assets/textures/wood.png"])

    def test_conflicting_names_receive_hash_suffix(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            one = root / "one" / "same.png"
            two = root / "two" / "same.png"
            one.parent.mkdir(); two.parent.mkdir()
            one.write_bytes(b"one"); two.write_bytes(b"two")
            blend = root / "scene.blend"; blend.write_bytes(b"")
            graph = ResourceGraph()
            graph.add_resource(record_from_path(str(one), kind="IMAGE", owner_type="Image", owner_name="One"))
            graph.add_resource(record_from_path(str(two), kind="IMAGE", owner_type="Image", owner_name="Two"))
            plan = build_package_plan(graph, None, str(blend))
            self.assertEqual(len({item.destination for item in plan.items}), 2)
            self.assertEqual(len(plan.conflicts), 1)


def named(name, **values):
    return SimpleNamespace(name=name, library=None, **values)


class ReferenceGraphTests(unittest.TestCase):
    def _material_fixture(self):
        image = named("Wood")
        texture = named("Image Texture", label="", image=image, node_tree=None)
        tree = named("WoodTree", bl_idname="ShaderNodeTree", nodes=[texture])
        material = named("WoodMaterial", node_tree=tree)
        slot = named("Wood Slot", material=material)
        obj = named("Cube", material_slots=[slot], modifiers=[], data=None, instance_collection=None)
        collection = named("Props", objects=[obj], all_objects=[obj])
        root_collection = named("Scene Collection", children=[collection], children_recursive=[collection])
        layer = named("ViewLayer")
        scene = named("Scene", node_tree=None, world=None, collection=root_collection, view_layers=[layer])
        data = SimpleNamespace(
            images=[image], materials=[material], worlds=[], lights=[], scenes=[scene],
            node_groups=[], objects=[obj], collections=[collection],
        )
        return data, image

    def test_image_traces_through_material_slot_object_collection_scene(self):
        data, image = self._material_fixture()
        graph = build_reference_graph(data)
        image_id = next(node.id for node in graph.nodes.values() if node.kind == "IMAGE" and node.name == image.name)
        paths = build_reference_paths(graph, image_id)
        kinds = [[graph.nodes[node_id].kind for node_id in path.node_ids] for path in paths]
        self.assertTrue(any(
            chain == ["IMAGE", "NODE", "NODE_TREE", "MATERIAL", "MATERIAL_SLOT", "OBJECT", "COLLECTION", "SCENE", "VIEW_LAYER"]
            for chain in kinds
        ))

    def test_nested_group_cycle_is_reported_and_stops(self):
        image = named("LoopImage")
        tree_a = named("TreeA", bl_idname="ShaderNodeTree", nodes=[])
        tree_b = named("TreeB", bl_idname="ShaderNodeTree", nodes=[])
        image_node = named("Image", label="", image=image, node_tree=None)
        group_b = named("Use B", label="", image=None, node_tree=tree_b)
        group_a = named("Use A", label="", image=None, node_tree=tree_a)
        tree_a.nodes.extend([image_node, group_b])
        tree_b.nodes.append(group_a)
        data = SimpleNamespace(
            images=[image], materials=[], worlds=[], lights=[], scenes=[],
            node_groups=[tree_a, tree_b], objects=[], collections=[],
        )
        graph = build_reference_graph(data)
        image_id = next(node.id for node in graph.nodes.values() if node.kind == "IMAGE")
        paths = build_reference_paths(graph, image_id)
        self.assertTrue(paths)
        self.assertTrue(any(path.cyclic for path in paths))
        self.assertLess(max(len(path.node_ids) for path in paths), 10)

    def test_stable_node_ids_do_not_use_python_identity(self):
        first, _ = self._material_fixture()
        second, _ = self._material_fixture()
        first_ids = set(build_reference_graph(first).nodes)
        second_ids = set(build_reference_graph(second).nodes)
        self.assertEqual(first_ids, second_ids)

    def test_usage_summary_deduplicates_material_and_groups_object_hosts(self):
        data, image = self._material_fixture()
        material = data.materials[0]
        second_slot = named("Wood Slot", material=material)
        second = named("Sphere", material_slots=[second_slot], modifiers=[], data=None, instance_collection=None)
        data.objects.append(second)
        data.collections[0].objects.append(second)
        data.collections[0].all_objects.append(second)
        graph = build_reference_graph(data)
        image_id = next(node.id for node in graph.nodes.values() if node.kind == "IMAGE" and node.name == image.name)
        groups = summarize_reference_usage(graph, image_id)
        material_group = next(group for group in groups if group.category == "MATERIAL")
        self.assertEqual(material_group.count, 1)
        usage = material_group.usages[0]
        self.assertEqual(len(usage.hosts), 2)
        self.assertEqual({host.detail.split(" · ")[0] for host in usage.hosts}, {"Cube", "Sphere"})
        self.assertTrue(get_paths_to_usage(graph, image_id, usage.id))

    def test_usage_summary_separates_world_light_compositor_and_modifier(self):
        image = named("Shared")
        def tree(name, tree_type="ShaderNodeTree"):
            return named(name, bl_idname=tree_type, nodes=[named(f"{name} Image", label="", image=image, node_tree=None)])
        world = named("World", node_tree=tree("WorldTree"))
        light = named("Key", node_tree=tree("LightTree"))
        compositor_tree = tree("CompositorTree", "CompositorNodeTree")
        group = tree("GeometryTree", "GeometryNodeTree")
        modifier = named("GeometryNodes", node_group=group)
        light_obj = named("LightObject", material_slots=[], modifiers=[], data=light, instance_collection=None)
        geo_obj = named("GeoObject", material_slots=[], modifiers=[modifier], data=None, instance_collection=None)
        root = named("Scene Collection", children=[], children_recursive=[])
        layer = named("ViewLayer")
        scene = named("Scene", node_tree=compositor_tree, world=world, collection=root, view_layers=[layer])
        data = SimpleNamespace(
            images=[image], materials=[], worlds=[world], lights=[light], scenes=[scene],
            node_groups=[group], objects=[light_obj, geo_obj], collections=[],
        )
        graph = build_reference_graph(data)
        image_id = next(node.id for node in graph.nodes.values() if node.kind == "IMAGE")
        categories = {group.category for group in summarize_reference_usage(graph, image_id)}
        self.assertTrue({"WORLD", "LIGHT", "COMPOSITOR", "MODIFIER"}.issubset(categories))

    def test_inspector_overview_and_default_flow_are_immediately_available(self):
        data, image = self._material_fixture()
        graph = build_reference_graph(data)
        image_id = next(node.id for node in graph.nodes.values() if node.kind == "IMAGE" and node.name == image.name)
        groups = summarize_reference_usage(graph, image_id)
        overview = build_reference_overview(graph, image_id)
        usage_id = choose_default_usage(groups)
        usage = graph.usage_index[usage_id]
        paths = get_paths_to_usage(graph, image_id, usage_id)
        path = choose_default_path(paths)
        cards = get_display_path(graph, path, usage.node_id)
        self.assertEqual(overview.materials, 1)
        self.assertEqual(overview.objects, 1)
        self.assertEqual(overview.scenes, 1)
        self.assertTrue(usage_id)
        self.assertEqual(cards[0].kind, "IMAGE")
        self.assertEqual(cards[-1].kind, "MATERIAL")
        self.assertTrue(all(card.type_label for card in cards))

    def test_default_usage_prefers_a_user_with_a_real_host(self):
        data, image = self._material_fixture()
        orphan_tree = named(
            "OrphanTree", bl_idname="ShaderNodeTree",
            nodes=[named("Orphan Image", label="", image=image, node_tree=None)],
        )
        data.node_groups.insert(0, orphan_tree)
        graph = build_reference_graph(data)
        image_id = next(node.id for node in graph.nodes.values() if node.kind == "IMAGE" and node.name == image.name)
        groups = summarize_reference_usage(graph, image_id)
        selected = graph.usage_index[choose_default_usage(groups)]
        self.assertEqual(selected.category, "MATERIAL")
        self.assertTrue(selected.hosts)

    def test_display_path_can_extend_to_a_specific_material_slot(self):
        data, image = self._material_fixture()
        graph = build_reference_graph(data)
        image_id = next(node.id for node in graph.nodes.values() if node.kind == "IMAGE" and node.name == image.name)
        groups = summarize_reference_usage(graph, image_id)
        usage = graph.usage_index[choose_default_usage(groups)]
        host = usage.hosts[0]
        path = choose_default_path(get_paths_to_usage(graph, image_id, usage.id), host.node_id)
        cards = get_display_path(graph, path, host.node_id)
        self.assertEqual(cards[-1].kind, "MATERIAL_SLOT")
        self.assertEqual(cards[-1].type_label, "材质槽")

    def test_complete_path_keeps_all_nested_group_levels_and_real_terminal(self):
        image = named("NestedImage")
        inner = named("InnerTree", bl_idname="ShaderNodeTree", nodes=[])
        middle = named("MiddleTree", bl_idname="ShaderNodeTree", nodes=[])
        outer = named("OuterTree", bl_idname="ShaderNodeTree", nodes=[])
        material_tree = named("MaterialTree", bl_idname="ShaderNodeTree", nodes=[])
        inner.nodes.append(named("Image Texture", label="", image=image, node_tree=None))
        middle.nodes.append(named("Inner Group", label="", image=None, node_tree=inner))
        outer.nodes.append(named("Middle Group", label="", image=None, node_tree=middle))
        material_tree.nodes.append(named("Outer Group", label="", image=None, node_tree=outer))
        material = named("NestedMaterial", node_tree=material_tree)
        slot = named("Slot", material=material)
        obj = named("NestedObject", material_slots=[slot], modifiers=[], data=None, instance_collection=None)
        child = named("Child", objects=[obj], all_objects=[obj], children=[])
        parent = named("Parent", objects=[], all_objects=[obj], children=[child])
        root = named("Scene Collection", children=[parent], children_recursive=[parent, child])
        scene = named("Scene", node_tree=None, world=None, collection=root, view_layers=[named("ViewLayer")])
        data = SimpleNamespace(
            images=[image], materials=[material], worlds=[], lights=[], scenes=[scene],
            node_groups=[inner, middle, outer], objects=[obj], collections=[child, parent],
        )
        graph = build_reference_graph(data)
        image_id = next(node.id for node in graph.nodes.values() if node.kind == "IMAGE")
        groups = summarize_reference_usage(graph, image_id)
        usage_id = choose_default_usage(groups)
        paths = get_complete_usage_paths(graph, image_id, usage_id)
        path = choose_default_complete_path(graph, paths)
        names = [graph.nodes[node_id].name for node_id in path.node_ids]
        for expected in (
            "InnerTree", "Inner Group", "MiddleTree", "Middle Group", "OuterTree",
            "Outer Group", "MaterialTree", "NestedMaterial", "NestedObject",
            "Child", "Parent", "Scene", "ViewLayer",
        ):
            self.assertTrue(any(name == expected or name.startswith(expected + "（") for name in names), expected)
        self.assertEqual(names[-1], "ViewLayer")
        steps = build_flow_steps(graph, path)
        self.assertEqual(len(steps), len(path.node_ids))
        self.assertEqual(steps[-1].name, "ViewLayer")

    def test_unhosted_nested_groups_still_end_at_outermost_tree(self):
        image = named("OrphanImage")
        inner = named("Inner", bl_idname="ShaderNodeTree", nodes=[named("Image", label="", image=image, node_tree=None)])
        outer = named("Outer", bl_idname="ShaderNodeTree", nodes=[named("Inner Group", label="", image=None, node_tree=inner)])
        data = SimpleNamespace(
            images=[image], materials=[], worlds=[], lights=[], scenes=[],
            node_groups=[inner, outer], objects=[], collections=[],
        )
        graph = build_reference_graph(data)
        image_id = next(node.id for node in graph.nodes.values() if node.kind == "IMAGE")
        groups = summarize_reference_usage(graph, image_id)
        paths = get_complete_usage_paths(graph, image_id, choose_default_usage(groups))
        path = choose_default_complete_path(graph, paths)
        self.assertTrue(graph.nodes[path.node_ids[-1]].name.startswith("Outer（"))

    def test_same_named_owner_trees_and_nodes_never_cross_link(self):
        image_a = named("A")
        image_b = named("B")

        def shader_tree(image):
            return named(
                "Shader Nodetree", bl_idname="ShaderNodeTree",
                nodes=[named("Image Texture", label="", image=image, node_tree=None)],
            )

        material_a = named("Material A", node_tree=shader_tree(image_a))
        material_b = named("Material B", node_tree=shader_tree(image_b))
        world = named("World", node_tree=shader_tree(image_b))
        object_a = named("Object A", material_slots=[named("Slot", material=material_a)], modifiers=[], data=None, instance_collection=None)
        object_b = named("Object B", material_slots=[named("Slot", material=material_b)], modifiers=[], data=None, instance_collection=None)
        data = SimpleNamespace(
            images=[image_a, image_b], materials=[material_a, material_b], worlds=[world], lights=[], scenes=[],
            node_groups=[], objects=[object_a, object_b], collections=[],
        )
        graph = build_reference_graph(data)
        root_a = next(node.id for node in graph.nodes.values() if node.kind == "IMAGE" and node.name == "A")
        paths = build_reference_paths(graph, root_a)
        path_nodes = {node_id for path in paths for node_id in path.node_ids}
        names = {graph.nodes[node_id].name for node_id in path_nodes}
        self.assertIn("Material A", names)
        self.assertIn("Object A", names)
        self.assertNotIn("Material B", names)
        self.assertNotIn("Object B", names)
        self.assertNotIn("World", names)
        image_nodes = [node for node in graph.nodes.values() if node.kind == "NODE"]
        self.assertEqual(len({node.id for node in image_nodes}), 3)
        self.assertEqual({node.tree_owner_name for node in image_nodes}, {"Material A", "Material B", "World"})


if __name__ == "__main__":
    unittest.main()
