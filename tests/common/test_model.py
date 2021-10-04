from unittest import TestCase

from guapow.service.optimizer.profile import OptimizationProfile, CPUSettings, ProcessSettings, IOScheduling, \
    IOSchedulingClass


class FileModelTest(TestCase):

    def test_to_file_str__must_consider_inner_models(self):
        test = OptimizationProfile.empty('test')
        test.cpu = CPUSettings(performance=True)
        test.process = ProcessSettings(None)
        test.process.nice.level = -4
        test.process.nice.delay = 5
        test.process.nice.watch = True
        test.process.io = IOScheduling(ioclass=IOSchedulingClass.BEST_EFFORT, nice_level=0)

        exp_string = 'cpu.performance=true\nproc.io.class=best_effort\nproc.io.nice=0\nproc.nice=-4\nproc.nice.delay=5\nproc.nice.watch=true\n'
        self.assertEqual(exp_string, test.to_file_str())
