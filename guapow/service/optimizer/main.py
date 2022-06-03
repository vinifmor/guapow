import asyncio
import getpass
import os
import time
from logging import getLogger
from typing import Tuple

from aiohttp import web

from guapow import __app_name__
from guapow.common.config import OptimizerConfig, read_optimizer_config
from guapow.common.dto import OptimizationRequest
from guapow.common.log import new_logger
from guapow.common.model_util import FileModelFiller
from guapow.service.optimizer import win_compositor, gpu
from guapow.service.optimizer.cpu import CPUFrequencyManager, get_cpu_count, CPUEnergyPolicyManager
from guapow.service.optimizer.flow import OptimizationQueue
from guapow.service.optimizer.gpu import GPUManager
from guapow.service.optimizer.handler import OptimizationHandler
from guapow.service.optimizer.mouse import MouseCursorManager
from guapow.service.optimizer.post_process.task import PostProcessTaskManager
from guapow.service.optimizer.profile import OptimizationProfile, OptimizationProfileReader, OptimizationProfileCache, \
    cache_profiles
from guapow.service.optimizer.task.manager import TasksManager, run_tasks
from guapow.service.optimizer.task.model import OptimizationContext, OptimizedProcess
from guapow.service.optimizer.watch import DeadProcessWatcherManager
from guapow.service.optimizer.web.application import create_web_app


def start():
    ti = time.time()
    app, opt_config = asyncio.get_event_loop().run_until_complete(prepare_app())
    tf = time.time()
    app.logger.info(f"Ready and attaching to port '{opt_config.port}' ({tf - ti:.4f} seconds)")
    web.run_app(port=opt_config.port, app=app, print=None)


async def prepare_app() -> Tuple[web.Application, OptimizerConfig]:
    getLogger('aiohttp.server').disabled = True

    is_service = OptimizerConfig.is_service()
    logger = new_logger(name=f'{__app_name__}-opt', service=is_service, enabled=OptimizerConfig.is_log_enabled(),
                        write_to_file=False, level=OptimizerConfig.get_log_level())
    user_id, user_name = os.getuid(), getpass.getuser()
    logger.debug(f"Initializing as user '{user_name}' (pid={os.getpid()})")

    model_filler = FileModelFiller(logger)
    opt_config = await read_optimizer_config(user_id=user_id, user_name=user_name, filler=model_filler, logger=logger)

    logger.info(f"Nice levels monitoring interval: {opt_config.renicer_interval} seconds")
    logger.info(f'Finished process checking interval: {opt_config.check_finished_interval} seconds')
    logger.info(f'Launcher mapping timeout: {opt_config.launcher_mapping_timeout} seconds')

    if not opt_config.gpu_cache:
        logger.warning("Available GPUs cache is disabled. Available GPUs will be mapped for every request")

    if opt_config.allow_root_scripts:
        logger.warning("Scripts are allowed to run at root level")

    if opt_config.profile_cache:
        logger.warning("Profile caching is enabled. Changes to files require restarting")

    compositor = None
    if opt_config.compositor:
        compositor = win_compositor.get_window_compositor_by_name(opt_config.compositor, logger)

        if compositor:
            logger.info(f'Predefined window compositor: {compositor.get_name()}')

    gpu_drivers = None

    if opt_config.gpu_vendor:
        gpu_driver = gpu.get_driver_by_vendor(opt_config.gpu_vendor)

        if gpu_driver:
            logger.info(f'Pre-defined GPU vendor: {opt_config.gpu_vendor}')
            gpu_drivers = [gpu_driver(cache=opt_config.gpu_cache, logger=logger)]
        else:
            logger.warning(f'Invalid pre-defined GPU vendor: {opt_config.gpu_vendor}')

    gpu_man = GPUManager(cache_gpus=opt_config.gpu_cache, logger=logger, drivers=gpu_drivers)

    cpu_count = get_cpu_count()
    cpufreq_man = CPUFrequencyManager(logger=logger, cpu_count=cpu_count)
    cpu_energy_man = CPUEnergyPolicyManager(logger=logger, cpu_count=cpu_count)
    context = OptimizationContext(cpufreq_man=cpufreq_man, gpu_man=gpu_man, logger=logger, cpu_count=cpu_count,
                                  compositor=compositor, allow_root_scripts=bool(opt_config.allow_root_scripts),
                                  launcher_mapping_timeout=opt_config.launcher_mapping_timeout,
                                  mouse_man=MouseCursorManager(logger), renicer_interval=opt_config.renicer_interval,
                                  cpuenergy_man=cpu_energy_man, queue=OptimizationQueue.empty())

    watcher_man = DeadProcessWatcherManager(context=context, restore_man=PostProcessTaskManager(context),
                                            check_interval=opt_config.check_finished_interval)

    tasks_man = TasksManager(context)
    await tasks_man.check_availability()

    opt_profile = OptimizationProfile.from_optimizer_config(opt_config)

    if opt_profile and opt_profile.is_valid():
        self_request = OptimizationRequest.self_request()
        self_request.prepare()

        available_init_tasks = await tasks_man.get_available_environment_tasks(OptimizedProcess(request=self_request, profile=opt_profile, created_at=time.time()))

        if available_init_tasks:
            fake_process = OptimizedProcess(request=self_request, profile=opt_profile, created_at=time.time())
            logger.debug("Waiting initial optimization tasks to complete")
            await asyncio.gather(*run_tasks(available_init_tasks, fake_process))
            logger.debug("Initial optimization tasks completed")
        else:
            logger.debug("No initial optimization tasks defined")
    else:
        logger.debug("No initial optimization tasks defined")

    profile_reader = OptimizationProfileReader(model_filler=model_filler,
                                               logger=context.logger,
                                               cache=OptimizationProfileCache(logger) if opt_config.profile_cache else None)

    if opt_config.profile_cache and opt_config.pre_cache_profiles:
        await cache_profiles(profile_reader, logger)

    handler = OptimizationHandler(context=context, tasks_man=tasks_man, watcher_man=watcher_man,
                                  profile_reader=profile_reader)
    return await create_web_app(handler=handler, queue=context.queue, config=opt_config, logger=logger), opt_config


if __name__ == '__main__':
    start()
