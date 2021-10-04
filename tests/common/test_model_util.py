from typing import Optional, Set, Dict, Tuple
from unittest import TestCase
from unittest.mock import Mock

from guapow.common.model import FileModel
from guapow.common.model_util import FileModelFiller


class SinglePropDefTestModel(FileModel):

    MAPPING = {
        'ids': ('ids', Set[str], None),
        'name': ('name', str, None),
        'check': ('check', bool, None),
        'only': ('only', bool, True),
        'color': ('color', str, 'red'),
        'integer': ('integer', int, 0),
        'float_point': ('float_point', float, 0.1)
    }

    def __init__(self, name: str = 'test', ids: Optional[Set[str]] = None, check: bool = False, only: bool = False,
                 color: Optional[str] = None, integer: Optional[int] = None, float_point: Optional[float] = None):
        self.name = name
        self.ids = ids
        self.check = check
        self.only = only
        self.color = color
        self.integer = integer
        self.float_point = float_point

    def get_file_mapping(self) -> Dict[str, Tuple[str, type, Optional[object]]]:
        return self.MAPPING

    def is_valid(self) -> bool:
        return any([self.name, self.ids])

    def get_file_root_node_name(self) -> Optional[str]:
        pass


class FileModelFillerTest(TestCase):

    def setUp(self):
        self.filler = FileModelFiller(Mock())

    def test_fill__must_not_set_single_property_definitions_with_none_as_default_value(self):
        model = SinglePropDefTestModel()

        self.assertEqual('test', model.name)
        self.assertIsNone(model.ids)
        self.assertEqual(False, model.check)

        self.filler.fill(root=model, file_content='name\nids\ncheck')

        # nothing changed
        self.assertEqual('test', model.name)
        self.assertIsNone(model.ids)
        self.assertEqual(False, model.check)

    def test_fill__must_set_single_property_definitions_with_not_none_default_values(self):
        model = SinglePropDefTestModel()

        self.assertEqual(False, model.only)
        self.assertIsNone(model.color)
        self.assertIsNone(model.integer)
        self.assertIsNone(model.float_point)

        self.filler.fill(root=model, file_content='only\ncolor\ninteger\nfloat_point')

        # nothing changed
        self.assertEqual(True, model.only)
        self.assertEqual('red', model.color)
        self.assertEqual(0, model.integer)
        self.assertEqual(0.1, model.float_point)
