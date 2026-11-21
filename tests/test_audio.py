import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
import numpy as np
import sounddevice as sd
from discord_cli.audio import Mixer, SILENCE, FRAMES, Call, Speaker


class MixerTests(unittest.TestCase):
    def test_silence_mix_and_clipping(self):
        mixer = Mixer()
        self.assertEqual(mixer.read(), SILENCE)
        pcm = np.full(FRAMES * 2, 30000, dtype='<i2').tobytes()
        mixer.push(1, pcm)
        mixer.push(2, pcm)
        output = np.frombuffer(mixer.read(), dtype='<i2')
        self.assertTrue(np.all(output == 32767))
        self.assertEqual(mixer.read(), SILENCE)

    def test_bounded_buffer_and_speaker_limit(self):
        mixer = Mixer()
        for user in range(100):
            for _ in range(15):
                mixer.push(user, SILENCE)
        self.assertEqual(len(mixer.queues), 64)
        self.assertTrue(all(len(q) == 10 for q in mixer.queues.values()))

    def test_non_audio_packets_are_ignored(self):
        mixer = Mixer()
        sink = Speaker(mixer)
        sink.write(SimpleNamespace(media_type='video', codec='H264'))
        self.assertEqual(mixer.read(), SILENCE)
        sink.cleanup()


class CallTests(unittest.IsolatedAsyncioTestCase):
    async def test_connect_failure_releases_devices(self):
        channel = SimpleNamespace(connect=AsyncMock(side_effect=TimeoutError()))
        output, microphone = MagicMock(), MagicMock()
        with patch('discord_cli.audio.sd.RawOutputStream', return_value=output), patch('discord_cli.audio.Microphone', return_value=microphone):
            call = Call()
            with self.assertRaisesRegex(RuntimeError, 'connecting to Discord voice: TimeoutError'):
                await call.connect(channel)
        output.close.assert_called_once()
        microphone.cleanup.assert_called_once()
        self.assertIsNone(call.output)
        self.assertIsNone(call.microphone)

    async def test_missing_default_microphone_joins_listen_only(self):
        voice = MagicMock()
        voice.disconnect = AsyncMock()
        channel = SimpleNamespace(connect=AsyncMock(return_value=voice))
        output = MagicMock()
        with patch('discord_cli.audio.sd.RawOutputStream', return_value=output), patch('discord_cli.audio.Microphone', side_effect=sd.PortAudioError('No default input')):
            call = Call()
            await call.connect(channel)
            self.assertTrue(channel.connect.await_args.kwargs['self_mute'])
            self.assertIsNone(call.microphone)
            self.assertIn('listen-only', call.notice)
            voice.listen.assert_called_once()
            voice.play.assert_not_called()
            await call.close()
        output.close.assert_called_once()
        voice.disconnect.assert_awaited_once()

    async def test_cleanup_failure_does_not_hide_connection_error(self):
        output = MagicMock()
        output.abort.side_effect = sd.PortAudioError('Already stopped')
        channel = SimpleNamespace(connect=AsyncMock(side_effect=TypeError('incompatible API')))
        with patch('discord_cli.audio.sd.RawOutputStream', return_value=output), patch('discord_cli.audio.Microphone', return_value=MagicMock()):
            call = Call()
            with self.assertRaisesRegex(RuntimeError, 'TypeError: incompatible API'):
                await call.connect(channel)
        output.close.assert_called_once()

    async def test_explicit_bad_microphone_shows_error_and_does_not_connect(self):
        channel = SimpleNamespace(connect=AsyncMock())
        with patch('discord_cli.audio.sd.RawOutputStream', return_value=MagicMock()), patch('discord_cli.audio.Microphone', side_effect=sd.PortAudioError('Invalid device')):
            call = Call(input_device=999)
            with self.assertRaisesRegex(RuntimeError, 'opening microphone: PortAudioError'):
                await call.connect(channel)
        channel.connect.assert_not_awaited()
