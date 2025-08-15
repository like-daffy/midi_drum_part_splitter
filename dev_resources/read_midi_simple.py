#!/usr/bin/env python3
"""
Simple MIDI reader for superior_drummer_mapping-1.mid
Run this script directly to read the MIDI file in the current directory.
"""

import mido
from collections import defaultdict


def midi_note_to_name(note_number):
    """Convert MIDI note number to note name (e.g., 60 -> C4)"""
    note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    octave = (note_number // 12) - 1
    note = note_names[note_number % 12]
    return f"{note}{octave}"


def read_midi_file():
    """Read the MIDI file and display notes"""
    midi_file_path = "superior_drummer_mapping-1.mid"
    
    try:
        mid = mido.MidiFile(midi_file_path)
    except Exception as e:
        print(f"Error reading MIDI file: {e}")
        return
    
    markers = []  # List of (time, marker_name) tuples
    notes = []    # List of (time, note_number) tuples
    
    # Process all tracks
    for track_idx, track in enumerate(mid.tracks):
        current_time = 0
        
        for msg in track:
            current_time += msg.time
            
            # Check for markers (text events)
            if msg.type == 'text' or msg.type == 'marker':
                markers.append((current_time, msg.text.strip()))
            
            # Check for note on events
            elif msg.type == 'note_on' and msg.velocity > 0:
                notes.append((current_time, msg.note))
    
    print(f"Reading MIDI file: {midi_file_path}")
    print("=" * 50)
    print(f"Found {len(markers)} markers and {len(notes)} notes")
    print()
    
    # Try to group by markers first
    if markers:
        print("Organizing notes by markers:")
        print("-" * 30)
        
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
        
        # Display notes by markers
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
    
    else:
        print("No markers found. Organizing notes by beats:")
        print("-" * 40)
        
        ticks_per_beat = mid.ticks_per_beat
        print(f"Ticks per beat: {ticks_per_beat}")
        print()
        
        notes_by_beat = defaultdict(list)
        
        for note_time, note_number in notes:
            # Calculate beat number (1-based)
            beat_number = (note_time // ticks_per_beat) + 1
            note_name = midi_note_to_name(note_number)
            notes_by_beat[beat_number].append(note_name)
        
        # Display notes by beats
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


if __name__ == "__main__":
    read_midi_file()
