"""Create an original, fully synthetic scene with no people or camera footage."""

import argparse
import subprocess
from pathlib import Path

from .video import HEIGHT, WIDTH, _binary


def _draw_box(frame: bytearray, x: int, foot_y: int, color: tuple) -> None:
    for y in range(max(0, foot_y - 21), min(HEIGHT, foot_y)):
        for column in range(max(0, x - 5), min(WIDTH, x + 5)):
            index = (y * WIDTH + column) * 3
            frame[index:index + 3] = bytes(color)


def make_demo_video(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    command = [_binary("ffmpeg"), "-y", "-v", "error", "-f", "rawvideo",
               "-pix_fmt", "rgb24", "-s", f"{WIDTH}x{HEIGHT}", "-r", "10",
               "-i", "pipe:0", "-an", "-c:v", "mjpeg", "-q:v", "3", str(path)]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for index in range(100):
            frame = bytearray(bytes((35, 43, 50)) * (WIDTH * HEIGHT))
            if index >= 10:
                foot = round(26 + min(index - 10, 35) * 1.2)
                _draw_box(frame, 55, foot, (232, 190, 85))
            if index >= 30:
                foot = round(25 + min(index - 30, 40) * 1.0)
                _draw_box(frame, 105, foot, (85, 205, 230))
            if 50 <= index <= 88:
                foot = round(72 - (index - 50) * 1.25)
                _draw_box(frame, 135, foot, (225, 90, 150))
            process.stdin.write(frame)
        process.stdin.close()
        if process.wait(timeout=15):
            raise RuntimeError("模拟视频编码失败：" + process.stderr.read().decode(errors="replace")[-300:])
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        process.stderr.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="生成自制模拟视频")
    parser.add_argument("output", type=Path)
    make_demo_video(parser.parse_args().output)


if __name__ == "__main__":
    main()
