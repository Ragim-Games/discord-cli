import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
import numpy as np
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
            with self.assertRaises(TimeoutError):
                await call.connect(channel)
        output.close.assert_called_once()
        microphone.cleanup.assert_called_once()
        self.assertIsNone(call.output)
        self.assertIsNone(call.microphone)
