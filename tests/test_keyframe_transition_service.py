import unittest

from services import keyframe_transition_service


class DummyTarget:
    def __init__(self, **values):
        for key, value in values.items():
            setattr(self, key, value)
        self.keyframes = []

    def keyframe_insert(self, *, data_path, frame):
        self.keyframes.append((data_path, frame))


class DummyObject(DummyTarget):
    def __init__(self, name, data=None, **values):
        super().__init__(**values)
        self.name = name
        self.data = data


class DummyRule:
    def __init__(self, property_name, target_value, *, target_value_type="EXPRESSION"):
        self.property_name = property_name
        self.target_value = target_value
        self.target_value_type = target_value_type
        self.target_value_bool = False
        self.target_value_int = 0
        self.target_value_float = 0.0
        self.target_value_text = ""
        self.target_value_enum = ""
        self.target_value_vector_2 = (0.0, 0.0)
        self.target_value_vector_3 = (0.0, 0.0, 0.0)
        self.target_value_vector_4 = (0.0, 0.0, 0.0, 0.0)
        self.target_value_color_3 = (1.0, 1.0, 1.0)
        self.target_value_color_4 = (1.0, 1.0, 1.0, 1.0)

        if target_value_type == "BOOL":
            self.target_value_bool = bool(target_value)
        elif target_value_type == "INT":
            self.target_value_int = int(target_value)
        elif target_value_type == "FLOAT":
            self.target_value_float = float(target_value)
        elif target_value_type == "STRING":
            self.target_value_text = str(target_value)
        elif target_value_type == "ENUM":
            self.target_value_enum = str(target_value)
        elif target_value_type == "VECTOR_2":
            self.target_value_vector_2 = tuple(target_value)
        elif target_value_type == "VECTOR_3":
            self.target_value_vector_3 = tuple(target_value)
        elif target_value_type == "VECTOR_4":
            self.target_value_vector_4 = tuple(target_value)
        elif target_value_type == "COLOR_3":
            self.target_value_color_3 = tuple(target_value)
        elif target_value_type == "COLOR_4":
            self.target_value_color_4 = tuple(target_value)


class DummyDataBlock:
    def __init__(self, value_map):
        self.value_map = value_map

    def path_resolve(self, data_path):
        return self.value_map[data_path]


class KeyframeTransitionServiceTests(unittest.TestCase):
    def test_build_transition_rules_supports_per_property_values(self):
        rules = keyframe_transition_service.build_transition_rules(
            (
                DummyRule("hide_render", True, target_value_type="BOOL"),
                DummyRule("data.energy", 1000, target_value_type="INT"),
            )
        )

        self.assertEqual(rules[0].property_name, "hide_render")
        self.assertIs(rules[0].value, True)
        self.assertEqual(rules[1].property_name, "energy")
        self.assertEqual(rules[1].value, 1000)

    def test_parse_value_expression_supports_literals(self):
        self.assertIs(keyframe_transition_service.parse_value_expression("True"), True)
        self.assertEqual(
            keyframe_transition_service.parse_value_expression("(1, 0, 0)"),
            (1, 0, 0),
        )

    def test_extract_hovered_property_name_uses_identifier(self):
        class ButtonProp:
            identifier = "data.energy"

        self.assertEqual(
            keyframe_transition_service.extract_hovered_property_name(ButtonProp()),
            "energy",
        )

    def test_extract_hovered_property_name_supports_context_property_tuple(self):
        active_property = (DummyDataBlock({"hide_render": True}), "hide_render", -1)
        self.assertEqual(
            keyframe_transition_service.extract_hovered_property_name(
                button_prop=None,
                active_property=active_property,
            ),
            "hide_render",
        )

    def test_read_hovered_property_value_supports_context_property_tuple(self):
        active_property = (DummyDataBlock({"hide_render": True}), "hide_render", -1)
        self.assertIs(
            keyframe_transition_service.read_hovered_property_value(active_property),
            True,
        )

    def test_format_value_expression_handles_scalars_and_vectors(self):
        self.assertEqual(keyframe_transition_service.format_value_expression(True), "True")
        self.assertEqual(keyframe_transition_service.format_value_expression(1000), "1000")
        self.assertEqual(
            keyframe_transition_service.format_value_expression((1.0, 0.0, 0.5)),
            "(1.0, 0.0, 0.5)",
        )

    def test_keyframe_transition_restores_original_value(self):
        obj = DummyObject("Cube", hide_render=False)
        rules = (
            keyframe_transition_service.TransitionRule("hide_render", True),
        )

        result = keyframe_transition_service.keyframe_property_transition(
            (obj,),
            rules,
            current_frame=12,
            frame_offset=2,
        )

        self.assertEqual(result.object_count, 1)
        self.assertEqual(result.transition_count, 1)
        self.assertFalse(obj.hide_render)
        self.assertEqual(obj.keyframes, [("hide_render", 12), ("hide_render", 14)])

    def test_keyframe_transition_supports_multiple_rules_with_different_values(self):
        data = DummyTarget(energy=5)
        obj = DummyObject("Light", data=data, hide_render=False)
        rules = (
            keyframe_transition_service.TransitionRule("hide_render", True),
            keyframe_transition_service.TransitionRule("energy", 1000),
        )

        result = keyframe_transition_service.keyframe_property_transition(
            (obj,),
            rules,
            current_frame=8,
            frame_offset=3,
        )

        self.assertEqual(result.object_count, 1)
        self.assertEqual(result.transition_count, 2)
        self.assertFalse(obj.hide_render)
        self.assertEqual(obj.data.energy, 5)
        self.assertEqual(obj.keyframes, [("hide_render", 8), ("hide_render", 11)])
        self.assertEqual(obj.data.keyframes, [("energy", 8), ("energy", 11)])


if __name__ == "__main__":
    unittest.main()
