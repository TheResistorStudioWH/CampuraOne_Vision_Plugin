"""Compare the synthetic video against manually entered event and sample labels."""

import csv
import json
from pathlib import Path

from .analysis import Analyzer, Config
from .runner import run_source
from .video import LocalFileSource


def evaluate(video: Path, samples_csv: Path, events_csv: Path) -> dict:
    with samples_csv.open(newline="", encoding="utf-8") as source:
        samples = {int(row["frame"]): row for row in csv.DictReader(source)}
    with events_csv.open(newline="", encoding="utf-8") as source:
        labels = [(int(row["frame"]), row["event"]) for row in csv.DictReader(source)]
    predicted_samples = {}
    predicted_events = []
    previous_entries = previous_exits = 0

    def on_frame(frame, result):
        nonlocal previous_entries, previous_exits
        index = result.frame_index - 1
        if index in samples:
            predicted_samples[index] = (result.entries, result.exits, result.queue_count)
        if result.entries > previous_entries:
            predicted_events.extend((index, "entry") for _ in range(result.entries - previous_entries))
        if result.exits > previous_exits:
            predicted_events.extend((index, "exit") for _ in range(result.exits - previous_exits))
        previous_entries, previous_exits = result.entries, result.exits

    result = run_source(LocalFileSource(video), Analyzer(Config()), on_frame)
    if len(predicted_samples) != len(samples):
        raise ValueError("标注帧超出视频范围")
    remaining = predicted_events[:]
    matched = 0
    for label_frame, label_type in labels:
        possible = [item for item in remaining if item[1] == label_type and abs(item[0] - label_frame) <= 1]
        if possible:
            selected = min(possible, key=lambda item: abs(item[0] - label_frame))
            remaining.remove(selected)
            matched += 1
    queue_abs_errors = []
    count_abs_errors = []
    for index, label in samples.items():
        predicted = predicted_samples[index]
        expected = tuple(int(label[key]) for key in ("entries", "exits", "queue"))
        count_abs_errors.append(abs(predicted[0] - expected[0]) + abs(predicted[1] - expected[1]))
        queue_abs_errors.append(abs(predicted[2] - expected[2]))
    return {
        "frames": result.frame_index,
        "labeled_events": len(labels),
        "matched_events_within_one_frame": matched,
        "false_event_counts": len(remaining),
        "missed_event_counts": len(labels) - matched,
        "sampled_frames": len(samples),
        "sampled_cumulative_count_absolute_error": sum(count_abs_errors),
        "queue_mean_absolute_error": sum(queue_abs_errors) / len(queue_abs_errors),
        "queue_max_absolute_error": max(queue_abs_errors),
        "predicted_events": predicted_events,
    }


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    report = evaluate(root / "fixtures/synthetic.avi",
                      root / "fixtures/manual_samples.csv",
                      root / "fixtures/manual_events.csv")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
