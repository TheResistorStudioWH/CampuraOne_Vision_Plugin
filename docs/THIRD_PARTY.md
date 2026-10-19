# 第三方许可与发行前核查

当前仓库自有代码是 MIT；模拟视频由本项目代码绘制。运行时需要系统自行提供的 FFmpeg CLI，仓库**不捆绑** FFmpeg、检测权重或 ONNX Runtime。

| 组件 | 已核实事实 | 当前使用 | 发行前动作 |
| --- | --- | --- | --- |
| FFmpeg | 官方说明核心通常为 LGPL 2.1+，启用 GPL 组件的构建受 GPL 约束；本机 Homebrew FFmpeg 9.0.1 显示 `--enable-gpl` 和 `--enable-libx264` | 仅调用本机已有 CLI，不在仓库分发 | 决定系统解码或锁定可合法分发的具体 FFmpeg 构建，保留源码、通知及许可证义务；逐平台核查编码器选项。[官方法律说明](https://www.ffmpeg.org/legal.html) |
| OpenCV | 4.5.0 起为 Apache 2.0 | 未使用 | 如引入须核对 Python wheel 及附带第三方库。[官方许可证](https://opencv.org/LICENSE/) |
| ONNX Runtime | 主仓库 MIT，另有第三方通知；硬件执行提供程序依赖平台 | 未使用 | 锁定版本、第三方通知和模型权重许可证。[官方许可证](https://github.com/microsoft/onnxruntime/blob/main/LICENSE)、[第三方通知](https://github.com/microsoft/onnxruntime/blob/main/ThirdPartyNotices.txt) |
| 检测模型及权重 | 尚未选择 | 无 | 对代码、训练数据、预训练权重、再分发、商用／公开发布权限分别查验；不可仅凭“插件开源”推定许可兼容。 |
| PyInstaller 等打包器 | 尚未选择；PyInstaller 文档有 GPL 例外 | 无 | 只在确定打包路径时核查当时版本的许可和二进制依赖。[官方文档](https://pyinstaller.org/en/stable/license.html) |
| 云视觉 API | 属于服务条款、计费、地域和数据处理安排，不是开源权重许可 | 无 | 获得账户、预算和数据授权后再测；密钥不进客户端源码或 Git。 |

此表只记录已查明的上游许可入口，不替代正式发行时按实际二进制和权重清单逐项审查。
