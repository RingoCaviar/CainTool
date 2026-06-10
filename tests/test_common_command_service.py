import unittest

from services import common_command_service


class DummyObject:
    def __init__(
        self,
        name,
        animation_data=None,
        *,
        data=None,
        clear_raises=None,
        **attributes,
    ):
        self.name = name
        self.animation_data = animation_data
        self.data = data
        self.clear_raises = clear_raises
        self.clear_count = 0
        self.update_count = 0
        for key, value in attributes.items():
            setattr(self, key, value)

    def animation_data_clear(self):
        if self.clear_raises is not None:
            raise self.clear_raises
        self.animation_data = None
        self.clear_count += 1

    def update_tag(self):
        self.update_count += 1


class ClearObjectAnimationDataTests(unittest.TestCase):
    def test_clear_object_animation_data_clears_animated_objects(self):
        animated = DummyObject("Cube", animation_data=object())
        static = DummyObject("Light")

        result = common_command_service.clear_object_animation_data((animated, static))

        self.assertEqual(result.cleared_count, 1)
        self.assertIsNone(animated.animation_data)
        self.assertEqual(animated.clear_count, 1)
        self.assertEqual(animated.update_count, 1)
        self.assertEqual(result.skipped_count, 1)
        self.assertEqual(result.skipped[0], "Light: 没有动画数据")

    def test_clear_object_animation_data_clears_object_data_animation(self):
        light_data = DummyObject("LightData", animation_data=object())
        light = DummyObject("Light", data=light_data)

        result = common_command_service.clear_object_animation_data((light,))

        self.assertEqual(result.cleared_count, 1)
        self.assertEqual(result.object_count, 1)
        self.assertIsNone(light_data.animation_data)
        self.assertEqual(light_data.clear_count, 1)
        self.assertEqual(light_data.update_count, 1)
        self.assertEqual(result.skipped_count, 0)

    def test_clear_object_animation_data_clears_shape_key_animation(self):
        shape_keys = DummyObject("Key", animation_data=object())
        mesh_data = DummyObject("Mesh", shape_keys=shape_keys)
        mesh = DummyObject("Cube", data=mesh_data)

        result = common_command_service.clear_object_animation_data((mesh,))

        self.assertEqual(result.cleared_count, 1)
        self.assertEqual(result.object_count, 1)
        self.assertIsNone(shape_keys.animation_data)
        self.assertEqual(shape_keys.clear_count, 1)
        self.assertEqual(shape_keys.update_count, 1)

    def test_clear_object_animation_data_clears_shared_data_once(self):
        shared_data = DummyObject("SharedLightData", animation_data=object())
        first = DummyObject("Light_A", data=shared_data)
        second = DummyObject("Light_B", data=shared_data)

        result = common_command_service.clear_object_animation_data((first, second))

        self.assertEqual(result.cleared_count, 1)
        self.assertEqual(result.object_count, 2)
        self.assertEqual(shared_data.clear_count, 1)
        self.assertEqual(shared_data.update_count, 1)
        self.assertEqual(result.skipped, [])

    def test_clear_object_animation_data_reports_clear_failures(self):
        obj = DummyObject(
            "Cube",
            animation_data=object(),
            clear_raises=RuntimeError("locked"),
        )

        result = common_command_service.clear_object_animation_data((obj,))

        self.assertEqual(result.cleared_count, 0)
        self.assertEqual(obj.update_count, 0)
        self.assertEqual(result.skipped, ["Cube: locked"])


if __name__ == "__main__":
    unittest.main()
