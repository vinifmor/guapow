from guapow import __app_name__
from guapow.cli import args
from guapow.cli.commands import map_commands
from guapow.common.log import new_logger


def run():
    logger = new_logger(f'{__app_name__}-cli', service=True, enabled=True, write_to_file=False, threaded=False)
    cmds = map_commands(logger)
    current_args = args.read(cmds.values())

    selected_cmd = cmds.get(current_args.command)
    if selected_cmd:
        if not selected_cmd.run(current_args):
            exit(1)
    else:
        logger.error("No command to execute")
        exit(1)


if __name__ == '__main__':
    run()
