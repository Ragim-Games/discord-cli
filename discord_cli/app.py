import asyncio
import contextlib
import discord
from prompt_toolkit.patch_stdout import patch_stdout
from .core import parse, resolve, safe_text
from .ui import choose, session

HELP = '''Commands:
  servers                 Choose a server with Up/Down and Enter
  Server: ID or name      Select a server directly
  channels                Choose a text or voice channel
  Channel: ID or name     Open a channel directly
  dm                      Choose an existing direct/group conversation
  dm: USER_ID             Open a direct conversation by user ID
  /return (or back)       Go back to the previous list (disconnects voice)
  leave                   Disconnect voice
  mute / unmute           Mute/unmute the microphone
  devices                 List local audio device IDs
  help / quit             Show help / exit
Type a message to send it to the selected text channel or DM.
Use /send TEXT for text that looks like a command. Use //TEXT for /TEXT.
Voice starts your default microphone and speakers. Headphones recommended.'''


def channel_label(channel):
    kind = 'voice' if isinstance(channel, discord.VoiceChannel) else 'text'
    category = getattr(channel, 'category', None)
    prefix = f'{category.name} / ' if category else ''
    return f'[{kind}] {prefix}{channel.name} ({channel.id})'


def dm_label(channel):
    if isinstance(channel, discord.DMChannel):
        return f'{channel.recipient} ({channel.id})'
    return f'{channel.name or ", ".join(str(u) for u in channel.recipients)} ({channel.id})'


class Client(discord.Client):
    def __init__(self, input_device=None, output_device=None):
        super().__init__(max_messages=None, chunk_guilds_at_startup=False,
                         guild_subscriptions=False, member_cache_flags=discord.MemberCacheFlags.none())
        self.server = self.channel = self.call = None
        self.input_device, self.output_device = input_device, output_device
        self.menu = False
        self.missed = 0
        self.was_ready = False

    def say(self, text):
        text = str(text)
        token = getattr(self.http, 'token', None)
        if isinstance(token, str) and token:
            text = text.replace(token, '[REDACTED]')
        print(safe_text(text))

    async def on_ready(self):
        if self.was_ready:
            self.say('Reconnected.')
            if self.server:
                updated = self.get_guild(self.server.id)
                if updated:
                    self.server = updated
                    await self.server.subscribe(typing=True, activities=False, threads=False, member_updates=False)
        self.was_ready = True

    async def on_disconnect(self):
        if self.was_ready and not self.is_closed():
            self.say('Connection interrupted. Reconnecting...')

    async def on_error(self, event_method, *args, **kwargs):
        # Do not emit event payloads or credentials through library tracebacks.
        self.say(f'An event could not be processed: {event_method}.')

    async def on_message(self, message):
        if self.channel and message.channel.id == self.channel.id:
            if self.menu:
                self.missed += 1
            else:
                self.show_message(message)

    def show_message(self, message):
        content = message.content or '[No text]'
        attachments = '\n'.join(a.url for a in message.attachments)
        self.say(f'{message.author.display_name}: {content}' + (f'\n{attachments}' if attachments else ''))

    async def pick(self, title, items, label):
        self.menu = True
        try:
            return await choose(title, items, label)
        finally:
            self.menu = False
            if self.missed:
                self.say(f'{self.missed} messages arrived while choosing. Reopen the channel for recent history.')
                self.missed = 0

    def channels(self):
        if not self.server:
            raise ValueError('Choose a server first.')
        return sorted((c for c in self.server.channels
                       if isinstance(c, (discord.TextChannel, discord.VoiceChannel))
                       and (self.server.me is None or c.permissions_for(self.server.me).view_channel)),
                      key=lambda c: (c.position, c.id))

    async def select_server(self, server):
        await self.leave()
        if self.server and self.server.id != server.id:
            await self.server.subscribe(typing=False, activities=False, threads=False, member_updates=False)
        await server.subscribe(typing=True, activities=False, threads=False, member_updates=False)
        self.server, self.channel = server, None
        self.say(f'Server: {server.name} ({server.id}). Type channels or Channel: ID.')

    async def open_channel(self, channel):
        if isinstance(channel, discord.VoiceChannel):
            from .audio import Call
            await self.leave()
            self.call = Call(self.input_device, self.output_device)
            self.say('Connecting voice...')
            await self.call.connect(channel)
            self.channel = channel
            if self.call.notice:
                self.say(self.call.notice)
            mode = 'Microphone ON' if self.call.microphone else 'Listen-only'
            self.say(f'Voice: {channel.name}. {mode}. Use mute or leave.')
            return
        await self.leave()
        self.channel = channel
        self.say(f'Channel: {getattr(channel, "name", None) or dm_label(channel)} ({channel.id})')
        # History is bounded and fetched only on explicit navigation.
        try:
            messages = [m async for m in channel.history(limit=20)]
            for message in reversed(messages):
                self.show_message(message)
        except discord.Forbidden:
            self.say('Cannot read message history. New messages will still appear when available.')

    async def leave(self):
        if self.call:
            call, self.call = self.call, None
            await call.close()
        if isinstance(self.channel, discord.VoiceChannel):
            self.channel = None

    async def command(self, line):
        action, value = parse(line)
        if action == 'quit':
            return False
        if action == 'help':
            self.say(HELP)
        elif action in ('servers', 'server'):
            server = resolve(self.guilds, value) if value else await self.pick('Servers', self.guilds, lambda g: f'{g.name} ({g.id})')
            if server:
                await self.select_server(server)
                if action == 'servers':
                    await self.command('channels')
        elif action in ('channels', 'channel'):
            channels = self.channels()
            channel = resolve(channels, value) if value else await self.pick('Channels', channels, channel_label)
            if channel:
                await self.open_channel(channel)
        elif action in ('dm', 'dm_id'):
            if value:
                if not value.isdecimal():
                    raise ValueError('Use dm: USER_ID.')
                user = await self.fetch_user(int(value))
                channel = await user.create_dm()
            else:
                channel = await self.pick('Direct messages', self.private_channels, dm_label)
            if channel:
                await self.open_channel(channel)
        elif action == 'leave':
            await self.leave()
            self.say('Voice disconnected.')
        elif action in ('mute', 'unmute'):
            if not self.call or not self.call.voice:
                raise ValueError('Join a voice channel first.')
            self.call.mute(action == 'mute')
            await self.call.voice.guild.change_voice_state(channel=self.call.voice.channel, self_mute=action == 'mute')
            self.say('Microphone muted.' if action == 'mute' else 'Microphone ON.')
        elif action == 'back':
            had_channel = self.channel is not None
            was_dm = isinstance(self.channel, (discord.DMChannel, discord.GroupChannel))
            await self.leave()
            self.channel = None
            if was_dm:
                await self.command('dm')
            elif had_channel and self.server:
                await self.command('channels')
            else:
                if self.server:
                    await self.server.subscribe(typing=False, activities=False, threads=False, member_updates=False)
                    self.server = None
                await self.command('servers')
        elif action == 'devices':
            import sounddevice
            self.say(sounddevice.query_devices())
        elif action == 'send' and value.strip():
            if not self.channel or isinstance(self.channel, discord.VoiceChannel):
                raise ValueError('Select a text channel or DM before sending messages.')
            if len(value) > 2000:
                raise ValueError('Messages must be 2,000 characters or fewer.')
            await self.channel.send(value)
        return True

    def prompt(self):
        if isinstance(self.channel, (discord.DMChannel, discord.GroupChannel)):
            path = 'DM/' + dm_label(self.channel)
        else:
            path = self.server.name if self.server else 'Discord'
            if self.channel:
                path += '/' + self.channel.name
        return safe_text(path).replace('\n', ' ').replace('\t', ' ') + '> '

    async def terminal(self):
        self.say(f'Logged in as {self.user}. Type help for commands.')
        prompt = session()
        initial = True
        try:
            while True:
                try:
                    if initial:
                        initial = False
                        await self.command('servers')
                    if self.call and self.call.error:
                        self.say(self.call.error)
                        self.call.error = None
                    line = await prompt.prompt_async(self.prompt)
                    if not self.is_ready():
                        self.say('Reconnecting. Wait before sending commands.')
                        if parse(line)[0] == 'quit':
                            break
                        continue
                    if not await self.command(line):
                        break
                except (EOFError, KeyboardInterrupt):
                    raise
                except Exception as exc:
                    # HTTP exception bodies can contain user input; avoid dumping payloads.
                    if isinstance(exc, discord.Forbidden):
                        self.say('Permission denied by Discord.')
                    elif isinstance(exc, discord.HTTPException):
                        self.say(f'Discord request failed (HTTP {exc.status}, code {exc.code}).')
                    elif isinstance(exc, (ValueError, RuntimeError)):
                        self.say(str(exc))
                    else:
                        self.say(f'Operation failed ({type(exc).__name__}): {exc}')
        except (EOFError, KeyboardInterrupt):
            pass
        finally:
            await self.leave()


async def run(token, input_device=None, output_device=None):
    client = Client(input_device, output_device)
    with patch_stdout():
        async with client:
            gateway = asyncio.create_task(client.start(token), name='discord-gateway')
            ready = asyncio.create_task(client.wait_until_ready(), name='discord-ready')
            terminal = None
            try:
                done, _ = await asyncio.wait([gateway, ready], return_when=asyncio.FIRST_COMPLETED, timeout=60)
                if gateway in done:
                    await gateway
                    return
                if ready not in done:
                    raise TimeoutError('Login timed out.')
                await ready
                terminal = asyncio.create_task(client.terminal(), name='terminal')
                done, _ = await asyncio.wait([gateway, terminal], return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    await task
            finally:
                for task in (ready, terminal, gateway):
                    if task:
                        task.cancel()
                for task in (ready, terminal, gateway):
                    if task:
                        with contextlib.suppress(asyncio.CancelledError, Exception):
                            await task
                await client.leave()
