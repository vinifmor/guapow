from unittest import TestCase

from guapow.common import class_util
from guapow.common.model_util import FileModelPropertyMapper, StringPropertyMapper, IntPropertyMapper, \
    FloatPropertyMapper, BoolPropertyMapper, StringListPropertyMapper, IntListPropertyMapper, CustomEnumPropertyMapper, \
    DictPropertyMapper, StringSetPropertyMapper


class InstantiateSubclassesTest(TestCase):

    def test__must_instantiate_all_FileModelPropertyMapper_subclasses(self):
        subs = class_util.instantiate_subclasses(FileModelPropertyMapper)
        self.assertIsNotNone(subs)

        self.assertEqual(9, len(subs))

        for mtype in {StringPropertyMapper, IntPropertyMapper, FloatPropertyMapper, BoolPropertyMapper,
                      StringListPropertyMapper, IntListPropertyMapper, StringSetPropertyMapper, CustomEnumPropertyMapper, DictPropertyMapper}:
            instances = [s for s in subs if isinstance(s, mtype)]
            self.assertEqual(1, len(instances), f"Unexpected number of instances ({len(instances)}) found for {mtype.__name__}")
