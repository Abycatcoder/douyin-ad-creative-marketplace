"""Integration tests using synthetic local media, never a real advertisement."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from PIL import Image, ImageDraw

SCRIPT = Path(__file__).with_name('material_pack.py')


def call(*args, ok=True):
    result = subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True)
    if ok:
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)
    assert result.returncode != 0, 'Expected rejection'
    return result.stderr


def test(root):
    root.mkdir(parents=True, exist_ok=True)
    im = Image.new('RGB', (600, 600), '#F1ECE2')
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((170, 160, 430, 430), radius=25, fill='#3C787E')
    d.rectangle((190, 185, 410, 205), fill='#A4CAC8')
    im.save(root/'sample.png')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-loop', '1', '-i', str(root/'sample.png'),
                    '-t', '1', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-threads', '2', str(root/'sample.mp4')], check=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'sine=frequency=220:duration=6', str(root/'tone.wav')], check=True)
    campaign = {
        'schema_version': '0.1', 'campaign_id': 'synthetic-test',
        'sources': [{'id': 'brief', 'description': '虚构测试说明，不是商业商品'}, {'id': 'media', 'description': '程序生成的几何测试图'}],
        'product': {'name': '测试收纳盒', 'category': '测试道具', 'facts': [
            {'id': 'f1', 'text': '几何图为绿色', 'source_id': 'media', 'status': 'verified'}]},
        'audiences': [{'id': 'a1', 'name': '桌面整理需求', 'need': '整齐', 'barrier': '不懂结构',
                       'basis': '演示假设', 'status': 'hypothesis', 'source_ids': ['brief'], 'age_range': None}],
        'creatives': [{'id': 'c1', 'audience_id': 'a1', 'hypothesis': '仅用于合成测试', 'test_variable': '开头',
                       'parent_version': None, 'change_summary': '初版', 'audio': None,
                       'scenes': [{'seconds': 2, 'text': '桌面整理，从这里开始', 'voiceover': '旁白仅为文字',
                                   'visual': '几何测试图', 'asset': 'sample.png', 'source_id': 'media', 'claims': []},
                                  {'seconds': 2, 'text': '查看细节，再做选择', 'voiceover': '',
                                   'visual': '循环测试片段', 'asset': 'sample.mp4', 'source_id': 'media', 'claims': []}]}]}
    p = root/'campaign.json'
    def save(c):
        p.write_text(json.dumps(c, ensure_ascii=False), encoding='utf-8')
    save(campaign)
    call('validate', p, '--media')
    out = root/'output'
    r = call('render', p, '--creative', 'c1', '--output', out)
    version = Path(r['directory'])
    first = (version/'video.mp4').read_bytes()
    assert json.loads((version/'qa.json').read_text())['status'] == 'needs_review'
    call('render', p, '--creative', 'c1', '--output', out, ok=False)
    assert (version/'video.mp4').read_bytes() == first
    checks = {k: {'status':'pass', 'observation':'Synthetic integration state-transition fixture, not real visual approval'}
              for k in ['factual_accuracy','product_consistency','text_legibility','creative_alignment','audiovisual']}
    checks['audiovisual']['status'] = 'not_applicable'
    review = root/'review.json'
    review.write_text(json.dumps({'reviewer':'synthetic-test', 'checks':checks}))
    assert call('review', version, '--input', review)['status'] == 'ready_for_human_review'
    checks['factual_accuracy']['status'] = 'fail'
    review.write_text(json.dumps({'reviewer':'synthetic-test', 'checks':checks}))
    assert call('review', version, '--input', review)['status'] == 'needs_revision'
    bad = copy.deepcopy(campaign)
    bad['creatives'][0]['scenes'][0]['claims'] = [{'text':'unknown claim','fact_ids':['missing']}]
    save(bad); call('validate', p, ok=False)
    bad = copy.deepcopy(campaign)
    bad['creatives'][0]['scenes'][0]['asset'] = 'missing.png'
    save(bad); call('validate', p); call('validate', p, '--media', ok=False)
    bad = copy.deepcopy(campaign)
    bad['creatives'][0]['scenes'][0]['seconds'] = -2
    save(bad); call('validate', p, ok=False)
    campaign['creatives'][0].update({'parent_version':'v001','change_summary':'修改开头并加入测试音轨',
                                    'audio':'tone.wav','audio_source_id':'media'})
    campaign['creatives'][0]['scenes'][0]['text'] = '先让桌面更有条理'
    save(campaign)
    second = call('render', p, '--creative', 'c1', '--output', out, '--version', 'v002')
    m = json.loads((Path(second['directory'])/'manifest.json').read_text())
    assert m['has_audio'] and m['parent_version'] == 'v001'
    assert (version/'video.mp4').read_bytes() == first
    call('review', Path(second['directory']), '--input', review, ok=False)  # Audio cannot be N/A.
    with (version/'video.mp4').open('ab') as f:
        f.write(b'tampered')
    call('review', version, '--input', review, ok=False)
    print(json.dumps({'passed': True, 'checks': ['mixed_image_video', 'chinese_text', 'silent_output',
        'audio_output', 'version_immutable', 'parent_link', 'review_transitions', 'unsupported_claim_rejected',
        'missing_media_rejected', 'invalid_duration_rejected', 'audio_review_required', 'tamper_rejected'],
        'fixture_directory': str(root)}, ensure_ascii=False))


if __name__ == '__main__':
    if len(sys.argv) > 1:
        test(Path(sys.argv[1]).resolve())
    else:
        with tempfile.TemporaryDirectory() as folder:
            test(Path(folder))
