import tempfile
import unittest
from pathlib import Path

from campura_vision.analysis import Analyzer, Config
from campura_vision.evaluate import evaluate
from campura_vision.runner import analyze_file, run_source
from campura_vision.video import HEIGHT, WIDTH, SourceDisconnected, VideoError, LocalFileSource

ROOT = Path(__file__).resolve().parents[1]


def scene(foot=None):
    frame = bytearray(bytes((35, 43, 50)) * (WIDTH * HEIGHT))
    if foot is not None:
        for y in range(foot - 15, foot):
            for x in range(50, 58):
                position = (y * WIDTH + x) * 3
                frame[position:position + 3] = bytes((220, 150, 90))
    return bytes(frame)


class ScriptedSource:
    fps = 10
    recoverable = True

    def __init__(self):
        self.opens = 0
        self.index = 0

    def open(self):
        self.opens += 1
        self.index = 0

    def read(self):
        if self.opens == 1:
            frames = [scene(), scene(35)]
            if self.index == len(frames):
                raise SourceDisconnected("模拟断流")
        else:
            frames = [scene(), scene(35), scene(42), scene(50), scene(60)]
            if self.index == len(frames):
                return None
        value = frames[self.index]
        self.index += 1
        return value

    def close(self):
        pass


class PipelineTest(unittest.TestCase):
    def test_manual_annotations(self):
        report = evaluate(ROOT / "fixtures/synthetic.avi",
                          ROOT / "fixtures/manual_samples.csv",
                          ROOT / "fixtures/manual_events.csv")
        self.assertEqual(report["frames"], 100)
        self.assertEqual(report["false_event_counts"], 0)
        self.assertEqual(report["missed_event_counts"], 0)
        self.assertEqual(report["queue_mean_absolute_error"], 0)

    def test_disconnect_reconnect_discards_old_tracks(self):
        source = ScriptedSource()
        states = []
        result = run_source(source, Analyzer(Config()),
                            on_state=lambda state, detail: states.append(state),
                            reconnect_delay=0)
        self.assertEqual(source.opens, 2)
        self.assertIn("disconnected", states)
        self.assertEqual(states[-1], "complete")
        self.assertEqual((result.entries, result.exits), (1, 0))

    def test_missing_video_has_clear_error(self):
        with self.assertRaisesRegex(VideoError, "不存在"):
            analyze_file(ROOT / "fixtures/not-present.avi")

    def test_unsupported_format_has_clear_error(self):
        with tempfile.TemporaryDirectory() as directory:
            bad_file = Path(directory) / "broken.avi"
            bad_file.write_bytes(b"not a video")
            with self.assertRaisesRegex(VideoError, "无法打开视频"):
                analyze_file(bad_file)

    def test_bad_geometry_rejected(self):
        with self.assertRaisesRegex(ValueError, "两个不同端点"):
            Config.from_dict({"line": [[0.5, 0.5], [0.5, 0.5]]})


if __name__ == "__main__":
    unittest.main()
