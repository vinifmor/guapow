import asyncio
import getpass
import os
import sys
import time
from subprocess import Popen

from guapow import __app_name__
from guapow.common import network
from guapow.common.auth import read_machine_id
from guapow.common.config import read_optimizer_config
from guapow.common.dto import OptimizationRequest
from guapow.common.log import new_logger
from guapow.common.model_util import FileModelFiller
from guapow.runner.profile import RunnerProfileReader
from guapow.runner.settings import is_log_enabled, read_valid_full_config, read_additional_profile_config, \
    InvalidConfigurationException, is_file_log
from guapow.runner.task import RunnerTaskManager, RunnerContext


def run():
    asyncio.get_event_loop().run_until_complete(launch_process())


async def launch_process():
    lti = time.time()
    if len(sys.argv) < 2:
        sys.stderr.write('Command not informed. Aborting...\n')
        exit(1)
    else:
        user_id, user_name, profile = os.getuid(), getpass.getuser(), os.getenv('GUAPOW_PROFILE')
        log_to_file = is_file_log()
        logger = new_logger(name=__app_name__, service=False, enabled=log_to_file or is_log_enabled(),
                            write_to_file=log_to_file, threaded=False)

        try:
            config_str, profile_config_str = read_valid_full_config(logger), None
        except InvalidConfigurationException:
            return exit(1)

        model_filler = FileModelFiller(logger)
        profile_reader = RunnerProfileReader(model_filler, logger)

        if config_str:
            runner_profile = profile_reader.map_valid_config(config=config_str)
        else:
            profile_config_str = read_additional_profile_config(logger)
            runner_profile = await profile_reader.read_available(user_id=user_id, user_name=user_name, profile=profile, add_settings=profile_config_str)

        context, extra_proc_args = None, {}

        if runner_profile:
            context = RunnerContext(logger=logger, processes_initialized=set(), environment_variables={}, stopped_processes={})
            await RunnerTaskManager(context).run(runner_profile)
            extra_proc_args.update(context.get_process_extra_arguments())

        cmd_str = ' '.join(sys.argv[1:])
        logger.info(f'Launching command: {cmd_str}')

        try:
            proc = Popen(sys.argv[1:], **extra_proc_args)
        except OSError as e:
            sys.stderr.write(f"An error occurred when launching: {' '.join(sys.argv[1:])}\n")
            sys.stderr.write(str(e))
            return exit(1)

        ltf = time.time()
        logger.info(f'Launch time: {ltf - lti:.4f} seconds')

        common_attrs = {'pid': proc.pid, 'command': cmd_str, 'user_name': user_name, 'created_at': time.time(),
                        'user_env': extra_proc_args['env'] if extra_proc_args and extra_proc_args['env'] else dict(os.environ)}

        if context:
            if context.processes_initialized:
                common_attrs['related_pids'] = context.processes_initialized

            if context.stopped_processes:
                common_attrs['stopped_processes'] = context.stopped_processes

                if runner_profile.stop.relaunch:
                    common_attrs['relaunch_stopped_processes'] = True

        if config_str:
            request = OptimizationRequest.new_from_config(config=config_str, **common_attrs)
        else:
            request = OptimizationRequest.new_from_profile(profile=profile, profile_config=profile_config_str, **common_attrs)

        opt_config = await read_optimizer_config(user_id=user_id, user_name=user_name, logger=logger,
                                                 filler=model_filler, only_properties={'port', 'request.encrypted'})

        if not opt_config:
            logger.warning("Invalid Optimizer config. It will not be possible to send the request")
            exit(1)

        machine_id = await read_machine_id() if opt_config.encrypted_requests else None

        if not machine_id:
            logger.warning("Encryption is disabled")

        await network.send(request=request, opt_config=opt_config, machine_id=machine_id, logger=logger)


if __name__ == '__main__':
    run()
