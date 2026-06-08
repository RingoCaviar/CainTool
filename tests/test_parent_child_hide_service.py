import unittest

from services import parent_child_hide_service


class DummyObject:
    def __init__(self, name, parent=None):
        self.name = name
        self.parent = parent
        self.children = []
        self._props = {}
        self._hide_eye = False
        self.hide_viewport = False
        self.hide_render = False
        self.hide_select = False
        if parent is not None:
            parent.children.append(self)

    @property
    def children_recursive(self):
        items = []
        for child in self.children:
            items.append(child)
            items.extend(child.children_recursive)
        return items

    def hide_get(self, *, view_layer):
        del view_layer
        return self._hide_eye

    def hide_set(self, value, *, view_layer):
        del view_layer
        self._hide_eye = value

    def get(self, key, default=None):
        return self._props.get(key, default)

    def __setitem__(self, key, value):
        self._props[key] = value


class ParentChildHideServiceTests(unittest.TestCase):
    def test_selected_roots_skips_children_of_selected_parent(self):
        root = DummyObject("Root")
        child = DummyObject("Child", parent=root)

        roots = parent_child_hide_service.selected_roots((root, child))

        self.assertEqual(roots, [root])

    def test_hide_selected_hierarchies_hides_parent_and_children(self):
        root = DummyObject("Root")
        child = DummyObject("Child", parent=root)
        grandchild = DummyObject("GrandChild", parent=child)

        result = parent_child_hide_service.hide_selected_hierarchies(
            (root,),
            view_layer=object(),
            include_render=True,
            include_select=True,
        )

        self.assertEqual(result.root_count, 1)
        self.assertEqual(result.hidden_count, 3)
        self.assertTrue(root.hide_get(view_layer=object()))
        self.assertTrue(child.hide_render)
        self.assertTrue(grandchild.hide_select)

    def test_restore_hierarchy_snapshot_restores_original_state(self):
        root = DummyObject("Root")
        child = DummyObject("Child", parent=root)
        child.hide_render = True

        result = parent_child_hide_service.hide_selected_hierarchies(
            (root,),
            view_layer=object(),
            include_render=True,
            include_select=False,
        )

        root.hide_set(False, view_layer=object())
        root.hide_viewport = False
        root.hide_render = False
        child.hide_set(False, view_layer=object())
        child.hide_viewport = False
        child.hide_render = False

        restored_count = parent_child_hide_service.restore_hierarchy_snapshot(
            result.snapshots[0].data,
            (root, child),
            view_layer=object(),
        )

        self.assertEqual(restored_count, 2)
        self.assertFalse(root.hide_get(view_layer=object()))
        self.assertFalse(root.hide_viewport)
        self.assertTrue(child.hide_render)


if __name__ == "__main__":
    unittest.main()
