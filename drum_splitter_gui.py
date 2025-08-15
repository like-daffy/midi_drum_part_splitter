#!/usr/bin/env python3
"""
Drum Splitter GUI (PyQt6)

Single-file application that splits drum MIDI files into separate parts using
note mappings defined in a YAML configuration. The default configuration is
hard-coded based on the "Organizing notes by markers" output from
superior_drummer_mapping.mid, using Cubase octave numbering (C-2..B8).

Features:
- Drag-and-drop a MIDI file into the window
- Browse and load a custom YAML mapping
- Persist preference to always use the same custom YAML mapping
- Preview 6 parts (Kick, Snare, Hihat, Ride, Crash, Tom) as draggable tiles
- Files are NOT saved automatically; drag a tile to Explorer/Finder to create it
- Disable a tile if the part would be empty
- Preserve pitch and velocity of notes

Packagable with PyInstaller on macOS and Windows.
"""

from __future__ import annotations

import os
import sys
import traceback
import tempfile
from typing import Dict, List, Set, Tuple, Optional

import mido
from PyQt6 import QtCore, QtGui, QtWidgets
import math
import yaml


# -----------------------------
# Default YAML configuration
# -----------------------------

DEFAULT_MAPPING_YAML = """
# Drum parts mapping using Cubase octave numbering (C-2..B8)
# Each part lists the note names that belong to that drum piece.
drum_parts:
  Kick:
    - A#0
    - B0
    - C1
  Snare:
    - F#-2
    - A0
    - C#1
    - D1
    - D#1
    - E1
    - F#3
    - G3
    - G#3
    - A3
    - A#3
    - B3
    - E4
    - F8
    - F#8
    - G8
  Hihat:
    - G-2
    - G#-2
    - A-2
    - A#-2
    - B-2
    - C-1
    - C#-1
    - D-1
    - D#-1
    - E-1
    - F-1
    - F#-1
    - G-1
    - G#-1
    - A-1
    - A#-1
    - B-1
    - C0
    - C#0
    - D0
    - F#1
    - G#1
    - A#1
    - C3
    - C#3
    - D3
    - D#3
    - E3
    - F3
    - B7
    - C8
    - C#8
    - D8
    - D#8
    - E8
  Ride:
    - F0
    - F#0
    - D#2
    - F2
    - B2
    - F7
    - F#7
    - G7
    - G#7
    - A7
    - A#7
  Crash:
    - D#0
    - E0
    - G0
    - G#0
    - C#2
    - D2
    - E2
    - F#2
    - G2
    - G#2
    - A2
    - A#2
    - B4
    - C5
    - C#5
    - D5
    - D#5
    - E5
    - F5
    - F#5
    - G5
    - G#5
    - A5
    - A#5
    - B5
    - C6
    - C#6
    - D6
    - D#6
    - E6
    - F6
    - F#6
    - G6
    - G#6
    - A6
    - A#6
    - B6
    - C7
    - C#7
    - D7
    - D#7
    - E7
  Tom:
    - F1
    - G1
    - A1
    - B1
    - C2
    - C4
    - C#4
    - D4
    - D#4
    - F4
    - F#4
    - G4
    - G#4
    - A4
    - A#4
"""


# -----------------------------
# MIDI utility functions (Cubase numbering)
# -----------------------------

NOTE_NAME_TO_SEMITONE = {
    'C': 0, 'C#': 1, 'DB': 1,
    'D': 2, 'D#': 3, 'EB': 3,
    'E': 4,
    'F': 5, 'F#': 6, 'GB': 6,
    'G': 7, 'G#': 8, 'AB': 8,
    'A': 9, 'A#': 10, 'BB': 10,
    'B': 11,
}


def midi_note_to_name(note_number: int) -> str:
    """Convert MIDI note number to name using Cubase octave numbering (C-2..B8)."""
    note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    octave = (note_number // 12) - 2
    note = note_names[note_number % 12]
    return f"{note}{octave}"


def midi_name_to_note(name: str) -> int:
    """Convert note name (e.g., 'A#0') to MIDI note number using Cubase numbering.

    Accepts sharps (#) and flats (b). Returns -1 if parsing fails or out of range.
    """
    if not name:
        return -1
    s = name.strip().upper().replace('♯', '#').replace('♭', 'B')
    # Normalize flats: e.g., Bb -> A#
    # We'll split letter+accidental and octave.
    try:
        # Find last occurrence of '-' or digit sequence as octave
        idx = len(s) - 1
        while idx >= 0 and (s[idx].isdigit() or s[idx] == '-'):
            idx -= 1
        letter = s[:idx + 1]
        octave_str = s[idx + 1:]
        if not octave_str:
            return -1
        octave = int(octave_str)

        # Map flats to sharps
        if len(letter) == 2 and letter[1] == 'B' and letter not in ('B', 'BB'):
            # It's a flat form like Db, Eb, Gb, Ab, Bb
            pass  # handled in NOTE_NAME_TO_SEMITONE via 'DB', 'EB', etc.

        semitone = NOTE_NAME_TO_SEMITONE.get(letter, None)
        if semitone is None:
            return -1

        midi_note = (octave + 2) * 12 + semitone
        if 0 <= midi_note <= 127:
            return midi_note
        return -1
    except Exception:
        return -1


# -----------------------------
# YAML mapping loader
# -----------------------------

def load_mapping_from_yaml(yaml_text: str) -> Dict[str, Set[int]]:
    """Parse YAML mapping text into a dict of part name -> set of MIDI note numbers."""
    try:
        data = yaml.safe_load(yaml_text) or {}
    except Exception as exc:
        raise ValueError(f"Failed to parse YAML: {exc}") from exc

    if not isinstance(data, dict) or 'drum_parts' not in data:
        raise ValueError("YAML must contain a 'drum_parts' mapping")

    drum_parts = data['drum_parts']
    if not isinstance(drum_parts, dict) or not drum_parts:
        raise ValueError("'drum_parts' must be a non-empty mapping of part -> notes")

    result: Dict[str, Set[int]] = {}
    for part_name, note_list in drum_parts.items():
        if not isinstance(note_list, list):
            raise ValueError(f"Part '{part_name}' must list note names")
        midi_notes: Set[int] = set()
        for note_name in note_list:
            midi_value = midi_name_to_note(str(note_name))
            if midi_value < 0:
                raise ValueError(f"Invalid note name '{note_name}' in part '{part_name}'")
            midi_notes.add(midi_value)
        result[str(part_name)] = midi_notes
    return result


def find_duplicate_notes(mapping: Dict[str, Set[int]]) -> Dict[int, List[str]]:
    """Return dict of midi_note -> list of part names where duplicates occur (len>1)."""
    note_to_parts: Dict[int, List[str]] = {}
    for part_name, note_set in mapping.items():
        for note in note_set:
            note_to_parts.setdefault(note, []).append(part_name)
    return {n: parts for n, parts in note_to_parts.items() if len(parts) > 1}


def format_duplicate_notes(dups: Dict[int, List[str]]) -> str:
    lines: List[str] = []
    for note_num in sorted(dups.keys()):
        name = midi_note_to_name(note_num)
        parts = ", ".join(sorted(dups[note_num]))
        lines.append(f"{name}: {parts}")
    return "\n".join(lines)


# -----------------------------
# MIDI splitting logic
# -----------------------------

MetaNamesToKeep = {
    'set_tempo', 'time_signature', 'key_signature', 'smpte_offset',
    'track_name', 'end_of_track', 'instrument_name', 'marker', 'cue_marker',
}


def split_midi_by_mapping(input_path: str, mapping: Dict[str, Set[int]]) -> Dict[str, mido.MidiFile]:
    """Split a MIDI file into multiple mido.MidiFile objects keyed by part name.

    - Preserves timing by accumulating delta time while skipping messages.
    - Preserves pitch and velocity of notes.
    - Copies useful meta messages.
    """
    try:
        original = mido.MidiFile(input_path)
    except Exception as exc:
        raise ValueError(f"Unrecognizable MIDI file: {exc}") from exc

    outputs: Dict[str, mido.MidiFile] = {}
    # Prepare MidiFile per part name
    for part_name in mapping.keys():
        outputs[part_name] = mido.MidiFile(ticks_per_beat=original.ticks_per_beat)

    # For each output, we mirror the original number of tracks,
    # and filter messages based on note membership per part.
    for part_name, note_set in mapping.items():
        out_mid = outputs[part_name]
        part_has_notes = False

        for track in original.tracks:
            new_track = mido.MidiTrack()
            out_mid.tracks.append(new_track)
            time_accumulator = 0

            for msg in track:
                time_accumulator += msg.time

                if msg.is_meta:
                    # Keep selected meta messages
                    if msg.type in MetaNamesToKeep:
                        copied = msg.copy(time=time_accumulator)
                        new_track.append(copied)
                        time_accumulator = 0
                    continue

                if msg.type in ('note_on', 'note_off'):
                    if msg.note in note_set:
                        copied = msg.copy(time=time_accumulator)
                        new_track.append(copied)
                        time_accumulator = 0
                        if msg.type == 'note_on' and getattr(msg, 'velocity', 0) > 0:
                            part_has_notes = True
                    # else: accumulate time only (skip message)
                else:
                    # Non-note MIDI messages: we skip them but preserve timing
                    # Add your own pass-through list here if needed.
                    pass

            # Ensure end_of_track exists and timing is closed
            new_track.append(mido.MetaMessage('end_of_track', time=time_accumulator))

        # Attach a flag on the MidiFile object to know if it has notes
        setattr(out_mid, '_has_notes', part_has_notes)

    return outputs


def save_split_midis(base_input_path: str, splits: Dict[str, mido.MidiFile]) -> List[str]:
    """Save split MidiFile objects next to the input file.

    Returns a list of saved file paths. Empty parts (no note events) are not saved.
    """
    saved_paths: List[str] = []
    folder = os.path.dirname(base_input_path)
    base_name = os.path.splitext(os.path.basename(base_input_path))[0]

    for part_name, mid in splits.items():
        has_notes = bool(getattr(mid, '_has_notes', False))
        if not has_notes:
            continue
        output_name = f"{base_name}-{part_name.lower()}.mid"
        output_path = os.path.join(folder, output_name)
        try:
            mid.save(output_path)
            # Double-check size
            if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                # Remove empty file if any
                if os.path.exists(output_path):
                    os.remove(output_path)
                continue
            saved_paths.append(output_path)
        except Exception:
            # If saving fails for any reason, best-effort cleanup
            try:
                if os.path.exists(output_path):
                    os.remove(output_path)
            except Exception:
                pass
            raise

    return saved_paths


# -----------------------------
# GUI Components
# -----------------------------

class OutputPlaceholder(QtWidgets.QWidget):
    """Placeholder widget shown in output section when no results are available."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(200)

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)

        rect = self.rect().adjusted(20, 20, -20, -20)
        pen = QtGui.QPen(QtGui.QColor('#666'))
        pen.setStyle(QtCore.Qt.PenStyle.DotLine)
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, 12, 12)

        # Helper text
        font = painter.font()
        font.setPointSize(16)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QtGui.QColor('#666'))
        painter.drawText(
            rect,
            QtCore.Qt.AlignmentFlag.AlignCenter,
            'Output Result\n\nClick "Proceed" to split MIDI file',
        )
        painter.end()


class DragDropList(QtWidgets.QListWidget):
    filesChanged = QtCore.pyqtSignal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setAlternatingRowColors(True)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.allow_click_browse: bool = True

    def sizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(600, 140)

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        super().paintEvent(event)
        # When empty, show a rounded dotted outline and centered helper text
        if self.count() == 0:
            painter = QtGui.QPainter(self.viewport())
            painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)

            rect = self.viewport().rect().adjusted(10, 10, -10, -10)
            pen = QtGui.QPen(QtGui.QColor('#888'))
            pen.setStyle(QtCore.Qt.PenStyle.DotLine)
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect, 12, 12)

            # Helper text
            font = painter.font()
            font.setPointSize(14)
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QtGui.QColor('#888'))
            painter.drawText(
                rect,
                QtCore.Qt.AlignmentFlag.AlignCenter,
                'Drag & drop a MIDI file here\n(or click to browse)',
            )
            painter.end()

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QtGui.QDragMoveEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QtGui.QDropEvent) -> None:
        if not event.mimeData().hasUrls():
            event.ignore()
            return
        # Single-file mode: take the first valid MIDI file, replace any existing item
        for url in event.mimeData().urls():
            local_path = url.toLocalFile()
            if not local_path:
                continue
            if not local_path.lower().endswith(('.mid', '.midi')):
                continue
            if not os.path.exists(local_path):
                continue
            self.clear()
            self.addItem(local_path)
            self.filesChanged.emit()
            self.allow_click_browse = False
            break

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.LeftButton and self.allow_click_browse:
            start_dir = os.path.dirname(self.item(0).text()) if self.count() > 0 else os.getcwd()
            path, _ = QtWidgets.QFileDialog.getOpenFileName(
                self,
                "Select MIDI File",
                start_dir,
                "MIDI Files (*.mid *.midi)"
            )
            if path:
                self.clear()
                self.addItem(path)
                self.filesChanged.emit()
                self.allow_click_browse = False
                event.accept()
                return
        super().mousePressEvent(event)

    def addFiles(self, paths: List[str]) -> None:
        # Single-file mode: take first valid path only
        for p in paths:
            if p.lower().endswith(('.mid', '.midi')) and os.path.exists(p):
                self.clear()
                self.addItem(p)
                self.filesChanged.emit()
                self.allow_click_browse = False
                break

    def resetToEmpty(self) -> None:
        self.clear()
        self.allow_click_browse = True
        self.filesChanged.emit()

    def removeSelected(self) -> None:
        for item in self.selectedItems():
            row = self.row(item)
            self.takeItem(row)
        self.filesChanged.emit()

    def currentFiles(self) -> List[str]:
        return [self.item(i).text() for i in range(self.count())]


class MainWindow(QtWidgets.QMainWindow):
    ORG_NAME = "MIDIUtilities"
    APP_NAME = "DrumSplitter"

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("MIDI Drum Splitter")
        self.setMinimumSize(780, 700)
        self._mapping_cache: Dict[str, Set[int]] | None = None

        # Persistent settings
        self.settings = QtCore.QSettings(self.ORG_NAME, self.APP_NAME)

        # Apply blue sea theme
        self._apply_blue_sea_theme()

        self._build_ui()
        self._load_preferences()
        self._load_effective_mapping()
        self._temp_dir_results: Optional[tempfile.TemporaryDirectory] = None

    # -------- Theme Application --------
    def _apply_blue_sea_theme(self) -> None:
        """Apply the Blue Sea theme without reading external files.

        We embed the palette from .superdesign/design_iterations/blue_sea_theme.css
        (OKLCH variables) and convert to sRGB hex for a valid Qt Style Sheet.
        """

        # Embedded OKLCH variables from .superdesign/design_iterations/blue_sea_theme.css
        css_vars = {
            'background': 'oklch(0.2784 0.1000 258.0)',
            'foreground': 'oklch(0.9500 0 0)',
            'card': 'oklch(0.3451 0.0800 258.0)',
            'card-foreground': 'oklch(0.9500 0 0)',
            'primary': 'oklch(0.6510 0.1500 255.0)',
            'primary-foreground': 'oklch(1.0000 0 0)',
            'secondary': 'oklch(0.8510 0.0500 255.0)',
            'secondary-foreground': 'oklch(0.2000 0 0)',
            'muted': 'oklch(0.4118 0.0600 258.0)',
            'muted-foreground': 'oklch(0.8000 0 0)',
            'accent': 'oklch(0.9529 0.0800 55.0)',
            'accent-foreground': 'oklch(0.2000 0 0)',
            'border': 'oklch(0.4118 0.0600 258.0)',
            'ring': 'oklch(0.6510 0.1500 255.0)'
        }

        def oklch_to_srgb_hex(l_val: float, c_val: float, h_deg: float) -> str:
            h_rad = math.radians(h_deg)
            a = math.cos(h_rad) * c_val
            b = math.sin(h_rad) * c_val

            l_ = l_val + 0.3963377774 * a + 0.2158037573 * b
            m_ = l_val - 0.1055613458 * a - 0.0638541728 * b
            s_ = l_val - 0.0894841775 * a - 1.2914855480 * b

            l3 = l_ ** 3
            m3 = m_ ** 3
            s3 = s_ ** 3

            r_lin = (+4.0767416621 * l3) + (-3.3077115913 * m3) + (0.2309699292 * s3)
            g_lin = (-1.2684380046 * l3) + (+2.6097574011 * m3) + (-0.3413193965 * s3)
            b_lin = (-0.0041960863 * l3) + (-0.7034186147 * m3) + (+1.7076147010 * s3)

            def lin_to_srgb(x: float) -> float:
                if x <= 0.0031308:
                    return 12.92 * x
                return 1.055 * (max(x, 0.0) ** (1 / 2.4)) - 0.055

            r = min(max(lin_to_srgb(r_lin), 0.0), 1.0)
            g = min(max(lin_to_srgb(g_lin), 0.0), 1.0)
            b = min(max(lin_to_srgb(b_lin), 0.0), 1.0)

            return '#%02X%02X%02X' % (int(round(r * 255)), int(round(g * 255)), int(round(b * 255)))

        def parse_oklch_str(s: str) -> str:
            try:
                inner = s[s.index('(') + 1:s.index(')')]
                parts = inner.replace('/', ' ').replace(',', ' ').split()
                l_val = float(parts[0])
                c_val = float(parts[1])
                h_deg = float(parts[2])
                return oklch_to_srgb_hex(l_val, c_val, h_deg)
            except Exception:
                # Fallback to a safe blue
                return '#1976D2'

        # Resolve all colors to sRGB hex
        COL = {name: parse_oklch_str(val) for name, val in css_vars.items()}

        qss = f"""
        /* Embedded Blue Sea Theme (converted from OKLCH to sRGB) */
        QMainWindow {{
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                       stop: 0 {COL['background']},
                                       stop: 1 {COL['card']});
            color: {COL['foreground']};
            font-family: Inter, 'Segoe UI', Arial, sans-serif;
        }}

        QWidget {{
            background: transparent;
            color: {COL['foreground']};
            font-family: Inter, 'Segoe UI', Arial, sans-serif;
            font-size: 13px;
        }}

        QLabel {{
            color: {COL['muted-foreground']};
            background: transparent;
            font-weight: 500;
        }}

        QPushButton {{
            background: {COL['primary']};
            border: 2px solid {COL['border']};
            border-radius: 8px;
            color: {COL['primary-foreground']};
            font-weight: bold;
            font-size: 14px;
            padding: 10px 20px;
            min-height: 20px;
        }}

        QPushButton:hover {{
            border: 2px solid {COL['ring']};
        }}

        QPushButton:default {{
            background: {COL['accent']};
            border: 2px solid {COL['accent']};
            color: {COL['accent-foreground']};
            font-size: 16px;
            font-weight: bold;
        }}

        QLineEdit {{
            background: {COL['muted']};
            border: 2px solid {COL['ring']};
            border-radius: 8px;
            padding: 8px 12px;
            color: {COL['foreground']};
            font-size: 14px;
        }}

        QLineEdit:focus {{
            border: 2px solid {COL['primary']};
        }}

        QCheckBox {{
            color: {COL['muted-foreground']};
            font-weight: 500;
            spacing: 8px;
        }}

        QCheckBox::indicator {{
            width: 18px;
            height: 18px;
            border: 2px solid {COL['primary']};
            border-radius: 4px;
            background: {COL['muted']};
        }}

        QCheckBox::indicator:checked {{
            background: {COL['primary']};
            border: 2px solid {COL['primary']};
        }}

        QListWidget {{
            border: none;
            background: transparent;
            font-size: 14px;
            font-weight: bold;
            color: {COL['primary']};
            padding: 8px;
            border-radius: 8px;
        }}

        QListWidget::item {{
            background: {COL['card']};
            border: 2px solid {COL['primary']};
            border-radius: 8px;
            padding: 16px;
            margin: 6px;
            font-weight: bold;
            color: {COL['card-foreground']};
        }}

        QListWidget::item:selected {{
            background: {COL['secondary']};
            border: 3px solid {COL['primary']};
            color: {COL['secondary-foreground']};
        }}

        QMessageBox {{
            background: {COL['card']};
            color: {COL['foreground']};
        }}

        QMessageBox QLabel {{
            color: {COL['muted-foreground']};
            font-size: 14px;
        }}
        """

        self.setStyleSheet(qss)

    # -------- UI Construction --------
    def _build_ui(self) -> None:
        central = QtWidgets.QWidget()
        main_layout = QtWidgets.QVBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # Create input section (independent widget)
        self.input_section = self._create_input_section()
        main_layout.addWidget(self.input_section, 0)

        # Create output section (independent widget)
        self.output_section = self._create_output_section()
        main_layout.addWidget(self.output_section, 1)

        # Create about section (independent widget)
        self.about_section = self._create_about_section()
        main_layout.addWidget(self.about_section, 0)

        self.setCentralWidget(central)

        # Connect signals
        self.btn_browse_yaml.clicked.connect(self._on_browse_yaml)
        self.btn_use_default_yaml.clicked.connect(self._on_use_default_yaml)
        self.btn_proceed.clicked.connect(self._on_proceed)
        self.drop_list.filesChanged.connect(self._on_input_files_changed)
        self.btn_select_again.clicked.connect(self._on_select_again)
        self.chk_use_same.toggled.connect(self._on_use_same_toggled)
        self.yaml_path_edit.textChanged.connect(self._on_yaml_path_changed)
        self.btn_save_template.clicked.connect(self._on_save_template)

    def _create_input_section(self) -> QtWidgets.QWidget:
        """Create the independent input section with intro, drag-drop, buttons, and settings."""
        input_widget = QtWidgets.QWidget()
        input_widget.setObjectName("InputSection")
        input_widget.setStyleSheet("QWidget#InputSection { background: rgba(255,255,255,0.02); border-radius: 12px; padding: 8px; }")
        
        layout = QtWidgets.QVBoxLayout(input_widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Instructions
        intro = QtWidgets.QLabel(
            "Drag-and-drop ONE MIDI file below (or click the area to browse), optionally pick a custom YAML mapping,\n"
            "then click Proceed to preview 6 parts you can drag out to Explorer/Finder to save."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        # Drag-and-drop list widget (shorter height)
        self.drop_list = DragDropList()
        self.drop_list.setMaximumHeight(100)
        layout.addWidget(self.drop_list, 0)

        # Proceed button centered
        proceed_row = QtWidgets.QHBoxLayout()
        proceed_row.addStretch(1)
        self.btn_select_again = QtWidgets.QPushButton("Select Again")
        self.btn_select_again.setFixedWidth(160)
        self.btn_select_again.setEnabled(False)
        self.btn_select_again.setVisible(False)
        proceed_row.addWidget(self.btn_select_again)
        self.btn_proceed = QtWidgets.QPushButton("Proceed")
        self.btn_proceed.setDefault(True)
        self.btn_proceed.setFixedWidth(160)
        proceed_row.addWidget(self.btn_proceed)
        proceed_row.addStretch(1)
        layout.addLayout(proceed_row)

        # YAML file picker row
        yaml_row = QtWidgets.QHBoxLayout()
        self.yaml_path_edit = QtWidgets.QLineEdit()
        self.yaml_path_edit.setPlaceholderText("Custom YAML mapping path (optional)")
        self.btn_browse_yaml = QtWidgets.QPushButton("Browse…")
        self.btn_use_default_yaml = QtWidgets.QPushButton("Default")
        yaml_row.addWidget(self.yaml_path_edit, 1)
        yaml_row.addWidget(self.btn_browse_yaml)
        yaml_row.addWidget(self.btn_use_default_yaml)
        layout.addLayout(yaml_row)

        # Preference checkbox and export template row
        pref_row = QtWidgets.QHBoxLayout()
        self.chk_use_same = QtWidgets.QCheckBox("Next time use the same configuration")
        pref_row.addWidget(self.chk_use_same)
        pref_row.addStretch(1)

        self.lbl_export_hint = QtWidgets.QLabel("You can export")
        pref_row.addWidget(self.lbl_export_hint)

        self.btn_save_template = QtWidgets.QPushButton("Default Template (.yaml)")
        pref_row.addWidget(self.btn_save_template)
        layout.addLayout(pref_row)

        return input_widget

    def _create_output_section(self) -> QtWidgets.QWidget:
        """Create the independent output section for results."""
        output_widget = QtWidgets.QWidget()
        output_widget.setObjectName("OutputSection")
        output_widget.setStyleSheet("QWidget#OutputSection { background: rgba(255,255,255,0.02); border-radius: 12px; padding: 8px; }")
        
        layout = QtWidgets.QVBoxLayout(output_widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Output placeholder (shows initially)
        self.output_placeholder = OutputPlaceholder()
        layout.addWidget(self.output_placeholder, 1)

        # Results area (in-window, hidden initially)
        self.results_scroll_area = QtWidgets.QScrollArea()
        self.results_scroll_area.setWidgetResizable(True)
        self.results_scroll_area.setVisible(False)

        self._results_panel = QtWidgets.QWidget()
        self._results_panel_layout = QtWidgets.QVBoxLayout(self._results_panel)
        self._results_panel_layout.setContentsMargins(0, 0, 0, 0)
        self._results_panel_layout.setSpacing(12)

        self.results_header = QtWidgets.QLabel()
        self.results_header.setText('<span style="font-size:14px; font-weight:800; color:#ffffff; background-color:#42A5F5; padding:8px 12px; border-radius:10px;">Drag out to save</span>')
        self.results_header.setWordWrap(False)
        self.results_header.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        self._results_panel_layout.addWidget(self.results_header)

        self.results_row = QtWidgets.QHBoxLayout()
        self.results_row.setSpacing(12)
        self._results_row_container = QtWidgets.QWidget()
        self._results_row_container.setLayout(self.results_row)
        self._results_panel_layout.addWidget(self._results_row_container)

        self.results_scroll_area.setWidget(self._results_panel)
        layout.addWidget(self.results_scroll_area, 1)

        return output_widget

    def _create_about_section(self) -> QtWidgets.QWidget:
        """Create the independent about section."""
        about_widget = QtWidgets.QWidget()
        about_widget.setObjectName("AboutSection")
        about_widget.setStyleSheet("QWidget#AboutSection { background: rgba(255,255,255,0.02); border-radius: 12px; padding: 8px; }")

        layout = QtWidgets.QVBoxLayout(about_widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(6)

        info = QtWidgets.QLabel('<a href="https://x.com/sochan_life" style="color: #bbb; text-decoration: none;">Copyright (c) 2025 Sochan, X(twitter): @sochan_life</a>')
        info.setStyleSheet("font-size: 14px;")
        info.setOpenExternalLinks(True)
        layout.addWidget(info)

        return about_widget

    # -------- Preferences --------
    def _load_preferences(self) -> None:
        use_same = self.settings.value('use_custom_config', False, type=bool)
        custom_path = self.settings.value('custom_config_path', '', type=str)
        self.chk_use_same.setChecked(bool(use_same))
        if custom_path:
            self.yaml_path_edit.setText(custom_path)

    def _persist_preferences(self) -> None:
        self.settings.setValue('use_custom_config', self.chk_use_same.isChecked())
        self.settings.setValue('custom_config_path', self.yaml_path_edit.text().strip())

    def _on_use_same_toggled(self, checked: bool) -> None:
        self._persist_preferences()

    def _on_yaml_path_changed(self) -> None:
        if self.chk_use_same.isChecked():
            self._persist_preferences()
        # Invalidate mapping cache so next run reloads
        self._mapping_cache = None

    # -------- YAML Handling --------
    def _get_effective_yaml_text(self) -> str:
        path = self.yaml_path_edit.text().strip()
        if self.chk_use_same.isChecked() and path:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as exc:
                QtWidgets.QMessageBox.warning(self, "YAML Error", f"Failed to read custom YAML:\n{exc}\nUsing default mapping instead.")
        return DEFAULT_MAPPING_YAML

    def _load_effective_mapping(self) -> None:
        is_custom = self.chk_use_same.isChecked() and bool(self.yaml_path_edit.text().strip())
        yaml_text = self._get_effective_yaml_text()
        try:
            mapping = load_mapping_from_yaml(yaml_text)
        except Exception as exc:
            self._mapping_cache = None
            QtWidgets.QMessageBox.critical(self, "YAML Error", f"Invalid YAML mapping:\n{exc}")
            # Clear custom path and uncheck reuse when custom config fails
            if is_custom:
                self.yaml_path_edit.setText("")
                self.chk_use_same.setChecked(False)
                self._persist_preferences()
            return

        dups = find_duplicate_notes(mapping)
        if dups:
            details = format_duplicate_notes(dups)
            if is_custom:
                # Custom YAML has duplicates: alert and block proceeding
                QtWidgets.QMessageBox.warning(
                    self,
                    "Duplicate Notes in Mapping",
                    f"The selected YAML contains duplicate notes assigned to multiple parts.\n\n{details}\n\nPlease resolve and try again.",
                )
                self._mapping_cache = None
                # Clear custom path and uncheck reuse when duplicates found
                self.yaml_path_edit.setText("")
                self.chk_use_same.setChecked(False)
                self._persist_preferences()
                return
            else:
                # Default mapping itself has duplicates -> terminate app
                QtWidgets.QMessageBox.critical(
                    self,
                    "Default Mapping Error",
                    f"Default YAML contains duplicate notes (developer fix required):\n\n{details}",
                )
                QtCore.QTimer.singleShot(0, QtWidgets.QApplication.instance().quit)
                self._mapping_cache = None
                return

        self._mapping_cache = mapping

    def _on_browse_yaml(self) -> None:
        start_dir = os.path.dirname(self.yaml_path_edit.text().strip()) if self.yaml_path_edit.text().strip() else os.getcwd()
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select YAML Mapping", start_dir, "YAML Files (*.yml *.yaml)")
        if path:
            self.yaml_path_edit.setText(path)
            self.chk_use_same.setChecked(True)
            self._persist_preferences()
            self._load_effective_mapping()

    def _on_use_default_yaml(self) -> None:
        # Clear custom path, uncheck reuse, and use default mapping immediately
        self.yaml_path_edit.setText("")
        self.chk_use_same.setChecked(False)
        self._persist_preferences()
        self._load_effective_mapping()

    def _on_save_template(self) -> None:
        default_path = os.path.join(os.getcwd(), "default.yaml")
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save Default Mapping Template",
            default_path,
            "YAML Files (*.yaml);;All Files (*)"
        )
        if not path:
            # User canceled; do nothing
            return
        # Ensure filename has .yaml or .yml extension
        base, ext = os.path.splitext(path)
        # Always force .yaml for UX consistency
        if ext.lower() != ".yaml":
            path = base + ".yaml"
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(DEFAULT_MAPPING_YAML)
            QtWidgets.QMessageBox.information(self, "Saved", f"Template saved to:\n{path}")
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Write Error", f"Failed to save template:\n{exc}")

    # -------- Proceed / Splitting --------
    def _on_proceed(self) -> None:
        files = self.drop_list.currentFiles()
        if not files:
            QtWidgets.QMessageBox.information(self, "No File", "Please drag-and-drop ONE MIDI file to proceed.")
            return

        # Load mapping (custom or default)
        self._load_effective_mapping()
        if not self._mapping_cache:
            return

        path = files[0]
        try:
            splits = split_midi_by_mapping(path, self._mapping_cache)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Split Error", f"Failed to split MIDI file:\n{exc}")
            return

        base_name = os.path.splitext(os.path.basename(path))[0]
        self._populate_results(base_name, splits)

    def _on_input_files_changed(self) -> None:
        # Clear previous results when input changes
        self._clear_results()
        # Show/enable Select Again only when a file is attached
        has_file = self.drop_list.count() > 0
        self.btn_select_again.setVisible(has_file)
        self.btn_select_again.setEnabled(has_file)

    def _clear_results(self) -> None:
        # Remove existing widgets from results_row
        while self.results_row.count():
            item = self.results_row.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        # Cleanup previous temporary directory if any
        try:
            if self._temp_dir_results is not None:
                self._temp_dir_results.cleanup()
        except Exception:
            pass
        self._temp_dir_results = None
        # Show placeholder, hide results
        self.output_placeholder.setVisible(True)
        self.results_scroll_area.setVisible(False)

    def _on_select_again(self) -> None:
        # Reset input area to initial state: empty and browse-enabled
        self.drop_list.resetToEmpty()
        self.btn_select_again.setVisible(False)
        self.btn_select_again.setEnabled(False)

    def _populate_results(self, base_name: str, splits: Dict[str, mido.MidiFile]) -> None:
        # Clear previous
        self._clear_results()

        # New temp dir for this result set
        self._temp_dir_results = tempfile.TemporaryDirectory(prefix="drum_split_")

        # Display order of six parts (Crash inserted between Ride and Tom)
        display_order = ["Kick", "Snare", "Hihat", "Ride", "Crash", "Tom"]
        for part in display_order:
            mid = splits.get(part)
            if mid is None:
                tile = PartDragTile(part, mido.MidiFile(), base_name, False, self._temp_dir_results, self)
            else:
                has_notes = bool(getattr(mid, "_has_notes", False))
                tile = PartDragTile(part, mid, base_name, has_notes, self._temp_dir_results, self)
            self.results_row.addWidget(tile, 1)

        # Hide placeholder, show results
        self.output_placeholder.setVisible(False)
        self.results_scroll_area.setVisible(True)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        # Ensure result temp dir is cleaned up on app close
        try:
            if self._temp_dir_results is not None:
                self._temp_dir_results.cleanup()
        except Exception:
            pass
        # If user opted not to reuse the same configuration, clear saved YAML path
        try:
            if not self.chk_use_same.isChecked():
                self.settings.setValue('custom_config_path', '')
        except Exception:
            pass
        super().closeEvent(event)


class PartDragTile(QtWidgets.QFrame):
    """A draggable tile representing one split part. Drag this tile to Explorer/Finder to save."""

    def __init__(self, part_name: str, midi_obj: mido.MidiFile, base_name: str,
                 enabled: bool, temp_dir: tempfile.TemporaryDirectory,
                 parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.part_name = part_name
        self.midi_obj = midi_obj
        self.base_name = base_name
        self.temp_dir = temp_dir
        self._temp_path: str | None = None

        self.setObjectName("PartDragTile")
        self.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        self.setFrameShadow(QtWidgets.QFrame.Shadow.Raised)
        self.setStyleSheet(
            "QFrame#PartDragTile { border: 2px dashed #6aa9e9; border-radius: 8px; max-width: 120px; }"
            "QFrame#PartDragTile[disabled=\"true\"] { border: 2px dashed #777; max-width: 120px; }"
        )

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        title = QtWidgets.QLabel(self.part_name)
        title.setStyleSheet("font-weight: bold; font-size: 16px;")
        layout.addWidget(title, 0, QtCore.Qt.AlignmentFlag.AlignHCenter)

        self.center_label = QtWidgets.QLabel("Drag\nout\nto\nsave")
        self.center_label.setStyleSheet("font-weight: 800; color: #42A5F5; font-size: 14px;")
        self.center_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.center_label, 1)

        self.setEnabled(enabled)
        if not enabled:
            self.center_label.setStyleSheet("")
            self.center_label.setText("Empty")

    def _ensure_temp_file(self) -> str:
        if self._temp_path and os.path.exists(self._temp_path):
            return self._temp_path
        safe_part = self.part_name.lower()
        filename = f"{self.base_name}-{safe_part}.mid"
        out_path = os.path.join(self.temp_dir.name, filename)
        try:
            self.midi_obj.save(out_path)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Export Error", f"Failed to create temporary file for {self.part_name}:\n{exc}")
            raise
        self._temp_path = out_path
        return out_path

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if not self.isEnabled():
            event.ignore()
            return
        if event.button() != QtCore.Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return

        try:
            temp_path = self._ensure_temp_file()
        except Exception:
            return

        mime = QtCore.QMimeData()
        mime.setUrls([QtCore.QUrl.fromLocalFile(temp_path)])

        drag = QtGui.QDrag(self)
        drag.setMimeData(mime)
        pm = QtGui.QPixmap(180, 44)
        pm.fill(QtGui.QColor("#1976D2"))
        painter = QtGui.QPainter(pm)
        painter.setPen(QtGui.QColor("white"))
        painter.setFont(QtGui.QFont("Segoe UI", 10, QtGui.QFont.Weight.Bold))
        painter.drawText(pm.rect(), QtCore.Qt.AlignmentFlag.AlignCenter, f"{self.base_name}-{self.part_name.lower()}.mid")
        painter.end()
        drag.setPixmap(pm)
        drag.exec(QtCore.Qt.DropAction.CopyAction)


class ResultsDialog(QtWidgets.QDialog):
    """Dialog showing draggable sections for split parts."""

    DISPLAY_ORDER = ["Kick", "Snare", "Hihat", "Ride", "Crash", "Tom"]

    def __init__(self, parent: QtWidgets.QWidget | None, base_name: str,
                 splits: Dict[str, mido.MidiFile]) -> None:
        super().__init__(parent)
        self.setWindowTitle("Split Results — Drag Out to Save")
        self.setMinimumSize(900, 360)
        self.base_name = base_name
        self.splits = splits
        self._temp_dir = tempfile.TemporaryDirectory(prefix="drum_split_")

        main = QtWidgets.QVBoxLayout(self)
        main.setContentsMargins(16, 16, 16, 16)
        main.setSpacing(12)

        header = QtWidgets.QLabel("Drag any non-empty part below onto Explorer/Finder to save it.")
        header.setWordWrap(True)
        main.addWidget(header)

        row = QtWidgets.QHBoxLayout()
        row.setSpacing(12)
        main.addLayout(row, 1)

        for part in self.DISPLAY_ORDER:
            mid = self.splits.get(part)
            if mid is None:
                tile = PartDragTile(part, mido.MidiFile(), self.base_name, False, self._temp_dir, self)
            else:
                has_notes = bool(getattr(mid, "_has_notes", False))
                tile = PartDragTile(part, mid, self.base_name, has_notes, self._temp_dir, self)
            row.addWidget(tile, 1)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        main.addLayout(btn_row)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        try:
            self._temp_dir.cleanup()
        except Exception:
            pass
        super().closeEvent(event)


def run() -> None:
    # High-DPI friendly (attributes differ across Qt versions)
    def _set_attr_if_available(name: str, enabled: bool = True) -> None:
        try:
            attr = getattr(QtCore.Qt.ApplicationAttribute, name)
        except AttributeError:
            return
        try:
            QtWidgets.QApplication.setAttribute(attr, enabled)
        except Exception:
            pass

    _set_attr_if_available('AA_EnableHighDpiScaling', True)
    _set_attr_if_available('AA_UseHighDpiPixmaps', True)

    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName(MainWindow.APP_NAME)
    app.setOrganizationName(MainWindow.ORG_NAME)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    try:
        run()
    except Exception:
        traceback.print_exc()

