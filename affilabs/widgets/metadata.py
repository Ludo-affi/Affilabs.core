"""TraceDrwaer Metadata classes.

Contains classes for widgets neccessary to entry metadata to be save in output file
in a format compatible with TraceDrawer.
"""

from __future__ import annotations

import csv
import re
from collections.abc import Collection, Hashable, Sequence
from datetime import UTC, datetime
from typing import Generic, NamedTuple, Self, TypeVar

from PySide6.QtCore import QSize, Qt, Slot
from PySide6.QtGui import QDoubleValidator, QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from settings import SW_VERSION

TIME_ZONE = datetime.now(UTC).astimezone().tzinfo


class ConcentrationEntry(NamedTuple):
    """Class to hold widgets for entering a concentration."""

    time: QLineEdit
    """Time entry box."""

    concentration: QLineEdit
    """Concentration Entry box."""

    def output(self: Self) -> str:
        """Write a string with the concentration in the TraceDrawer format."""
        # Checks for a valid concentration, which is required
        try:
            concentration = float(self.concentration.text())
        except ValueError:
            return ""

        # Chceks for a valid time, which is optional
        time: float | None
        try:
            time = float(self.time.text())
        except ValueError:
            time = None

        # Formats the output based on wheather a time was included
        string = (
            f"{concentration:E}({time:E})" if time is not None else f"{concentration:E}"
        )

        # Python puts a `+` after the `E` which TraceDrawer won't accept,
        # so we remove all `+`s
        return string.replace("+", "")

    def from_string(self: Self, string: str) -> None:
        """Read a concentration from a string."""
        # Regex that will match a number, possibly in scientific notation
        number_regex = r"[-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?"

        # Tries to match the string with the format "number(number)"
        match = re.fullmatch(f"({number_regex})\\(({number_regex})\\)", string)

        # If the match was succesful update the concentration
        if match:
            self.concentration.insert(match[1])
            self.time.insert(match[2])
            return

        # Tries to match just a number
        match = re.fullmatch(number_regex, string)

        # If match is succesful updates the concentration
        if match:
            self.concentration.insert(match[0])


class Concentrations(QWidget):
    """Widget to allow user to enter a list of concentrations."""

    data: list[ConcentrationEntry]
    """list to hold the concentration and time entry boxes."""

    main_layout: QGridLayout
    """Main layout of the widget."""

    add_concentration_button: QPushButton
    """Button to add a concentration entry."""

    del_concentration_button: QPushButton
    """Button to remove a concentration entry."""

    def __init__(
        self: Self,
        parent: QWidget | None = None,
        f: Qt.WindowType = Qt.WindowType.Widget,
    ) -> None:
        """Widget to allow user to enter a list of concentrations."""
        super().__init__(parent, f)

        # list to hold the concentration and time entry boxes
        self.data = []

        # Main layout of the widget
        self.main_layout = QGridLayout(self)

        # Buttons to add or remove concentration entries
        self.add_concentration_button = QPushButton("Add Concentration")
        self.add_concentration_button.clicked.connect(self.add_concentration)
        self.del_concentration_button = QPushButton("Remove Concentration")
        self.del_concentration_button.clicked.connect(self.del_concentartion)

        # Adds the buttons to the layout
        self.main_layout.addWidget(self.add_concentration_button, 0, 0, 1, -1)
        self.main_layout.addWidget(self.del_concentration_button, 1, 0, 1, -1)

    @Slot()
    def add_concentration(self: Self) -> None:
        """Add boxes to enter another concentration."""
        # Creates the entry boxes
        concentration = QLineEdit()
        time = QLineEdit()

        # Adds validators to the boxes so that only numbers can be entered
        concentration.setValidator(QDoubleValidator())
        time.setValidator(QDoubleValidator())

        # Sets prompt text for the boxes
        concentration.setPlaceholderText("Concentration (M)")
        time.setPlaceholderText("Time (s)")

        # Adjusts minimum width so that the prompt can always be seen
        concentration.setMinimumWidth(concentration.sizeHint().width())

        # Gets the row that this line needs to be added to
        row = len(self.data)

        # Removes the buttons from the layout
        self.main_layout.removeWidget(self.add_concentration_button)
        self.main_layout.removeWidget(self.del_concentration_button)

        # Adds the entry boxes to the layout
        self.main_layout.addWidget(concentration, row, 0)
        self.main_layout.addWidget(time, row, 1)

        # Adds the buttons back in the layout in their new spots
        self.main_layout.addWidget(self.add_concentration_button, row + 1, 0, 1, -1)
        self.main_layout.addWidget(self.del_concentration_button, row + 2, 0, 1, -1)

        # Stores the entry boxes
        self.data.append(ConcentrationEntry(time, concentration))

    @Slot()
    def del_concentartion(self: Self) -> None:
        """Remove a concentration from the list."""
        # Checks to make sure there is a concentration to remove
        if self.data:
            # Gets the boxes to be removed
            time, concentration = self.data.pop()

            # Removes the boxes from the widget
            self.main_layout.removeWidget(concentration)
            self.main_layout.removeWidget(time)

            # Hides the boxes, should hopfully be deleted by the GC eventually
            concentration.hide()
            time.hide()

            # Should maybe move the buttons, but the row with no more widgets seems to
            # not render at all, so you can't tell they're not on the right row, and
            # they'll be moved if another row is added.

    def clear(self: Self) -> None:
        """Clear all user input."""
        while self.data:
            self.del_concentartion()

    def sizeHint(self: Self) -> QSize:  # noqa: N802
        """Override default size to be smaller."""
        return self.minimumSize()

    def output(self: Self) -> str:
        """Output a string in the format needed by TraceDrawer."""
        # Concentrations are separated by semicolons
        return ";".join(concentration.output() for concentration in self.data)

    def from_string(self: Self, string: str) -> None:
        """Read concentrations from a string."""
        # Concentrations are separated by semicolons
        concentrations = string.split(";")

        # If there are any concentrations we replace the current concentration with them
        if concentrations != [""]:
            self.clear()
            for concentration in concentrations:
                self.add_concentration()
                self.data[-1].from_string(concentration)


# Type variable for a type that can be used as a key to a dictionary
KeyType = TypeVar("KeyType", bound=Hashable, contravariant=True)


class CurveOutput(NamedTuple, Generic[KeyType]):
    """Class to hold output of CurveMetadata."""

    ligand: dict[KeyType, str]
    """Dictionary with the ligand field name and value in it."""

    target: dict[KeyType, str]
    """Dictionary with the target field name and value in it."""

    concentrations: dict[KeyType, str]
    """Dictionary with the concentration name and value in it."""


class CurveMetadata(NamedTuple):
    """Class to hold widgets for entering curve metadata."""

    ligand: QLineEdit
    """Ligand entry box."""

    target: QLineEdit
    """Target entry box."""

    concentrations: Concentrations
    """Concentrations entry widget."""

    name: str
    """Name of the curve."""

    def output(self: Self, field: KeyType, value: KeyType) -> CurveOutput[KeyType]:
        """Output metadata for a curve as a tuple of dictionaries.

        The field and value args are the keys of the dictionary that
        will map to the field name and value respectively.
        """
        # Gets the metadata
        ligand = self.ligand.text()
        target = self.target.text()
        concentrations = self.concentrations.output()

        # If a value is missing, we ommit the field as well
        return CurveOutput(
            ligand={
                field: "Curve ligand",
                value: ligand,
            }
            if ligand
            else {},
            target={
                field: "Curve target",
                value: target,
            }
            if target
            else {},
            concentrations={
                field: "Curve concentration (M)",
                value: concentrations,
            }
            if concentrations
            else {},
        )

    def from_string(self: Self, ligand: str, target: str, concentrations: str) -> None:
        """Read curve metadata from strings."""
        if ligand:
            self.ligand.setText(ligand)

        if target:
            self.target.setText(target)

        self.concentrations.from_string(concentrations)


class CurveTableOutput(NamedTuple, Generic[KeyType]):
    """Iterable object holding dictionaries wwith the metadata for curves."""

    number: dict[KeyType, str]
    """The number of the curves."""

    name: dict[KeyType, str]
    """The name of the curves."""

    kind: dict[KeyType, str]
    """The type of the curves, TraceDrawer says to always put "Cuvre" here."""

    ligand: dict[KeyType, str]
    """The lignads of the curves."""

    concentrations: dict[KeyType, str]
    """The concentrations of the curves."""

    target: dict[KeyType, str]
    """The target of the curves."""

    description: dict[KeyType, str]
    """The description of the curves."""

    header: dict[KeyType, str]
    """Header for each curve, is always "X\tY"."""


class CurveTable(QWidget):
    """Widget to allow user to enter metadata for each curve."""

    data: list[CurveMetadata]
    """Holds a widget for each curve to be included in the metadata."""

    main_layout: QGridLayout
    """The widget's main layout."""

    def __init__(
        self: Self,
        channels: list[str],
        parent: QWidget | None = None,
        f: Qt.WindowType = Qt.WindowType.Widget,
    ) -> None:
        """Widget to allow user to enter metadata for each curve."""
        super().__init__(parent, f)

        # list to hold properties for each curve
        self.data = []

        # Main layout of the widget
        self.main_layout = QGridLayout(self)

        # Adds  column for each channel
        for i, channel in enumerate(channels):
            # Creates the widgets to enter metadata
            ligand = QLineEdit()
            target = QLineEdit()
            concentrations = Concentrations()
            name = f"Channel {channel.capitalize()}"

            # Sets prompts for the LineEdits
            ligand.setPlaceholderText("Ligand")
            target.setPlaceholderText("Target")

            # Adds the widgets to the layout in the current column
            self.main_layout.addWidget(QLabel(name), 0, i)
            self.main_layout.addWidget(ligand, 1, i)
            self.main_layout.addWidget(target, 2, i)
            self.main_layout.addWidget(concentrations, 3, i)

            # Stores the widgets
            self.data.append(CurveMetadata(ligand, target, concentrations, name))

    def clear(self: Self) -> None:
        """Clear user input."""
        for ligand, target, concentration, _ in self.data:
            ligand.clear()
            target.clear()
            concentration.clear()

    def output(
        self: Self,
        columns: Sequence[KeyType],
        name: str,
    ) -> CurveTableOutput[KeyType]:
        """Output metadata for all curves as an iterator of dictionaries.

        The columns argument is the keys of the columns for the dictionary
        in order, and must be twice as long as the list of curves.
        """
        if len(columns) != 2 * len(self.data):
            msg = f"Expected {2 * len(self.data)} columns, found {len(columns)}"
            raise ValueError(msg)

        out: CurveTableOutput[KeyType] = CurveTableOutput(
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
        )

        for i, curve in enumerate(self.data):
            # Each curve gets 2 columns in the output file
            field = columns[2 * i]
            value = columns[2 * i + 1]

            # Adds generated metadata
            out.number[field] = "Curve"
            out.number[value] = str(i + 1)

            out.name[field] = "Curve name"
            out.name[value] = curve.name

            out.kind[field] = "Curve type"
            out.kind[value] = "Curve"

            out.description[field] = "Curve description"
            out.description[value] = f"{name} for {curve.name}"

            out.header[field] = "X"
            out.header[value] = "Y"

            # Adds metadata given by user
            curve_metadata = curve.output(field, value)
            out.ligand.update(curve_metadata.ligand)
            out.target.update(curve_metadata.target)
            out.concentrations.update(curve_metadata.concentrations)

        return out

    def from_file(
        self: Self,
        reader: csv.DictReader,  # type: ignore[type-arg]
        columns: Sequence[KeyType],
    ) -> None:
        """Read in curve metadata from file."""
        if len(columns) != 2 * len(self.data):
            msg = f"Expected {2 * len(self.data)} columns, found {len(columns)}"
            raise ValueError(msg)

        # Reads lines from file, names starting with underscores are not used
        _number_line = next(reader)
        _name_line = next(reader)
        _type_line = next(reader)
        ligand_line = next(reader)
        concentrations_line = next(reader)
        target_line = next(reader)
        _description_line = next(reader)
        _header_line = next(reader)

        # Updates curev metadata
        for i, curve in enumerate(self.data):
            value = columns[2 * i + 1]
            curve.from_string(
                ligand_line[value],
                target_line[value],
                concentrations_line[value],
            )


class Metadata(QWidget):
    """Let user enter metadata.

    This widget will allow the user to enter metadata that will be added to save files
    so that TraceDrawer can import the files with the meta data.
    """

    channels: list[str]
    """list of channels that curves can come from."""

    main_layout: QFormLayout
    """The widget's main layout."""

    type_input: QLineEdit
    """Entry box for the type (model) of the instrument."""

    id_input: QLineEdit
    """Entry box for the ID (Serial Number) of the instrument."""

    curve_table: CurveTable
    """Widget to allow the user to enter metadata for each curve."""

    def __init__(
        self: Self,
        channels: list[str],
        parent: QWidget | None = None,
        f: Qt.WindowType = Qt.WindowType.Widget,
    ) -> None:
        """Let user enter metadata.

        This widget will allow the user to enter metadata that will be added to save
        files so that TraceDrawer can import the files with the meta data.
        """
        super().__init__(parent, f)

        # Stores the list of channels
        self.channels = channels

        # Main layout
        self.main_layout = QFormLayout(self)

        # Widgets to put in the layout, fields to enter text
        self.type_input = QLineEdit("P4SPR")
        self.id_input = QLineEdit()
        self.curve_table = CurveTable(channels)

        # Puts the widgets in the layout
        self.main_layout.addRow("Instrument Model:", self.type_input)
        self.main_layout.addRow("Instrument ID:", self.id_input)
        self.main_layout.addRow(self.curve_table)

        # Field to indicate wheither to show a prompt when the user saves
        self.show_on_save = True

    def write_tracedrawer_header(
        self: Self,
        writer: csv.DictWriter,  # type: ignore[type-arg]
        fieldnames: Sequence[str],
        name: str,
        references: Collection[float],
    ) -> None:
        """Write metadata header.

        Write a metadata header so that the file can be imported with metadata
        into TraceDrawer.
        """
        if len(references) != len(self.channels):
            msg = f"Expected {len(self.channels)} references, found {len(references)}."
            raise ValueError(msg)

        # The field names gives the position where an entry will be written in the CSV
        # file. So with variable `pos` a dictionary with entry `pos[i]` will be written
        # in the `i`th column of the CSV file.
        pos = fieldnames

        # Gets the current time to use in the metadata
        now = datetime.now(TIME_ZONE)

        # Writes the first bit of meta data which pertains to the whole file.
        # Optional fields are only included if given by the user, otherwise blank lines
        # are written.
        writer.writerows(
            (
                {
                    pos[0]: "Plot name",
                    pos[1]: name,
                },
                {
                    pos[0]: "Plot xlabel",
                    pos[1]: "Time (s)",
                },
                {
                    pos[0]: "Plot ylabel",
                    pos[1]: "RU",
                },
                {
                    pos[0]: "Property Analysis date",
                    pos[1]: str(now),
                },
                {
                    pos[0]: "Property Filename",
                    pos[1]: f"{name} {now:%Y-%m-%d %H:%M}",
                },
                {
                    pos[0]: "Property Instrument id",
                    pos[1]: self.id_input.text(),
                }
                if self.id_input.text()
                else {},
                {
                    pos[0]: "Property Instrument type",
                    pos[1]: self.type_input.text(),
                }
                if self.type_input.text()
                else {},
                {
                    pos[0]: "Property Software",
                    pos[1]: f"ezControl {SW_VERSION}",
                },
                {
                    pos[0]: "Property Solid support",
                },
                {
                    pos[0]: "Property Reference Levels (nm)",
                    pos[1]: ";".join(map(str, references)),
                },
            ),
        )

        # Writes the curve metadata
        writer.writerows(self.curve_table.output(pos, name))

    @Slot()
    def clear(self: Self) -> None:
        """Clear all user input."""
        self.type_input.setText("P4SPR")
        self.id_input.clear()
        self.curve_table.clear()

    def read_header(
        self: Self,
        reader: csv.DictReader,  # type: ignore[type-arg]
        columns: Sequence[KeyType],
    ) -> list[float]:
        """Read the header from a data file.

        Currently supports one line headers and full tracedrawer headers.
        """
        if len(columns) != 2 * len(self.channels):
            msg = f"Expected {2 * len(self.channels)} columns, found {len(columns)}"
            raise ValueError(msg)

        # The TraceDrawer header consists of fields in the first column
        # and their corresponding value in the next column
        field = columns[0]
        value = columns[1]

        # Gets the first line and check if it's a TraceDrawer header
        # If it isn't, we assume it's a simple one line header
        first_line = next(reader)
        if first_line[field] == "Plot name":
            # Gets the header lines for all curves
            # Names begining with underscores aren't used
            _xlabel_line = next(reader)
            _ylabel_line = next(reader)
            _date_line = next(reader)
            _file_line = next(reader)
            id_line = next(reader)
            type_line = next(reader)
            software_line = next(reader)
            _support_line = next(reader)

            # The original version 2.5.3 didn't save the reference points
            if software_line[value] != "ezControl Version 2.5.3":
                references_line = next(reader)
                references = list(map(float, references_line[value].split(";")))
            else:
                references = [610] * len(self.channels)

            # Updates fields if they are present in the file
            id_number = id_line[value]
            if id_number:
                self.id_input.setText(id_number)

            kind = type_line[value]
            if kind:
                self.type_input.setText(kind)

            self.curve_table.from_file(reader, columns)

            return references

        return []


class MetadataPrompt(QDialog):
    """Dialog window to prompt the user to enter the desired metadata."""

    main_layout: QVBoxLayout
    """The widget's main layout."""

    prompt: QLabel
    """Presents the user wwith information."""

    metadata: Metadata
    """Widget where the user enter metadata."""

    dont_show: QCheckBox
    """Check box to have the prompt window not pop up again."""

    buttons: QHBoxLayout
    """Secondary layout to hold buttons."""

    ok_button: QPushButton
    """Button to accept the given input."""

    clear_button: QPushButton
    """Button to clear the input given so far."""

    def __init__(
        self: Self,
        metadata: Metadata,
        parent: QWidget | None = None,
        f: Qt.WindowType = Qt.WindowType.Widget,
    ) -> None:
        """Dialog window to prompt the user to enter the desired metadata."""
        super().__init__(parent, f)

        # Sets the window title and icon
        self.setWindowTitle("Affinite Instruments")
        self.setWindowIcon(QIcon(":/img/img/affinite2.ico"))

        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)

        # Widgets to be added to the main layout
        self.prompt = QLabel(
            "Please enter the following properties to include them as "
            "metadata in the save file. All fields are optional, just leave any field "
            "blank to exclude it.",
        )
        self.prompt.setWordWrap(True)
        self.metadata = metadata
        self.dont_show = QCheckBox(
            "Do not show this window again (Also available in SPR Setting)",
        )
        self.dont_show.clicked.connect(self.dont_show_again)
        self.buttons = QHBoxLayout()

        # Buttons for clearing input and finishing
        self.ok_button = QPushButton("Okay")
        self.ok_button.clicked.connect(self.accept)
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.metadata.clear)

        # Adds buttons to the button layout
        self.buttons.addWidget(self.clear_button)
        self.buttons.addWidget(self.ok_button)

        # Adds widgets to the main layout
        self.main_layout.addWidget(self.prompt)
        self.main_layout.addWidget(self.metadata)
        self.main_layout.addWidget(self.dont_show)
        self.main_layout.addLayout(self.buttons)

    @Slot(bool)
    def dont_show_again(self: Self, button_checked: bool) -> None:  # noqa: FBT001
        """Set the show on save property."""
        self.metadata.show_on_save = not button_checked


# Test script which will just display the prompt dialog window
if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication

    from settings import CH_LIST

    app = QApplication([])

    metadata = Metadata(CH_LIST)

    propmpt = MetadataPrompt(metadata)
    propmpt.show()

    app.exec()
