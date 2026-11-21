import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
import discord
from prompt_toolkit.application import create_app_session
from prompt_toolkit.output import DummyOutput
from discord_cli.app import Client, run


class AppTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = Client()
        self.client.say = MagicMock()

    async def asyncTearDown(self):
        await self.client.close()

    async def test_send_requires_destination(self):
        with self.assertRaises(ValueError):
            await self.client.command('523')

    async def test_send_and_command_escaping(self):
        channel = SimpleNamespace(send=AsyncMock())
        self.client.channel = channel
        await self.client.command('523')
        await self.client.command('/send quit')
        self.assertEqual([c.args[0] for c in channel.send.await_args_list], ['523', 'quit'])
        with self.assertRaises(ValueError):
            await self.client.command('x' * 2001)
        self.assertFalse(await self.client.command('quit'))

    async def test_only_selected_channel_is_displayed(self):
        self.client.channel = SimpleNamespace(id=523)
        message = SimpleNamespace(channel=SimpleNamespace(id=999))
        await self.client.on_message(message)
        self.client.say.assert_not_called()
        message.channel.id = 523
        message.content = 'Hello world'
        message.author = SimpleNamespace(display_name='user_523')
        message.attachments = []
        await self.client.on_message(message)
        self.client.say.assert_called_once_with('user_523: Hello world')
        self.client.menu = True
        await self.client.on_message(message)
        self.assertEqual(self.client.missed, 1)

    async def test_server_switch_unsubscribes_and_clears_channel(self):
        previous = SimpleNamespace(id=1, subscribe=AsyncMock())
        target = SimpleNamespace(id=2, name='Server2', subscribe=AsyncMock())
        self.client.server = previous
        self.client.channel = SimpleNamespace(id=55)
        await self.client.select_server(target)
        self.assertIs(self.client.server, target)
        self.assertIsNone(self.client.channel)
        self.assertFalse(previous.subscribe.await_args.kwargs['typing'])
        self.assertTrue(target.subscribe.await_args.kwargs['typing'])

    async def test_voice_joins_and_cleans_up(self):
        channel = MagicMock(spec=discord.VoiceChannel)
        channel.name = 'Voice'
        call = SimpleNamespace(connect=AsyncMock(), close=AsyncMock())
        with patch('discord_cli.audio.Call', return_value=call):
            await self.client.open_channel(channel)
        call.connect.assert_awaited_once_with(channel)
        self.assertIs(self.client.channel, channel)
        await self.client.leave()
        call.close.assert_awaited_once()
        self.assertIsNone(self.client.channel)

    async def test_failed_login_propagates_without_waiting_for_ready(self):
        with create_app_session(output=DummyOutput()), patch.object(Client, 'start', side_effect=discord.LoginFailure('invalid')):
            with self.assertRaises(discord.LoginFailure):
                await run('test-placeholder')

    async def test_return_to_channels_then_servers(self):
        server = SimpleNamespace(id=1, subscribe=AsyncMock(), channels=[])
        self.client.server = server
        self.client.channel = SimpleNamespace(id=2)
        self.client.pick = AsyncMock(return_value=None)
        await self.client.command('/return')
        self.assertIsNone(self.client.channel)
        self.assertIs(self.client.server, server)
        self.assertEqual(self.client.pick.await_args.args[0], 'Channels')
        await self.client.command('/return')
        self.assertIsNone(self.client.server)
        self.assertEqual(self.client.pick.await_args.args[0], 'Servers')

    async def test_return_from_dm_opens_dm_list(self):
        self.client.channel = MagicMock(spec=discord.DMChannel)
        self.client.pick = AsyncMock(return_value=None)
        await self.client.command('/return')
        self.assertIsNone(self.client.channel)
        self.assertEqual(self.client.pick.await_args.args[0], 'Direct messages')
