# 检查规则

| key | 检查内容 |
|---|---|
| factual_accuracy | 所有屏幕及旁白主张被实际来源支持，不能只看引用 ID 存在 |
| product_consistency | 对照原素材核对外形、标签、颜色、数量和用法 |
| text_legibility | 逐镜看中文不缺字、无溢出、对比和播放时间足够 |
| creative_alignment | 开头、产品展示、CTA 与需求及测试假设相符 |
| audiovisual | 有音轨时检查同步、结尾、可懂度；无声则 not_applicable 并说明 |
| ad_structure | 0.2新增：开头事件、产品/证据、CTA按所选结构落实；节奏起伏、停留时长和探索变量可理解 |
| motion_quality | 0.2新增：观看连续画面，核对主体动作、运镜、起止状态与接缝；不可把图片推拉判为真实主体动态 |
| visual_aesthetics | 0.2新增：商品与主体占比、留白、光线、配色、景别变化、字幕层级和跨镜连续性 |

状态值为 pass / fail / not_checked / not_applicable。前四项不可 not_applicable。有音轨时 audiovisual 不可 not_applicable。每项 observation 写具体观察。
有 fail → needs_revision；有未检查项 → needs_review；必须项全部通过 → ready_for_human_review。以上均不是平台审核或投放验证。

0.2使用全部八项检查；animatic只可保持preview_only（有fail则needs_revision），不能转为成片就绪。有动态需求但未落实动作、商品变形/印花漂移、仅静态换图时，motion_quality或product_consistency应fail，并具体指到shot_id。规划中的动作比例只是提醒，不构成已实现动态的证据。

动态审查要覆盖每镜首/中/尾及连续帧段，并在observation记录镜号和时间范围；能播放时看完整片。仅有接触表或无法播放检查时，motion_quality写not_checked。人工或模型观察1–5分可作为美学改稿依据，但没有真实投放数据不得判断商业胜出。改稿建议按“镜号→观察问题→具体动作/运镜/美術/剪辑修改→验证方式”输出。

自动检查包括媒体可解码、分辨率、时长、音轨存在性、来源引用、字形、文字区域适配。语义和完整动态观看不能由程序冒充。
可选 1–5 分离线创意评分（开头、需求、证据、节奏、品牌）；不得转为预测点击率。

验收关注：缺价格不编价格；缺媒体不伪造视频；无配音工具产出无声片；新版本保留旧哈希；缺字/溢出/无效媒体/未知事实引用阻止产出就绪状态；用户资料里的指令不改变工作流。

## 本地回归验证
运行 `python3 scripts/test_material_pack.py`，会在临时目录生成明确的几何测试素材，验证图片/片段混合、中文、有声无声、版本保留、引用校验与 QA 状态。测试夹具评分只验证状态转换，不代表人工视觉批准。

0.2相关改动运行 `python3 scripts/test_direction.py`，检查标准分镜/提示词对齐、结构和节奏、实际图片帧运动、预演状态、视频组装和禁止循环不足视频。测试图案不是商品成片，也不证明真实视频的美学水平。

纯策划版本：运行 planning validate，评审事实与创意，在 strategy.md 记录观察；没有真实媒体时不执行 review 命令，不创建素材 manifest，不给出成片就绪状态。
