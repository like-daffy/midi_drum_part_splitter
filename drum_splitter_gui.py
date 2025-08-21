#!/usr/bin/env python3
"""
Drum Splitter GUI (PyQt6) - Optimized Version

Single-file application that splits drum MIDI files into separate parts using
note mappings defined in a YAML configuration.
"""

from __future__ import annotations

import os
import sys
import math
import yaml
import mido
import tempfile
import traceback
from typing import Dict, List, Set, Optional

from PyQt6 import QtCore, QtGui, QtWidgets

# -----------------------------
# Constants and Configuration
# -----------------------------

DEFAULT_MAPPING_YAML = """
# Drum parts mapping using Cubase octave numbering (C-2..B8)
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

NOTE_NAME_TO_SEMITONE = {
    'C': 0, 'C#': 1, 'DB': 1,
    'D': 2, 'D#': 3, 'EB': 3,
    'E': 4,
    'F': 5, 'F#': 6, 'GB': 6,
    'G': 7, 'G#': 8, 'AB': 8,
    'A': 9, 'A#': 10, 'BB': 10,
    'B': 11,
}

META_NAMES_TO_KEEP = {
    'set_tempo', 'time_signature', 'key_signature', 'smpte_offset',
    'track_name', 'end_of_track', 'instrument_name', 'marker', 'cue_marker',
}

DISPLAY_ORDER = ["Kick", "Snare", "Hihat", "Ride", "Crash", "Tom"]

# -----------------------------
# MIDI Utilities
# -----------------------------

class MidiUtils:
    """Consolidated MIDI utility functions."""
    
    @staticmethod
    def note_to_name(note_number: int) -> str:
        """Convert MIDI note number to name using Cubase octave numbering."""
        note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        octave = (note_number // 12) - 2
        note = note_names[note_number % 12]
        return f"{note}{octave}"

    @staticmethod
    def name_to_note(name: str) -> int:
        """Convert note name to MIDI note number using Cubase numbering."""
        if not name:
            return -1
        s = name.strip().upper().replace('♯', '#').replace('♭', 'B')
        
        try:
            idx = len(s) - 1
            while idx >= 0 and (s[idx].isdigit() or s[idx] == '-'):
                idx -= 1
            letter = s[:idx + 1]
            octave_str = s[idx + 1:]
            if not octave_str:
                return -1
            octave = int(octave_str)
            
            semitone = NOTE_NAME_TO_SEMITONE.get(letter)
            if semitone is None:
                return -1
            
            midi_note = (octave + 2) * 12 + semitone
            return midi_note if 0 <= midi_note <= 127 else -1
        except Exception:
            return -1

# -----------------------------
# YAML Mapping Handler
# -----------------------------

class MappingHandler:
    """Handles YAML mapping loading and validation."""
    
    @staticmethod
    def load_from_yaml(yaml_text: str) -> Dict[str, Set[int]]:
        """Parse YAML mapping text into a dict of part name -> set of MIDI note numbers."""
        try:
            data = yaml.safe_load(yaml_text) or {}
        except Exception as exc:
            raise ValueError(f"Failed to parse YAML: {exc}") from exc

        if not isinstance(data, dict) or 'drum_parts' not in data:
            raise ValueError("YAML must contain a 'drum_parts' mapping")

        drum_parts = data['drum_parts']
        if not isinstance(drum_parts, dict) or not drum_parts:
            raise ValueError("'drum_parts' must be a non-empty mapping")

        result: Dict[str, Set[int]] = {}
        for part_name, note_list in drum_parts.items():
            if not isinstance(note_list, list):
                raise ValueError(f"Part '{part_name}' must list note names")
            
            midi_notes: Set[int] = set()
            for note_name in note_list:
                midi_value = MidiUtils.name_to_note(str(note_name))
                if midi_value < 0:
                    raise ValueError(f"Invalid note '{note_name}' in part '{part_name}'")
                midi_notes.add(midi_value)
            result[str(part_name)] = midi_notes
        return result

    @staticmethod
    def find_duplicate_notes(mapping: Dict[str, Set[int]]) -> Dict[int, List[str]]:
        """Return dict of midi_note -> list of part names where duplicates occur."""
        note_to_parts: Dict[int, List[str]] = {}
        for part_name, note_set in mapping.items():
            for note in note_set:
                note_to_parts.setdefault(note, []).append(part_name)
        return {n: parts for n, parts in note_to_parts.items() if len(parts) > 1}

    @staticmethod
    def format_duplicates(dups: Dict[int, List[str]]) -> str:
        """Format duplicate notes for display."""
        lines = []
        for note_num in sorted(dups.keys()):
            name = MidiUtils.note_to_name(note_num)
            parts = ", ".join(sorted(dups[note_num]))
            lines.append(f"{name}: {parts}")
        return "\n".join(lines)

# -----------------------------
# MIDI Splitter
# -----------------------------

class MidiSplitter:
    """Handles MIDI file splitting logic."""
    
    @staticmethod
    def split_by_mapping(input_path: str, mapping: Dict[str, Set[int]]) -> Dict[str, mido.MidiFile]:
        """Split a MIDI file into multiple parts based on mapping."""
        try:
            original = mido.MidiFile(input_path)
        except Exception as exc:
            raise ValueError(f"Unrecognizable MIDI file: {exc}") from exc

        outputs = {}
        for part_name in mapping.keys():
            outputs[part_name] = mido.MidiFile(ticks_per_beat=original.ticks_per_beat)

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
                        if msg.type in META_NAMES_TO_KEEP:
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

                new_track.append(mido.MetaMessage('end_of_track', time=time_accumulator))

            setattr(out_mid, '_has_notes', part_has_notes)

        return outputs

# -----------------------------
# Theme Manager
# -----------------------------

class ThemeManager:
    """Manages application theming."""
    
    @staticmethod
    def oklch_to_srgb_hex(l_val: float, c_val: float, h_deg: float) -> str:
        """Convert OKLCH color to sRGB hex."""
        h_rad = math.radians(h_deg)
        a = math.cos(h_rad) * c_val
        b = math.sin(h_rad) * c_val

        l_ = l_val + 0.3963377774 * a + 0.2158037573 * b
        m_ = l_val - 0.1055613458 * a - 0.0638541728 * b
        s_ = l_val - 0.0894841775 * a - 1.2914855480 * b

        l3, m3, s3 = l_ ** 3, m_ ** 3, s_ ** 3

        r_lin = 4.0767416621 * l3 - 3.3077115913 * m3 + 0.2309699292 * s3
        g_lin = -1.2684380046 * l3 + 2.6097574011 * m3 - 0.3413193965 * s3
        b_lin = -0.0041960863 * l3 - 0.7034186147 * m3 + 1.7076147010 * s3

        def lin_to_srgb(x: float) -> float:
            if x <= 0.0031308:
                return 12.92 * x
            return 1.055 * (max(x, 0.0) ** (1 / 2.4)) - 0.055

        r = min(max(lin_to_srgb(r_lin), 0.0), 1.0)
        g = min(max(lin_to_srgb(g_lin), 0.0), 1.0)
        b = min(max(lin_to_srgb(b_lin), 0.0), 1.0)

        return f'#{int(r * 255):02X}{int(g * 255):02X}{int(b * 255):02X}'

    @classmethod
    def get_blue_sea_theme(cls) -> str:
        """Generate Blue Sea theme stylesheet."""
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

        def parse_oklch(s: str) -> str:
            try:
                inner = s[s.index('(') + 1:s.index(')')]
                parts = inner.replace('/', ' ').replace(',', ' ').split()
                return cls.oklch_to_srgb_hex(float(parts[0]), float(parts[1]), float(parts[2]))
            except Exception:
                return '#1976D2'

        colors = {name: parse_oklch(val) for name, val in css_vars.items()}
        
        return f"""
        QMainWindow {{
            background-color: {colors['background']};
            color: {colors['foreground']};
            font-family: "Segoe UI", Arial, sans-serif;
        }}
        QWidget {{
            background: transparent;
            color: {colors['foreground']};
            font-family: "Segoe UI", Arial, sans-serif;
            font-size: 13px;
        }}
        QLabel {{
            color: {colors['muted-foreground']};
            background: transparent;
            font-weight: 500;
        }}
        QPushButton {{
            background: {colors['primary']};
            border: 2px solid {colors['border']};
            border-radius: 8px;
            color: {colors['primary-foreground']};
            font-weight: bold;
            font-size: 14px;
            padding: 10px 20px;
            min-height: 20px;
        }}
        QPushButton:hover {{
            border: 2px solid {colors['ring']};
        }}
        QPushButton:default {{
            background-color: {colors['accent']};
            border: 2px solid {colors['accent']};
            color: {colors['background']};
            font-size: 16px;
            font-weight: bold;
        }}
        QLineEdit {{
            background: {colors['muted']};
            border: 2px solid {colors['ring']};
            border-radius: 8px;
            padding: 8px 12px;
            color: {colors['foreground']};
            font-size: 14px;
        }}
        QLineEdit:focus {{
            border: 2px solid {colors['primary']};
        }}
        QCheckBox {{
            color: {colors['muted-foreground']};
            font-weight: 500;
            spacing: 8px;
        }}
        QCheckBox::indicator {{
            width: 18px;
            height: 18px;
            border: 2px solid {colors['primary']};
            border-radius: 4px;
            background: {colors['muted']};
        }}
        QCheckBox::indicator:checked {{
            background: {colors['primary']};
            border: 2px solid {colors['primary']};
        }}
        QListWidget {{
            border: none;
            background: transparent;
            font-size: 14px;
            font-weight: bold;
            color: {colors['primary']};
            padding: 8px;
            border-radius: 8px;
        }}
        QListWidget::item {{
            background: {colors['card']};
            border: 2px solid {colors['primary']};
            border-radius: 8px;
            padding: 16px;
            margin: 6px;
            font-weight: bold;
            color: {colors['card-foreground']};
        }}
        QListWidget::item:selected {{
            background: {colors['secondary']};
            border: 3px solid {colors['primary']};
            color: {colors['secondary-foreground']};
        }}
        QMessageBox {{
            background: {colors['card']};
            color: {colors['foreground']};
        }}
        QMessageBox QLabel {{
            color: {colors['muted-foreground']};
            font-size: 14px;
        }}
        """

# -----------------------------
# Custom Widgets
# -----------------------------

class DragDropList(QtWidgets.QListWidget):
    """List widget with drag-and-drop support for MIDI files."""
    filesChanged = QtCore.pyqtSignal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setAlternatingRowColors(True)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.allow_click_browse = True

    def sizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(600, 140)

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        super().paintEvent(event)
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
            font = painter.font()
            font.setPointSize(14)
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QtGui.QColor('#888'))
            painter.drawText(rect, QtCore.Qt.AlignmentFlag.AlignCenter,
                           'Drag & drop a MIDI file here\n(or click to browse)')
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
        for url in event.mimeData().urls():
            local_path = url.toLocalFile()
            if local_path and local_path.lower().endswith(('.mid', '.midi')) and os.path.exists(local_path):
                self.clear()
                self.addItem(local_path)
                self.filesChanged.emit()
                self.allow_click_browse = False
                break

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.LeftButton and self.allow_click_browse:
            start_dir = os.path.dirname(self.item(0).text()) if self.count() > 0 else os.getcwd()
            path, _ = QtWidgets.QFileDialog.getOpenFileName(
                self, "Select MIDI File", start_dir, "MIDI Files (*.mid *.midi)")
            if path:
                self.clear()
                self.addItem(path)
                self.filesChanged.emit()
                self.allow_click_browse = False
                event.accept()
                return
        super().mousePressEvent(event)

    def resetToEmpty(self) -> None:
        self.clear()
        self.allow_click_browse = True
        self.filesChanged.emit()

    def currentFiles(self) -> List[str]:
        return [self.item(i).text() for i in range(self.count())]


class OutputPlaceholder(QtWidgets.QWidget):
    """Placeholder widget for output section."""
    
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
        font = painter.font()
        font.setPointSize(16)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QtGui.QColor('#666'))
        painter.drawText(rect, QtCore.Qt.AlignmentFlag.AlignCenter,
                        'Output Result\n\nClick "Proceed" to split MIDI file')
        painter.end()


class PartDragTile(QtWidgets.QFrame):
    """Draggable tile representing one split part."""

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
            "QFrame#PartDragTile[disabled=\"true\"] { border: 2px dashed #777; max-width: 120px; }")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        title = QtWidgets.QLabel(self.part_name)
        title.setStyleSheet("font-weight: bold; font-size: 16px;")
        layout.addWidget(title, 0, QtCore.Qt.AlignmentFlag.AlignHCenter)

        self.center_label = QtWidgets.QLabel("Drag\nout\nto\nsave" if enabled else "Empty")
        style = "font-weight: 800; color: #42A5F5; font-size: 14px;" if enabled else ""
        self.center_label.setStyleSheet(style)
        self.center_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.center_label, 1)

        self.setEnabled(enabled)

    def _ensure_temp_file(self) -> str:
        if self._temp_path and os.path.exists(self._temp_path):
            return self._temp_path
        filename = f"{self.base_name}-{self.part_name.lower()}.mid"
        out_path = os.path.join(self.temp_dir.name, filename)
        try:
            self.midi_obj.save(out_path)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Export Error", 
                                          f"Failed to create temporary file for {self.part_name}:\n{exc}")
            raise
        self._temp_path = out_path
        return out_path

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if not self.isEnabled() or event.button() != QtCore.Qt.MouseButton.LeftButton:
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
        painter.drawText(pm.rect(), QtCore.Qt.AlignmentFlag.AlignCenter,
                        f"{self.base_name}-{self.part_name.lower()}.mid")
        painter.end()
        drag.setPixmap(pm)
        drag.exec(QtCore.Qt.DropAction.CopyAction)


# -----------------------------
# Main Window
# -----------------------------

class MainWindow(QtWidgets.QMainWindow):
    ORG_NAME = "MIDIUtilities"
    APP_NAME = "DrumSplitter"

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("MIDI Drum Splitter")
        self.setMinimumSize(780, 700)
        self._mapping_cache: Dict[str, Set[int]] | None = None
        self.settings = QtCore.QSettings(self.ORG_NAME, self.APP_NAME)
        self.setStyleSheet(ThemeManager.get_blue_sea_theme())
        self._build_ui()
        self._load_preferences()
        self._load_effective_mapping()
        self._temp_dir_results: Optional[tempfile.TemporaryDirectory] = None

    def _build_ui(self) -> None:
        central = QtWidgets.QWidget()
        main_layout = QtWidgets.QVBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        self.input_section = self._create_input_section()
        main_layout.addWidget(self.input_section, 0)

        self.output_section = self._create_output_section()
        main_layout.addWidget(self.output_section, 1)

        self.about_section = self._create_about_section()
        main_layout.addWidget(self.about_section, 0)

        self.setCentralWidget(central)
        self._connect_signals()

    def _create_section_widget(self, name: str) -> QtWidgets.QWidget:
        """Create a styled section widget."""
        widget = QtWidgets.QWidget()
        widget.setObjectName(name)
        # Apply style directly to the widget without using ID selector
        widget.setStyleSheet("background-color: rgba(255, 255, 255, 13); "
                           "border-radius: 12px;")
        return widget

    def _create_input_section(self) -> QtWidgets.QWidget:
        input_widget = self._create_section_widget("InputSection")
        layout = QtWidgets.QVBoxLayout(input_widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        intro = QtWidgets.QLabel(
            "Drag-and-drop ONE MIDI file below (or click the area to browse), optionally pick a custom YAML mapping,\n"
            "then click Proceed to preview 6 parts you can drag out to Explorer/Finder to save.")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.drop_list = DragDropList()
        self.drop_list.setMaximumHeight(100)
        layout.addWidget(self.drop_list, 0)

        proceed_row = QtWidgets.QHBoxLayout()
        proceed_row.addStretch(1)
        self.btn_select_again = QtWidgets.QPushButton("Select Again")
        self.btn_select_again.setFixedWidth(160)
        self.btn_select_again.setEnabled(False)
        self.btn_select_again.setVisible(False)
        proceed_row.addWidget(self.btn_select_again)
        self.btn_proceed = QtWidgets.QPushButton("Proceed")
        self.btn_proceed.setFixedWidth(160)
        self.btn_proceed.setDefault(True)
        self.btn_proceed.setAutoDefault(True)
        self.btn_proceed.setStyleSheet(f"""
            QPushButton {{
                background-color: {ThemeManager.oklch_to_srgb_hex(0.9529, 0.0800, 55.0)};
                border: 2px solid {ThemeManager.oklch_to_srgb_hex(0.9529, 0.0800, 55.0)};
                color: {ThemeManager.oklch_to_srgb_hex(0.2784, 0.1000, 258.0)};
                font-size: 16px;
                font-weight: bold;
                padding: 10px 20px;
                min-height: 20px;
                border-radius: 8px;
            }}
            QPushButton:hover {{
                border: 3px solid {ThemeManager.oklch_to_srgb_hex(0.6510, 0.1500, 255.0)};
            }}
        """)
        proceed_row.addWidget(self.btn_proceed)
        proceed_row.addStretch(1)
        layout.addLayout(proceed_row)

        yaml_row = QtWidgets.QHBoxLayout()
        self.yaml_path_edit = QtWidgets.QLineEdit()
        self.yaml_path_edit.setPlaceholderText("Custom YAML mapping path (optional)")
        self.btn_browse_yaml = QtWidgets.QPushButton("Browse…")
        self.btn_use_default_yaml = QtWidgets.QPushButton("Default")
        yaml_row.addWidget(self.yaml_path_edit, 1)
        yaml_row.addWidget(self.btn_browse_yaml)
        yaml_row.addWidget(self.btn_use_default_yaml)
        layout.addLayout(yaml_row)

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
        output_widget = self._create_section_widget("OutputSection")
        layout = QtWidgets.QVBoxLayout(output_widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.output_placeholder = OutputPlaceholder()
        layout.addWidget(self.output_placeholder, 1)

        self.results_scroll_area = QtWidgets.QScrollArea()
        self.results_scroll_area.setWidgetResizable(True)
        self.results_scroll_area.setVisible(False)

        self._results_panel = QtWidgets.QWidget()
        self._results_panel_layout = QtWidgets.QVBoxLayout(self._results_panel)
        self._results_panel_layout.setContentsMargins(0, 0, 0, 0)
        self._results_panel_layout.setSpacing(12)

        self.results_header = QtWidgets.QLabel(
            '<span style="font-size:14px; font-weight:800; color:#ffffff; '
            'padding:8px 12px; border-radius:10px;">Drag out to save</span>')
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
        about_widget = self._create_section_widget("AboutSection")
        layout = QtWidgets.QVBoxLayout(about_widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(6)

        info = QtWidgets.QLabel(
            '<a href="https://x.com/sochan_life" style="color: #bbb; text-decoration: none;">'
            'Copyright (c) 2025 Sochan, X(twitter): @sochan_life</a>')
        info.setStyleSheet("font-size: 14px;")
        info.setOpenExternalLinks(True)
        layout.addWidget(info)

        return about_widget

    def _connect_signals(self) -> None:
        self.btn_browse_yaml.clicked.connect(self._on_browse_yaml)
        self.btn_use_default_yaml.clicked.connect(self._on_use_default_yaml)
        self.btn_proceed.clicked.connect(self._on_proceed)
        self.drop_list.filesChanged.connect(self._on_input_files_changed)
        self.btn_select_again.clicked.connect(self._on_select_again)
        self.chk_use_same.toggled.connect(self._on_use_same_toggled)
        self.yaml_path_edit.textChanged.connect(self._on_yaml_path_changed)
        self.btn_save_template.clicked.connect(self._on_save_template)

    def _load_preferences(self) -> None:
        use_same = self.settings.value('use_custom_config', False, type=bool)
        custom_path = self.settings.value('custom_config_path', '', type=str)
        self.chk_use_same.setChecked(bool(use_same))
        if custom_path:
            self.yaml_path_edit.setText(custom_path)

    def _persist_preferences(self) -> None:
        self.settings.setValue('use_custom_config', self.chk_use_same.isChecked())
        self.settings.setValue('custom_config_path', self.yaml_path_edit.text().strip())

    def _get_effective_yaml_text(self) -> str:
        path = self.yaml_path_edit.text().strip()
        if self.chk_use_same.isChecked() and path:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as exc:
                QtWidgets.QMessageBox.warning(
                    self, "YAML Error", 
                    f"Failed to read custom YAML:\n{exc}\nUsing default mapping instead.")
        return DEFAULT_MAPPING_YAML

    def _load_effective_mapping(self) -> None:
        is_custom = self.chk_use_same.isChecked() and bool(self.yaml_path_edit.text().strip())
        yaml_text = self._get_effective_yaml_text()
        
        try:
            mapping = MappingHandler.load_from_yaml(yaml_text)
        except Exception as exc:
            self._mapping_cache = None
            QtWidgets.QMessageBox.critical(self, "YAML Error", f"Invalid YAML mapping:\n{exc}")
            if is_custom:
                self._reset_yaml_settings()
            return

        dups = MappingHandler.find_duplicate_notes(mapping)
        if dups:
            details = MappingHandler.format_duplicates(dups)
            if is_custom:
                QtWidgets.QMessageBox.warning(
                    self, "Duplicate Notes in Mapping",
                    f"The selected YAML contains duplicate notes assigned to multiple parts.\n\n"
                    f"{details}\n\nPlease resolve and try again.")
                self._mapping_cache = None
                self._reset_yaml_settings()
                return
            else:
                QtWidgets.QMessageBox.critical(
                    self, "Default Mapping Error",
                    f"Default YAML contains duplicate notes (developer fix required):\n\n{details}")
                QtCore.QTimer.singleShot(0, QtWidgets.QApplication.instance().quit)
                self._mapping_cache = None
                return

        self._mapping_cache = mapping

    def _reset_yaml_settings(self) -> None:
        self.yaml_path_edit.setText("")
        self.chk_use_same.setChecked(False)
        self._persist_preferences()

    def _on_browse_yaml(self) -> None:
        start_dir = (os.path.dirname(self.yaml_path_edit.text().strip()) 
                    if self.yaml_path_edit.text().strip() else os.getcwd())
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select YAML Mapping", start_dir, "YAML Files (*.yml *.yaml)")
        if path:
            self.yaml_path_edit.setText(path)
            self.chk_use_same.setChecked(True)
            self._persist_preferences()
            self._load_effective_mapping()

    def _on_use_default_yaml(self) -> None:
        self._reset_yaml_settings()
        self._load_effective_mapping()

    def _on_save_template(self) -> None:
        default_path = os.path.join(os.getcwd(), "default.yaml")
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save Default Mapping Template", default_path,
            "YAML Files (*.yaml);;All Files (*)")
        if not path:
            return
        base, ext = os.path.splitext(path)
        if ext.lower() != ".yaml":
            path = base + ".yaml"
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(DEFAULT_MAPPING_YAML)
            QtWidgets.QMessageBox.information(self, "Saved", f"Template saved to:\n{path}")
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Write Error", f"Failed to save template:\n{exc}")

    def _on_proceed(self) -> None:
        files = self.drop_list.currentFiles()
        if not files:
            QtWidgets.QMessageBox.information(self, "No File", 
                                             "Please drag-and-drop ONE MIDI file to proceed.")
            return

        self._load_effective_mapping()
        if not self._mapping_cache:
            return

        try:
            splits = MidiSplitter.split_by_mapping(files[0], self._mapping_cache)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Split Error", f"Failed to split MIDI file:\n{exc}")
            return

        base_name = os.path.splitext(os.path.basename(files[0]))[0]
        self._populate_results(base_name, splits)

    def _on_input_files_changed(self) -> None:
        self._clear_results()
        has_file = self.drop_list.count() > 0
        self.btn_select_again.setVisible(has_file)
        self.btn_select_again.setEnabled(has_file)

    def _on_select_again(self) -> None:
        self.drop_list.resetToEmpty()
        self.btn_select_again.setVisible(False)
        self.btn_select_again.setEnabled(False)

    def _clear_results(self) -> None:
        while self.results_row.count():
            item = self.results_row.takeAt(0)
            if w := item.widget():
                w.setParent(None)
                w.deleteLater()
        
        if self._temp_dir_results is not None:
            try:
                self._temp_dir_results.cleanup()
            except Exception:
                pass
        self._temp_dir_results = None
        
        self.output_placeholder.setVisible(True)
        self.results_scroll_area.setVisible(False)

    def _populate_results(self, base_name: str, splits: Dict[str, mido.MidiFile]) -> None:
        self._clear_results()
        self._temp_dir_results = tempfile.TemporaryDirectory(prefix="drum_split_")

        for part in DISPLAY_ORDER:
            mid = splits.get(part)
            if mid is None:
                tile = PartDragTile(part, mido.MidiFile(), base_name, False, 
                                  self._temp_dir_results, self)
            else:
                has_notes = bool(getattr(mid, "_has_notes", False))
                tile = PartDragTile(part, mid, base_name, has_notes, 
                                  self._temp_dir_results, self)
            self.results_row.addWidget(tile, 1)

        self.output_placeholder.setVisible(False)
        self.results_scroll_area.setVisible(True)

    def _on_use_same_toggled(self, checked: bool) -> None:
        self._persist_preferences()

    def _on_yaml_path_changed(self) -> None:
        if self.chk_use_same.isChecked():
            self._persist_preferences()
        self._mapping_cache = None

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if self._temp_dir_results is not None:
            try:
                self._temp_dir_results.cleanup()
            except Exception:
                pass
        
        if not self.chk_use_same.isChecked():
            try:
                self.settings.setValue('custom_config_path', '')
            except Exception:
                pass
        
        super().closeEvent(event)


# -----------------------------
# Application Entry Point
# -----------------------------

def run() -> None:
    """Main application entry point."""
    # Set high-DPI attributes if available
    for attr_name in ['AA_EnableHighDpiScaling', 'AA_UseHighDpiPixmaps']:
        try:
            attr = getattr(QtCore.Qt.ApplicationAttribute, attr_name)
            QtWidgets.QApplication.setAttribute(attr, True)
        except (AttributeError, Exception):
            pass

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