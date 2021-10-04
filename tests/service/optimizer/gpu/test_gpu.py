from unittest import TestCase

from guapow.service.optimizer.gpu import get_driver_by_vendor, NvidiaGPUDriver, AMDGPUDriver


class GetDriverByVendorTest(TestCase):

    def test__must_return_the_the_class_for_nvidia(self):
        cls_ = get_driver_by_vendor('  Nvidia ')
        self.assertEqual(NvidiaGPUDriver, cls_)

    def test__must_return_the_the_class_for_amd(self):
        cls_ = get_driver_by_vendor('  AMD ')
        self.assertEqual(AMDGPUDriver, cls_)

    def test__must_return_none_for_intel(self):
        cls_ = get_driver_by_vendor('  Intel ')
        self.assertIsNone(cls_)
