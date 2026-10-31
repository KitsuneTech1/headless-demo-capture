"""
Usage example for headless-demo-capture.
Demonstrates recording a target window into an animated GIF.
"""

import sys
from headless_demo_capture import capture_demo


def main():
  target_window = "Notepad"
  output_file = "docs/demo.gif"
  duration_seconds = 3.0
  fps_rate = 8.0

  print(f"Starting capture of window '{target_window}'...")
  print(f"Target duration: {duration_seconds}s at {fps_rate} FPS")
  print(f"Target output file: {output_file}")

  try:
    result_path = capture_demo(
        window=target_window,
        duration=duration_seconds,
        output=output_file,
        fps=fps_rate,
    )
    print(f"Recording complete. Output saved to: {result_path}")
  except FileNotFoundError as err:
    print(f"Environment error: {err}")
    print(
        "Ensure snap.exe is installed and present in your system PATH before"
        " running."
    )
    sys.exit(1)
  except RuntimeError as err:
    print(f"Capture error: {err}")
    sys.exit(1)


if __name__ == "__main__":
  main()
