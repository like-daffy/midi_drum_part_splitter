#!/usr/bin/env python3
"""
MIDI Drum Part Splitter
Reads a MIDI file and displays notes organized by markers or beats.
Also checks for missing notes across the full 10-octave range.
"""

import mido
import sys
from collections import defaultdict


def midi_note_to_name(note_number):
    """Convert MIDI note number to note name using Cubase octave numbering (e.g., 60 -> C3)"""
    note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    octave = (note_number // 12) - 2  # Cubase uses -2 instead of -1 for octave calculation
    note = note_names[note_number % 12]
    return f"{note}{octave}"


def get_all_possible_notes():
    """Generate all possible notes from C-2 to B8 (10 octaves) using Cubase octave numbering"""
    all_notes = []
    note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    
    # With Cubase numbering: C-2 starts at MIDI note 0, B8 ends at MIDI note 127
    for octave in range(-2, 9):
        for note_name in note_names:
            all_notes.append(f"{note_name}{octave}")
    
    return all_notes


def find_missing_notes(notes_in_midi):
    """Find which notes from the full 10-octave range are missing"""
    all_possible_notes = get_all_possible_notes()
    notes_in_midi_set = set(notes_in_midi)
    
    missing_notes = []
    for note in all_possible_notes:
        if note not in notes_in_midi_set:
            missing_notes.append(note)
    
    return missing_notes


def extract_markers_and_notes(midi_file_path):
    """Extract markers and notes from MIDI file"""
    try:
        mid = mido.MidiFile(midi_file_path)
    except Exception as e:
        print(f"Error reading MIDI file: {e}")
        return None, None, None
    
    markers = []  # List of (time, marker_name) tuples
    notes = []    # List of (time, note_number) tuples
    unique_notes = set()  # Set of unique note names
    note_events = []  # List of all note events for debugging
    
    # Process all tracks
    for track_idx, track in enumerate(mid.tracks):
        current_time = 0
        
        for msg in track:
            current_time += msg.time
            
            # Check for markers (text events)
            if msg.type == 'text' or msg.type == 'marker':
                markers.append((current_time, msg.text.strip()))
            
            # Check for note on events (including velocity = 0 which is equivalent to note_off)
            elif msg.type == 'note_on':
                notes.append((current_time, msg.note))
                note_name = midi_note_to_name(msg.note)
                unique_notes.add(note_name)
                note_events.append(f"Note On: {note_name} at {current_time} ticks, velocity={msg.velocity}")
            
            # Also check for note_off events to ensure we don't miss any notes
            elif msg.type == 'note_off':
                notes.append((current_time, msg.note))
                note_name = midi_note_to_name(msg.note)
                unique_notes.add(note_name)
                note_events.append(f"Note Off: {note_name} at {current_time} ticks, velocity={msg.velocity}")
    
    print(f"Total note events processed: {len(note_events)}")
    print(f"Unique notes found: {len(unique_notes)}")
    
    return markers, notes, list(unique_notes)


def group_notes_by_markers(markers, notes):
    """Group notes by their corresponding markers"""
    if not markers:
        return None
    
    # Sort markers and notes by time
    markers.sort(key=lambda x: x[0])
    notes.sort(key=lambda x: x[0])
    
    notes_by_marker = defaultdict(list)
    marker_index = 0
    current_marker = "Unknown"
    
    for note_time, note_number in notes:
        # Find the appropriate marker for this note
        while (marker_index < len(markers) and 
               markers[marker_index][0] <= note_time):
            current_marker = markers[marker_index][1]
            marker_index += 1
        
        note_name = midi_note_to_name(note_number)
        notes_by_marker[current_marker].append(note_name)
    
    return notes_by_marker


def group_notes_by_beats(notes, ticks_per_beat):
    """Group notes by beats"""
    if not notes:
        return {}
    
    notes_by_beat = defaultdict(list)
    
    for note_time, note_number in notes:
        # Calculate beat number (1-based)
        beat_number = (note_time // ticks_per_beat) + 1
        note_name = midi_note_to_name(note_number)
        notes_by_beat[beat_number].append(note_name)
    
    return notes_by_beat


def analyze_note_timing(notes, ticks_per_beat):
    """Analyze note timing to identify patterns like sixteenth notes"""
    if not notes:
        return {}
    
    # Convert ticks to beats
    notes_by_beat = defaultdict(list)
    notes_by_subdivision = defaultdict(list)
    
    for note_time, note_number in notes:
        # Calculate beat number (1-based)
        beat_number = (note_time // ticks_per_beat) + 1
        
        # Calculate subdivision within the beat (for sixteenth notes)
        ticks_into_beat = note_time % ticks_per_beat
        subdivision = (ticks_into_beat * 16) // ticks_per_beat  # 16 subdivisions = sixteenth notes
        
        notes_by_beat[beat_number].append((note_time, note_number))
        notes_by_subdivision[subdivision].append((note_time, note_number))
    
    return notes_by_beat, notes_by_subdivision


def display_notes_by_markers(notes_by_marker):
    """Display notes organized by markers"""
    for marker, note_list in notes_by_marker.items():
        print(f"Marker: {marker}")
        if note_list:
            # Remove duplicates while preserving order
            unique_notes = []
            seen = set()
            for note in note_list:
                if note not in seen:
                    unique_notes.append(note)
                    seen.add(note)
            print(", ".join(unique_notes))
        else:
            print("(no notes)")
        print()


def display_notes_by_beats(notes_by_beat):
    """Display notes organized by beats"""
    for beat in sorted(notes_by_beat.keys()):
        note_list = notes_by_beat[beat]
        print(f"Beat {beat}: ", end="")
        if note_list:
            # Remove duplicates while preserving order
            unique_notes = []
            seen = set()
            for note in note_list:
                if note not in seen:
                    unique_notes.append(note)
                    seen.add(note)
            print(", ".join(unique_notes))
        else:
            print("(no notes)")


def main():
    if len(sys.argv) != 2:
        print("Usage: python midi_reader.py <midi_file>")
        print("Example: python midi_reader.py superior_drummer_mapping-1.mid")
        return
    
    midi_file_path = sys.argv[1]
    
    print(f"Reading MIDI file: {midi_file_path}")
    print("=" * 50)
    
    # Extract markers, notes, and unique note names
    markers, notes, unique_notes = extract_markers_and_notes(midi_file_path)
    
    if markers is None or notes is None:
        return
    
    print(f"Found {len(markers)} markers and {len(notes)} notes")
    print()
    
    # Check for missing notes across the full 10-octave range
    print("Checking for missing notes across 10 octaves (C-2 to B8) using Cubase octave numbering:")
    print("-" * 70)
    
    missing_notes = find_missing_notes(unique_notes)
    
    if missing_notes:
        print(f"Missing notes ({len(missing_notes)} total):")
        # Group missing notes by octave for better readability
        missing_by_octave = defaultdict(list)
        for note in missing_notes:
            # Extract octave from note name (e.g., "C-1" -> "-1", "G9" -> "9")
            if note[-2:].isdigit() or (note[-2] == '-' and note[-1].isdigit()):
                if note[-2] == '-':
                    octave = note[-2:]
                else:
                    octave = note[-1]
            else:
                octave = note[-1]
            
            missing_by_octave[octave].append(note)
        
        # Display missing notes grouped by octave
        for octave in sorted(missing_by_octave.keys(), key=lambda x: int(x) if x != '-' else -1):
            notes_in_octave = missing_by_octave[octave]
            print(f"Octave {octave}: {', '.join(sorted(notes_in_octave))}")
    else:
        print("All notes from C-2 to B8 are present in the MIDI file!")
    
    print()
    
    # Analyze timing patterns for sixteenth notes
    try:
        mid = mido.MidiFile(midi_file_path)
        ticks_per_beat = mid.ticks_per_beat
        print(f"MIDI timing analysis:")
        print(f"Ticks per beat: {ticks_per_beat}")
        print(f"Tempo: {mid.ticks_per_beat} ticks per beat")
        
        notes_by_beat, notes_by_subdivision = analyze_note_timing(notes, ticks_per_beat)
        
        print(f"Notes found across {len(notes_by_beat)} beats")
        print(f"Subdivision analysis (0-15 = sixteenth note positions):")
        for subdivision in sorted(notes_by_subdivision.keys()):
            count = len(notes_by_subdivision[subdivision])
            print(f"  Position {subdivision}: {count} notes")
        
        print()
        
    except Exception as e:
        print(f"Error analyzing timing: {e}")
    
    # Try to group by markers first
    if markers:
        print("Organizing notes by markers:")
        print("-" * 30)
        notes_by_marker = group_notes_by_markers(markers, notes)
        display_notes_by_markers(notes_by_marker)
    else:
        print("No markers found. Organizing notes by beats:")
        print("-" * 40)
        
        # Get ticks per beat from MIDI file
        try:
            mid = mido.MidiFile(midi_file_path)
            ticks_per_beat = mid.ticks_per_beat
            print(f"Ticks per beat: {ticks_per_beat}")
            print()
            
            notes_by_beat = group_notes_by_beats(notes, ticks_per_beat)
            display_notes_by_beats(notes_by_beat)
        except Exception as e:
            print(f"Error processing beats: {e}")


if __name__ == "__main__":
    main()
