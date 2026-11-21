import asyncio
import unittest
from prompt_toolkit.application import create_app_session
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from discord_cli.ui import choose


class MenuTests(unittest.IsolatedAsyncioTestCase):
    async def test_arrow_down_and_enter(self):
        with create_pipe_input() as pipe, create_app_session(input=pipe, output=DummyOutput()):
            task = asyncio.create_task(choose('Servers', ['Server1', 'Server2'], str))
            pipe.send_text('\x1b[B\r')
            self.assertEqual(await asyncio.wait_for(task, 3), 'Server2')

    async def test_cancel(self):
        with create_pipe_input() as pipe, create_app_session(input=pipe, output=DummyOutput()):
            task = asyncio.create_task(choose('Channels', ['general'], str))
            pipe.send_text('\x03')
            self.assertIsNone(await asyncio.wait_for(task, 3))
