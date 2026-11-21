from prompt_toolkit import PromptSession
from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from .core import safe_text


async def choose(title, items, label):
    if not items:
        print('No available entries.')
        return None
    selected = 0
    keys = KeyBindings()

    @keys.add('up')
    def up(event):
        nonlocal selected
        selected = (selected - 1) % len(items)

    @keys.add('down')
    def down(event):
        nonlocal selected
        selected = (selected + 1) % len(items)

    @keys.add('enter')
    def enter(event):
        event.app.exit(result=items[selected])

    @keys.add('escape')
    @keys.add('c-c')
    def cancel(event):
        event.app.exit(result=None)

    def render():
        start = max(0, min(selected - 5, len(items) - 10))
        lines = [('', f'{title} | Up/Down: select | Enter: open | Esc: cancel\n')]
        for index in range(start, min(start + 10, len(items))):
            text = safe_text(label(items[index])).replace('\n', ' ').replace('\t', ' ')
            lines.append(('reverse' if index == selected else '', f'{">" if index == selected else " "} {text}\n'))
        lines.append(('', f'{selected + 1}/{len(items)}'))
        return lines

    return await Application(layout=Layout(Window(FormattedTextControl(render))),
                             key_bindings=keys, full_screen=False).run_async()


def session():
    # No disk history (messages and tokens must not leak into shell history).
    return PromptSession(history=None, enable_history_search=False)
