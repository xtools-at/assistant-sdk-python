#!/usr/bin/python
# Copyright (C) 2017 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import unittest

import time
import threading
import wave

from googlesamples.assistant.audio_helpers import (
    WaveSource, WaveSink, ConversationStream,
    normalize_audio_buffer, align_buf
)
from six import BytesIO


class WaveSourceTest(unittest.TestCase):
    def setUp(self):
        stream = BytesIO()
        w = wave.open(stream, 'wb')
        sample_rate = 16000
        bytes_per_sample = 2
        w.setframerate(sample_rate)
        w.setsampwidth(bytes_per_sample)
        w.setnchannels(1)
        w.writeframes(b'audiodata')
        self.stream = BytesIO(stream.getvalue())
        self.source = WaveSource(self.stream, sample_rate, bytes_per_sample)
        self.sleep_time_1024 = self.source._sleep_time(1024)
        self.sleep_time_512 = self.source._sleep_time(512)

    def test_sleep_time(self):
        self.assertEqual(self.sleep_time_512, self.sleep_time_1024 / 2)

    def test_no_sleep_on_first_read(self):
        previous_time = time.time()
        self.source.read(1024)
        # check sleep was not called
        self.assertLess(time.time(), previous_time + self.sleep_time_1024)

    def test_first_sleep(self):
        self.source.read(1024)
        previous_time = time.time()
        self.source.read(512)
        # sleep was called with sleep_time_1024
        self.assertGreater(time.time(), previous_time + self.sleep_time_1024)

    def test_next_sleep(self):
        self.source.read(1024)
        self.source.read(512)
        previous_time = time.time()
        self.source.read(0)
        # sleep was called with sleep_time_512
        self.assertGreater(time.time(), previous_time + self.sleep_time_512)
        self.assertLess(time.time(), previous_time + self.sleep_time_1024)

    def test_read_header(self):
        self.assertEqual(b'audiodata', self.source.read(9))

    def test_raw(self):
        self.stream = BytesIO(b'audiodata')
        self.source = WaveSource(self.stream, 16000, 2)
        self.assertEqual(b'audiodata', self.source.read(9))

    def test_silence(self):
        self.assertEqual(b'audiodata', self.source.read(9))
        self.assertEqual(b'\x00'*9, self.source.read(9))


class WaveSinkTest(unittest.TestCase):
    def setUp(self):
        self.stream = BytesIO()
        self.sink = WaveSink(self.stream, 16000, 2)

    def test_write_header(self):
        self.sink.write(b'abcd')
        self.assertEqual(b'RIFF', self.stream.getvalue()[:4])


class DummyStream(BytesIO):
    def start(self):
        pass

    def stop(self):
        pass


class ConversationStreamTest(unittest.TestCase):
    def setUp(self):
        self.source = DummyStream(b'audio data')
        self.sink = DummyStream()
        self.stream = ConversationStream(source=self.source,
                                         sink=self.sink,
                                         iter_size=1024,
                                         sample_width=2)
        self.stream.volume_percentage = 100

    def test_stop_recording(self):
        self.stream.start_recording()
        self.assertEqual(b'audio', self.stream.read(5))
        self.stream.stop_recording()
        self.assertEqual(b'', self.stream.read(5))

    def test_start_playback(self):
        self.playback_started = False

        def start_playback():
            self.playback_started = True
            self.stream.start_playback()
        t = threading.Timer(0.1, start_playback)
        t.start()
        # write will block until start_playback is called.
        self.stream.write(b'foo')
        self.assertEqual(True, self.playback_started)
        self.assertEqual(b'foo\0', self.sink.getvalue())

    def test_oneshot_conversation(self):
        self.assertEqual(b'audio', self.stream.read(5))
        self.stream.stop_recording()
        self.stream.start_playback()
        self.stream.write(b'foo')
        self.stream.stop_playback()

    def test_normalize_audio_buffer(self):
        self.assertEqual(b'', normalize_audio_buffer(b'', 100))
        self.assertEqual(b'foobar', normalize_audio_buffer(b'foobar', 100))
        self.assertEqual(b'\xd4\x00\xa9\x01',
                         normalize_audio_buffer(b'\x01\x02\x03\x04', 50))

    def test_align_buf(self):
        self.assertEqual(b'foo\0', align_buf(b'foo', 2))
        self.assertEqual(b'foobar', align_buf(b'foobar', 2))
        self.assertEqual(b'foo\0\0\0', align_buf(b'foo', 6))


if __name__ == '__main__':
    unittest.main()
