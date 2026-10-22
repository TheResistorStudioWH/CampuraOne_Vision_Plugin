# 第三方与模型清单

核对日期：2026-10-20。当前运行代码只有本项目代码和用户环境中的 Python 标准库；没有复制任何模型权重、FFmpeg 或云 SDK。源码使用 MIT，保留仓库 LICENSE。

| 项目 | 当前使用 / 许可证证据 | 尚需核对 |
| --- | --- | --- |
| Python | 当前使用本机 3.9.6；[Python 许可说明](https://docs.python.org/3/license.html)包含 PSF 与随附组件条款 | 若冻结并分发 Python，随发行版保留对应版本及第三方许可材料 |
| setuptools | pyproject 声明的可选构建工具，不是源码运行依赖 | 发布时锁定构建工具版本并收集其许可证；本轮未安装或构建 wheel |
| HTML/CSS/JavaScript | 本项目自有实现，无字体、图标、CDN、npm 库 | 未来增加资源时单独记录来源 |
| PaddleDetection release/2.9 | 候选，未安装；[仓库 LICENSE](https://github.com/PaddlePaddle/PaddleDetection/blob/release/2.9/LICENSE)为 Apache-2.0 | 精确检测器/跟踪器权重名、下载源、SHA256、模型卡、训练集约束与再分发许可分别核查 |
| 百度动态人流量 API | 候选，未调用；[文档](https://ai.baidu.com/ai-doc/BODY/wk3cpyyog)本轮抓取超时 | 实际调用的服务条款、画面留存/训练用途、地域、计费/免费额度、商用与学校授权，不适用“仓库 MIT” |
| 千问视觉 API | 候选，未调用；[视觉模型文档](https://help.aliyun.com/zh/model-studio/vision-model/) | 确定模型 ID/版本，核对服务部署范围及数据条款；不能拿开源 Qwen 权重许可代替托管 API 条款 |
| FFmpeg | 未来解码候选，当前不依赖；[官方说明](https://www.ffmpeg.org/legal.html)区分 LGPL 与启用 GPL 组件后的构建 | 必须审查实际二进制 configure、外部库、源代码/声明等分发义务；不默认所有构建都是 LGPL |
| ONNX Runtime / Core ML / DirectML | 未来本机推理备选，未安装/打包 | 具体版本、后端依赖、模型算子兼容、分发条款、Windows/macOS 实测 |
| PyInstaller / 安装器工具 | 未来打包候选，未使用 | 工具及 bootloader/运行时许可证、目标平台构建、签名、公证、卸载；当前不存在已发布安装包 |

**具体权重许可：尚未核查通过，因为本版没有选用任何具体权重。** 代码仓库的 Apache-2.0 不能作为任意下载权重允许商用或再分发的证明。日后每个权重需记录精确文件、版本、校验值、来源、适用许可与使用范围；未确认就不打包。

[北京地域说明](https://help.aliyun.com/en/model-studio/beijing-access-information)指出接入地域与推理部署范围不同。选择“中国内地云”时，合同/配置需落实到具体模型的推理范围，而非只检查 URL。采购与任何画面传输都还未发生。
