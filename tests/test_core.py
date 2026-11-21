import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from discord_cli.core import parse, resolve, safe_text, load_token, save_token


class CoreTests(unittest.TestCase):
    def test_user_navigation_sequence(self):
        self.assertEqual([parse(s) for s in ['Server: 523', 'Channel: 523', '523']],
                         [('server', '523'), ('channel', '523'), ('send', '523')])

    def test_literal_commands_and_spacing(self):
        self.assertEqual(parse('/send quit'), ('send', 'quit'))
        self.assertEqual(parse('//help'), ('send', '/help'))
        self.assertEqual(parse('  Hello  '), ('send', '  Hello  '))
        self.assertEqual(parse('SERVER: My Server'), ('server', 'My Server'))
        self.assertEqual(parse('dm: 123'), ('dm_id', '123'))
        self.assertEqual(parse('/return'), ('back', ''))
        self.assertEqual(parse('/send /return'), ('send', '/return'))

    def test_duplicate_names_require_id(self):
        items = [SimpleNamespace(id=1, name='General'), SimpleNamespace(id=2, name='General')]
        self.assertEqual(resolve(items, '2').id, 2)
        with self.assertRaises(ValueError):
            resolve(items, 'general')
        with self.assertRaises(ValueError):
            resolve(items, '999')

    def test_remote_terminal_controls_removed(self):
        output = safe_text('user\x1b[2J\x07\x9b31m\r: Hello\nworld')
        self.assertNotIn('\x1b', output)
        self.assertNotIn('\x07', output)
        self.assertNotIn('\x9b', output)
        self.assertNotIn('\r', output)
        self.assertIn('\n', output)

    def test_config_roundtrip_and_invalid_data(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'config.json'
            self.assertIsNone(load_token(path))
            save_token('test-placeholder', path)
            self.assertEqual(load_token(path), 'test-placeholder')
            save_token('replacement-placeholder', path)
            self.assertEqual(load_token(path), 'replacement-placeholder')
            self.assertEqual(len(list(Path(folder).iterdir())), 1)
            for invalid in ['{broken', '[]', '{"token": 5}', '{"token":""}']:
                path.write_text(invalid)
                with self.assertRaises(ValueError):
                    load_token(path)
