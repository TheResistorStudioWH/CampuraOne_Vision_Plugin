import argparse
import json
import sys
from .estimator import InputError, estimate
from .samples import NAMES, example


def main():
    parser = argparse.ArgumentParser(description='Campura One 独立插件 · 本地模拟试算')
    commands = parser.add_subparsers(dest='command', required=True)
    demo = commands.add_parser('example', help='输出带当前时间的模拟 JSON')
    demo.add_argument('name', choices=NAMES, nargs='?', default='dining')
    calc = commands.add_parser('estimate', help='读取模拟 JSON 文件并试算；- 表示标准输入')
    calc.add_argument('file')
    serve = commands.add_parser('serve', help='启动仅限本机的试算界面')
    serve.add_argument('--port', type=int, default=0)
    serve.add_argument('--open', action='store_true', help='打开系统浏览器')
    args = parser.parse_args()
    try:
        if args.command == 'serve':
            from .server import serve as run
            run(args.port, args.open)
            return
        if args.command == 'example':
            output = example(args.name)
        else:
            if args.file == '-':
                raw = sys.stdin.read(512001)
            else:
                with open(args.file, encoding='utf-8') as stream:
                    raw = stream.read(512001)
            if len(raw.encode('utf-8')) > 512000:
                raise InputError('输入超过 512 KB')
            output = estimate(json.loads(raw))
        print(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False))
    except (InputError, ValueError, OSError) as error:
        print('无法试算：' + str(error), file=sys.stderr)
        raise SystemExit(2)


if __name__ == '__main__':
    main()
