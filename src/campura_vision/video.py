"""Video input boundary. Phase one intentionally accepts local files only."""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Protocol

WIDTH = 160
HEIGHT = 90
FRAME_BYTES = WIDTH * HEIGHT * 3


class VideoError(Exception):
    pass


class SourceDisconnected(VideoError):
    pass


class FrameSource(Protocol):
    fps: float
    recoverable: bool

    def open(self) -> None: ...
    def read(self) -> Optional[bytes]: ...
    def close(self) -> None: ...


def _binary(name: str) -> str:
    found = shutil.which(name)
    if not found:
        raise VideoError(f"找不到 {name}；请安装 FFmpeg 并把 {name} 加入 PATH")
    return found


class LocalFileSource:
    recoverable = False

    def __init__(self, path: Path):
        self.path = Path(path).expanduser().resolve()
        self.fps = 10.0
        self._process: Optional[subprocess.Popen] = None

    def open(self) -> None:
        if not self.path.is_file():
            raise VideoError("视频文件不存在或没有读取权限")
        try:
            probe = subprocess.run(
                [_binary("ffprobe"), "-v", "error", "-select_streams", "v:0",
                 "-show_entries", "stream=width,height,avg_frame_rate",
                 "-of", "json", str(self.path)],
                capture_output=True, text=True, timeout=15, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise VideoError("无法检查视频文件；请确认文件可读且格式受支持") from error
        if probe.returncode or not probe.stdout.strip():
            raise VideoError("无法打开视频：文件损坏、无权限或格式不受 FFmpeg 支持")
        try:
            stream = json.loads(probe.stdout)["streams"][0]
            numerator, denominator = map(int, stream["avg_frame_rate"].split("/"))
            self.fps = min(30.0, max(1.0, numerator / denominator)) if denominator else 10.0
        except (ValueError, KeyError, IndexError, TypeError, ZeroDivisionError) as error:
            raise VideoError("视频没有可解码的视频流") from error
        self._process = subprocess.Popen(
            [_binary("ffmpeg"), "-nostdin", "-v", "error", "-i", str(self.path),
             "-an", "-vf", f"scale={WIDTH}:{HEIGHT}", "-f", "rawvideo",
             "-pix_fmt", "rgb24", "pipe:1"],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )

    def read(self) -> Optional[bytes]:
        if self._process is None or self._process.stdout is None:
            raise VideoError("视频源尚未启动")
        chunks = []
        remaining = FRAME_BYTES
        while remaining:
            chunk = self._process.stdout.read(remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        if not chunks:
            try:
                code = self._process.wait(timeout=5)
            except subprocess.TimeoutExpired as error:
                raise SourceDisconnected("视频解码进程未正常退出") from error
            if code:
                raise SourceDisconnected("视频解码中断；文件可能损坏或格式不受支持")
            return None
        if remaining:
            raise SourceDisconnected("视频画面不完整，分析已停止")
        return b"".join(chunks)

    def close(self) -> None:
        process = self._process
        self._process = None
        if process is None:
            return
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
        if process.stdout:
            process.stdout.close()
        if process.stderr:
            process.stderr.close()
