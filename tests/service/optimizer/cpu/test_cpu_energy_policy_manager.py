import os.path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import Mock

from guapow.service.optimizer.cpu import CPUEnergyPolicyManager
from tests import RESOURCES_DIR

TEMP_EPB_FILE_PATTERN = RESOURCES_DIR + '/cpu{idx}_ep'


class CPUEnergyPolicyManagerTest(IsolatedAsyncioTestCase):

    def tearDown(self):
        for idx in range(2):
            file_path = TEMP_EPB_FILE_PATTERN.format(idx=idx)
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except OSError:
                    print(f"[error] could not remove file: {file_path}")

    def test_can_work__false_when_no_cpus(self):
        man = CPUEnergyPolicyManager(cpu_count=0, logger=Mock())
        res, msg = man.can_work()
        self.assertFalse(res)
        self.assertIsInstance(msg, str)

    def test_can_work__false_when_no_file(self):
        man = CPUEnergyPolicyManager(cpu_count=1, logger=Mock(), file_pattern=RESOURCES_DIR + '/epb_{idx}.txt')
        res, msg = man.can_work()
        self.assertFalse(res)
        self.assertIsInstance(msg, str)

    def test_can_work__true_when_cpu_count_higher_than_zero_and_existing_file(self):
        with open(TEMP_EPB_FILE_PATTERN.format(idx=0), 'w+') as f:
            f.write('6')

        man = CPUEnergyPolicyManager(cpu_count=1, logger=Mock(), file_pattern=TEMP_EPB_FILE_PATTERN)
        res, msg = man.can_work()
        self.assertTrue(res)
        self.assertIsNone(msg)

    async def test_map_current_state(self):
        for idx, state in enumerate((5, 3)):
            with open(TEMP_EPB_FILE_PATTERN.format(idx=idx), 'w+') as f:
                f.write(str(state))

        man = CPUEnergyPolicyManager(cpu_count=2, logger=Mock(), file_pattern=TEMP_EPB_FILE_PATTERN)
        res = await man.map_current_state()
        self.assertEqual({0: 5, 1: 3}, res)

    async def test_change_states(self):
        for idx in range(2):
            with open(TEMP_EPB_FILE_PATTERN.format(idx=idx), 'w+') as f:
                f.write('6')

        man = CPUEnergyPolicyManager(cpu_count=2, logger=Mock(), file_pattern=TEMP_EPB_FILE_PATTERN)
        changes = {0: 3, 1: 9}
        res = await man.change_states(changes)

        self.assertEqual({0: True, 1: True}, res)

        for idx in range(2):
            with open(TEMP_EPB_FILE_PATTERN.format(idx=idx)) as f:
                state = f.read()

            self.assertEqual(changes[idx], int(state))

    def test_save_state(self):
        man = CPUEnergyPolicyManager(cpu_count=2, logger=Mock())
        state = {0: 4, 1: 9}
        man.save_state(state)
        self.assertEqual(state, man.saved_state)

    def test_save_state__must_no_update_the_value_of_existing_keys(self):
        man = CPUEnergyPolicyManager(cpu_count=2, logger=Mock())
        man.save_state({0: 4, 1: 9})
        man.save_state({0: 7, 1: 3, 2: 8})
        self.assertEqual({0: 4, 1: 9, 2: 8}, man.saved_state)

    def test_clear_state__must_remove_all_saved_entries_if_no_key_defined(self):
        man = CPUEnergyPolicyManager(cpu_count=2, logger=Mock())
        state = {0: 4, 1: 9}
        man.save_state(state)
        man.clear_state()
        self.assertEqual(dict(), man.saved_state)

    def test_clear_state__must_remove_defined_existing_keys(self):
        man = CPUEnergyPolicyManager(cpu_count=2, logger=Mock())
        state = {0: 4, 1: 9, 2: 6}
        man.save_state(state)
        man.clear_state(1, 3)  # 3 does not exist
        self.assertEqual({0: 4, 2: 6}, man.saved_state)
