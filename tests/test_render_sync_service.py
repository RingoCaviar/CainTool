import unittest

from services import render_sync_service


class DummyProp:
    def __init__(self, identifier, is_readonly=False):
        self.identifier = identifier
        self.is_readonly = is_readonly


class DummyRNA:
    def __init__(self, identifiers):
        self.properties = [DummyProp(identifier) for identifier in identifiers]


class DummyGroup:
    def __init__(self, **values):
        self.bl_rna = DummyRNA(values.keys())
        for key, value in values.items():
            setattr(self, key, value)


class DummyViewLayers:
    def __init__(self, active):
        self.active = active
        self._items = {active.name: active}

    def get(self, name):
        return self._items.get(name)


class DummyViewLayer:
    def __init__(self, name, eevee):
        self.name = name
        self.eevee = eevee


class DummySettings:
    def __init__(self, render_sync_target=False, **values):
        self.render_sync_target = render_sync_target
        for key, value in values.items():
            setattr(self, key, value)


class DummyScene:
    def __init__(self, name, *, target=False, engine="CYCLES"):
        self.name = name
        self.render = DummyGroup(
            engine=engine,
            filepath="//out",
            resolution_x=1920,
            image_settings=DummyGroup(file_format="PNG", color_mode="RGBA"),
            ffmpeg=DummyGroup(format="MPEG4"),
        )
        self.view_settings = DummyGroup(look="None")
        self.cycles = DummyGroup(samples=64)
        self.eevee = DummyGroup(taa_samples=16)
        self.world = object()
        self.caintool = DummySettings(render_sync_target=target)
        active_layer = DummyViewLayer("ViewLayer", DummyGroup(gtao_factor=1.0))
        active_layer.bl_rna = DummyRNA(("name", "use_pass_z", "use_pass_normal"))
        active_layer.use_pass_z = False
        active_layer.use_pass_normal = False
        self.view_layers = DummyViewLayers(active_layer)


class RenderSyncServiceTests(unittest.TestCase):
    def test_copy_property_group_excludes_output_path(self):
        master = DummyScene("Master")
        slave = DummyScene("Slave")
        master.render.resolution_x = 1280
        master.render.filepath = "//master"
        slave.render.filepath = "//slave"

        render_sync_service.copy_property_group(master, slave, "render", exclude_list=("filepath",))

        self.assertEqual(slave.render.resolution_x, 1280)
        self.assertEqual(slave.render.filepath, "//slave")

    def test_get_target_scenes_skips_master(self):
        master = DummyScene("Master")
        a = DummyScene("A", target=True)
        b = DummyScene("B", target=False)

        targets = render_sync_service.get_target_scenes(master, (master, a, b))

        self.assertEqual(targets, [a])

    def test_perform_sync_copies_render_data(self):
        master = DummyScene("Master")
        slave = DummyScene("Slave", target=True)
        master.render.resolution_x = 2048
        master.render.image_settings.file_format = "OPEN_EXR"
        master.cycles.samples = 256

        result = render_sync_service.perform_sync(master, (master, slave))

        self.assertEqual(result.synced_count, 1)
        self.assertEqual(slave.render.resolution_x, 2048)
        self.assertEqual(slave.render.image_settings.file_format, "PNG")
        self.assertEqual(slave.cycles.samples, 256)

    def test_perform_sync_returns_zero_when_no_targets(self):
        master = DummyScene("Master")

        result = render_sync_service.perform_sync(master, (master,))

        self.assertEqual(result.synced_count, 0)
        self.assertEqual(result.skipped_count, 0)

    def test_perform_sync_only_copies_enabled_groups(self):
        master = DummyScene("Master")
        slave = DummyScene("Slave", target=True)
        master.render.resolution_x = 2048
        master.render.image_settings.file_format = "OPEN_EXR"
        master.view_layers.active.use_pass_z = True
        slave.render.filepath = "//slave"

        options = render_sync_service.RenderSyncOptions(
            render_settings=False,
            color_management=False,
            engine_settings=False,
            world=False,
            output_format=True,
            render_passes=True,
        )
        render_sync_service.perform_sync(master, (master, slave), options)

        self.assertEqual(slave.render.resolution_x, 1920)
        self.assertEqual(slave.render.image_settings.file_format, "OPEN_EXR")
        self.assertTrue(slave.view_layers.active.use_pass_z)
        self.assertEqual(slave.render.filepath, "//slave")

    def test_perform_sync_clears_target_world_when_source_has_no_world(self):
        master = DummyScene("Master")
        slave = DummyScene("Slave", target=True)
        master.world = None

        render_sync_service.perform_sync(master, (master, slave))

        self.assertIsNone(slave.world)

    def test_perform_sync_skips_render_passes_without_matching_view_layer(self):
        master = DummyScene("Master")
        slave = DummyScene("Slave", target=True)
        master.view_layers.active.use_pass_z = True

        unmatched_layer = DummyViewLayer("DifferentLayer", DummyGroup(gtao_factor=1.0))
        unmatched_layer.bl_rna = DummyRNA(("name", "use_pass_z"))
        unmatched_layer.use_pass_z = False
        slave.view_layers = DummyViewLayers(unmatched_layer)

        render_sync_service.perform_sync(master, (master, slave))

        self.assertFalse(unmatched_layer.use_pass_z)


if __name__ == "__main__":
    unittest.main()
