#!/usr/bin/env python3
"""给 index.html 里每一步的「红字动作 + 黑字食材」生成 Breeze 女声（不读克数、灰字说明）。
流程（在 voice-lib 的队列里生成，成品放 audio/）：
  make_audio.py texts                 从 index.html 提取所有句子 → audio/_work/clips.json
  make_audio.py round SEED            给还没成功的句子写一个 try 申请（打印申请 id）
  （voicelib.py submit <id>，等 status 变 idle）
  make_audio.py collect ID SEED       切开、检查、通过的存成 audio/vNN.mp3
  make_audio.py manifest              写 audio/manifest.json 和 index.html 里要内嵌的映射
"""
import sys, os, re, json, subprocess, glob
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(ROOT, 'audio', '_work'); os.makedirs(WORK, exist_ok=True)
VL = os.path.expanduser('~/mnt/voice-lib')
INS = '一位温柔自信的年轻女性，声音清晰，语气亲切，表达轻快而富有感染力。'
CN = {'2':'两','3':'三','4':'四','5':'五','6':'六','7':'七','8':'八'}

def spoken(v, i):
    i = i.replace('（可选）', '可选').replace(' 320°F', '三百二十华氏度').replace('1–2 分钟', '一到两分钟').replace('、', '')
    i = re.sub(r'^(\d) 个杯子$', lambda m: CN[m.group(1)] + '个杯子', i)
    i = re.sub(r'^分成 (\d) 份$', lambda m: '分成' + CN[m.group(1)] + '份', i)
    return v + i

def load(): return json.load(open(os.path.join(WORK, 'clips.json')))
def state():
    p = os.path.join(WORK, 'state.json'); return json.load(open(p)) if os.path.exists(p) else {}
def save(s): json.dump(s, open(os.path.join(WORK, 'state.json'), 'w'), ensure_ascii=False, indent=1)

def main():
    cmd = sys.argv[1]
    if cmd == 'texts':
        subprocess.check_call(['node', os.path.join(ROOT, 'tools', 'extract_clips.js'), os.path.join(WORK, 'clips.json'), os.path.join(ROOT, 'index.html')], stdout=subprocess.DEVNULL)
        c = load()
        for n, x in enumerate(c, 1): x['id'] = f'v{n:02d}'; x['spoken'] = spoken(x['v'], x['i'])
        json.dump(c, open(os.path.join(WORK, 'clips.json'), 'w'), ensure_ascii=False, indent=1); print(len(c), '句')
    elif cmd == 'round':
        seed = sys.argv[2]; st = state(); args = []
        for x in load():
            if x['id'] in st: continue
            t = x['spoken'] + ('' if x['spoken'][-1] in '！？' else '。')
            args.append(f"{x['id']}_s{seed} = {t}好。")
        if not args: print('NONE'); return
        out = subprocess.run(['python3', VL + '/tools/voicelib.py', 'try', '--project', 'dessert-menu', '--ref', f'audio-s{seed}', '--engine', 'breeze', '--seed', seed, '--instruction', INS] + args, capture_output=True, text=True).stdout
        print(len(args), '句', re.search(r'申请 (\S+)（', out).group(1))
    elif cmd == 'collect':
        id_, seed = sys.argv[2], sys.argv[3]; st = state(); sys.path.insert(0, os.path.join(ROOT, 'tools'))
        import numpy as np; from cut_each import cut_one; from cut_clips import write
        for x in load():
            f = f"{VL}/_trial/{id_}/{x['id']}_s{seed}.wav"
            if x['id'] in st or not os.path.exists(f): continue
            try: y, sr, tl, inner = cut_one(f)
            except Exception as e: print(x['id'], x['spoken'], '→ 失败：', e); continue
            n = len(re.sub(r'[。！？]', '', x['spoken'])); d = len(y) / sr; worst = max([g[1] - g[0] for g in inner], default=0)
            bad = worst > 0.30 or d / n < 0.12 or d > 0.28 * n + 0.6
            print(x['id'], f'{d:.2f}s {n}字 句内最长停顿 {worst:.2f}', '→ 不合格' if bad else 'OK', x['spoken'])
            if bad: continue
            wav = os.path.join(WORK, x['id'] + '.wav'); write(wav, y, sr)
            subprocess.check_call(['ffmpeg', '-y', '-loglevel', 'error', '-i', wav, '-codec:a', 'libmp3lame', '-q:a', '3', os.path.join(ROOT, 'audio', x['id'] + '.mp3')])
            st[x['id']] = {'seed': int(seed), 'dur': round(d, 2)}
        save(st); print('已完成', len(st), '/', len(load()))
    elif cmd == 'manifest':
        m = {x['key']: x['id'] + '.mp3' for x in load() if x['id'] in state()}
        json.dump(m, open(os.path.join(ROOT, 'audio', 'manifest.json'), 'w'), ensure_ascii=False, indent=1); print(len(m), '条')
main()
