"""
headless_demo_capture
Record animated GIF demonstrations from window targets on Windows without stealing focus.
Requires snap.exe available in system PATH.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from typing import List, Sequence, Tuple


__version__ = "0.1.0"


def build_default_palette() -> bytes:
  """Build a standard 256-color RGB palette (6x6x6 color cube + 40 grays)."""
  palette = bytearray()
  # 6x6x6 color cube (216 colors)
  for r in (0, 51, 102, 153, 204, 255):
    for g in (0, 51, 102, 153, 204, 255):
      for b in (0, 51, 102, 153, 204, 255):
        palette.extend((r, g, b))
  # 40 grayscale levels
  for i in range(40):
    val = int(i * 255 / 39)
    palette.extend((val, val, val))
  return bytes(palette)


DEFAULT_PALETTE = build_default_palette()


def quantize_pixel(r: int, g: int, b: int) -> int:
  """Map 24-bit RGB values to the 6x6x6 uniform color cube index (0-215)."""
  r_i = (r * 5 + 127) // 255
  g_i = (g * 5 + 127) // 255
  b_i = (b * 5 + 127) // 255
  return r_i * 36 + g_i * 6 + b_i


def parse_bmp(data: bytes) -> Tuple[int, int, List[int]]:
  """Parse uncompressed 24-bit or 32-bit Windows BMP image data into indexed pixel bytes."""
  if len(data) < 54 or data[:2] != b"BM":
    raise ValueError("Invalid BMP header")

  pixel_offset = int.from_bytes(data[10:14], "little")
  width = int.from_bytes(data[18:22], "little", signed=True)
  height = int.from_bytes(data[22:26], "little", signed=True)
  planes = int.from_bytes(data[26:28], "little")
  bpp = int.from_bytes(data[28:30], "little")
  compression = int.from_bytes(data[30:34], "little")

  if planes != 1:
    raise ValueError(f"Unsupported planes count: {planes}")
  if compression != 0:
    raise ValueError(f"Unsupported BMP compression format: {compression}")
  if bpp not in (24, 32):
    raise ValueError(f"Unsupported bit depth: {bpp} (expected 24 or 32)")

  top_down = height < 0
  abs_width = abs(width)
  abs_height = abs(height)

  bytes_per_pixel = bpp // 8
  row_stride = (abs_width * bytes_per_pixel + 3) & ~3

  indices: List[int] = []
  for row_idx in range(abs_height):
    actual_row = row_idx if top_down else (abs_height - 1 - row_idx)
    row_start = pixel_offset + actual_row * row_stride
    row_bytes = data[row_start : row_start + abs_width * bytes_per_pixel]
    for x in range(abs_width):
      px = row_bytes[x * bytes_per_pixel : (x + 1) * bytes_per_pixel]
      b, g, r = px[0], px[1], px[2]
      indices.append(quantize_pixel(r, g, b))

  return abs_width, abs_height, indices


def _lzw_compress(indices: Sequence[int], min_code_size: int = 8) -> bytes:
  """Compress color indices using GIF-flavored LZW algorithm."""
  clear_code = 1 << min_code_size
  eoi_code = clear_code + 1

  def reset_dict():
    return {bytes([i]): i for i in range(clear_code)}, clear_code + 2, (
        min_code_size + 1
    )

  code_table, next_code, code_size = reset_dict()

  bits_buffer = 0
  bits_count = 0
  byte_stream = bytearray()

  def write_code(code: int, current_size: int):
    nonlocal bits_buffer, bits_count
    bits_buffer |= code << bits_count
    bits_count += current_size
    while bits_count >= 8:
      byte_stream.append(bits_buffer & 0xFF)
      bits_buffer >>= 8
      bits_count -= 8

  write_code(clear_code, code_size)

  pattern = b""
  for idx in indices:
    ch = bytes([idx])
    combined = pattern + ch
    if combined in code_table:
      pattern = combined
    else:
      write_code(code_table[pattern], code_size)
      if next_code < 4096:
        code_table[combined] = next_code
        next_code += 1
        if next_code == (1 << code_size) and code_size < 12:
          code_size += 1
      else:
        write_code(clear_code, code_size)
        code_table, next_code, code_size = reset_dict()
      pattern = ch

  if pattern:
    write_code(code_table[pattern], code_size)
  write_code(eoi_code, code_size)

  if bits_count > 0:
    byte_stream.append(bits_buffer & 0xFF)

  output = bytearray([min_code_size])
  stream_pos = 0
  while stream_pos < len(byte_stream):
    chunk = byte_stream[stream_pos : stream_pos + 255]
    output.append(len(chunk))
    output.extend(chunk)
    stream_pos += len(chunk)
  output.append(0)
  return bytes(output)


def write_gif(
    frames: List[Tuple[int, int, List[int]]], output_path: str, fps: float = 10.0
) -> None:
  """Write a series of parsed frames to an animated GIF89a file."""
  if not frames:
    raise ValueError("Cannot write GIF without frames")

  width, height, _ = frames[0]
  delay_hundredths = max(1, int(round(100.0 / max(fps, 0.1))))

  os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

  with open(output_path, "wb") as f:
    f.write(b"GIF89a")
    f.write(width.to_bytes(2, "little"))
    f.write(height.to_bytes(2, "little"))
    f.write(bytes([0xF7, 0x00, 0x00]))
    f.write(DEFAULT_PALETTE)

    # Netscape 2.0 application extension for looping
    f.write(b"\x21\xFF\x0BNETSCAPE2.0\x03\x01\x00\x00\x00")

    for frame_w, frame_h, indices in frames:
      # Normalize size if window resized slightly during capture
      if frame_w != width or frame_h != height:
        target_indices = [0] * (width * height)
        copy_w = min(width, frame_w)
        copy_h = min(height, frame_h)
        for y in range(copy_h):
          src_start = y * frame_w
          dst_start = y * width
          target_indices[dst_start : dst_start + copy_w] = indices[
              src_start : src_start + copy_w
          ]
        indices = target_indices

      # Graphic Control Extension
      f.write(b"\x21\xF9\x04\x00")
      f.write(delay_hundredths.to_bytes(2, "little"))
      f.write(b"\x00\x00")

      # Image Descriptor
      f.write(b"\x2C\x00\x00\x00\x00")
      f.write(width.to_bytes(2, "little"))
      f.write(height.to_bytes(2, "little"))
      f.write(b"\x00")

      # Image Data
      compressed_data = _lzw_compress(indices, min_code_size=8)
      f.write(compressed_data)

    # GIF Trailer
    f.write(b"\x3B")


def capture_window_frame(
    window: str, output_bmp: str, snap_cmd: str = "snap.exe"
) -> None:
  """Capture a single frame from the specified window without stealing focus using snap.exe."""
  result = subprocess.run(
      [snap_cmd, "--window", window, "--output", output_bmp],
      capture_output=True,
      text=True,
  )
  if result.returncode != 0:
    error_msg = result.stderr.strip() or f"snap.exe exited with code {result.returncode}"
    raise RuntimeError(
        f"Failed to capture frame from window '{window}': {error_msg}"
    )


def capture_demo(
    window: str,
    duration: float = 5.0,
    output: str = "docs/demo.gif",
    fps: float = 10.0,
    snap_cmd: str = "snap.exe",
) -> str:
  """
  Record an animated GIF demo from a target window on Windows without stealing focus.

  Args:
      window: Target window title to record.
      duration: Duration of recording in seconds.
      output: Destination path for the generated GIF file.
      fps: Target capture frame rate.
      snap_cmd: Path or binary name of snap.exe tool.

  Returns:
      Resolved path to the generated GIF.
  """
  if not shutil.which(snap_cmd):
    raise FileNotFoundError(
        f"Required capture utility '{snap_cmd}' was not found in PATH. "
        "Please install snap.exe and verify that it is accessible via PATH."
    )

  if duration <= 0:
    raise ValueError("Duration must be a positive number of seconds.")
  if fps <= 0:
    raise ValueError("FPS must be greater than zero.")

  total_frames = max(1, int(round(duration * fps)))
  frame_interval = 1.0 / fps

  frames: List[Tuple[int, int, List[int]]] = []

  with tempfile.TemporaryDirectory(prefix="demo_capture_") as temp_dir:
    for i in range(total_frames):
      loop_start = time.time()
      frame_file = os.path.join(temp_dir, f"frame_{i:04d}.bmp")

      capture_window_frame(window, frame_file, snap_cmd=snap_cmd)

      with open(frame_file, "rb") as f:
        bmp_data = f.read()

      parsed_frame = parse_bmp(bmp_data)
      frames.append(parsed_frame)

      elapsed = time.time() - loop_start
      remaining_sleep = frame_interval - elapsed
      if remaining_sleep > 0 and i < total_frames - 1:
        time.sleep(remaining_sleep)

    write_gif(frames, output, fps=fps)

  return output


def parse_args(args=None):
  """Parse command line arguments."""
  parser = argparse.ArgumentParser(
      description=(
          "Record animated GIF from a window on Windows without stealing"
          " focus using snap.exe."
      )
  )
  parser.add_argument(
      "--window",
      required=True,
      help="Title of the target window to capture",
  )
  parser.add_argument(
      "--duration",
      type=float,
      default=5.0,
      help="Recording duration in seconds (default: 5.0)",
  )
  parser.add_argument(
      "--output",
      default="docs/demo.gif",
      help="Output path for the recorded GIF (default: docs/demo.gif)",
  )
  parser.add_argument(
      "--fps",
      type=float,
      default=10.0,
      help="Frames per second to record (default: 10.0)",
  )
  return parser.parse_args(args)


def main():
  """CLI entrypoint."""
  args = parse_args()
  try:
    saved_path = capture_demo(
        window=args.window,
        duration=args.duration,
        output=args.output,
        fps=args.fps,
    )
    print(f"Captured demo successfully saved to {saved_path}")
  except Exception as exc:
    print(f"Error: {exc}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
  main()
