"""
Unit tests for headless_demo_capture.
Tests verify BMP parsing, GIF LZW compression, output file construction,
CLI argument handling, and capture logic with mocked snap.exe commands.
"""

import io
import math
import os
import shutil
import sys
import unittest
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import headless_demo_capture as hdc


TEST_TEMP_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".test-tmp-safe",
)


@contextmanager
def fixed_temp_dir(name):
  """Use stable repo-local paths for runners that restrict random temp dirs."""
  path = os.path.join(TEST_TEMP_ROOT, name)
  os.makedirs(path, exist_ok=True)
  try:
    yield path
  finally:
    shutil.rmtree(path, ignore_errors=True)
    if os.path.isdir(TEST_TEMP_ROOT) and not os.listdir(TEST_TEMP_ROOT):
      os.rmdir(TEST_TEMP_ROOT)


def make_test_bmp(
    width: int = 4,
    height: int = 4,
    color: tuple = (255, 0, 0),
    bpp: int = 24,
    top_down: bool = False,
) -> bytes:
  """Generate raw uncompressed BMP bytes for testing."""
  bytes_per_pixel = bpp // 8
  row_stride = (width * bytes_per_pixel + 3) & ~3
  pixel_data = bytearray()
  padding = b"\x00" * (row_stride - width * bytes_per_pixel)

  b, g, r = color[2], color[1], color[0]
  pixel = bytes([b, g, r]) if bpp == 24 else bytes([b, g, r, 255])
  row = pixel * width + padding

  for _ in range(height):
    pixel_data.extend(row)

  header_size = 54
  file_size = header_size + len(pixel_data)
  stored_height = -height if top_down else height

  header = bytearray(b"BM")
  header.extend(file_size.to_bytes(4, "little"))
  header.extend((0).to_bytes(4, "little"))
  header.extend(header_size.to_bytes(4, "little"))
  header.extend((40).to_bytes(4, "little"))
  header.extend(width.to_bytes(4, "little", signed=True))
  header.extend(stored_height.to_bytes(4, "little", signed=True))
  header.extend((1).to_bytes(2, "little"))
  header.extend(bpp.to_bytes(2, "little"))
  header.extend((0).to_bytes(4, "little"))
  header.extend(len(pixel_data).to_bytes(4, "little"))
  header.extend((2835).to_bytes(4, "little"))
  header.extend((2835).to_bytes(4, "little"))
  header.extend((0).to_bytes(4, "little"))
  header.extend((0).to_bytes(4, "little"))
  header.extend(pixel_data)
  return bytes(header)


class TestHeadlessDemoCapture(unittest.TestCase):

  def test_parse_bmp_valid_24bit(self):
    bmp_bytes = make_test_bmp(width=6, height=3, color=(0, 255, 0), bpp=24)
    w, h, indices = hdc.parse_bmp(bmp_bytes)
    self.assertEqual(w, 6)
    self.assertEqual(h, 3)
    self.assertEqual(len(indices), 18)
    # Color (0, 255, 0) maps to quantized index 30 in 6x6x6 cube
    expected_idx = hdc.quantize_pixel(0, 255, 0)
    self.assertEqual(indices[0], expected_idx)

  def test_parse_bmp_valid_32bit_top_down(self):
    bmp_bytes = make_test_bmp(
        width=2, height=2, color=(0, 0, 255), bpp=32, top_down=True
    )
    w, h, indices = hdc.parse_bmp(bmp_bytes)
    self.assertEqual(w, 2)
    self.assertEqual(h, 2)
    self.assertEqual(len(indices), 4)

  def test_parse_bmp_invalid_header(self):
    with self.assertRaises(ValueError):
      hdc.parse_bmp(b"NOT_A_BMP_DATA_HEADER")

  def test_parse_bmp_unsupported_bpp(self):
    bmp_bytes = make_test_bmp(width=2, height=2, bpp=24)
    # Tamper with bpp field at offset 28
    tampered = bytearray(bmp_bytes)
    tampered[28:30] = (16).to_bytes(2, "little")
    with self.assertRaises(ValueError):
      hdc.parse_bmp(bytes(tampered))

  def test_parse_bmp_truncated_pixels_raise(self):
    bmp_bytes = make_test_bmp(width=3, height=2)
    with self.assertRaisesRegex(ValueError, "truncated"):
      hdc.parse_bmp(bmp_bytes[:-1])

  def test_parse_bmp_invalid_dimensions_raise(self):
    bmp_bytes = bytearray(make_test_bmp(width=2, height=2))
    bmp_bytes[18:22] = (0).to_bytes(4, "little", signed=True)
    with self.assertRaisesRegex(ValueError, "width"):
      hdc.parse_bmp(bytes(bmp_bytes))

  def test_lzw_compression(self):
    indices = [hdc.quantize_pixel(255, 255, 255)] * 64
    compressed = hdc._lzw_compress(indices, min_code_size=8)
    self.assertTrue(len(compressed) > 0)
    self.assertEqual(compressed[0], 8)  # Minimum code size header
    self.assertEqual(compressed[-1], 0)  # Block terminator

  def test_write_gif_creates_valid_structure(self):
    frame1 = (2, 2, [0, 1, 2, 3])
    frame2 = (2, 2, [3, 2, 1, 0])
    with fixed_temp_dir("write-valid") as temp_dir:
      out_path = os.path.join(temp_dir, "test.gif")
      hdc.write_gif([frame1, frame2], out_path, fps=5.0)

      self.assertTrue(os.path.exists(out_path))
      with open(out_path, "rb") as f:
        data = f.read()

      self.assertTrue(data.startswith(b"GIF89a"))
      self.assertIn(b"NETSCAPE2.0", data)
      self.assertTrue(data.endswith(b"\x3B"))

  def test_write_gif_empty_frames_raises(self):
    with fixed_temp_dir("write-empty") as temp_dir:
      out_path = os.path.join(temp_dir, "empty.gif")
      with self.assertRaises(ValueError):
        hdc.write_gif([], out_path)

  def test_write_gif_creates_missing_output_directory(self):
    with fixed_temp_dir("write-parent") as temp_dir:
      out_path = os.path.join(temp_dir, "nested", "demo.gif")
      hdc.write_gif([(1, 1, [0])], out_path)
      self.assertTrue(os.path.isfile(out_path))

  def test_write_gif_rejects_bad_frame(self):
    with fixed_temp_dir("write-bad-frame") as temp_dir:
      out_path = os.path.join(temp_dir, "bad.gif")
      with self.assertRaisesRegex(ValueError, "pixel count"):
        hdc.write_gif([(2, 2, [0, 1, 2])], out_path)

  def test_write_gif_rejects_non_finite_fps(self):
    with fixed_temp_dir("write-bad-fps") as temp_dir:
      out_path = os.path.join(temp_dir, "bad.gif")
      with self.assertRaises(ValueError):
        hdc.write_gif([(1, 1, [0])], out_path, fps=math.inf)

  def test_cli_argument_parsing(self):
    args = hdc.parse_args([
        "--window",
        "Notepad",
        "--duration",
        "2.5",
        "--output",
        "output.gif",
        "--fps",
        "12",
    ])
    self.assertEqual(args.window, "Notepad")
    self.assertEqual(args.duration, 2.5)
    self.assertEqual(args.output, "output.gif")
    self.assertEqual(args.fps, 12.0)

  def test_cli_default_arguments(self):
    args = hdc.parse_args(["--window", "Calculator"])
    self.assertEqual(args.window, "Calculator")
    self.assertEqual(args.duration, 5.0)
    self.assertEqual(args.output, "docs/demo.gif")
    self.assertEqual(args.fps, 10.0)

  def test_capture_demo_missing_snap_tool(self):
    with patch("shutil.which", return_value=None):
      with self.assertRaises(FileNotFoundError) as ctx:
        hdc.capture_demo("Window Title")
      self.assertIn("snap.exe", str(ctx.exception))

  def test_capture_demo_invalid_duration_or_fps(self):
    with patch("shutil.which", return_value="C:\\tools\\snap.exe"):
      with self.assertRaises(ValueError):
        hdc.capture_demo("Window Title", duration=-1.0)
      with self.assertRaises(ValueError):
        hdc.capture_demo("Window Title", fps=0)
      with self.assertRaises(ValueError):
        hdc.capture_demo("", duration=1.0)
      with self.assertRaises(ValueError):
        hdc.capture_demo("Window Title", duration=math.nan)
      with self.assertRaisesRegex(ValueError, "non-empty path"):
        hdc.capture_demo("Window Title", output="")

  @patch("shutil.which", return_value="C:\\tools\\snap.exe")
  @patch("headless_demo_capture.capture_window_frame", side_effect=RuntimeError("capture failed"))
  def test_capture_demo_preserves_capture_error(self, mock_capture, mock_which):
    with self.assertRaisesRegex(RuntimeError, "capture failed"):
      hdc.capture_demo("Window Title", duration=1.0, fps=1.0)

  @patch("subprocess.run")
  def test_capture_window_frame_reports_missing_output(self, mock_subprocess_run):
    mock_result = MagicMock(returncode=0, stderr="")
    mock_subprocess_run.return_value = mock_result
    with fixed_temp_dir("capture-missing") as temp_dir:
      output_bmp = os.path.join(temp_dir, "missing.bmp")
      with self.assertRaisesRegex(RuntimeError, "did not create"):
        hdc.capture_window_frame("Test Window", output_bmp, snap_cmd="snap.exe")
    mock_subprocess_run.assert_called_once_with(
        ["snap.exe", "--window", "Test Window", "--output", output_bmp],
        capture_output=True,
        text=True,
    )

  @patch("subprocess.run")
  def test_capture_window_frame_reports_command_failure(self, mock_subprocess_run):
    mock_subprocess_run.return_value = MagicMock(
        returncode=2, stderr="window not found"
    )
    with fixed_temp_dir("capture-failure") as temp_dir:
      output_bmp = os.path.join(temp_dir, "failed.bmp")
      with self.assertRaisesRegex(RuntimeError, "window not found"):
        hdc.capture_window_frame("Test Window", output_bmp, snap_cmd="snap.exe")

  def test_main_reports_capture_error(self):
    stderr = io.StringIO()
    with patch.object(sys, "argv", ["headless_demo_capture.py", "--window", "Test"]):
      with patch.object(
          hdc, "capture_demo", side_effect=RuntimeError("capture failed")
      ):
        with patch.object(sys, "stderr", stderr):
          with self.assertRaises(SystemExit) as exit_info:
            hdc.main()

    self.assertEqual(exit_info.exception.code, 1)
    self.assertIn("Error: capture failed", stderr.getvalue())

  @patch("headless_demo_capture.time.sleep", return_value=None)
  @patch("shutil.which", return_value="C:\\tools\\snap.exe")
  @patch("subprocess.run")
  def test_capture_demo_success(
      self, mock_subprocess_run, mock_which, mock_sleep
  ):
    test_bmp = make_test_bmp(width=4, height=4, color=(128, 64, 32))

    def side_effect(cmd, capture_output=True, text=True):
      output_idx = cmd.index("--output") + 1
      bmp_target = cmd[output_idx]
      with open(bmp_target, "wb") as f:
        f.write(test_bmp)
      mock_res = MagicMock()
      mock_res.returncode = 0
      mock_res.stderr = ""
      return mock_res

    mock_subprocess_run.side_effect = side_effect

    with fixed_temp_dir("capture-output") as temp_dir:
      out_gif = os.path.join(temp_dir, "demo_result.gif")
      with fixed_temp_dir("capture-work") as capture_dir:
        with patch.object(hdc.tempfile, "mkdtemp", return_value=capture_dir):
          res = hdc.capture_demo(
              window="Test Window",
              duration=0.2,
              output=out_gif,
              fps=5.0,
          )
      self.assertEqual(res, out_gif)
      self.assertTrue(os.path.exists(out_gif))
      with open(out_gif, "rb") as f:
        content = f.read()
      self.assertTrue(content.startswith(b"GIF89a"))
      self.assertTrue(content.endswith(b"\x3B"))


if __name__ == "__main__":
  unittest.main()
