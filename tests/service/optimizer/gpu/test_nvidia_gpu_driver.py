from unittest import IsolatedAsyncioTestCase
from unittest.mock import Mock, patch, call

from guapow import __app_name__
from guapow.service.optimizer.gpu import NvidiaGPUDriver, GPUPowerMode


class NvidiaGPUDriverTest(IsolatedAsyncioTestCase):

    @patch(f'{__app_name__}.service.optimizer.gpu.shutil.which', return_value='')
    def test_can_work__false_when_nvidia_settings_is_not_installed(self, which: Mock):
        driver = NvidiaGPUDriver(cache=False, logger=Mock())
        can_work, msg = driver.can_work()
        self.assertEqual(False, can_work)
        self.assertIsInstance(msg, str)
        which.assert_called_once_with('nvidia-settings')

    @patch(f'{__app_name__}.service.optimizer.gpu.shutil.which', side_effect=['nvidia-settings', ''])
    def test_can_work__false_when_nvidia_smi_is_not_installed(self, which: Mock):
        driver = NvidiaGPUDriver(cache=False, logger=Mock())
        can_work, msg = driver.can_work()
        self.assertEqual(False, can_work)
        self.assertIsInstance(msg, str)
        which.assert_has_calls([call('nvidia-settings'), call('nvidia-smi')])

    @patch(f'{__app_name__}.service.optimizer.gpu.shutil.which', side_effect=['nvidia-settings', 'nvidia-smi'])
    def test_can_work__true_when_nvidia_settings_and_smi_are_not_installed(self, which: Mock):
        driver = NvidiaGPUDriver(cache=False, logger=Mock())
        can_work, msg = driver.can_work()
        self.assertEqual(True, can_work)
        self.assertIsNone(msg)
        which.assert_has_calls([call('nvidia-settings'), call('nvidia-smi')])

    @patch(f'{__app_name__}.service.optimizer.gpu.system.async_syscall', return_value=(0, '0 \n 1 '))
    async def test_get_gpus__must_call_nvidia_smi_to_list_available_gpu_indexes(self, async_syscall: Mock):
        driver = NvidiaGPUDriver(cache=False, logger=Mock())
        self.assertEqual({'0', '1'}, await driver.get_gpus())
        async_syscall.assert_called_once_with('nvidia-smi --query-gpu=index --format=csv,noheader')

    @patch(f'{__app_name__}.service.optimizer.gpu.system.async_syscall', return_value=(1, '0 \n 1 '))
    async def test_get_gpus__must_return_empty_set_when_exitcode_is_not_zero(self, async_syscall: Mock):
        driver = NvidiaGPUDriver(cache=False, logger=Mock())
        self.assertEqual(set(), await driver.get_gpus())
        async_syscall.assert_called_once()

    @patch(f'{__app_name__}.service.optimizer.gpu.system.async_syscall', return_value=(0, ''))
    async def test_get_gpus__must_return_empty_set_when_no_output(self, async_syscall: Mock):
        driver = NvidiaGPUDriver(cache=False, logger=Mock())
        self.assertEqual(set(), await driver.get_gpus())
        async_syscall.assert_called_once()

    @patch(f'{__app_name__}.service.optimizer.gpu.system.async_syscall', return_value=(0, "Attribute 'GPUPowerMizerMode' (user:0[gpu:0]): 2.\nAttribute 'GPUPowerMizerMode' (user:0[gpu:1]): 1.\nAttribute 'GPUPowerMizerMode' (user:0[gpu:2]): 0 "))
    async def test_get_power_mode__return_modes_from_nvidia_settings_query_for_defined_ids(self, async_syscall: Mock):
        driver = NvidiaGPUDriver(cache=False, logger=Mock())
        self.assertEqual({'0': GPUPowerMode.AUTO,
                          '1': GPUPowerMode.PERFORMANCE}, await driver.get_power_mode({'0', '1'}))  # gpu '2' mode must not be returned
        async_syscall.assert_called_once()
        self.assertTrue(async_syscall.call_args.args[0].startswith('nvidia-settings '))
        self.assertIn(' -q [gpu:0]/GpuPowerMizerMode', async_syscall.call_args.args[0])
        self.assertIn(' -q [gpu:1]/GpuPowerMizerMode', async_syscall.call_args.args[0])

    @patch(f'{__app_name__}.service.optimizer.gpu.system.async_syscall', return_value=(1, "Attribute 'GPUPowerMizerMode' (user:0[gpu:0]): 2.\nAttribute 'GPUPowerMizerMode' (user:0[gpu:1]): 1."))
    async def test_get_power_mode__return_none_when_exitcode_nonzero(self, async_syscall: Mock):
        driver = NvidiaGPUDriver(cache=False, logger=Mock())
        self.assertIsNone(await driver.get_power_mode({'0', '1'}))
        async_syscall.assert_called_once()

    @patch(f'{__app_name__}.service.optimizer.gpu.system.async_syscall', return_value=(0, "Attribute 'GPUPowerMizerMode' (user:0[gpu:0]) assigned value 1.\nAttribute 'GPUPowerMizerMode' (user:0[gpu:1]) assigned value 0.\nAttribute 'GPUPowerMizerMode' (user:0[gpu:2]) assigned value 2."))
    async def test_set_power_mode__must_change_defined_gpus_to_defined_mode(self, async_syscall: Mock):
        driver = NvidiaGPUDriver(cache=False, logger=Mock())

        env = {'TEST': 1, 'LANG': 'fr.UTF-8'}
        res = await driver.set_power_mode({'0': GPUPowerMode.PERFORMANCE, '1': GPUPowerMode.ON_DEMAND}, user_environment=env)
        self.assertEqual({'0': True, '1': True}, res)
        async_syscall.assert_called_once()
        self.assertTrue(async_syscall.call_args.args[0].startswith('nvidia-settings '))
        self.assertIn('custom_env', async_syscall.call_args.kwargs)
        self.assertIn(f' -a [gpu:0]/GpuPowerMizerMode={GPUPowerMode.PERFORMANCE.value}', async_syscall.call_args.args[0])
        self.assertIn(f' -a [gpu:1]/GpuPowerMizerMode={GPUPowerMode.ON_DEMAND.value}', async_syscall.call_args.args[0])
        self.assertEqual({**env, 'LANG': 'en_US.UTF-8'}, async_syscall.call_args.kwargs['custom_env'])

    @patch(f'{__app_name__}.service.optimizer.gpu.system.async_syscall', return_value=(0, "Attribute 'GPUPowerMizerMode' (user:0[gpu:0]) assigned value 1.\nAttribute 'GPUPowerMizerMode' (user:0[gpu:1]) assigned value 0."))
    async def test_set_power_mode__return_not_changed_gpu_mode_as_a_false_value(self, async_syscall: Mock):
        driver = NvidiaGPUDriver(cache=False, logger=Mock())

        res = await driver.set_power_mode({'0': GPUPowerMode.PERFORMANCE, '1': GPUPowerMode.PERFORMANCE})
        self.assertEqual({'0': True, '1': False}, res)
        async_syscall.assert_called_once()

    @patch(f'{__app_name__}.service.optimizer.gpu.system.async_syscall', return_value=(1, "error"))
    async def test_set_power_mode__return_false_for_all_gpus_when_unknown_output(self, async_syscall: Mock):
        driver = NvidiaGPUDriver(cache=False, logger=Mock())

        res = await driver.set_power_mode({'0': GPUPowerMode.PERFORMANCE, '1': GPUPowerMode.PERFORMANCE})
        self.assertEqual({'0': False, '1': False}, res)
        async_syscall.assert_called_once()

    @patch(f'{__app_name__}.service.optimizer.gpu.system.async_syscall', return_value=(1, ""))
    async def test_set_power_mode__return_false_for_all_gpus_when_empty_output(self, async_syscall: Mock):
        driver = NvidiaGPUDriver(cache=False, logger=Mock())

        res = await driver.set_power_mode({'0': GPUPowerMode.PERFORMANCE, '1': GPUPowerMode.PERFORMANCE})
        self.assertEqual({'0': False, '1': False}, res)
        async_syscall.assert_called_once()

    @patch(f'{__app_name__}.service.optimizer.gpu.system.async_syscall', return_value=(1, ""))
    async def test_set_power_mode__must_call_nvidia_settings_with_english_as_default_language_when_no_user_env_is_defined(self, async_syscall: Mock):
        driver = NvidiaGPUDriver(cache=False, logger=Mock())

        await driver.set_power_mode({'0': GPUPowerMode.PERFORMANCE, '1': GPUPowerMode.ON_DEMAND}, user_environment=None)
        self.assertTrue(async_syscall.call_args.args[0].startswith('nvidia-settings '))
        self.assertIn('custom_env', async_syscall.call_args.kwargs)
        self.assertIn(f' -a [gpu:0]/GpuPowerMizerMode={GPUPowerMode.PERFORMANCE.value}', async_syscall.call_args.args[0])
        self.assertIn(f' -a [gpu:1]/GpuPowerMizerMode={GPUPowerMode.ON_DEMAND.value}', async_syscall.call_args.args[0])
        self.assertEqual({'LANG': 'en_US.UTF-8'}, async_syscall.call_args.kwargs['custom_env'])
