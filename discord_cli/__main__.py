import argparse
import asyncio
import getpass
import sys
from .core import CONFIG, load_token, save_token


def main():
    parser = argparse.ArgumentParser(description='Discord CLI - lightweight personal terminal client')
    parser.add_argument('--reset-token', action='store_true', help='Replace the saved token')
    parser.add_argument('--input-device', type=int, help='Microphone device ID')
    parser.add_argument('--output-device', type=int, help='Speaker device ID')
    parser.add_argument('--devices', action='store_true', help='List audio devices without logging in')
    args = parser.parse_args()
    try:
        if args.devices:
            import sounddevice
            print(sounddevice.query_devices())
            return
        if not sys.stdin.isatty():
            parser.exit(1, 'Use an interactive terminal to run Discord CLI.\n')
        token = None if args.reset_token else load_token()
        if not token:
            print('Discord CLI uses a personal account token. Discord prohibits self-bots; your account may be terminated.')
            print('The token will be stored as plain text in local config.json. Never share this file.')
            token = getpass.getpass('Discord token: ').strip()
            if not token:
                parser.exit(1, 'No token entered.\n')
            save_token(token)
            print('Token saved to config.json.')
        from .app import run
        import discord
        try:
            asyncio.run(run(token, args.input_device, args.output_device))
        except discord.LoginFailure:
            parser.exit(1, 'Login failed. Run start.cmd --reset-token to enter a new token.\n')
        except (discord.DiscordException, OSError, TimeoutError):
            parser.exit(1, 'Connection failed. Check your network and account status, then retry.\n')
    except ImportError:
        parser.exit(1, 'Missing dependencies. Run setup.cmd first.\n')
    except ValueError as exc:
        parser.exit(1, str(exc) + '\n')
    except OSError:
        parser.exit(1, 'Cannot access config.json. Check file permissions and free disk space.\n')
    except (EOFError, KeyboardInterrupt):
        print('\nGoodbye.')


if __name__ == '__main__':
    main()
