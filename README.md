# headless-demo-capture

headless-demo-capture is a lightweight Python utility to record animated GIF demonstrations from a target window on Windows without stealing focus.

It captures background or inactive windows cleanly so you can produce clear documentation and demo recordings while continuing to work.

## Requirements

- Python 3.8 or higher (uses only Python standard library modules).
- Windows operating system.
- `snap.exe` installed and available in your system PATH.

### Notice About snap.exe

headless-demo-capture does not hook into Windows display drivers or inject code into other processes. It delegates non-intrusive window capture to the standalone `snap.exe` utility. You must have `snap.exe` installed on your machine and discoverable in PATH.

If `snap.exe` is not found, the tool will exit cleanly and inform you that the executable is missing.

## Installation

headless-demo-capture uses only the Python standard library. No pip dependencies are required.

Clone or copy the repository files into your project:

```bash
git clone https://github.com/KitsuneTech1/headless-demo-capture.git
cd headless-demo-capture
```

## CLI Usage

Record a demo from any open window by title:

```bash
python headless_demo_capture.py --window "Calculator" --duration 5 --output docs/demo.gif --fps 10
```

### Options

- `--window`: Title of the window to capture (required).
- `--duration`: Total duration of recording in seconds (default: 5.0).
- `--output`: File destination path for the recorded GIF (default: docs/demo.gif).
- `--fps`: Frame capture rate in frames per second (default: 10.0).

## Python API Usage

You can import and call `capture_demo` directly in Python scripts:

```python
from headless_demo_capture import capture_demo

output_path = capture_demo(
    window="Untitled - Notepad",
    duration=4.0,
    output="docs/demo.gif",
    fps=10.0
)

print(f"Demo saved to {output_path}")
```

## Running the Example

A sample script is provided in `demo.py`:

```bash
python demo.py
```

## Running Tests

All unit tests use the standard library `unittest` module and do not require external test runners:

```bash
python -m unittest discover tests
```

## License

MIT License. Copyright (c) 2026 KitsuneTech1.
