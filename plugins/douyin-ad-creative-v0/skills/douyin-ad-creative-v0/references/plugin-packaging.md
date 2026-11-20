# 插件打包与恢复
本技能是 douyin-ad-creative-v0 插件的 V0 工作流。插件不包含千川 MCP、OAuth、写广告、预算或报表接口，V1 再接入。没有空白连接器配置。

插件结构：
- .codex-plugin/plugin.json：使用本技能 assets/plugin.json
- skills/douyin-ad-creative-v0/：本技能完整目录，包括 references、scripts、assets 字体和许可证
- README.md：使用本技能 assets/plugin-README.md，面向使用者的入口和能力说明

本技能及内置 manifest 保留完整源文件。恢复插件时读取并使用宿主 plugin-creator，创建同名插件，将完整技能复制到 skills/douyin-ad-creative-v0，使用 assets/plugin.json 作为 manifest；再使用其校验及个人 marketplace 流程。避免双重隐式触发：技能和插件均可见时，在同一任务只执行一次本工作流。

Python3.10+、Pillow、fontTools、FFmpeg/FFprobe 是实际渲染依赖。字体子集基于 Noto Sans CJK，授权见 assets/OFL.txt。额外图片/视频/配音工具按宿主实际可用性调用。

当前包版本0.2.0，名称仍为douyin-ad-creative-v0。完整复制时排除__pycache__和.pyc等临时产物。源Skill与内置manifest/README一起保存，可重建插件；本地目录存在或通过校验不等于插件已在用户界面完成安装。

个人Skill的agents/openai.yaml可能包含policy.products。插件校验器不接受该字段，因此只在插件副本移除policy.products，保留allow_implicit_invocation与其他界面字段；不要反向修改个人Skill的产品可见性设置。
