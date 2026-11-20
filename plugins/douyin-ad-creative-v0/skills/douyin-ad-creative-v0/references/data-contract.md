# V0 数据契约与命令

所有路径相对 campaign.json 所在目录，或用绝对本地路径。示例数据只是结构示范，用户任务中必须用实际来源替换。

## 新任务使用0.2

0.2继承下方0.1的来源、事实、受众、创意ID、主张、版本与路径字段。旧0.1仅供历史复现；新任务或改稿必须将 schema_version 改为 `0.2` 并补齐以下字段。不要只改版本号。

product新增 `appearance_lock`：商品外形、颜色、印花及关键部件位置/数量等不可改变的信息，不补造看不见的结构。

creative新增：

| 字段 | 内容 |
|---|---|
| creative_type | problem_solution / scenario_story / detail_reveal / styling_montage / demonstration |
| rhythm_type | punchy / progressive / narrative / sensory |
| concept | 创意概念与叙事看点 |
| use_scene | 具体使用时刻与发生的事件 |
| hook | 开头吸引方式 |
| core_message | 单一核心信息 |
| cta | 结尾行动 |
| visual_style | 对象；必填palette、lighting、composition、continuity四个字符串；可选background_color（#RRGGBB），用于预演背景 |
| production_mode | motion_video=视频片段成片；animatic=图片运动预演，不能标成真实动态成片 |
| rhythm_override_reason | 可选；镜长超出预设、CTA不足1.5秒时写明原因 |
| motion_exception_reason | 可选；静物题材有意减少主体/环境运动时写明理由 |

每镜必须包含以下字段，`text`可为空以保留无字幕镜头，其他文本不得省略，无声音或无运动写“无”：

| 输出列 | JSON字段 | 填写方式 |
|---|---|---|
| 镜号 | shot_id | 创意内唯一，如s01 |
| 场景 | scene | 地点、时间、情境 |
| 景别 | shot_size | 远景/全景/中景/近景/特写/大特写 |
| 镜头运动方式 | camera_movement | 有方向/速度/幅度的主要运镜，或固定机位 |
| 画面内容 | visual | 主体、商品、构图及可见事件 |
| 声音 | voiceover | 对白或旁白；无则“无” |
| 音乐 | music | 情绪、节奏、入出点；无则“无” |
| 音响 | sound_effects | 环境声/动作声/音效与触发时点；无则“无” |
| 文字标语 | text | 短句；允许空字符串 |

另填 `seconds`（秒）、`stage`（对应广告结构阶段）、`subject_action`、`environment_motion`、`start_state`、`end_state`、`transition`（与下一镜如何衔接，末镜写结束）。结构阶段顺序见creative-direction.md，允许同一阶段连续多镜，不得跳过证据或CTA。

保留 `asset`、`source_id`、`claims`；规划阶段asset可为null，source_id引用已知商品资料或参考图。生成视频后新增真实生成来源记录，将asset指向完成的视频并更新source_id；用 `reference_asset` 和 `reference_source_id` 保留生成用参考图路径与原始来源ID，避免导出时把生成视频当成自己的参考图。实际生成任务及工具回执记录在来源或任务日志，不能用提示词状态冒充执行状态。

可选 `trim_start`（原视频起始秒数，默认0）；视频必须覆盖trim_start+seconds，不自动循环不足片段。图片预演可选 `preview_motion`: push_in / pull_out / pan_left / pan_right / hold。它只是预演的后期图片运动，不能实现分镜中的人物动作。`transition`是剪辑意图；内置合成器当前只输出硬切，其他衔接需检查源片段或使用额外剪辑。

## 导出分镜与提示词

```bash
python3 "$SKILL_DIR/scripts/material_pack.py" plan /absolute/task/campaign.json --output /absolute/task/plan-v002
```

命令先检查结构/节奏和字段，再逐创意导出script.md（严格九列+独立时间线）、video-prompts.json与video-prompts.md。output必须为新目录。提示词由分镜编译，每镜保存镜号、时长、来源、正向描述、约束和后期指令；不伪造供应商任务。规划输出不包含成片manifest。

## 0.1基础字段示例（历史兼容，不能直接用于新任务）

```json
{
  "schema_version": "0.1",
  "campaign_id": "product-launch",
  "destination": "unknown",
  "sources": [
    {"id": "brief", "description": "用户提供的商品说明；当前会话"},
    {"id": "photo", "description": "用户提供的正面商品图"}
  ],
  "product": {
    "name": "商品名称",
    "category": "商品品类",
    "facts": [
      {"id": "f1", "text": "用户明确提供的商品事实", "source_id": "brief", "status": "provided"}
    ]
  },
  "audiences": [
    {
      "id": "a1", "name": "场景型受众", "need": "需要解决什么",
      "barrier": "为什么犹豫购买", "basis": "从商品用途提出的待验证假设",
      "age_range": null, "interests": [], "status": "hypothesis", "source_ids": ["brief"]
    }
  ],
  "creatives": [
    {
      "id": "c1", "audience_id": "a1",
      "hypothesis": "展示真实使用过程可能降低理解成本；尚未投放验证",
      "test_variable": "开头表达", "parent_version": null, "change_summary": "首次制作",
      "audio": null,
      "scenes": [
        {
          "seconds": 4, "text": "查看商品细节",
          "voiceover": "这里填写配音稿，不会自动生成音频。",
          "visual": "正面产品图，完整保留商品",
          "asset": "inputs/product.jpg", "source_id": "photo", "claims": []
        }
      ]
    }
  ]
}
```

fact.status 只允许 provided、verified、unknown。unknown 不得用于素材中的事实主张。宣称事实的镜头使用 `claims: [{"text":"主张原文","fact_ids":["f1"]}]`；主张包含屏幕文字和旁白，不漏报。程序只检查引用完整性，真实支持关系靠语义评审。
sources 保存证据描述，也可增加 path、url、tool、task_id、observed_at 等来源信息。未取得的资料不可写成已观察。
同一 campaign 中各来源、事实、画像、创意 ID 分别唯一，使用英数字、下划线和连字符，最长 64。
parent_version 如 v001 必须对应现存版本。修改创意保存新的 JSON，旧版 input.json 为不可变快照。
creative.audio 为真实本地音频时必须提供 audio_source_id，且音轨覆盖完整时间线。原片声音默认移除。

## 执行
将 SKILL_DIR 替换为当前实际技能根目录；不要依赖创建时的绝对路径。
```bash
python3 "$SKILL_DIR/scripts/material_pack.py" doctor
python3 "$SKILL_DIR/scripts/material_pack.py" validate /absolute/task/campaign.json
python3 "$SKILL_DIR/scripts/material_pack.py" validate /absolute/task/campaign.json --media
python3 "$SKILL_DIR/scripts/material_pack.py" render /absolute/task/campaign.json --creative c1 --output /absolute/task/materials --version v001
```

每个 creative 分别 render，不能只渲染第一条却宣称全部完成。
每次输出非零返回码即失败；错误是 JSON，失败版 qa.status=failed。失败目录保留供排查，重试使用新的版本号，不覆盖失败版或成功版。

0.2的review在下方五项之外必须增加ad_structure、motion_quality、visual_aesthetics三项，全部使用实际观察。animatic始终为preview_only（检查失败时needs_revision），不因评审通过变成动态成片。技术检查通过也不能证明动态或美学达标。

以下 review 仅适用于成功渲染并有 manifest.json 的素材版本。纯策划稿只运行 validate，在 strategy.md 中记录事实/创意评审和未检查的媒体项目。

检查样例（必须用实际观察替换说明）：
```json
{
  "reviewer": "Codex visual review",
  "checks": {
    "factual_accuracy": {"status":"not_checked","observation":"尚未对照商品资料"},
    "product_consistency": {"status":"not_checked","observation":"尚未对照原图"},
    "text_legibility": {"status":"not_checked","observation":"尚未查看抽帧"},
    "creative_alignment": {"status":"not_checked","observation":"尚未核对目标受众"},
    "audiovisual": {"status":"not_checked","observation":"尚未检查音轨"}
  }
}
```

```bash
python3 "$SKILL_DIR/scripts/material_pack.py" review /absolute/task/materials/c1/v001 --input /absolute/task/review.json
```

检查会核验所有已登记文件的哈希。若成片或报告被外部修改，先制作新版本，不能沿用原检查记录。

## 交付文件
- campaign.json：事实、画像、创意、分镜和媒体映射。
- strategy.md：以表格对比受众、卖点、开头、变量，列出未知信息。
- materials/<creative>/vNNN：真实媒体和机器可读版本/QA。
- production-tasks.md：仅在有待补媒体、外部生成或配音任务时创建。
- 不创建虚假平台 ID、虚假指标或虚假已验证经验。
