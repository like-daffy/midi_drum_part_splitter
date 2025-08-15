#!/usr/bin/env python3
"""
Drum Splitter GUI (PyQt6)

Single-file application that splits drum MIDI files into separate parts using
note mappings defined in a YAML configuration. The default configuration is
hard-coded based on the "Organizing notes by markers" output from
superior_drummer_mapping.mid, using Cubase octave numbering (C-2..B8).

Features:
- Drag-and-drop MIDI files into the window
- Browse and load a custom YAML mapping
- Persist preference to always use the same custom YAML mapping
- Split to files named "{original name} - {part}.mid" in the same folder
- Skip writing a split file if it would be empty
- Preserve pitch and velocity of notes

Packagable with PyInstaller on macOS and Windows.
"""

from __future__ import annotations

import os
import sys
import traceback
from typing import Dict, List, Set, Tuple

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
    - D#0
    - E0
    - F#1
    - G#1
    - A#1
    - G#2
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

class DragDropList(QtWidgets.QListWidget):
    filesChanged = QtCore.pyqtSignal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setAlternatingRowColors(True)
        # [NEXT VERSION] Enable ExtendedSelection to support multi-file selection
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        # Styling is now handled by the global blue sea theme CSS

    def sizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(600, 220)

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
                'Drag and drop the drum MIDI file here',
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
        # [NEXT VERSION] To support multiple files, remove the clear() call and allow multiple insertions
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
            break

    def addFiles(self, paths: List[str]) -> None:
        # Single-file mode: take first valid path only
        # [NEXT VERSION] Accept multiple files; append instead of replacing
        for p in paths:
            if p.lower().endswith(('.mid', '.midi')) and os.path.exists(p):
                self.clear()
                self.addItem(p)
                self.filesChanged.emit()
                break

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
        self.setMinimumSize(780, 640)
        self._mapping_cache: Dict[str, Set[int]] | None = None

        # Persistent settings
        self.settings = QtCore.QSettings(self.ORG_NAME, self.APP_NAME)

        # Apply blue sea theme
        self._apply_blue_sea_theme()

        self._build_ui()
        self._load_preferences()
        self._load_effective_mapping()

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
        layout = QtWidgets.QVBoxLayout(central)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Instructions
        intro = QtWidgets.QLabel(
            "Drag-and-drop MIDI files below, optionally pick a custom YAML mapping,\n"
            "then click Proceed to split by drum parts."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        # Drag-and-drop list widget
        self.drop_list = DragDropList()
        layout.addWidget(self.drop_list, 1)

        # Buttons row: Remove and Clear (hidden in this version)
        # [NEXT VERSION] Show these buttons to manage multiple files
        # buttons_row = QtWidgets.QHBoxLayout()
        # self.btn_remove = QtWidgets.QPushButton("Remove Selected")
        # self.btn_clear = QtWidgets.QPushButton("Clear")
        # buttons_row.addWidget(self.btn_remove)
        # buttons_row.addWidget(self.btn_clear)
        # buttons_row.addStretch(1)
        # layout.addLayout(buttons_row)

        # Proceed button centered
        proceed_row = QtWidgets.QHBoxLayout()
        proceed_row.addStretch(1)
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
        yaml_row.addWidget(self.yaml_path_edit, 1)
        yaml_row.addWidget(self.btn_browse_yaml)
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

        self.setCentralWidget(central)

        # Signals
        self.btn_browse_yaml.clicked.connect(self._on_browse_yaml)
        self.btn_proceed.clicked.connect(self._on_proceed)
        # [NEXT VERSION]
        # self.btn_remove.clicked.connect(self.drop_list.removeSelected)
        # self.btn_clear.clicked.connect(lambda: (self.drop_list.clear(), self.drop_list.filesChanged.emit()))
        self.chk_use_same.toggled.connect(self._on_use_same_toggled)
        self.yaml_path_edit.textChanged.connect(self._on_yaml_path_changed)
        self.btn_save_template.clicked.connect(self._on_save_template)

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
        try:
            self._mapping_cache = load_mapping_from_yaml(self._get_effective_yaml_text())
        except Exception as exc:
            self._mapping_cache = None
            QtWidgets.QMessageBox.critical(self, "YAML Error", f"Invalid YAML mapping:\n{exc}")

    def _on_browse_yaml(self) -> None:
        start_dir = os.path.dirname(self.yaml_path_edit.text().strip()) if self.yaml_path_edit.text().strip() else os.getcwd()
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select YAML Mapping", start_dir, "YAML Files (*.yml *.yaml)")
        if path:
            self.yaml_path_edit.setText(path)
            self.chk_use_same.setChecked(True)
            self._persist_preferences()
            self._load_effective_mapping()

    def _on_save_template(self) -> None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Default Mapping Template", os.getcwd(), "YAML Files (*.yml *.yaml)")
        if not path:
            return
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
            QtWidgets.QMessageBox.information(self, "No Files", "Please drag-and-drop one or more MIDI files to proceed.")
            return

        # Load mapping (custom or default)
        self._load_effective_mapping()
        if not self._mapping_cache:
            return

        mapping = self._mapping_cache
        failed: List[Tuple[str, str]] = []
        saved_total: List[str] = []

        # Single-file mode: process only the first file
        # [NEXT VERSION] Iterate all files to batch process
        for path in files[:1]:
            try:
                splits = split_midi_by_mapping(path, mapping)
                saved = save_split_midis(path, splits)
                saved_total.extend(saved)
            except Exception as exc:
                failed.append((path, str(exc)))

        if saved_total:
            msg = "Saved files:\n" + "\n".join(saved_total)
        else:
            msg = "No split files were created. Either there were no matching notes, or all parts were empty."

        if failed:
            msg += "\n\nErrors:\n" + "\n".join(f"- {p}: {e}" for p, e in failed)

        QtWidgets.QMessageBox.information(self, "Done", msg)


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

