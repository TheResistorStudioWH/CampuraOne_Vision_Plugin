"""Small replaceable detector, short-lived tracker and counting pipeline.

This reference detector compares each frame against the first, empty frame.
It is only suitable for a static synthetic scene, never a validated people model.
"""

from dataclasses import dataclass, field
from math import hypot
from typing import List, Protocol, Sequence, Tuple

Point = Tuple[float, float]


@dataclass(frozen=True)
class Config:
    line: Tuple[Point, Point] = ((0.1, 0.5), (0.9, 0.5))
    queue_zone: Tuple[Point, ...] = ((0.2, 0.58), (0.5, 0.58), (0.5, 0.9), (0.2, 0.9))
    count_entries: bool = True
    count_queue: bool = True

    @classmethod
    def from_dict(cls, value: dict) -> "Config":
        if not isinstance(value, dict):
            raise ValueError("配置必须是对象")
        def point(raw: Sequence[float]) -> Point:
            if not isinstance(raw, (list, tuple)) or len(raw) != 2:
                raise ValueError("坐标必须是两个数字")
            x, y = float(raw[0]), float(raw[1])
            if not (0 <= x <= 1 and 0 <= y <= 1):
                raise ValueError("坐标必须在画面内（0 到 1）")
            return x, y

        line = tuple(point(p) for p in value.get("line", cls.line))
        zone = tuple(point(p) for p in value.get("queue_zone", cls.queue_zone))
        if len(line) != 2 or line[0] == line[1]:
            raise ValueError("计数线需要两个不同端点")
        if len(zone) < 3 or len(set(zone)) < 3:
            raise ValueError("排队区域至少需要三个不同顶点")
        area = abs(sum(zone[i][0] * zone[(i + 1) % len(zone)][1]
                       - zone[(i + 1) % len(zone)][0] * zone[i][1]
                       for i in range(len(zone)))) / 2
        if area < 0.0001:
            raise ValueError("排队区域面积过小或顶点顺序交叉")
        entries = value.get("count_entries", True)
        queue = value.get("count_queue", True)
        if not isinstance(entries, bool) or not isinstance(queue, bool):
            raise ValueError("分析任务开关必须是布尔值")
        return cls(line, zone, entries, queue)

    def to_dict(self) -> dict:
        return {
            "line": self.line,
            "queue_zone": self.queue_zone,
            "count_entries": self.count_entries,
            "count_queue": self.count_queue,
        }


@dataclass(frozen=True)
class Detection:
    foot: Point
    box: Tuple[int, int, int, int]


class Detector(Protocol):
    def detect(self, rgb: bytes, width: int, height: int) -> List[Detection]: ...
    def reset(self) -> None: ...


class BackgroundDifferenceDetector:
    """Reference detector for a fixed synthetic view with an empty first frame."""

    def __init__(self, threshold: int = 105, min_area: int = 18):
        self.background: bytes = b""
        self.threshold = threshold
        self.min_area = min_area

    def reset(self) -> None:
        self.background = b""

    def detect(self, rgb: bytes, width: int, height: int) -> List[Detection]:
        if len(rgb) != width * height * 3:
            raise ValueError("解码画面大小不正确")
        if not self.background:
            self.background = rgb
            return []
        bg = self.background
        mask = bytearray(width * height)
        for i in range(width * height):
            j = i * 3
            if (abs(rgb[j] - bg[j]) + abs(rgb[j + 1] - bg[j + 1])
                    + abs(rgb[j + 2] - bg[j + 2])) >= self.threshold:
                mask[i] = 1

        found: List[Detection] = []
        for seed in range(len(mask)):
            if not mask[seed]:
                continue
            mask[seed] = 0
            stack = [seed]
            count = 0
            min_x = max_x = seed % width
            min_y = max_y = seed // width
            while stack:
                current = stack.pop()
                x, y = current % width, current // width
                count += 1
                min_x, max_x = min(min_x, x), max(max_x, x)
                min_y, max_y = min(min_y, y), max(max_y, y)
                for neighbor in (current - 1 if x else -1,
                                 current + 1 if x + 1 < width else -1,
                                 current - width if y else -1,
                                 current + width if y + 1 < height else -1):
                    if neighbor >= 0 and mask[neighbor]:
                        mask[neighbor] = 0
                        stack.append(neighbor)
            if count >= self.min_area:
                found.append(Detection(
                    ((min_x + max_x + 1) / (2 * width), (max_y + 1) / height),
                    (min_x, min_y, max_x + 1, max_y + 1),
                ))
        return found


def side(point: Point, line: Tuple[Point, Point]) -> float:
    (ax, ay), (bx, by) = line
    return (bx - ax) * (point[1] - ay) - (by - ay) * (point[0] - ax)


def inside(point: Point, polygon: Sequence[Point]) -> bool:
    x, y = point
    result = False
    j = len(polygon) - 1
    for i in range(len(polygon)):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            result = not result
        j = i
    return result


@dataclass
class Track:
    id: int
    foot: Point
    last_side: int
    missed: int = 0


@dataclass
class Result:
    entries: int = 0
    exits: int = 0
    queue_count: int = 0
    frame_index: int = 0
    detections: List[Detection] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "entries": self.entries,
            "exits": self.exits,
            "queue_count": self.queue_count,
            "frame_index": self.frame_index,
            "detected_objects": len(self.detections),
            "eta_minutes": None,
        }


class Analyzer:
    def __init__(self, config: Config, detector: Detector = None):
        self.config = config
        self.detector = detector or BackgroundDifferenceDetector()
        self.result = Result()
        self._tracks: List[Track] = []
        self._next_id = 1

    def reset_after_gap(self) -> None:
        """Keep aggregates; discard identities and stale queue count after a gap."""
        self.detector.reset()
        self._tracks.clear()
        self.result.queue_count = 0
        self.result.detections = []

    def process(self, rgb: bytes, width: int, height: int) -> Result:
        detections = self.detector.detect(rgb, width, height)
        available = set(range(len(detections)))
        for track in self._tracks:
            nearest = min(available, key=lambda i: hypot(
                track.foot[0] - detections[i].foot[0],
                track.foot[1] - detections[i].foot[1]), default=None)
            if nearest is None or hypot(
                    track.foot[0] - detections[nearest].foot[0],
                    track.foot[1] - detections[nearest].foot[1]) > 0.18:
                track.missed += 1
                continue
            current = detections[nearest].foot
            available.remove(nearest)
            if self.config.count_entries:
                raw_side = side(current, self.config.line)
                new_side = (raw_side > 0) - (raw_side < 0)
                if track.last_side < 0 < new_side:
                    self.result.entries += 1
                elif track.last_side > 0 > new_side:
                    self.result.exits += 1
                if new_side:
                    track.last_side = new_side
            track.foot = current
            track.missed = 0
        self._tracks = [track for track in self._tracks if track.missed <= 3]
        for index in sorted(available):
            raw_side = side(detections[index].foot, self.config.line)
            self._tracks.append(Track(self._next_id, detections[index].foot,
                                      (raw_side > 0) - (raw_side < 0)))
            self._next_id += 1
        self.result.queue_count = sum(
            inside(item.foot, self.config.queue_zone) for item in detections
        ) if self.config.count_queue else 0
        self.result.detections = detections
        self.result.frame_index += 1
        return self.result
