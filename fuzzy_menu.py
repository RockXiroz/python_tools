"""
Interactive fuzzy-search menu.

Usage example
-------------
    from fuzzy_menu import FuzzyMenu, RunTool

    def greet():
        print("Hello!")

    tools = {
        "run_greet": RunTool("Greet the user", greet),
        "run_reboot": RunTool("Reboot the system", lambda: print("Rebooting...")),
    }

    FuzzyMenu(tools).run()
"""

import sys
import tty
import termios
from dataclasses import dataclass
from typing import Callable


@dataclass
class RunTool:
    usage: str
    func: Callable


# ── terminal helpers ──────────────────────────────────────────────────────────

def _getch() -> str:
    """Read a single keypress without echoing it."""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        # Handle escape sequences (arrow keys)
        if ch == "\x1b":
            ch2 = sys.stdin.read(1)
            if ch2 == "[":
                ch3 = sys.stdin.read(1)
                return f"\x1b[{ch3}"
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


CLEAR_LINE = "\r\033[K"
MOVE_UP    = "\033[A"
HIDE_CUR   = "\033[?25l"
SHOW_CUR   = "\033[?25h"


# ── fuzzy scoring ─────────────────────────────────────────────────────────────

def _fuzzy_score(query: str, text: str) -> int:
    """
    Returns a score >= 0 when every char of *query* appears in order in *text*,
    -1 if they don't all match.  Higher score = better match.
    """
    q = query.lower()
    t = text.lower()
    if not q:
        return 0
    ti = 0
    score = 0
    prev_match = -1
    for ch in q:
        matched = False
        while ti < len(t):
            if t[ti] == ch:
                # Consecutive or word-start bonuses
                if ti == prev_match + 1:
                    score += 10   # consecutive bonus
                if ti == 0 or t[ti - 1] in "_- ":
                    score += 5    # word-boundary bonus
                prev_match = ti
                ti += 1
                matched = True
                break
            ti += 1
        if not matched:
            return -1
    return score


# ── main class ────────────────────────────────────────────────────────────────

class FuzzyMenu:
    """Interactive fuzzy-search menu over a dict of RunTool entries."""

    def __init__(self, tools: dict[str, "RunTool"]):
        self.tools = tools          # original dict
        self._results: list[tuple[str, RunTool]] = []
        self._cursor = 0
        self._query = ""

    # ── rendering ─────────────────────────────────────────────────────────────

    def _render(self, prev_lines: int) -> int:
        """Redraw the UI; returns number of lines printed (for next erase)."""
        # Erase previous render
        buf = []
        for _ in range(prev_lines):
            buf.append(f"{MOVE_UP}{CLEAR_LINE}")

        # Search prompt
        buf.append(f"{CLEAR_LINE}\033[1m> \033[0m{self._query}\n")

        if not self._results:
            buf.append(f"{CLEAR_LINE}  \033[90m(no matches)\033[0m\n")
            print("".join(buf), end="", flush=True)
            return 2

        # Result list
        for i, (name, tool) in enumerate(self._results):
            prefix = "\033[32m❯ \033[0m" if i == self._cursor else "  "
            style  = "\033[1m" if i == self._cursor else ""
            reset  = "\033[0m"
            buf.append(f"{CLEAR_LINE}{prefix}{style}{name}{reset}  "
                       f"\033[90m{tool.usage}\033[0m\n")

        # Usage hint for selected item
        sel_tool = self._results[self._cursor][1]
        buf.append(f"{CLEAR_LINE}\033[90m↑↓ navigate · Enter execute · Ctrl-C quit\033[0m\n")

        print("".join(buf), end="", flush=True)
        return len(self._results) + 2   # prompt + results + hint line

    def _search(self):
        scored = []
        for name, tool in self.tools.items():
            s = _fuzzy_score(self._query, name)
            if s >= 0:
                scored.append((s, name, tool))
        scored.sort(key=lambda x: -x[0])
        self._results = [(name, tool) for _, name, tool in scored]
        self._cursor = 0

    # ── public entry point ────────────────────────────────────────────────────

    def run(self):
        """Start the interactive loop."""
        print(HIDE_CUR, end="", flush=True)
        self._search()
        prev_lines = 0
        try:
            while True:
                prev_lines = self._render(prev_lines)
                key = _getch()

                if key in ("\x03", "\x04"):          # Ctrl-C / Ctrl-D
                    break

                elif key == "\x1b[A":                # Up arrow
                    if self._results:
                        self._cursor = (self._cursor - 1) % len(self._results)

                elif key == "\x1b[B":                # Down arrow
                    if self._results:
                        self._cursor = (self._cursor + 1) % len(self._results)

                elif key in ("\r", "\n"):             # Enter – execute
                    if self._results:
                        name, tool = self._results[self._cursor]
                        # Clear UI before running
                        for _ in range(prev_lines + 1):
                            print(f"{MOVE_UP}{CLEAR_LINE}", end="")
                        print(f"\033[1mRunning:\033[0m {name}\n")
                        tool.func()
                        break

                elif key == "\x7f":                  # Backspace
                    self._query = self._query[:-1]
                    self._search()

                elif key.isprintable():
                    self._query += key
                    self._search()

        finally:
            print(SHOW_CUR, end="", flush=True)


# ── demo ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    def _reboot():
        print("Rebooting system...")

    def _status():
        print("System status: OK")

    def _deploy():
        print("Deploying application...")

    def _logs():
        print("Tailing logs...")

    demo_tools = {
        "run_reboot":      RunTool("Reboot the system immediately",       _reboot),
        "run_status":      RunTool("Show current system status",          _status),
        "run_deploy":      RunTool("Deploy the latest build",             _deploy),
        "run_logs":        RunTool("Tail application logs",               _logs),
        "run_backup":      RunTool("Create a full system backup",         lambda: print("Backing up...")),
        "run_health_check":RunTool("Run all health-check probes",         lambda: print("All probes passed.")),
    }

    FuzzyMenu(demo_tools).run()
