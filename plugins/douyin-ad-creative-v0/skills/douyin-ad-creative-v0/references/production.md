# 生产方式

运行 `python3 scripts/material_pack.py doctor`（路径相对本技能根目录）。需要 Python 3.10+、Pillow、fontTools、FFmpeg、FFprobe。Python 依赖见 scripts/requirements.txt；系统自行提供 FFmpeg。不调用 OpenAI API，文字推理由宿主 Codex 完成。

自带 Noto 中文字体子集及 OFL 授权，覆盖 GB2312 常用汉字、拉丁字符和常用标点。先检查字形；生僻字缺字可通过 --font 指定合法可用字体，不输出方框字。

## 已有媒体
Pillow 可读图片或 FFmpeg 可读视频均可。新任务使用0.2；先按video-prompts.md选择生产路线。motion_video每镜必须是实际视频，使用trim_start裁切，短片段不足以覆盖动作时阻止渲染，不循环补齐。animatic可将图片轻推拉/平移，等比留边保留商品；字幕稳定叠加，避免随图片缩放。视频画面使用完整竖版视区，字幕采用底部渐变及最多两行短句，避开关键商品部位。背景色可设visual_style.background_color。

0.1历史复现仍沿用旧版拼图布局及短片段循环，不用于新创作。

原视频声音默认移除，避免混音；creative.audio可指定一条本地完整混音轨。无音轨则是无声视频。音轨不足成片时长会阻止渲染；长于成片则截取并记录警告。
scene.text 是内嵌字幕和 SRT；scene.voiceover 仅配音稿，必须有实际音频文件才能出声音。
镜长依据creative-direction.md中的节奏预设；时长是创作建议，不是平台标准。内置剪辑只实现硬切，不能把transition中的叠化、匹配剪辑等文字当作已执行效果；生成后按实际画面复核。

## 生成工具增强
先发现宿主实际工具，不硬编码供应商、密钥或不存在的 API。工具输出记录来源、工具名及任务 ID（若有）。异步任务未结束标 pending，不创建成功记录。核对产品形状、商标、包装、文字、数量、用法；无法还原时使用真实原素材。
生成图参与视频合成应标为图片剪辑，不宣称动态实测。

## 资料不全
先完成策划部分。planning 模式允许媒体待补；render 模式必须有真实本地文件。清楚指出缺少的图片或片段即可继续。

## 输出
每版目录为 <output>/<creative_id>/vNNN/，包含 input.json、video.mp4、cover.jpg、storyboard.jpg、captions.srt、script.md、manifest.json、qa.json 和逐镜 sample-*.jpg；0.2另含video-prompts.json/md。版本目录须不存在。记录产物哈希与来源，review.json 必须来自实际检查。animatic的交付状态为preview_only，并明确待补真实动态；motion_video渲染后仍需完整质量评审。
