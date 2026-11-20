"""Storyboard contract, prompt compilation, and planning exports for schema 0.2."""
import json
from pathlib import Path
import re

STRUCTURES = {
    'problem_solution': ['hook', 'problem', 'reveal', 'evidence', 'cta'],
    'scenario_story': ['hook', 'context', 'reveal', 'evidence', 'payoff', 'cta'],
    'detail_reveal': ['hook', 'reveal', 'evidence', 'payoff', 'cta'],
    'styling_montage': ['hook', 'context', 'evidence', 'payoff', 'cta'],
    'demonstration': ['hook', 'context', 'action', 'evidence', 'cta'],
}
RHYTHMS = {'punchy': (.6, 3), 'progressive': (1.5, 5),
           'narrative': (1.5, 6), 'sensory': (2, 6)}
SHOT_SIZES = ['远景', '全景', '中景', '近景', '特写', '大特写']
EXTRA_REVIEW_KEYS = ['ad_structure', 'motion_quality', 'visual_aesthetics']
HEADERS = ['镜号', '场景', '景别', '镜头运动方式', '画面内容', '声音', '音乐', '音响', '文字标语']
FIELDS = ['shot_id', 'scene', 'shot_size', 'camera_movement', 'visual',
          'voiceover', 'music', 'sound_effects', 'text']


def require(ok, message):
    if not ok:
        raise ValueError(message)


def required_text(value, label):
    require(isinstance(value, str) and bool(value.strip()), f'{label}: nonempty text required')


def validate_direction(data):
    required_text(data['product'].get('appearance_lock'), 'product.appearance_lock')
    source_ids = {s['id'] for s in data['sources']}
    for c in data['creatives']:
        label = c['id']
        require(c.get('creative_type') in STRUCTURES, f'{label}: unsupported creative_type')
        require(c.get('rhythm_type') in RHYTHMS, f'{label}: unsupported rhythm_type')
        require(c.get('production_mode') in ['animatic', 'motion_video'], f'{label}: choose production_mode')
        for key in ['concept', 'use_scene', 'hook', 'core_message', 'cta']:
            required_text(c.get(key), f'{label}.{key}')
        style = c.get('visual_style')
        require(isinstance(style, dict), f'{label}: visual_style must be object')
        for key in ['palette', 'lighting', 'composition', 'continuity']:
            required_text(style.get(key), f'{label}.visual_style.{key}')
        for key in ['background_color', 'text_color']:
            if key in style:
                require(isinstance(style[key], str) and re.fullmatch(r'#[0-9A-Fa-f]{6}', style[key]), f'{key}: expected #RRGGBB')
        for key in ['rhythm_override_reason', 'motion_exception_reason']:
            if key in c:
                required_text(c[key], f'{label}.{key}')
        stages, seen = [], set()
        lo, hi = RHYTHMS[c['rhythm_type']]
        for s in c['scenes']:
            for key in FIELDS + ['stage', 'subject_action', 'environment_motion', 'start_state', 'end_state', 'transition']:
                if key == 'text':
                    require(isinstance(s.get(key), str), f'{label}.text must be text, may be empty')
                else:
                    required_text(s.get(key), f'{label}.{key}')
            require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', s['shot_id']), 'Invalid shot_id')
            require(s['shot_id'] not in seen, f'{label}: duplicate shot_id')
            seen.add(s['shot_id'])
            if 'reference_source_id' in s:
                require(s['reference_source_id'] in source_ids, f'{s["shot_id"]}: unknown reference_source_id')
            require(s['shot_size'] in SHOT_SIZES, f'{s["shot_id"]}: invalid shot_size')
            require(s.get('preview_motion', 'push_in') in ['push_in', 'pull_out', 'pan_left', 'pan_right', 'hold'], 'Invalid preview_motion')
            trim = s.get('trim_start', 0)
            require(type(trim) in [int, float] and 0 <= trim < 86400, 'Invalid trim_start')
            require(lo <= s['seconds'] <= hi or c.get('rhythm_override_reason'),
                    f'{s["shot_id"]}: duration outside {c["rhythm_type"]} range {lo}..{hi}; document rhythm_override_reason')
            if not stages or stages[-1] != s['stage']:
                stages.append(s['stage'])
        require(stages == STRUCTURES[c['creative_type']], f'{label}: stages must follow {STRUCTURES[c["creative_type"]]}')
        require(c['scenes'][-1]['seconds'] >= 1.5 or c.get('rhythm_override_reason'), f'{label}: CTA needs reading time')


def direction_warnings(c):
    scenes = c['scenes']
    moving = sum(s['seconds'] for s in scenes if s['subject_action'] != '无' or s['environment_motion'] != '无')
    ratio = moving / sum(s['seconds'] for s in scenes)
    warnings = []
    if ratio < .6 and not c.get('motion_exception_reason'):
        warnings.append('主体/环境运动计划时长低于60%；补充动作或说明静物创作理由。这不是成片动态检测。')
    if len({s['shot_size'] for s in scenes}) == 1:
        warnings.append('全部镜头景别相同；检查是否有意采用单一构图。')
    if len({s['seconds'] for s in scenes}) == 1:
        warnings.append('所有镜头等长；检查节奏起伏与文字停留。')
    if c['production_mode'] == 'animatic':
        warnings.append('图片运动预演；真实主体动态视频尚未生成。')
    return warnings


def compile_prompts(data, c):
    style = c['visual_style']
    prompts = []
    for s in c['scenes']:
        prompt = (
            f'竖版9:16，单镜头，计划使用{s["seconds"]:g}秒。参考来源：{s.get("reference_source_id", s["source_id"])}。'
            f'商品一致性锚点：{data["product"]["appearance_lock"]}。'
            f'连续性：{style["continuity"]}。场景：{s["scene"]}；景别：{s["shot_size"]}。'
            f'画面：{s["visual"]}。开始状态：{s["start_state"]}。'
            f'主体动作：{s["subject_action"]}。运镜：{s["camera_movement"]}。'
            f'环境运动：{s["environment_motion"]}。结束状态：{s["end_state"]}。'
            f'光线：{style["lighting"]}。色板：{style["palette"]}。构图：{style["composition"]}。'
        )
        prompts.append({
            'shot_id': s['shot_id'], 'seconds': s['seconds'],
            'reference_source_id': s.get('reference_source_id', s['source_id']),
            'reference_asset': s.get('reference_asset', s.get('asset')),
            'prompt': prompt,
            'constraints': '保持商品颜色、印花、文字、形状、部件数量与位置；不补造不可见背面或被遮挡的图案文字，动作不得暴露缺乏参考的未知区域；保持解剖与动作连续，不变形、不闪烁；广告字幕与价格后期添加。',
            'postproduction': dict(zip(['声音', '音乐', '音响', '文字标语', '衔接'],
                                      [s['voiceover'], s['music'], s['sound_effects'], s['text'], s['transition']])),
            'status': 'prompt_ready',
        })
    return prompts


def cell(value):
    return str(value).replace('|', '\\|').replace('\n', ' / ')


def write_planning(data, c, dest):
    """Write exact nine-column storyboard plus a separate timing/action table."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    prompts = compile_prompts(data, c)
    intro = [f'# {c["id"]} 广告分镜', '', f'创意概念：{c["concept"]}',
             f'场景：{c["use_scene"]}', f'结构：{c["creative_type"]}；节奏：{c["rhythm_type"]}',
             f'核心信息：{c["core_message"]}', f'CTA：{c["cta"]}', '',
             '| ' + ' | '.join(HEADERS) + ' |', '| ' + ' | '.join(['---'] * 9) + ' |']
    for s in c['scenes']:
        intro.append('| ' + ' | '.join(cell(s[k]) if s[k] else '无' for k in FIELDS) + ' |')
    intro += ['', '## 时间线与动作', '',
              '| 镜号 | 时间段 | 结构功能 | 主体动作 | 环境运动 | 开始状态 | 结束状态 | 衔接 |',
              '| --- | --- | --- | --- | --- | --- | --- | --- |']
    elapsed = 0
    for s in c['scenes']:
        intro.append('| ' + ' | '.join(cell(x) for x in [s['shot_id'], f'{elapsed:g}–{elapsed+s["seconds"]:g}s',
            s['stage'], s['subject_action'], s['environment_motion'], s['start_state'], s['end_state'], s['transition']]) + ' |')
        elapsed += s['seconds']
    intro += ['', '声音、音乐、音响为制作指令；是否已实现以实际音轨和成片检查为准。']
    warnings = direction_warnings(c)
    if warnings:
        intro += ['', '## 制作待办', ''] + [f'- {x}' for x in warnings]
    (dest/'script.md').write_text('\n'.join(intro) + '\n', encoding='utf-8')
    (dest/'video-prompts.json').write_text(json.dumps({'creative_id': c['id'], 'shots': prompts}, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    lines = [f'# {c["id"]} 逐镜视频提示词', '', '提示词已生成；不代表视频任务已经执行。', '']
    for p in prompts:
        lines += [f'## {p["shot_id"]} · {p["seconds"]:g}秒', '', p['prompt'], '',
                  '约束：' + p['constraints'], '', '后期：' + json.dumps(p['postproduction'], ensure_ascii=False), '']
    (dest/'video-prompts.md').write_text('\n'.join(lines), encoding='utf-8')
    return {'creative_id': c['id'], 'directory': str(dest), 'shots': len(prompts), 'warnings': warnings}
