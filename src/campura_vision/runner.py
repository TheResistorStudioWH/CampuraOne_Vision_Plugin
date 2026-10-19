"""Source lifecycle, disconnect handling and offline evaluation."""

import time
from pathlib import Path
from threading import Event
from typing import Callable, Optional

from .analysis import Analyzer, Config, Result
from .video import FrameSource, LocalFileSource, SourceDisconnected, VideoError, WIDTH, HEIGHT

FrameCallback = Callable[[bytes, Result], None]
StateCallback = Callable[[str, str], None]


def run_source(source: FrameSource, analyzer: Analyzer,
               on_frame: FrameCallback = lambda frame, result: None,
               on_state: StateCallback = lambda state, detail: None,
               stop: Optional[Event] = None, paced: bool = False,
               reconnect_delay: float = 1.0, max_retries: int = 3) -> Result:
    stop = stop or Event()
    failures = 0
    while not stop.is_set():
        try:
            source.open()
            on_state("running", "正在分析本机画面")
            next_frame_at = time.monotonic()
            while not stop.is_set():
                frame = source.read()
                if frame is None:
                    on_state("complete", "视频播放结束；显示的是最后一帧统计")
                    return analyzer.result
                result = analyzer.process(frame, WIDTH, HEIGHT)
                on_frame(frame, result)
                if paced:
                    next_frame_at += 1 / max(1.0, source.fps)
                    stop.wait(max(0.0, next_frame_at - time.monotonic()))
            on_state("stopped", "已停止；当前排队人数不再实时更新")
            return analyzer.result
        except (SourceDisconnected, VideoError, OSError, ValueError) as error:
            analyzer.reset_after_gap()
            if not source.recoverable or failures >= max_retries or stop.is_set():
                on_state("error", str(error))
                return analyzer.result
            failures += 1
            on_state("disconnected", f"视频中断：{error}；准备第 {failures} 次重连")
            stop.wait(reconnect_delay)
        finally:
            source.close()
    on_state("stopped", "已停止；当前排队人数不再实时更新")
    return analyzer.result


def analyze_file(path: Path, config: Config = Config()) -> Result:
    final_state = []
    result = run_source(LocalFileSource(path), Analyzer(config),
                        on_state=lambda state, detail: final_state.append((state, detail)))
    if final_state and final_state[-1][0] == "error":
        raise VideoError(final_state[-1][1])
    return result
