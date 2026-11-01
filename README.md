# headless-demo-capture

Record an animated GIF from an already open Windows window without moving focus or sending input to it.

The Python code calls `snap.exe` once per frame, converts the returned uncompressed 24-bit or 32-bit BMP images, and writes a GIF89a file. The target window must already exist. Window matching and support for inactive or minimized windows come from `snap.exe` and Windows.

## Requirements

- Windows
- Python 3.8 or newer
- `snap.exe` from the published snap project, available on `PATH`

This repository does not ship or build `snap.exe`. Install the executable separately and check it with `where.exe snap.exe` before recording. In PowerShell, include the `.exe` suffix because `where` is also a PowerShell alias.

The project uses only the Python standard library. It does not open a GUI, activate the target window, or send mouse and keyboard input.

Live capture requires an existing matching window in an interactive Windows desktop session. The test command below is the offline verification path.

## Install

Copy the repository files into a directory. No pip install step is required.

## Command line

Open the window you want to record, then run:

```text
python headless_demo_capture.py --window "Calculator" --duration 5 --output docs/demo.gif --fps 10
```

Options:

- `--window`: Window title passed to `snap.exe`. Required.
- `--duration`: Recording duration in seconds. Default: `5.0`.
- `--output`: GIF path. Default: `docs/demo.gif`.
- `--fps`: Capture rate. Default: `10.0`.

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

`demo.py` shows a small API call using a window titled `Notepad`:

```text
python demo.py
```

Change the title before running it if the target window has a different title.

## Tests

The tests use `unittest` and mock the external capture command. They do not open windows, send input, call `snap.exe`, or use the network.

```text
python -m unittest discover tests -v
```

## License

MIT License. Copyright (c) 2026 KitsuneTech1.
