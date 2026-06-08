import unittest

from services import scene_render_service


class DummyRender:
    def __init__(self, engine):
        self.engine = engine


class DummyCycles:
    def __init__(self):
        self.samples = 16
        self.preview_samples = 4
        self.adaptive_threshold = 0.1


class DummyScene:
    def __init__(self, name, engine):
        self.name = name
        self.render = DummyRender(engine)
        self.cycles = DummyCycles()


class SceneRenderServiceTests(unittest.TestCase):
    def test_apply_cycles_samples_updates_only_cycles_scenes(self):
        cycles_scene = DummyScene("Cycles", "CYCLES")
        eevee_scene = DummyScene("Eevee", "BLENDER_EEVEE_NEXT")

        result = scene_render_service.apply_cycles_samples(
            (cycles_scene, eevee_scene),
            render_samples=256,
            viewport_samples=32,
            adaptive_threshold=0.001,
        )

        self.assertEqual(result.updated_count, 1)
        self.assertEqual(result.skipped_count, 1)
        self.assertEqual(cycles_scene.cycles.samples, 256)
        self.assertEqual(cycles_scene.cycles.preview_samples, 32)
        self.assertEqual(cycles_scene.cycles.adaptive_threshold, 0.001)

    def test_apply_cycles_samples_rejects_invalid_values(self):
        with self.assertRaises(ValueError):
            scene_render_service.apply_cycles_samples(
                (),
                render_samples=0,
                viewport_samples=32,
                adaptive_threshold=0.001,
            )


if __name__ == "__main__":
    unittest.main()
