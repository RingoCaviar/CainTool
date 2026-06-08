import unittest

from services import batch_property_service


class DummyTarget:
    def __init__(self, **values):
        for key, value in values.items():
            setattr(self, key, value)


class DummyObject(DummyTarget):
    def __init__(self, name, data=None, **values):
        super().__init__(**values)
        self.name = name
        self.data = data


class BatchPropertyServiceTests(unittest.TestCase):
    def test_parse_value_expression_supports_literals_and_strings(self):
        self.assertEqual(batch_property_service.parse_value_expression("1000"), 1000)
        self.assertEqual(
            batch_property_service.parse_value_expression("(1, 0, 0)"),
            (1, 0, 0),
        )
        self.assertIs(batch_property_service.parse_value_expression("True"), True)
        self.assertIs(batch_property_service.parse_value_expression("False"), False)
        self.assertEqual(batch_property_service.parse_value_expression("energy"), "energy")

    def test_parse_value_expression_rejects_empty_value(self):
        with self.assertRaises(ValueError):
            batch_property_service.parse_value_expression("   ")

    def test_batch_set_property_prefers_existing_targets(self):
        light_data = DummyTarget(energy=5)
        light = DummyObject("Light", data=light_data)
        mesh = DummyObject("Cube", hide_render=False)

        result = batch_property_service.batch_set_property((light, mesh), "hide_render", True)

        self.assertEqual(result.changed_count, 1)
        self.assertTrue(mesh.hide_render)
        self.assertEqual(result.skipped_count, 1)

    def test_batch_set_property_updates_data_and_object_when_available(self):
        data = DummyTarget(energy=10)
        obj = DummyObject("Lamp", data=data, energy=20)

        result = batch_property_service.batch_set_property((obj,), "energy", 1000)

        self.assertEqual(result.changed_count, 1)
        self.assertEqual(obj.energy, 1000)
        self.assertEqual(obj.data.energy, 1000)

    def test_batch_set_property_coerces_string_bool_for_boolean_targets(self):
        obj = DummyObject("Cube", hide_render=False)

        result = batch_property_service.batch_set_property((obj,), "hide_render", "True")

        self.assertEqual(result.changed_count, 1)
        self.assertIs(obj.hide_render, True)

    def test_batch_set_property_supports_vector_values(self):
        obj = DummyObject("Cube", location=(0.0, 0.0, 0.0))

        result = batch_property_service.batch_set_property((obj,), "location", (1.0, 2.0, 3.0))

        self.assertEqual(result.changed_count, 1)
        self.assertEqual(obj.location, (1.0, 2.0, 3.0))


if __name__ == "__main__":
    unittest.main()
