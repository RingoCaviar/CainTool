import unittest

from services import value_input_service


class DummyHolder:
    def __init__(self):
        self.batch_property_value_type = value_input_service.VALUE_TYPE_EXPRESSION
        self.batch_property_value = "0"
        self.batch_property_value_bool = False
        self.batch_property_value_int = 0
        self.batch_property_value_float = 0.0
        self.batch_property_value_text = ""
        self.batch_property_value_enum = ""
        self.batch_property_value_vector_2 = (0.0, 0.0)
        self.batch_property_value_vector_3 = (0.0, 0.0, 0.0)
        self.batch_property_value_vector_4 = (0.0, 0.0, 0.0, 0.0)
        self.batch_property_value_color_3 = (1.0, 1.0, 1.0)
        self.batch_property_value_color_4 = (1.0, 1.0, 1.0, 1.0)


class DummyButtonProp:
    def __init__(self, prop_type="", subtype="", array_length=0):
        self.type = prop_type
        self.subtype = subtype
        self.array_length = array_length


class ValueInputServiceTests(unittest.TestCase):
    def test_assign_value_to_holder_detects_bool(self):
        holder = DummyHolder()

        value_type = value_input_service.assign_value_to_holder(
            holder,
            "batch_property_value",
            True,
        )

        self.assertEqual(value_type, value_input_service.VALUE_TYPE_BOOL)
        self.assertEqual(holder.batch_property_value_type, value_input_service.VALUE_TYPE_BOOL)
        self.assertTrue(holder.batch_property_value_bool)

    def test_assign_value_to_holder_uses_button_prop_for_enum(self):
        holder = DummyHolder()
        button_prop = DummyButtonProp(prop_type="ENUM")

        value_type = value_input_service.assign_value_to_holder(
            holder,
            "batch_property_value",
            "RENDERED",
            button_prop=button_prop,
        )

        self.assertEqual(value_type, value_input_service.VALUE_TYPE_ENUM)
        self.assertEqual(holder.batch_property_value_enum, "RENDERED")

    def test_read_value_from_holder_reads_vector_mode(self):
        holder = DummyHolder()
        holder.batch_property_value_type = value_input_service.VALUE_TYPE_VECTOR_3
        holder.batch_property_value_vector_3 = (1.0, 2.0, 3.0)

        value = value_input_service.read_value_from_holder(holder, "batch_property_value")

        self.assertEqual(value, (1.0, 2.0, 3.0))

    def test_read_value_from_holder_keeps_expression_mode(self):
        holder = DummyHolder()
        holder.batch_property_value_type = value_input_service.VALUE_TYPE_EXPRESSION
        holder.batch_property_value = "False"

        value = value_input_service.read_value_from_holder(holder, "batch_property_value")

        self.assertIs(value, False)


if __name__ == "__main__":
    unittest.main()
