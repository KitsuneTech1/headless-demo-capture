<p align="center"><a href="https://kitsunetechnologies.org/work"><img src="https://raw.githubusercontent.com/KitsuneTech1/.github/main/assets/kitsune-banner.svg" alt="Built by Kitsune Technologies" width="760"></a></p>

# Quiet Demo

Record animated GIFs from Windows windows without stealing focus.

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT"></a>
  <img src="https://img.shields.io/badge/language-Python%203.8+-blue.svg" alt="Python 3.8+">
</p>

The Python code calls `snap.exe` once per frame, converts the returned uncompressed 24-bit or 32-bit BMP images, and writes a GIF89a file. The target window must already exist. Window matching and support for inactive or minimized windows come from `snap.exe` and Windows.

## Requirements

- Windows
- Python 3.8 or newer
- `snap.exe` from the published snap project, available on `PATH`

This repository does not ship or build `snap.exe`. Install the executable separately and check it with `where.exe snap.exe` before recording. In PowerShell, include the `.exe` suffix because `where` is also a PowerShell alias.

The project uses only the Python standard library. It does not open a GUI, activate the target window, or send mouse and keyboard input.

Live capture requires an existing matching window in an interactive Windows desktop session. The test command below is the offline verification path.

## Install

Clone or download this repository. No pip install required; the code uses only the Python standard library.

Before recording, install snap.exe and confirm it is on PATH. The project does not ship snap.exe.

## Quick Start

1. Install snap.exe and verify it is on PATH:
   ```
   where.exe snap.exe
   ```

2. Open the window you want to record, then run:
   ```
   python headless_demo_capture.py --window "Window Title" --duration 5 --fps 10
   ```

   Replace "Window Title" with the exact title of the window to capture. The GIF saves to `docs/demo.gif` by default.

3. Supported options:
   - `--window`: Window title passed to snap.exe. Required.
   - `--duration`: Recording duration in seconds. Default: `5.0`.
   - `--output`: Output GIF path. Default: `docs/demo.gif`.
   - `--fps`: Frame rate. Default: `10.0`.

Capture requests are limited to 100,000 frames. Each `snap.exe` frame request has a 60-second timeout.

The output directory is created when needed. The command exits with an error if `snap.exe` is missing, a frame cannot be captured, a frame is not a supported BMP, or the inputs are invalid.

## Python API

```python
from headless_demo_capture import capture_demo

output_path = capture_demo(
    window="Untitled - Notepad",
    duration=4.0,
    output="docs/demo.gif",
    fps=10.0,
)

print(f"Demo saved to {output_path}")
```

`capture_demo` returns the absolute path to the GIF. Pass `snap_cmd` when the executable is not named `snap.exe` or is not on `PATH`:

```python
capture_demo(window="Calculator", snap_cmd=r"C:\tools\snap.exe")
```

The capture loop is timed with a monotonic clock, so frame spacing is best effort. The GIF uses a fixed 256-color palette.

## Example

`demo.py` shows a small API call. Edit the `target_window` variable to match the title of a window you have open, then run:

```
python demo.py
```

## Tests

The tests use `unittest` and mock the external capture command. They do not open windows, send input, call `snap.exe`, or use the network.

```text
python -m unittest discover tests -v
```

## License

MIT. Copyright (c) 2026 Kitsune Technologies LLC. Do what you like with it, commercially or otherwise, just keep the copyright notice. Full text in [LICENSE](LICENSE).

---

<p align="center"><sub>Part of <b>Buildtober 2026</b>: 31 open source projects in 31 days. Built by <a href="https://kitsunetechnologies.org/work">Kitsune Technologies</a>. More at <a href="https://github.com/KitsuneTech1">github.com/KitsuneTech1</a>.</sub></p>
