# Discord CLI

A small English-language personal Discord terminal client for Windows CMD,
PowerShell, and Windows Terminal. Navigate servers and channels with arrow keys
or explicit IDs, read live messages, open DMs, and join voice with microphone and
speaker audio. No server administration, nickname editing, or profile settings.

**Account risk:** Discord explicitly prohibits automating personal accounts
outside its OAuth2/bot API, and using this client can result in account termination.
See [Discord's policy](https://support.discord.com/hc/en-us/articles/115002192352).
This is an unofficial client, not an approved Discord application.

## Install and run

Install 64-bit Python 3.11 or newer and Git, with both available on PATH.
Use an interactive Windows terminal:

```cmd
git clone https://github.com/Ragim-Games/discord-cli.git
cd discord-cli
setup.cmd
start.cmd
```

The first launch asks for a personal account token with hidden input. Enter your
own token locally; do not paste it into an issue, chat, screenshot, or command line.
The token is saved to `config.json` beside the project and reused next launch.
It is stored in **plain text**, as requested; anyone who can read this file can
access the credential. The file and temporary copies are excluded from Git.
No token discovery, browser token extraction, or credential collection is performed.

To replace an invalid token:

```cmd
start.cmd --reset-token
```

The Discord core is pinned to a source commit because the published 2.1.0 release
does not provide the current native voice API. Native voice 0.1.1 declares
`discord.py-self>=2.2.0`, while the available core identifies as `2.2.0a`.
`setup.cmd` installs the core with its voice dependencies, then installs that
extension with `--no-deps` to work around this upstream version declaration.
`pip check` will report this known metadata mismatch. Runtime imports, Opus
encoding, and mocked voice integration are tested; real Discord voice negotiation
still requires a live account test. Dependencies remain experimental.

## Navigation

On login, a server list opens. Use **Up/Down**, then **Enter**. The channel list
opens next; `[text]` and `[voice]` distinguish channel types. **Esc** cancels a menu.
Names and IDs appear together so duplicate names can be distinguished.

Direct navigation works as follows (replace the example IDs with real ones):

```text
Discord> Server: 523
My Server> Channel: 523
My Server/general> 523
user_523: Hello world
```

Only the currently selected conversation prints live messages. Incoming output
preserves the message you are typing. Submitted input lines disappear, leaving
only the received chat messages instead of a duplicate prompt-and-message echo.
Opening a text channel or DM displays its
latest 20 messages. Messages arriving during a menu are counted rather than
overwriting the list; reopen the conversation to view recent history.

| Command | Action |
| --- | --- |
| `servers` | Open server picker, then channel picker |
| `Server: ID` or `Server: Name` | Select a server |
| `channels` | Open channel picker |
| `Channel: ID` or `Channel: Name` | Enter a text or voice channel |
| `dm` | Pick an existing DM or group DM |
| `dm: USER_ID` | Open a one-to-one DM; sending is a separate action |
| `/return` (or `back`) | Disconnect voice and return to the channel, DM, or server list |
| `leave` | Disconnect voice |
| `mute`, `unmute` | Control microphone |
| `devices` | List audio devices |
| `help`, `quit` | Show help or exit |
| `/send quit` | Send the literal message `quit` |
| `//hello` | Send the literal message `/hello` |

Bare text is sent only after selecting a text channel or DM. Numeric text such as
`523` is a message, not a navigation command. Ambiguous names require an ID or the
picker. Sending uses your account's permissions and Discord rate limits. There
are no scheduled, bulk, or automatic messages. Input history is not saved to disk.

## Voice

Selecting a voice channel connects microphone and speakers automatically.
**Your microphone is live after connection.** Use `mute` to stop transmitting
audio and `leave` to release the devices. Headphones prevent acoustic feedback;
echo cancellation, noise suppression, video, stage channels, and DM calls are
not implemented. Text chat is supported in ordinary text channels and DMs;
forum posts and thread navigation are not implemented.

Default Windows recording and playback devices are used at 48 kHz. To select
other devices, first run `start.cmd --devices`, then use the displayed IDs:

```cmd
start.cmd --input-device 1 --output-device 4
```

Voice uses native transport with DAVE support, Opus at 32 kbit/s, mono microphone
capture converted to stereo, and bounded per-speaker playback queues. Default
devices must accept 48 kHz PCM. If opening devices or connecting fails, the client
releases audio resources and returns to the prompt. Changing to another channel
disconnects the existing call. No audio is recorded to disk.

## Resource use and verification

- One asynchronous Gateway connection; no polling for chat or periodic redraw.
- Message cache disabled, startup member chunking disabled, member cache disabled.
- Only the selected server is subscribed for events; no presence/member tracking.
- At most 20 messages fetched during explicit navigation.
- Audio libraries load on first voice use; devices run only during a call.
- Playback buffering is bounded to 10 frames per speaker and 64 active queues.

Actual RAM and CPU usage depend on server count, traffic, and audio hardware;
there is no claimed or measured live-account resource ceiling.

```cmd
.venv\Scripts\python -m unittest discover -s tests -v
```

Tests cover command parsing, token file round trips, terminal control stripping,
arrow-key menus, destination checks, event filtering, server switching, failed
login handling, voice lifecycle, bounded audio mixing, and device cleanup.
They do not contact Discord or transmit messages. Live login, reconnect behavior,
DM delivery, and two-party voice quality require manual validation with an account.
