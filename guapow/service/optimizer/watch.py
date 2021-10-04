import asyncio
from asyncio import Lock
from copy import deepcopy
from typing import Optional, List, Set, Dict

from guapow.common import system
from guapow.service.optimizer.post_process.context import PostProcessContext, PostProcessContextMapper
from guapow.service.optimizer.post_process.summary import GeneralPostProcessSummarizer
from guapow.service.optimizer.post_process.task import PostProcessTaskManager
from guapow.service.optimizer.task.model import OptimizedProcess, OptimizationContext


class DeadProcessWatcher:

    def __init__(self, context: OptimizationContext, restore_man: PostProcessTaskManager, check_interval: int, to_watch: Optional[List[OptimizedProcess]] = None,
                 to_relaunch: Optional[Dict[str, str]] = None):
        self._context = context
        self._check_interval = check_interval
        self._restore_man = restore_man
        self._log = context.logger
        self._to_watch = to_watch
        self._lock_to_watch = Lock()
        self._watching = False
        self._lock_watching = Lock()
        self._to_relaunch = to_relaunch

        if self._to_watch:
            for p in self._to_watch:
                self._register_post_commands_to_relaunch(p)

    def _update_to_relaunch(self, commands: Dict[str, str]):
        for comm, cmd in commands.items():
            cached_cmd = self._to_relaunch.get(comm)

            if not cached_cmd or not cached_cmd.startswith('/'):
                self._to_relaunch[comm] = cmd

    def _register_post_commands_to_relaunch(self, process: OptimizedProcess):
        if process.stopped_processes and process.relaunch_stopped_processes:
            self._update_to_relaunch(process.stopped_processes)

        if process.stopped_after_launch and process.relaunch_stopped_after_launch:
            self._update_to_relaunch(process.stopped_after_launch)

    async def watch(self, process: OptimizedProcess):
        async with self._lock_to_watch:
            if self._to_watch is None:
                self._to_watch = []

            self._to_watch.append(process)
            self._log.debug(f"Watching a new process '{process.pid}' ({len(self._to_watch)} now)")
            self._register_post_commands_to_relaunch(process)

    async def map_context(self) -> PostProcessContext:
        post_summary = await GeneralPostProcessSummarizer.instance().summarize(processes=self._to_watch,
                                                                               pids_alive=system.read_current_pids(),
                                                                               processes_to_relaunch=self._to_relaunch,
                                                                               context=self._context)

        if post_summary.dead_pids:
            await self._context.queue.remove_pids(*(data[1] for data in post_summary.dead_pids))

            dead_pids = sorted(post_summary.dead_pids)
            for idx, data in enumerate(dead_pids):
                del self._to_watch[data[0] - idx]

            self._log.debug(f"{len(dead_pids)} process(es) stopped: {', '.join((str(p[1]) for p in dead_pids))}")

        context = PostProcessContextMapper.instance().map(post_summary)

        if self._to_relaunch:  # cleaning up commands that will be relaunched
            if context.stopped_processes:
                for comm_cmd in context.stopped_processes:
                    if comm_cmd[0] in self._to_relaunch:
                        del self._to_relaunch[comm_cmd[0]]

            if context.not_stopped_processes:
                for comm in context.not_stopped_processes:
                    if comm in self._to_relaunch:
                        del self._to_relaunch[comm]

        return context

    async def start_watching(self):
        async with self._lock_watching:
            self._watching = True

        while True:
            async with self._lock_to_watch:
                context = await self.map_context()

            restore_tasks = self._restore_man.create_tasks(context)

            if restore_tasks:
                await asyncio.gather(*restore_tasks)

            async with self._lock_to_watch:
                if not self._to_watch:
                    break

            await asyncio.sleep(self._check_interval)

        async with self._lock_watching:
            self._watching = False

        self._log.debug("No processes to watch. Stopped watching.")

    async def is_watching(self) -> bool:
        async with self._lock_watching:
            return self._watching

    async def get_watched_pids(self) -> Optional[Set[int]]:
        if self._to_watch:
            async with self._lock_to_watch:
                return {p.pid for p in self._to_watch}

    def get_to_relaunch_view(self) -> Optional[Dict[str, str]]:
        if self._to_relaunch is not None:
            return deepcopy(self._to_relaunch)


class DeadProcessWatcherManager:

    def __init__(self, check_interval: int, restore_man: PostProcessTaskManager, context: OptimizationContext):
        self._watcher = DeadProcessWatcher(context=context, check_interval=check_interval, restore_man=restore_man, to_relaunch={})

    async def watch(self, process: OptimizedProcess):
        if process:
            await self._watcher.watch(process)
            if not await self._watcher.is_watching():
                asyncio.get_event_loop().create_task(self._watcher.start_watching())
