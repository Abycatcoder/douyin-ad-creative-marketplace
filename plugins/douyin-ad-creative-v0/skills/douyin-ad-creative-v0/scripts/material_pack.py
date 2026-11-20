#!/usr/bin/env python3
"""Offline, versioned product-media composition. No advertising or network API."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from creative_contract import validate_direction, write_planning, EXTRA_REVIEW_KEYS

ROOT = Path(__file__).resolve().parents[1]
REVIEW_KEYS = ['factual_accuracy', 'product_consistency', 'text_legibility', 'creative_alignment', 'audiovisual']


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def run(args, cwd=None):
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=300)
    require(p.returncode == 0, f'{args[0]} failed: {p.stderr[-2000:]}')
    return p.stdout


def probe(path):
    return json.loads(run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)]))


def local(path, base):
    require(isinstance(path, str) and bool(path.strip()), 'Missing local media path')
    require(not re.match(r'^[a-zA-Z]+://', path), 'Export remote media to a local file first')
    p = Path(path).expanduser()
    return (base / p).resolve() if not p.is_absolute() else p.resolve()


def text_value(v, label):
    require(isinstance(v, str) and bool(v.strip()), f'{label}: nonempty text required')


def number(v, low, high, label):
    require(type(v) in (int, float) and math.isfinite(v) and low <= v <= high,
            f'{label}: expected finite number {low}..{high}')


def index(items, label):
    require(isinstance(items, list) and items, f'{label}: nonempty list required')
    result = {}
    for item in items:
        require(isinstance(item, dict), f'{label}: expected object')
        k = item.get('id')
        require(isinstance(k, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', k), f'{label}: invalid id')
        require(k not in result, f'{label}: duplicate id {k}')
        result[k] = item
    return result


def validate(data, base, media=False):
    require(data.get('schema_version') in ['0.1', '0.2'], 'schema_version must be 0.1 or 0.2')
    text_value(data.get('campaign_id'), 'campaign_id')
    product = data.get('product', {})
    text_value(product.get('name'), 'product.name')
    text_value(product.get('category'), 'product.category')
    sources = index(data.get('sources'), 'sources')
    for s in sources.values():
        text_value(s.get('description'), 'source.description')
    facts = index(product.get('facts'), 'product.facts')
    for f in facts.values():
        text_value(f.get('text'), 'fact.text')
        require(f.get('source_id') in sources, 'Unknown fact source')
        require(f.get('status') in ['provided', 'verified', 'unknown'], 'Invalid fact status')
    audiences = index(data.get('audiences'), 'audiences')
    for a in audiences.values():
        for key in ['name', 'need', 'barrier', 'basis']:
            text_value(a.get(key), f'audience.{key}')
        require(a.get('status') in ['hypothesis', 'data_supported'], 'Invalid audience status')
        require(isinstance(a.get('source_ids'), list) and all(x in sources for x in a['source_ids']), 'Unknown audience source')
        require(a['status'] != 'data_supported' or a['source_ids'], 'Data-supported audience needs evidence')
        require(a.get('age_range') is None or isinstance(a.get('age_range'), str), 'age_range must be null or text')
    creatives = index(data.get('creatives'), 'creatives')
    for c in creatives.values():
        require(c.get('audience_id') in audiences, 'Unknown creative audience')
        for key in ['hypothesis', 'test_variable', 'change_summary']:
            text_value(c.get(key), f'creative.{key}')
        require(c.get('parent_version') is None or re.fullmatch(r'v[0-9]{3,}', str(c['parent_version'])), 'Invalid parent_version')
        scenes = c.get('scenes')
        require(isinstance(scenes, list) and 1 <= len(scenes) <= 30, 'Expected 1..30 scenes')
        duration = 0
        for n, s in enumerate(scenes):
            require(isinstance(s, dict), 'scene must be object')
            number(s.get('seconds'), 0.5, 30, 'scene.seconds')
            duration += s['seconds']
            if data['schema_version'] == '0.2':
                require(isinstance(s.get('text'), str), 'scene.text must be text')
            else:
                text_value(s.get('text'), 'scene.text')
            text_value(s.get('visual'), 'scene.visual')
            require(isinstance(s.get('voiceover', ''), str), 'voiceover must be text')
            require(s.get('source_id') in sources, 'Unknown scene source')
            claims = s.get('claims')
            require(isinstance(claims, list), 'scene.claims must be a list, empty if no factual claims')
            for claim in claims:
                text_value(claim.get('text'), 'claim.text')
                refs = claim.get('fact_ids')
                require(isinstance(refs, list) and refs, 'Every declared claim needs fact_ids')
                require(all(f in facts and facts[f]['status'] != 'unknown' for f in refs), 'Claim references unknown/unsupported fact')
            if media:
                p = local(s.get('asset'), base)
                require(p.is_file(), f'Missing scene {n+1} asset: {p}')
        require(duration <= 180, 'V0 renderer supports at most 180 seconds per creative')
        if media and c.get('audio'):
            p = local(c['audio'], base)
            require(p.is_file(), f'Missing audio: {p}')
            require(c.get('audio_source_id') in sources, 'Audio needs source_id')
    if data['schema_version'] == '0.2':
        validate_direction(data)
    return creatives


def doctor():
    import importlib.util
    checks = {k: bool(shutil.which(k)) for k in ['ffmpeg', 'ffprobe']}
    checks.update({k: bool(importlib.util.find_spec(k)) for k in ['PIL', 'fontTools']})
    checks['bundled_font'] = (ROOT / 'assets/NotoSansSC-Subset.otf').is_file()
    return {'ready': all(checks.values()), 'checks': checks}


def srt_time(seconds):
    t = round(seconds * 1000)
    return f'{t//3600000:02d}:{t//60000%60:02d}:{t//1000%60:02d},{t%1000:03d}'


def make_overlay(text, brand, width, height, fontpath, modern=False):
    from PIL import Image, ImageDraw, ImageFont
    from fontTools.ttLib import TTFont
    with TTFont(str(fontpath), fontNumber=0) as font:
        cmap = font.getBestCmap()
    missing = {c for c in text + ('' if modern else brand) if not c.isspace() and ord(c) not in cmap}
    require(not missing, f'Font lacks glyphs {sorted(missing)}; use --font')
    im = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if modern:
        if not text.strip():
            return im
        # Keep the media dominant and type stable; avoid the legacy 48% opaque panels.
        for y in range(int(height * .72), height):
            alpha = round(180 * (y-height*.72)/(height*.28))
            d.line((0, y, width, y), fill=(12, 16, 20, max(0, alpha)))
        available = width * .80
        for size in range(int(width*.055), max(13, int(width*.032))-1, -1):
            font = ImageFont.truetype(str(fontpath), size)
            lines, line = [], ''
            for char in text:
                if char == '\n' or (line and d.textlength(line+char, font=font) > available):
                    lines.append(line); line = '' if char == '\n' else char
                else:
                    line += char
            lines.append(line)
            if len(lines) <= 2:
                break
        else:
            raise ValueError('Screen text exceeds two lines; shorten scene.text')
        y = int(height * .79)
        for line in lines:
            d.text((int(width*.075), y), line, font=font, fill='#FFFFFF', stroke_width=1, stroke_fill='#202020')
            y += int(size*1.4)
        return im
    d.rectangle((0, 0, width, int(height * .16)), fill='#101A22')
    d.rectangle((0, int(height * .68), width, height), fill='#101A22')
    left, available = int(width * .075), int(width * .80)
    font = ImageFont.truetype(str(fontpath), max(14, int(width * .033)))
    require(d.textlength(brand, font=font) <= available, 'Product/brand label too long; shorten product.display_name')
    d.text((left, int(height * .10)), brand, font=font, fill='#A7B6C4')
    for size in range(int(width*.065), max(17, int(width*.035))-1, -1):
        font = ImageFont.truetype(str(fontpath), size)
        lines = []
        for paragraph in text.split('\n'):
            line = ''
            for char in paragraph:
                if line and d.textlength(line+char, font=font) > available:
                    lines.append(line); line = char
                else:
                    line += char
            lines.append(line)
        if len(lines)*(size*1.45) <= height*.19:
            break
    else:
        raise ValueError('Screen text too long for safe text panel; shorten scene.text')
    y = int(height * .735)
    for line in lines:
        d.text((left, y), line, font=font, fill='#F8FAFC')
        y += round(size * 1.45)
    return im


def render(args):
    from PIL import Image, ImageOps, ImageDraw
    config = Path(args.input).resolve()
    data = read(config)
    creatives = validate(data, config.parent, media=True)
    require(args.creative in creatives, 'Unknown --creative')
    c = creatives[args.creative]
    modern = data['schema_version'] == '0.2'
    mode = c.get('production_mode', 'asset_composition') if modern else 'asset_composition'
    number(args.width, 360, 2160, 'width'); number(args.height, 640, 3840, 'height')
    require(args.width % 2 == 0 and args.height % 2 == 0, 'Width/height must be even')
    require(args.width < args.height, 'V0 preview expects portrait dimensions')
    require(re.fullmatch(r'v[0-9]{3,}', args.version), 'Version must be v001, v002, ...')
    folder = Path(args.output).resolve() / args.creative
    if c.get('parent_version'):
        parent = folder / c['parent_version'] / 'manifest.json'
        require(parent.is_file(), 'parent_version must exist in this creative output directory')
        require(c['parent_version'] != args.version, 'Parent and current version must differ')
    dest = folder / args.version
    require(not dest.exists(), f'Version already exists; use a new version: {dest}')
    require(doctor()['ready'], 'Run doctor and install missing dependencies')
    font = Path(args.font).resolve() if args.font else ROOT / 'assets/NotoSansSC-Subset.otf'
    total = sum(s['seconds'] for s in c['scenes'])
    audio = local(c['audio'], config.parent) if c.get('audio') else None
    warnings = []
    media_kinds = []
    if modern:
        from creative_contract import direction_warnings
        warnings.extend(direction_warnings(c))
        # A video plan cannot silently fall back to looped photos or short clips.
        for scene in c['scenes']:
            p = local(scene['asset'], config.parent)
            try:
                with Image.open(p) as candidate:
                    candidate.verify()
                kind = 'image'
            except (OSError, SyntaxError):
                info = probe(p)
                require(any(s['codec_type'] == 'video' for s in info['streams']), f'No video stream: {p}')
                kind = 'video'
                require(float(info['format']['duration']) + .04 >= scene.get('trim_start', 0) + scene['seconds'],
                        f'{scene["shot_id"]}: video shorter than requested shot; provide more footage')
            require(mode != 'motion_video' or kind == 'video',
                    f'{scene["shot_id"]}: motion_video needs video footage; images can only render as animatic')
            media_kinds.append(kind)
    if audio:
        info = probe(audio)
        require(any(x['codec_type'] == 'audio' for x in info['streams']), 'Audio input has no audio stream')
        audio_duration = float(info['format']['duration'])
        require(audio_duration + .1 >= total, 'Audio is shorter than video; provide a complete audio track')
        if audio_duration > total+.1:
            warnings.append('Audio longer than video; trimmed to timeline. Review ending.')
    else:
        warnings.append('Silent video; voiceover text has not been synthesized.')
    # Reserve version before writing; failures remain visibly failed, never masquerade as ready.
    dest.mkdir(parents=True, exist_ok=False)
    try:
        write(dest / 'input.json', data)
        write(dest / 'qa.json', {'status': 'rendering'})
        sources = []
        captions, script, elapsed = [], [f'# {args.creative} / {args.version}', '', c['hypothesis'], ''], 0
        with tempfile.TemporaryDirectory(prefix='douyin-v0-') as temp:
            work = Path(temp)
            w, h = args.width, args.height
            box_w, box_h = int(w*.90)//2*2, int(h*.50)//2*2
            x, y = (w-box_w)//2, int(h*.17)
            background = '#101A22'
            if modern:
                box_w, box_h = int(w*.88)//2*2, int(h*.82)//2*2
                x, y = (w-box_w)//2, int(h*.04)
                background = c['visual_style'].get('background_color', '#F4F1EC')
            brand = data['product'].get('display_name', data['product']['name'])
            for i, scene in enumerate(c['scenes']):
                p = local(scene['asset'], config.parent)
                sources.append({'path': str(p), 'source_id': scene['source_id'], 'sha256': sha(p)})
                overlay = make_overlay(scene['text'], brand, w, h, font, modern)
                overlay.save(work / f'overlay{i}.png')
                sec = scene['seconds']
                try:
                    with Image.open(p) as source:
                        picture = ImageOps.exif_transpose(source).convert('RGBA')
                        picture = ImageOps.contain(picture, (box_w, box_h))
                        frame = Image.new('RGB', (w, h), background)
                        frame.paste(picture, (x+(box_w-picture.width)//2, y+(box_h-picture.height)//2), picture)
                        if not modern:
                            frame.paste(overlay, (0, 0), overlay)
                        frame.save(work / f'frame{i}.png')
                    inputs = ['-loop', '1', '-i', f'frame{i}.png']
                    filters = ['-vf', 'format=yuv420p']
                    if modern:
                        nframes = max(2, round(sec*25))
                        progress = f'on/{nframes-1}'
                        movement = scene.get('preview_motion', ['push_in', 'pan_left', 'pull_out', 'pan_right'][i%4])
                        zoom = {'push_in': f'1+0.055*{progress}', 'pull_out': f'1.055-0.055*{progress}'}.get(movement, '1.045' if movement != 'hold' else '1')
                        px = f'(iw-iw/zoom)*{progress}' if movement == 'pan_right' else f'(iw-iw/zoom)*(1-{progress})' if movement == 'pan_left' else '(iw-iw/zoom)/2'
                        inputs = ['-i', f'frame{i}.png', '-loop', '1', '-i', f'overlay{i}.png']
                        graph = (f"[0:v]scale={w*2}:{h*2},zoompan=z='{zoom}':x='{px}':y='(ih-ih/zoom)/2':d={nframes}:s={w}x{h}:fps=25,setsar=1[b];"
                                 '[b][1:v]overlay=0:0:shortest=1,format=yuv420p[v]')
                        filters = ['-filter_complex_threads', '1', '-filter_complex', graph, '-map', '[v]']
                except (OSError, SyntaxError):
                    video = probe(p)
                    require(any(s['codec_type'] == 'video' for s in video['streams']), f'No video stream: {p}')
                    inputs = (['-ss', str(scene.get('trim_start', 0))] if modern else ['-stream_loop', '-1']) + ['-i', str(p), '-loop', '1', '-i', f'overlay{i}.png']
                    vw, vh, vy = (w, h, 0) if modern else (box_w, box_h, y)
                    graph = (f'[0:v]scale={vw}:{vh}:force_original_aspect_ratio=decrease,'
                             f'pad={w}:{h}:(ow-iw)/2:{vy}+({vh}-ih)/2:color=0x{background[1:]},setsar=1,setpts=PTS-STARTPTS[b];'
                             '[b][1:v]overlay=0:0:shortest=1,format=yuv420p[v]')
                    filters = ['-filter_complex_threads', '1', '-filter_complex', graph, '-map', '[v]']
                run(['ffmpeg', '-v', 'error', '-y', *inputs, *filters, '-t', str(sec), '-r', '25',
                     '-an', '-c:v', 'libx264', '-threads', '2', '-preset', 'fast', '-crf', '22',
                     '-pix_fmt', 'yuv420p', f'segment{i}.mp4'], cwd=work)
                run(['ffmpeg', '-v', 'error', '-y', '-ss', str(sec/2), '-i', f'segment{i}.mp4',
                     '-frames:v', '1', str(dest / f'sample-{i+1:02d}.jpg')], cwd=work)
                if scene['text']:
                    captions.append(f'{len(captions)+1}\n{srt_time(elapsed)} --> {srt_time(elapsed+sec)}\n{scene["text"]}\n')
                script.extend([f'## 镜头 {i+1} | {elapsed:g}–{elapsed+sec:g}s', scene['visual'],
                               f'屏幕：{scene["text"]}', f'旁白稿：{scene.get("voiceover", "")}', ''])
                elapsed += sec
            (work / 'concat.txt').write_text(''.join(f"file 'segment{i}.mp4'\n" for i in range(len(c['scenes']))))
            inputs = ['-f', 'concat', '-safe', '1', '-i', 'concat.txt']
            maps = ['-map', '0:v:0', '-c:v', 'copy']
            if audio:
                inputs += ['-i', str(audio)]
                maps += ['-map', '1:a:0', '-c:a', 'aac', '-b:a', '160k']
                sources.append({'path': str(audio), 'source_id': c['audio_source_id'], 'sha256': sha(audio)})
            else:
                maps += ['-an']
            run(['ffmpeg', '-v', 'error', '-y', *inputs, *maps, '-t', str(total), '-movflags', '+faststart',
                 str(dest / 'video.mp4')], cwd=work)
        info = probe(dest / 'video.mp4')
        streams = info['streams']
        vs = next(s for s in streams if s['codec_type'] == 'video')
        require(vs['width'] == w and vs['height'] == h, 'Output dimensions mismatch')
        require(abs(float(info['format']['duration'])-total) <= .2, 'Output duration mismatch')
        require(any(s['codec_type']=='audio' for s in streams) == bool(audio), 'Output audio mismatch')
        # Decode the complete output to catch damaged frames, not just metadata.
        run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(dest/'video.mp4'), '-f', 'null', '-'])
        shutil.copyfile(dest/'sample-01.jpg', dest/'cover.jpg')
        thumbs = []
        for p in sorted(dest.glob('sample-*.jpg')):
            with Image.open(p) as frame:
                thumbs.append(ImageOps.contain(frame.convert('RGB'), (216, 384)))
        sheet = Image.new('RGB', (216*min(3, len(thumbs)), 414*math.ceil(len(thumbs)/3)), '#ECF0F3')
        draw = ImageDraw.Draw(sheet)
        for i, thumb in enumerate(thumbs):
            sheet.paste(thumb, (i%3*216, i//3*414))
            draw.text((i%3*216+10, i//3*414+392), f'SCENE {i+1}', fill='#101A22')
        sheet.save(dest/'storyboard.jpg')
        (dest/'captions.srt').write_text('\n'.join(captions), encoding='utf-8')
        if modern:
            write_planning(data, c, dest)
        else:
            (dest/'script.md').write_text('\n'.join(script), encoding='utf-8')
        review_keys = REVIEW_KEYS + EXTRA_REVIEW_KEYS if modern else REVIEW_KEYS
        initial_status = 'preview_only' if mode == 'animatic' else 'needs_review'
        qa = {'status': initial_status, 'technical_checks': 'pass', 'warnings': warnings,
              'checks': {k: {'status': 'not_checked', 'observation': ''} for k in review_keys},
              'platform_approval': 'not_checked', 'performance': {'ctr': None, 'cvr': None, 'cpa': None, 'roi': None}}
        write(dest/'qa.json', qa)
        manifest = {'plugin_version': '0.2.0', 'schema_version': data['schema_version'], 'campaign_id': data['campaign_id'], 'creative_id': args.creative,
                    'version': args.version, 'parent_version': c.get('parent_version'),
                    'change_summary': c['change_summary'], 'audience_id': c['audience_id'],
                    'created_at': datetime.now(timezone.utc).isoformat(), 'status': initial_status,
                    'production_mode': mode, 'media_kinds': media_kinds, 'required_review_keys': review_keys, 'learning_status': 'untested',
                    'width': w, 'height': h, 'seconds': total, 'has_audio': bool(audio),
                    'sources': sources, 'files': {p.name: sha(p) for p in sorted(dest.iterdir()) if p.is_file()}}
        write(dest/'manifest.json', manifest)
        return {'status': initial_status, 'directory': str(dest), 'video': str(dest/'video.mp4'), 'warnings': warnings}
    except Exception as exc:
        write(dest/'qa.json', {'status': 'failed', 'error': str(exc)})
        raise


def review(args):
    dest = Path(args.directory).resolve()
    manifest = read(dest/'manifest.json')
    qa = read(dest/'qa.json')
    require(qa.get('technical_checks') == 'pass', 'Technical checks must pass before review')
    for name, digest in manifest['files'].items():
        require(Path(name).name == name, 'Invalid manifest file name')
        require((dest/name).is_file() and sha(dest/name) == digest, f'Output changed since render/review: {name}')
    result = read(args.input)
    text_value(result.get('reviewer'), 'reviewer')
    checks = result.get('checks', {})
    review_keys = manifest.get('required_review_keys', REVIEW_KEYS)
    require(set(checks) == set(review_keys), f'Review requires checks: {review_keys}')
    for k, v in checks.items():
        require(v.get('status') in ['pass', 'fail', 'not_checked', 'not_applicable'], 'Invalid review status')
        text_value(v.get('observation'), f'{k}.observation')
        require(v['status'] != 'not_applicable' or (k == 'audiovisual' and not manifest['has_audio']), 'Invalid not_applicable')
    values = [x['status'] for x in checks.values()]
    status = 'needs_revision' if 'fail' in values else 'needs_review' if 'not_checked' in values else 'ready_for_human_review'
    if manifest.get('production_mode') == 'animatic' and status != 'needs_revision':
        status = 'preview_only'
    qa.update({'status': status, 'checks': checks, 'reviewer': result['reviewer']})
    write(dest/'review.json', result)
    write(dest/'qa.json', qa)
    manifest['status'] = status
    for name in ['qa.json', 'review.json']:
        manifest['files'][name] = sha(dest/name)
    write(dest/'manifest.json', manifest)
    return {'status': status, 'directory': str(dest)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('doctor')
    p = sub.add_parser('validate'); p.add_argument('input'); p.add_argument('--media', action='store_true')
    p = sub.add_parser('plan'); p.add_argument('input'); p.add_argument('--output', required=True)
    p = sub.add_parser('render')
    p.add_argument('input'); p.add_argument('--creative', required=True); p.add_argument('--output', required=True)
    p.add_argument('--version', default='v001'); p.add_argument('--width', type=int, default=720)
    p.add_argument('--height', type=int, default=1280); p.add_argument('--font')
    p = sub.add_parser('review'); p.add_argument('directory'); p.add_argument('--input', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'doctor':
            result = doctor()
            print(json.dumps(result, ensure_ascii=False)); return 0 if result['ready'] else 2
        elif args.command == 'validate':
            file = Path(args.input).resolve()
            cs = validate(read(file), file.parent, args.media)
            result = {'valid': True, 'creatives': list(cs), 'media_checked': args.media}
        elif args.command == 'plan':
            file = Path(args.input).resolve()
            data = read(file)
            cs = validate(data, file.parent)
            require(data['schema_version'] == '0.2', 'plan exports require schema 0.2; enrich legacy storyboard first')
            dest = Path(args.output).resolve()
            require(not dest.exists(), 'Plan output exists; choose a new directory to preserve prior versions')
            dest.mkdir(parents=True)
            write(dest/'campaign.json', data)
            result = {'status': 'planning_only', 'creatives': [write_planning(data, c, dest/c['id']) for c in cs.values()]}
        elif args.command == 'render':
            result = render(args)
        else:
            result = review(args)
        print(json.dumps(result, ensure_ascii=False)); return 0
    except Exception as exc:
        print(json.dumps({'status': 'error', 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
