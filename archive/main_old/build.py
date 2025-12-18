"""Build the compressed folder with the executable."""

from pathlib import Path
from re import search
from shutil import make_archive
from sys import argv

from PyInstaller.__main__ import run as pyinstaller


def build(*args: str) -> None:
    """Build the executable."""
    pyinstaller([*args, "main.spec"])


def pack() -> None:
    """Compress the folder with the executable."""
    match = search("name='(ezControl.+)',", Path("main.spec").read_text())
    if not match:
        msg = "Could not find executable name in main.spec."
        raise ValueError(msg)
    version = match.group(1)
    make_archive(
        base_name=f"dist/{version}",
        format="zip",
        root_dir="dist",
        base_dir=f"{version}",
    )
    print(version)  # noqa: T201


def main() -> None:
    """Build the executable and compress the folder."""
    build(*argv[1:])
    pack()


if __name__ == "__main__":
    main()
