# 验证记录 · 2026-10-20

## macOS 实测

- 主机：macOS Darwin arm64；系统 Python 3.9.6；已有 FFmpeg 9.0.1。
- 已生成自制 `160×90`、10 fps、100 帧 MJPEG AVI 并离线分析。分析输出：进入 2、离开 1、末帧排队区域 1、ETA `null`。
- 人工观看 0、10、20、30、40、50、60、70、80、90、99 帧及三次穿线附近帧，填写 11 个采样标注和 3 个事件标注。事件匹配容差 ±1 帧。自动对照结果：3/3 事件匹配；误计 0、漏计 0；采样队列人数平均绝对误差 0、最大绝对误差 0。只对这一段简单模拟画面成立。
- `PYTHONPATH=src python3 -m unittest discover -s tests -v`：5 项通过；包括模拟断流后重连、轨迹清空、缺失／不支持文件错误和无效几何配置。
- `PYTHONPYCACHEPREFIX=/private/tmp/campura-vision-pycache PYTHONPATH=src python3 -m compileall -q src tests`：通过。macOS 系统 Python 默认字节码缓存位于工作区外，故显式改到临时目录。
- 本机页面实际打开并检查：预览画面刷新、实时人数变化、播放结束后队列人数显示不可用、预计等候时间始终不提供；停止后画线并保存配置。发现并修复了浏览器 Content Security Policy 未允许 `blob:` 预览图片的问题。
- 源码运行通过；**未构建 macOS 安装包**，也未连接相机或云端。

## Windows 状态

没有 Windows 实机或虚拟机验证。PowerShell 命令和源码使用跨平台 API，但不能据此声称 Windows 构建或运行成功。需要在 Windows 10/11 目标机确认 Python、FFmpeg 可用，再执行 README 的命令、验证页面、断流和完整安装包生命周期。

## 摄像头与授权状态

USB、ONVIF/RTSP 和真实商户场景均未连接或测试。模拟重连测试只验证状态机和轨迹重置，不代表摄像头断线恢复已通过。学校、商户、摄像头管理方和画面中参与者的试点授权尚未取得，因此当前没有真实视频或云上传。
