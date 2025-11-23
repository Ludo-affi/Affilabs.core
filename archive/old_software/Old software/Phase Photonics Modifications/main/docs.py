"""Makes documentation."""

from argparse import ArgumentParser
from http.server import SimpleHTTPRequestHandler, test
from os import chdir
from pathlib import Path
from shutil import copyfile

from pdoc import pdoc, render

from settings import SW_VERSION


def make(*, preview: bool = False) -> None:
    """Make documentation."""
    # Settings for hte documentation generator
    render.configure(
        edit_url_map={
            "main":
            "https://gitlab.com/affinite-software/ezcontrol/-/blob/main/main.py",
            "widgets":
            "https://gitlab.com/affinite-software/ezcontrol/-/tree/main/widgets/",
            "utils":
            "https://gitlab.com/affinite-software/ezcontrol/-/tree/main/utils/",
            "settings":
            "https://gitlab.com/affinite-software/ezcontrol/-/blob/main/settings.py",
        },
        logo="/ezcontrol/logo.png",
        logo_link="https://www.affiniteinstruments.com/",
        favicon="/ezcontrol/icon.ico",
        footer_text=f"ezControl {SW_VERSION}",
    )

    # Generates the documentation
    pdoc("main", "widgets", "utils", "settings", output_directory=Path("public"))
    copyfile("ui/img/affinite-no-background.png", "public/logo.png")
    copyfile("ui/img/affinite2.ico", "public/icon.ico")

    # Optionally creates a server to view the documentation on you local computer
    if preview:
        print("View documentation at http://localhost:8000")  # noqa: T201
        chdir("public")
        try:
            test(SimpleHTTPRequestHandler)
        finally:
            chdir("..")


def main() -> None:
    """CLI for making and viewing documantation."""
    parser = ArgumentParser()
    parser.add_argument(
        "-p",
        "--preview",
        help="Preview the documentation at http://localhost:8000",
        action="store_true",
    )
    args = parser.parse_args()
    make(preview=args.preview)

if __name__ == "__main__":
    main()
