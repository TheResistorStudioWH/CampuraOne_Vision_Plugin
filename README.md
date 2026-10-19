# Campura One 店内视觉分析插件

商家可选安装的独立项目。当前版本是**单机位、离线、模拟视频原型**，不连接商家端、学生端、PHP、生产环境或真实校园监控。Windows 与 macOS 均为产品目标平台；目前仅在 macOS 上实际运行验证，Windows 尚未构建或运行验证。

## 已实现

- 使用自制模拟视频，读取本机文件并显示本机预览。
- 点击画面绘制计数线（两点）和排队区域（四点），选择两个分析任务。
- 静态背景前景检测、短时跟踪、进出计数、排队区域人数；检测器接口可替换。
- 断流状态、有限重连流程和重连后轨迹重置的模拟测试。
- 只在 `127.0.0.1` 开启临时页面及结果接口，随机令牌保护；不保存画面或身份轨迹。
- 明确显示当前排队人数是否有效；预计等候时间固定为空，因为没有订单／服务速度数据。

这套检测器依赖首帧为空、固定背景和明显前景，**不具备真实行人检测能力**。目前没有 USB 或网络摄像头适配，没有安装包，也没有云模型调用。

## 运行

需要 Python 3.9+、`ffmpeg` 和 `ffprobe` 在 `PATH` 中。FFmpeg 由开发者自行安装；仓库不包含其二进制文件。

macOS / Linux 开发环境：

```bash
PYTHONPATH=src python3 -m campura_vision.cli make-demo fixtures/synthetic.avi
PYTHONPATH=src python3 -m campura_vision.cli analyze fixtures/synthetic.avi
PYTHONPATH=src python3 -m campura_vision.evaluate
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m campura_vision.cli serve fixtures/synthetic.avi
```

Windows PowerShell（**待 Windows 实机验证**）：

```powershell
$env:PYTHONPATH = 'src'
py -3 -m campura_vision.cli make-demo fixtures\synthetic.avi
py -3 -m campura_vision.cli analyze fixtures\synthetic.avi
py -3 -m campura_vision.evaluate
py -3 -m unittest discover -s tests -v
py -3 -m campura_vision.cli serve fixtures\synthetic.avi
```

`serve` 只读本机路径，页面会显示随机本机 URL。停止程序使用终端 Ctrl+C。URL 中的令牌只用于本次运行，不写入仓库。请不要提交真实摄像头地址、密码、视频或日志。

## 标注与结果

`fixtures/synthetic.avi` 为本项目程序绘制的矩形人物模拟画面，无真人。查看了 0–99 帧中的 11 个采样帧及三次穿线附近的逐帧画面后，人工填入 `manual_samples.csv` 与 `manual_events.csv`。事件容差为 ±1 帧；测试输出见 [验证记录](docs/VALIDATION.md)。这一小段简单画面的零误差不能推广到真实门店。

## 文档

- [路线图与阶段状态](docs/ROADMAP.md)
- [架构、视频适配与本地接口](docs/ARCHITECTURE.md)
- [许可清单与发行前检查](docs/THIRD_PARTY.md)
- [验证记录](docs/VALIDATION.md)

本仓库自有代码采用 MIT 许可证。FFmpeg、未来的推理运行时、检测模型权重和云模型服务均按各自许可或服务条款核查。
