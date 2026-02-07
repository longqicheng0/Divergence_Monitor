"""Welcome screen and menu for interactive CLI."""

from __future__ import annotations

import textwrap
from typing import Optional

from readchar import key, readkey


def _render_banner(text: str) -> str:
    try:
        from pyfiglet import Figlet

        figlet = Figlet(font="slant")
        return figlet.renderText(text)
    except Exception:
        return textwrap.dedent(
            f"""
             ____  _                                  _
            |  _ \\(_)_   _____ _ __ __ _  ___  _ __  | |_ ___
            | | | | \ \ / / _ \\ '__/ _` |/ _ \\| '_ \\ | __/ _ \\
            | |_| | |\\ V /  __/ | | (_| | (_) | | | || ||  __/
            |____/|_| \\_/ \\___|_|  \\__, |\\___/|_| |_| \\__\\___|
                                   |___/
            {text}
            """
        ).strip("\n")


def build_welcome(project_name: str, description: str) -> str:
    """Build the welcome banner and description text."""

    banner = _render_banner(project_name)
    return f"{banner}\n{description}"


def show_welcome(project_name: str, description: str) -> None:
    """Print the welcome banner and description."""

    print(build_welcome(project_name, description))


def show_menu() -> str:
    """Display the main menu and return the selected option."""

    print("\nChoose an option:")
    print("[1] Train/Test on Historical Data (offline/backtest)")
    print("[2] Live Monitoring (WebSocket)")
    print("[3] Exit")
    return input("Press Enter after choosing: ").strip()


def select_menu_option(header: Optional[str] = None) -> Optional[str]:
    """Loop until a valid menu option is selected or exit is chosen."""

    options = [
        "Train/Test on Historical Data (offline/backtest)",
        "Live Monitoring (WebSocket)",
        "Exit",
    ]
    index = 0
    while True:
        print("\033c", end="")
        if header:
            print(header)
            print("")
        print("Choose an option (use arrow keys, Enter to select):\n")
        for i, label in enumerate(options):
            marker = ">" if i == index else " "
            print(f"{marker} [{i + 1}] {label}")

        pressed = readkey()
        if pressed in {key.UP, "k"}:
            index = (index - 1) % len(options)
        elif pressed in {key.DOWN, "j"}:
            index = (index + 1) % len(options)
        elif pressed in {key.ENTER, "\r", "\n"}:
            return str(index + 1)
