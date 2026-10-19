# 架构与接口草案

## 组件边界

```text
本机文件／未来 USB、ONVIF-RTSP
  → VideoSource（探测、解码、状态）
  → Detector（可替换，输出框与脚点）
  → 短时 Tracker（会话内 ID，不落盘）
  → 过线和区域计数
  → 127.0.0.1 配置／预览／结果接口
  → 将来：经授权的商家端本地汇总接口
```

当前 `LocalFileSource` 调用本机 `ffprobe` 探测，再以 `ffmpeg` 输出 160×90 RGB 帧。`BackgroundDifferenceDetector` 与 `Analyzer` 是示意算法；`Detector` 协议允许换成人体检测模型。断流后清除短时轨迹和队列即时值，累计进出数保持；重连不得把断流前后的两个人错误地连接为一个。

## 视频输入适配计划

| 输入 | 接入与预览 | 故障诊断 | 当前状态 |
| --- | --- | --- | --- |
| 本地文件 | `ffprobe` 检查视频流，`ffmpeg` 输出固定尺寸画面；文件终止后状态为“播放结束” | 文件不存在／无读权限、探测失败或格式不支持、截断帧、解码异常 | 已实现并用模拟 MJPEG AVI 验证；其他编码待测 |
| USB 摄像头 | Windows 用 Media Foundation 枚举和采集，macOS 用 AVFoundation；只预览设备实际提供的格式，确认相机占用状态 | 无设备、系统相机权限拒绝、设备占用、格式／分辨率不支持、首帧超时、热拔插 | 仅设计；未申请摄像头权限、未连接设备 |
| ONVIF/RTSP | ONVIF 只用于发现能力和取得流地址，视频用 RTSP 接入；支持 TCP、超时、退避重连，记录最后成功帧时间 | 无网络、鉴权失败、流 URI 无效、端口拒绝、解码不支持、断流；如果设备无可用流应明确显示“无法预览”原因 | 仅设计；未连接网络摄像头 |

Windows 相机可通过 Media Foundation 枚举，macOS 相机访问需系统授权和用途说明：[微软设备枚举](https://learn.microsoft.com/en-us/windows/win32/medfound/enumerating-video-capture-devices)、[Apple 授权说明](https://developer.apple.com/documentation/AVFoundation/requesting-authorization-to-capture-and-save-media)。ONVIF Profile S 涵盖网络视频流能力，但设备具体实现仍需实测：[ONVIF Profile S](https://www.onvif.org/profiles/profile-s/)。

摄像头地址、密码、访问令牌不得出现在 Git、命令行参数、错误日志或商家端业务 API 中。后续用 Windows Credential Manager／macOS Keychain 保存凭据，并且只在用户主动配置后访问设备。原型当前仅接受本机视频文件路径；**不得把真实摄像头 URL 当文件路径输入**。

## 当前本机页面和接口

- 绑定 `127.0.0.1`，随机端口、每次启动随机令牌；令牌来自启动输出，API 请求使用 `X-Campura-Token`。页面不加载外部资源。
- `GET /api/status`：运行状态、错误原因、设置、累计人数、队列人数、有效性。`eta_minutes` 永远为 `null`。
- `GET /api/frame`：仅本机页面预览的当前 BMP 画面，不写文件。未来商家端发现接口不应开放该画面。
- `POST /api/config`：保存归一化坐标中的计数线、排队多边形和任务开关；运行中禁止改动。
- `POST /api/start`、`POST /api/stop`：手动启停。页面不承担身份认证或商家归属验证，因此只用于原型。

未来稳定版应使用版本化 `/v1/capabilities`、`/v1/health`、`/v1/results`；结果带单机位 ID、采集时间、过期时间、来源类型、质量标记、进出累计窗口和当前排队数。接口仅暴露汇总值，不返回人脸、身份、完整轨迹或视频帧。商家端与插件身份绑定和本地发现文件格式另行设计，不把当前随机端口 API 当稳定合同。

## 模型、跟踪与计算资源

检测器返回人体框／脚点，跟踪器仅保留短时 ID，过线算法按上一非零侧到当前侧变化计数，队列按脚点是否处于多边形统计。遮挡、多人交错、反复徘徊、相机移动与视角畸变均需人工标注数据评估。当前背景差分不适用于这些真实场景。

未来本机 ONNX 方案：Windows 首选 WinML／按机型确认 DirectML 与 CPU 回退；macOS 评估 CoreML、Apple Neural Engine 与 CPU 回退。解码分别评估 Media Foundation 硬解和 VideoToolbox，记录是否真的启用硬件而非假设。官方资料：[ONNX Runtime Windows](https://onnxruntime.ai/docs/get-started/with-windows.html)、[DirectML](https://onnxruntime.ai/docs/execution-providers/DirectML-ExecutionProvider.html)、[CoreML](https://onnxruntime.ai/docs/execution-providers/CoreML-ExecutionProvider.html)、[VideoToolbox](https://developer.apple.com/documentation/videotoolbox)、[Media Foundation D3D11 解码](https://learn.microsoft.com/en-us/windows/desktop/medfound/supporting-direct3d-11-video-decoding-in-media-foundation)。

云端作为后续可选推理适配器：本机或授权网关仍须采集／解码／压缩／抽帧；只在授权范围内发送最少画面，服务端模型、短时跟踪和计数分别评测。大型视频理解模型可辅助场景说明和复核，但不能凭单次文字回答充当连续精确计数。当前代码没有云端调用。

| 平台 | 正式版采集／解码候选 | 推理候选 | 打包候选 | 当前验证 |
| --- | --- | --- | --- | --- |
| Windows | Media Foundation 采集与设备权限检查；优先测试系统硬解，外部 FFmpeg 作为兼容方案 | WinML、DirectML 或 CPU 回退，按低配机型测 | 签名 MSI／MSIX，加卸载和升级回归 | 只有源码层跨平台设计；尚无 Windows 实机 |
| macOS | AVFoundation 采集与权限；VideoToolbox 硬解，外部 FFmpeg 作为兼容方案 | CoreML／Apple Neural Engine 或 CPU 回退，按机型测 | 签名并公证的 `.pkg`／`.dmg` | 仅外部 FFmpeg 离线源码运行；无正式安装包 |

本机 FFmpeg 原型**没有启用或验证硬件解码**。单机性能是否足够，需在目标低配电脑和实际编码格式上测试后决定。

## 包装与发现

第一阶段是源码运行，尚无安装包。正式版计划 Windows 签名安装包及 macOS 签名、公证安装包，均从各平台构建并运行回归。FFmpeg 可选系统原生解码替代；若发行时捆绑第三方库，必须锁定构建版本并附相应许可与通知。插件默认手动启动；退出关闭本机端口，卸载可清除配置与凭据。未来商家端仅凭带版本和能力字段的本机发现握手判断可用性，失败显示“未安装／未运行／版本不兼容／无摄像头权限”等明确状态。
