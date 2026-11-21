"""Audio devices are opened only while connected to voice."""
from collections import deque
from threading import Lock
import discord
import numpy as np
import sounddevice as sd
from discord.ext.native_voice import MediaSink, PCMDecodeSink, VoiceClient

FRAMES = 960
SILENCE = bytes(FRAMES * 4)


class Mixer:
    """Bounded per-speaker queues; callback mixes one 20 ms frame at a time."""
    def __init__(self):
        self.queues = {}
        self.lock = Lock()

    def push(self, speaker, pcm):
        with self.lock:
            if speaker not in self.queues and len(self.queues) >= 64:
                return
            queue = self.queues.setdefault(speaker, deque(maxlen=10))
            for offset in range(0, len(pcm), len(SILENCE)):
                queue.append(pcm[offset:offset + len(SILENCE)].ljust(len(SILENCE), b'\0'))

    def read(self):
        with self.lock:
            chunks = [q.popleft() for q in self.queues.values() if q]
            self.queues = {key: q for key, q in self.queues.items() if q}
        if not chunks:
            return SILENCE
        if len(chunks) == 1:
            return chunks[0]
        mixed = np.zeros(FRAMES * 2, dtype=np.int32)
        for chunk in chunks:
            mixed += np.frombuffer(chunk, dtype='<i2')
        return np.clip(mixed, -32768, 32767).astype('<i2').tobytes()


class Speaker(MediaSink):
    def __init__(self, mixer):
        super().__init__()
        self.mixer = mixer

    def wants_media(self, media_type, codec):
        return not self.closed and media_type == 'audio' and codec == 'pcm'

    def write(self, packet):
        if self.wants_media(packet.media_type, packet.codec):
            self.mixer.push(packet.ssrc, packet.payload)


class Microphone(discord.AudioSource):
    def __init__(self, device=None):
        self.stream = sd.RawInputStream(samplerate=48000, channels=1, dtype='int16',
                                        blocksize=FRAMES, device=device)
        self.muted = False
        self.closed = False
        try:
            self.stream.start()
        except BaseException:
            self.stream.close()
            self.closed = True
            raise

    def read(self):
        if self.closed:
            return b''
        try:
            data, _ = self.stream.read(FRAMES)
        except sd.PortAudioError:
            if self.closed:
                return b''
            raise
        if self.muted:
            return SILENCE
        return np.repeat(np.frombuffer(data, dtype='<i2'), 2).tobytes()

    def cleanup(self):
        if not self.closed:
            self.closed = True
            self.stream.abort()
            self.stream.close()


class Call:
    def __init__(self, input_device=None, output_device=None):
        self.input_device, self.output_device = input_device, output_device
        self.voice = self.microphone = self.output = None
        self.error = None
        self.notice = None

    async def connect(self, channel):
        await self.close()
        self.error = None
        self.notice = None
        stage = 'opening speakers'
        try:
            mixer = Mixer()
            self.output = sd.RawOutputStream(samplerate=48000, channels=2,
                dtype='int16', blocksize=FRAMES, device=self.output_device,
                callback=lambda out, frames, time, status: self._output(mixer, out))
            stage = 'opening microphone'
            try:
                self.microphone = Microphone(self.input_device)
            except sd.PortAudioError as exc:
                if self.input_device is not None:
                    raise
                self.notice = f'Microphone unavailable ({exc}). Joined in listen-only mode.'
            stage = 'connecting to Discord voice'
            self.voice = await channel.connect(cls=VoiceClient, timeout=30, reconnect=True,
                                               self_mute=self.microphone is None)
            stage = 'starting speakers'
            self.output.start()
            stage = 'starting voice reception'
            self.voice.listen(PCMDecodeSink(Speaker(mixer), fec=True))
            if self.microphone:
                stage = 'starting microphone transmission'
                self.voice.play(self.microphone, application='voip', bitrate=32,
                                signal_type='voice', after=self._ended)
        except Exception as exc:
            await self.close()
            raise RuntimeError(f'Voice failed while {stage}: {type(exc).__name__}: {exc}. '
                               'Use devices to check audio devices; run setup.cmd if dependencies are missing.') from exc
        except BaseException:
            await self.close()
            raise

    def _ended(self, error):
        if error:
            self.error = 'Microphone playback stopped. Use leave, then reconnect.'

    @staticmethod
    def _output(mixer, out):
        out[:] = mixer.read()

    def mute(self, value):
        if not self.microphone:
            raise ValueError('No microphone is active. Connect an input device and rejoin the voice channel.')
        self.microphone.muted = value

    async def close(self):
        voice, self.voice = self.voice, None
        microphone, self.microphone = self.microphone, None
        output, self.output = self.output, None
        # One cleanup failure must not skip the remaining devices or mask the
        # original connection error. This also makes repeated close calls safe.
        actions = []
        if voice:
            actions.extend((voice.stop, voice.stop_listening))
        if microphone:
            actions.append(microphone.cleanup)
        if output:
            actions.extend((output.abort, output.close))
        for action in actions:
            try:
                action()
            except Exception:
                pass
        if voice:
            try:
                await voice.disconnect(force=True)
            except Exception:
                try:
                    voice.cleanup()
                except Exception:
                    pass
