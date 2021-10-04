from unittest import IsolatedAsyncioTestCase
from unittest.mock import Mock

from guapow.runner.profile import RunnerProfile
from guapow.runner.task import RunnerContext, AddDefinedEnvironmentVariables
from tests import RESOURCES_DIR


class AddDefinedEnvironmentVariablesTest(IsolatedAsyncioTestCase):

    def setUp(self):
        self.context = RunnerContext(logger=Mock(), processes_initialized=None, environment_variables={}, stopped_processes=set())
        self.task = AddDefinedEnvironmentVariables(self.context)
        self.profile = RunnerProfile.empty(f'{RESOURCES_DIR}/test')
        self.profile.environment_variables = {}

    async def test_run__not_add_blank_vars(self):
        self.profile.environment_variables.update({None: 'xpto', '': 1})
        await self.task.run(self.profile)

        self.assertEqual(0, len(self.context.environment_variables))

    async def test_run__add_vars_values_as_strings(self):
        self.profile.environment_variables.update({'a': 1, 'b': True})
        await self.task.run(self.profile)

        self.assertEqual(2, len(self.context.environment_variables))

        for var, val in {'a': '1', 'b': 'True'}.items():
            self.assertIn(var, self.context.environment_variables)
            self.assertEqual(val, self.context.environment_variables[var])

    async def test_run__add_var_none_values_as_an_empty_string(self):
        self.profile.environment_variables.update({'a': None})
        await self.task.run(self.profile)

        self.assertEqual(1, len(self.context.environment_variables))

        self.assertIn('a', self.context.environment_variables)
        self.assertEqual('', self.context.environment_variables['a'])

