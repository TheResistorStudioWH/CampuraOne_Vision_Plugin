"""Command-line entry point for a separate, optional local program."""

import argparse
import json
from pathlib import Path

from .analysis import Config
from .demo import make_demo_video
from .runner import analyze_file
from .server import serve
from .video import VideoError


def main() -> None:
    parser = argparse.ArgumentParser(description="Campura One 店内视觉分析离线原型")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("make-demo", help="生成合法的自制模拟视频")
    demo.add_argument("output", type=Path)
    analyze = sub.add_parser("analyze", help="离线统计并输出本机 JSON")
    analyze.add_argument("video", type=Path)
    analyze.add_argument("--config", type=Path)
    viewer = sub.add_parser("serve", help="打开本机预览和配置页面")
    viewer.add_argument("video", type=Path)
    viewer.add_argument("--port", type=int, default=0)
    viewer.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "make-demo":
            make_demo_video(args.output)
            print("模拟视频已生成：" + str(args.output))
        elif args.command == "analyze":
            config = Config.from_dict(json.loads(args.config.read_text())) if args.config else Config()
            print(json.dumps(analyze_file(args.video, config).to_dict(), ensure_ascii=False, indent=2))
        else:
            serve(args.video, args.port, not args.no_browser)
    except (VideoError, ValueError) as error:
        parser.exit(2, "错误：" + str(error) + "\n")


if __name__ == "__main__":
    main()
