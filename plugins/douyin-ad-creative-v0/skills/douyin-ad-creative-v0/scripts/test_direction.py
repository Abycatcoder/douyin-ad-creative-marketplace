"""Contract and render regressions; generated geometry is not advertising evidence."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from PIL import Image, ImageChops, ImageDraw
from creative_contract import HEADERS

SCRIPT = Path(__file__).with_name('material_pack.py')


def call(*args, ok=True):
    p = subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True)
    assert (p.returncode == 0) == ok, p.stdout + p.stderr
    return json.loads(p.stdout) if ok else p.stderr


def test(root):
    root.mkdir(parents=True, exist_ok=True)
    picture = Image.new('RGB', (400, 600), '#E8D3BA')
    draw = ImageDraw.Draw(picture)
    draw.rectangle((70, 80, 330, 520), fill='#405A63')
    draw.ellipse((120, 160, 280, 320), fill='#EFA555')
    picture.save(root/'geometry.png')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=size=360x640:rate=25',
                    '-t', '3', '-c:v', 'libx264', '-threads', '2', '-pix_fmt', 'yuv420p', str(root/'motion.mp4')], check=True)
    c = {'id':'c1', 'audience_id':'a1', 'hypothesis':'虚构渲染验证', 'test_variable':'结构', 'parent_version':None,
         'change_summary':'测试', 'audio':None, 'creative_type':'detail_reveal', 'rhythm_type':'progressive',
         'production_mode':'animatic', 'concept':'几何测试', 'use_scene':'测试台', 'hook':'看形状',
         'core_message':'几何造型', 'cta':'查看细节',
         'visual_style':{'palette':'暖米色', 'lighting':'左侧柔光', 'composition':'主体居中', 'continuity':'同一几何图'},
         'scenes':[]}
    for i, stage in enumerate(['hook', 'reveal', 'evidence', 'payoff', 'cta']):
        c['scenes'].append({'shot_id':f's{i+1:02d}', 'stage':stage, 'seconds':2,
            'scene':'测试台', 'shot_size':'中景' if i%2 == 0 else '特写', 'camera_movement':'缓慢向右平移',
            'visual':'几何图演示，不是商品实拍', 'voiceover':'无', 'music':'无', 'sound_effects':'无',
            'text':'查看细节' if i%2 == 0 else '', 'subject_action':'无', 'environment_motion':'无',
            'start_state':'画面中部', 'end_state':'画面右侧', 'transition':'硬切',
            'asset':'geometry.png', 'source_id':'media', 'claims':[],
            'preview_motion':['push_in','pan_left','pull_out','pan_right','hold'][i]})
    data = {'schema_version':'0.2', 'campaign_id':'synthetic-direction',
        'sources':[{'id':'media', 'description':'程序生成的非商业测试几何'}],
        'product':{'name':'测试图', 'category':'测试', 'appearance_lock':'深蓝矩形和橙色圆形',
                   'facts':[{'id':'f1','text':'测试图形','source_id':'media','status':'provided'}]},
        'audiences':[{'id':'a1','name':'测试','need':'验证','barrier':'无','basis':'虚构示例',
                      'status':'hypothesis','source_ids':['media'],'age_range':None}], 'creatives':[c]}
    config = root/'campaign.json'
    def save(value):
        config.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
    save(data)
    call('validate', config, '--media')
    call('plan', config, '--output', root/'plan')
    assert '| ' + ' | '.join(HEADERS) + ' |' in (root/'plan/c1/script.md').read_text()
    prompts = json.loads((root/'plan/c1/video-prompts.json').read_text())['shots']
    assert [s['shot_id'] for s in prompts] == [s['shot_id'] for s in c['scenes']]
    assert prompts[0]['seconds'] == c['scenes'][0]['seconds']
    assert c['scenes'][0]['camera_movement'] in prompts[0]['prompt']
    call('plan', config, '--output', root/'plan', ok=False)
    for key in ['music', 'sound_effects', 'camera_movement', 'end_state']:
        bad = copy.deepcopy(data); del bad['creatives'][0]['scenes'][0][key]
        save(bad); call('validate', config, ok=False)
    bad = copy.deepcopy(data); bad['creatives'][0]['scenes'].pop()
    save(bad); call('validate', config, ok=False)
    bad = copy.deepcopy(data); bad['creatives'][0]['scenes'][1]['seconds'] = 9
    save(bad); call('validate', config, ok=False)
    bad['creatives'][0]['rhythm_override_reason'] = '长镜头展示实际完整操作'
    save(bad); call('validate', config)
    save(data)
    result = call('render', config, '--creative', 'c1', '--output', root/'out', '--width',360,'--height',640)
    dest = Path(result['directory'])
    assert result['status'] == 'preview_only'
    for name, when in [('early',.1),('late',1.8)]:
        subprocess.run(['ffmpeg','-v','error','-y','-ss',str(when),'-i',str(dest/'video.mp4'),'-frames:v','1',str(root/f'{name}.png')],check=True)
    with Image.open(root/'early.png') as a, Image.open(root/'late.png') as b:
        # Compare image area only, not text or cuts; tests actual intra-shot movement.
        assert ImageChops.difference(a.crop((30,80,320,460)), b.crop((30,80,320,460))).getbbox()
    manifest = json.loads((dest/'manifest.json').read_text())
    checks = {k:{'status':'pass','observation':'合成夹具验证状态，非真实创意批准'} for k in manifest['required_review_keys']}
    checks['audiovisual']['status'] = 'not_applicable'
    review = root/'review.json'; review.write_text(json.dumps({'reviewer':'fixture','checks':checks}))
    assert call('review', dest, '--input', review)['status'] == 'preview_only'
    # Still images cannot be mislabelled motion video, even with all fields present.
    c['production_mode'] = 'motion_video'; save(data)
    call('render',config,'--creative','c1','--output',root/'out','--version','v002',ok=False)
    for scene in c['scenes']:
        scene.update(asset='motion.mp4', trim_start=.2)
    save(data)
    result = call('render',config,'--creative','c1','--output',root/'out','--version','v002','--width',360,'--height',640)
    assert result['status'] == 'needs_review'
    m = json.loads((Path(result['directory'])/'manifest.json').read_text())
    assert m['media_kinds'] == ['video']*5
    c['scenes'][0]['trim_start'] = 2; save(data)
    call('render',config,'--creative','c1','--output',root/'out','--version','v003',ok=False)
    print(json.dumps({'passed':True, 'checks':['nine_columns','prompt_shot_alignment','required_audio_fields',
        'structure_and_rhythm','real_preview_frame_motion','preview_not_ready','no_photo_as_motion_video',
        'video_assembly','short_clip_not_looped'], 'fixture_directory':str(root)}))


if __name__ == '__main__':
    if len(sys.argv)>1:
        test(Path(sys.argv[1]).resolve())
    else:
        with tempfile.TemporaryDirectory() as folder:
            test(Path(folder))
