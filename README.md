# MIDI Drum 분할 프로그램

PyQt6 기반의 GUI 애플리케이션으로, 드럼 MIDI 파일을 노트 매핑에 따라 Kick, Snare, Hihat, Ride, Crash, Tom Tom 으로 분리해 줍니다. 사용자 지정 YAML 설정도 지원합니다.

## 주요 기능

- 🎵 **단일 파일 드럼 분리** – MIDI 파일을 드래그 앤 드롭하면 자동으로 파트별 분리
- 📝 **사용자 지정 YAML 매핑** – 내 매핑 파일을 불러오거나 내장 Superior Drummer 3 매핑 사용 가능
- 💾 **설정 기억 기능** – 사용자가 지정한 YAML 설정을 저장
- 🎯 **Cubase 옥타브 표기** – Cubase 호환 음이름(C-2 ~ B8) 사용
- 📦 **단일 실행 파일** – PyInstaller로 독립 실행 파일 제작 가능

## 빠른 시작

### 설치 방법

1. **저장소 복제**
   ```bash
   git clone https://github.com/like-daffy/midi-drum-splitter.git
   cd midi-drum-splitter
   ```

2. **필수 라이브러리 설치**
   ```bash
   pip install -r requirements.txt
   ```

3. **애플리케이션 직접 실행**
   ```bash
   python drum_splitter_gui.py
   ```

### 사용 방법

1. 프로그램 창에 MIDI 파일을 **드래그 앤 드롭**
2. **(선택)** "Browse..." 버튼으로 사용자 지정 YAML 매핑 파일 불러오기
3. **(선택)** "다음에도 동일한 설정 사용" 체크박스로 설정 저장
4. **"Proceed" 클릭** → MIDI 파일이 파트별로 분리됨

출력 파일은 원본 파일과 동일한 폴더에 저장되며, 예시는 다음과 같습니다.
- `your_file-kick.mid`
- `your_file-snare.mid`
- `your_file-hihat.mid`
- 등등...

## 기본 드럼 매핑

프로그램에는 Cubase 옥타브 표기를 기반으로 한 **Superior Drummer 3 최적화 매핑**이 내장되어 있습니다.

- **Kick**: A#0, B0, C1  
- **Snare**: F#-2, A0, C#1, D1, D#1, E1, F#3, G3, G#3, A3, A#3, B3, E4, F8, F#8, G8  
- **Hihat**: G-2 ~ E8 (다양한 하이햇 연주 커버)  
- **Ride**: F0, F#0, D#2, F2, B2, F7, F#7, G7, G#7, A7, A#7  
- **Crash**: D#0, E0, G0, G#0, C#2 ~ E7 (넓은 크래시 심벌 범위)  
- **Tom**: F1, G1, A1, B1, C2, C4, C#4, D4, D#4, F4, F#4, G4, G#4, A4, A#4  

## 커스텀 YAML 설정

YAML 형식으로 직접 드럼 매핑을 작성할 수 있습니다.

```yaml
# 사용자 지정 드럼 매핑
drum_parts:
  Kick:
    - C1
    - C#1
  Snare:
    - D1
    - D#1
  # ... 다른 파트 추가
```

"Default Template (.yaml)" 버튼을 클릭하면 내장 매핑을 템플릿으로 내보낼 수 있습니다.

## 독립 실행 파일 만들기

```bash
pip install pyinstaller
pyinstaller --onefile --windowed drum_splitter_gui.py
```

`dist/` 폴더에 실행 파일이 생성됩니다.

## 프로젝트 구조

```
midi-drum-splitter/
├── drum_splitter_gui.py    # 메인 애플리케이션 (테마 포함 단일 파일)
├── requirements.txt        # Python 라이브러리 목록
├── README.md               # 이 파일
├── examples/               # 샘플 MIDI 파일
│   ├── superior_drummer_mapping.mid
│   └── Drum_01.mid
└── dev_resources/          # 개발용 파일
    ├── midi_reader.py      # CLI MIDI 분석기
    └── read_midi_simple.py # 간단한 MIDI 리더
```

## 요구 사항

- Python 3.8 이상
- PyQt6 6.6.0 이상
- mido 1.3.0 이상
- PyYAML 6.0.0 이상

## 라이선스

MIT License – 자세한 내용은 LICENSE 파일 참조

## 참고사항

- GUI 프레임워크로 PyQt6 사용
- MIDI 파일 처리를 위해 mido 사용
- Superior Drummer 3에 최적화된 기본 매핑 제공


# MIDI Drum Splitter

A PyQt6 GUI application that splits drum MIDI files into separate parts (kick, snare, hihat, ride, crash, tom tom) based on note mappings. Supports custom YAML configurations.

## Features

- 🎵 **Single-file drum splitting** - Drag and drop a MIDI file to split it into drum parts
Inter font
- 📝 **Custom YAML mapping** - Load your own drum note mappings or use the built-in Superior Drummer 3 mapping
- 💾 **Persistent preferences** - Remembers your custom YAML configuration
- 🎯 **Cubase octave numbering** - Uses Cubase-compatible note naming (C-2 to B8)
- 📦 **Single executable** - Can be packaged with PyInstaller for standalone distribution

## Quick Start

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/like-daffy/midi-drum-splitter.git
   cd midi-drum-splitter
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application:**
   ```bash
   python drum_splitter_gui.py
   ```

### Usage

1. **Drag and drop** a MIDI file into the application window
2. **(Optional)** Load a custom YAML mapping file using the "Browse..." button
3. **(Optional)** Check "Next time use the same configuration" to remember your settings
4. **Click "Proceed"** to split the MIDI file

Output files will be saved in the same folder as the input file with names like:
- `your_file-kick.mid`
- `your_file-snare.mid`
- `your_file-hihat.mid`
- etc.

## Default Drum Mapping

The application includes a built-in mapping optimized for Superior Drummer 3 with Cubase octave numbering:

- **Kick**: A#0, B0, C1
- **Snare**: F#-2, A0, C#1, D1, D#1, E1, F#3, G3, G#3, A3, A#3, B3, E4, F8, F#8, G8
- **Hihat**: G-2 through E8 (extensive range for different hihat articulations)
- **Ride**: F0, F#0, D#2, F2, B2, F7, F#7, G7, G#7, A7, A#7
- **Crash**: D#0, E0, G0, G#0, C#2 through E7 (wide range for crash cymbals)
- **Tom**: F1, G1, A1, B1, C2, C4, C#4, D4, D#4, F4, F#4, G4, G#4, A4, A#4

## Custom YAML Configuration

You can create your own drum mappings using YAML format:

```yaml
# Custom drum mapping
drum_parts:
  Kick:
    - C1
    - C#1
  Snare:
    - D1
    - D#1
  # ... add more parts
```

Use the "Default Template (.yaml)" button to export the built-in mapping as a starting point.

## Building Standalone Executable

To create a standalone executable:

```bash
pip install pyinstaller
pyinstaller --onefile --windowed drum_splitter_gui.py
```

The executable will be created in the `dist/` folder.

## Project Structure

```
midi-drum-splitter/
├── drum_splitter_gui.py    # Main application (single file with embedded theme)
├── requirements.txt        # Python dependencies
├── README.md              # This file
├── examples/              # Sample MIDI files
│   ├── superior_drummer_mapping.mid
│   └── Drum_01.mid
└── dev_resources/         # Development files
    ├── midi_reader.py     # Command-line MIDI analyzer
    └── read_midi_simple.py # Simple MIDI reader
```

## Requirements

- Python 3.8+
- PyQt6 6.6.0+
- mido 1.3.0+
- PyYAML 6.0.0+

## License

MIT License - see LICENSE file for details

## Acknowledgments

- Built with PyQt6 for the GUI framework
- Uses mido for MIDI file processing
- Default mapping optimized for Superior Drummer 3
