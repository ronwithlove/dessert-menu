#!/usr/bin/env python3
"""每句单独生成（句尾带一个「好。」语气词当垫尾）→ 去掉垫尾、去首尾静音、统一响度。
用法：cut_each.py 输出目录 名字1=文件1.wav 名字2=文件2.wav ... [--preview 试听.wav]
垫尾判定：最后一个 ≥0.18s 的停顿之后的那段声音。垫尾长度不在 0.1–1.0s 就报警，不输出。"""
import sys, os, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cut_clips import read, write, silences, process, MIN_GAP

def cut_one(path):
    x, sr = read(path); L = len(x) / sr
    gaps = [g for g in silences(x, sr) if g[1] - g[0] >= MIN_GAP and g[0] > 0.01 and g[1] < L - 0.01]
    if not gaps: raise ValueError('没找到垫尾前的停顿')
    last = gaps[-1]
    # 垫尾真实结束：last[1] 之后到最后一个有声帧
    tail_part = x[int(last[1] * sr):]
    from cut_clips import frames_db
    db = frames_db(tail_part, sr); v = np.where(db > frames_db(x, sr).max() - 35)[0]
    tail_len = (v[-1] - v[0] + 1) * 0.01 if len(v) else 0
    if not (0.1 <= tail_len <= 1.0): raise ValueError(f'垫尾长度 {tail_len:.2f}s 不对')
    body = x[:int((last[0] + last[1]) / 2 * sr)]
    inner = [g for g in gaps[:-1]]
    return process(body, sr), sr, tail_len, inner

def main():
    a = sys.argv[1:]; prev = None
    if '--preview' in a: i = a.index('--preview'); prev = a[i + 1]; del a[i:i + 2]
    out = a[0]; os.makedirs(out, exist_ok=True); clips = []; bad = 0
    for it in a[1:]:
        name, path = it.split('=', 1)
        try:
            y, sr, tl, inner = cut_one(path)
        except Exception as e:
            print(f'  {name:<8}失败：{e}'); bad += 1; continue
        write(os.path.join(out, name + '.wav'), y, sr); clips.append(y)
        warn = f'  ⚠ 句内停顿 {[round(g[1]-g[0],2) for g in inner]}' if inner else ''
        print(f'  {name:<8}{len(y)/sr:5.2f}s  垫尾{tl:.2f}s{warn}')
    if prev and clips:
        gap = np.zeros(int(1.0 * sr)); write(prev, np.concatenate([np.concatenate([c, gap]) for c in clips]), sr)
    sys.exit(1 if bad else 0)
if __name__ == "__main__": main()
