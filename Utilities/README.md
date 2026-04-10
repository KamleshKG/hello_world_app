# PyPlayer 🎬

A modern, lightweight media player built in Python.

## Supported formats
Video: MP4, MKV, AVI, MOV, WEBM, FLV, WMV, M4V, TS, MPG
Audio: MP3, FLAC, WAV, OGG, M4A, AAC, OPUS, WMA

## Setup

### 1. Install mpv (the media engine)
```
# Windows (winget)
winget install mpv

# Windows (choco)
choco install mpv

# macOS
brew install mpv

# Ubuntu/Debian
sudo apt install mpv libmpv-dev
```

### 2. Install Python dependencies
```
pip install -r requirements.txt
```

### 3. Run
```
python player.py

# Or open files directly
python player.py /path/to/video.mp4
```

## Keyboard shortcuts
| Key          | Action              |
|--------------|---------------------|
| Space        | Play / Pause        |
| ← / →        | Seek -5s / +5s      |
| ↑ / ↓        | Volume +5 / -5      |
| F11          | Toggle fullscreen   |
| Escape       | Exit fullscreen     |

## Features
- Hardware-accelerated video playback (GPU via mpv/libmpv)
- Playlist with drag-to-add and folder scanning
- Metadata reading (title, artist, duration via mutagen)
- Audio-art placeholder for music files
- Shuffle and repeat (none / all / one)
- Seek bar with click and drag
- Volume control
- Fullscreen mode
- Supports CLI file arguments

## Windows note
After installing mpv via winget, you may need to add mpv to PATH or place
`mpv-2.dll` (from https://sourceforge.net/projects/mpv-player-windows/files/libmpv/)
in the same folder as player.py. python-mpv looks for libmpv on PATH.
