#!/usr/bin/env python3
"""把 Breeze 整串生成的 wav 按停顿切成一句一个文件。
用法：cut_clips.py 整串.wav 句子.json 输出目录 [--names n1,n2,..] [--preview 试听.wav]
句子.json 是 spoken 字符串列表，每句里的「，」数 = 句内会出现的停顿数，句间还有一个停顿。
停顿数对不上就报错并列出停顿位置，不乱切。"""
import sys, json, wave, argparse, os
import numpy as np

SR = 24000
FR = 0.01           # 10 ms 一帧
MIN_GAP = 0.18      # 停顿至少多长算数
TAIL = 0.15         # 每句尾巴留的余音
SHRINK = 0.25       # 句内长停顿压到多少秒
TARGET_DB = -16.0   # 句子响度（RMS，只算有声音的帧）

def read(p):
    w = wave.open(p); assert w.getnchannels() == 1 and w.getsampwidth() == 2
    sr = w.getframerate(); x = np.frombuffer(w.readframes(w.getnframes()), dtype='<i2').astype(np.float64) / 32768
    return x, sr

def write(p, x, sr):
    x = np.clip(x, -1, 1)
    w = wave.open(p, 'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
    w.writeframes((x * 32767).astype('<i2').tobytes()); w.close()

def frames_db(x, sr):
    n = int(sr * FR); m = len(x) // n
    r = np.sqrt((x[:m * n].reshape(m, n) ** 2).mean(1) + 1e-12)
    return 20 * np.log10(r)

def silences(x, sr, thr_off=-38):
    db = frames_db(x, sr); thr = db.max() + thr_off if False else (db.max() - 35)
    sil = db < thr; runs = []; i = 0
    while i < len(sil):
        if sil[i]:
            j = i
            while j < len(sil) and sil[j]: j += 1
            runs.append((i * FR, j * FR)); i = j
        else: i += 1
    return runs

def norm(x, sr):
    db = frames_db(x, sr); act = db > db.max() - 30
    n = int(sr * FR); m = len(x) // n
    seg = x[:m * n].reshape(m, n)[act]
    rms = np.sqrt((seg ** 2).mean()); g = 10 ** (TARGET_DB / 20) / rms
    y = x * g; pk = np.abs(y).max()
    if pk > 0.89: y *= 0.89 / pk
    return y

def process(seg, sr):
    """去首尾静音，句内长停顿压短，留尾巴再淡出，统一响度"""
    db = frames_db(seg, sr); n = int(sr * FR); thr = db.max() - 35
    voiced = np.where(db >= thr)[0]
    a, b = voiced[0] * n, (voiced[-1] + 1) * n
    seg = seg[max(0, a - int(.03 * sr)):min(len(seg), b + int(TAIL * sr))]
    # 压句内长停顿
    db = frames_db(seg, sr); sil = db < db.max() - 35
    out = []; i = 0
    while i < len(sil):
        j = i
        while j < len(sil) and sil[j] == sil[i]: j += 1
        chunk = seg[i * n:j * n]
        if sil[i] and 0 < i and j < len(sil) - 1 and len(chunk) > SHRINK * sr:
            h = int(SHRINK * sr / 2); chunk = np.concatenate([chunk[:h], chunk[-h:]])
        out.append(chunk); i = j
    seg = np.concatenate(out + [seg[len(sil) * n:]])
    f = int(.05 * sr); seg[-f:] *= np.linspace(1, 0, f)
    seg[:int(.01 * sr)] *= np.linspace(0, 1, int(.01 * sr))
    return norm(seg, sr)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('wav'); ap.add_argument('texts'); ap.add_argument('outdir')
    ap.add_argument('--names'); ap.add_argument('--preview'); ap.add_argument('--preview-gap', type=float, default=1.0)
    a = ap.parse_args()
    x, sr = read(a.wav); texts = json.load(open(a.texts))
    names = a.names.split(',') if a.names else [f'{i+1:02d}' for i in range(len(texts))]
    k = [t.count('，') for t in texts]; expect = sum(k) + len(texts) - 1
    gaps = [g for g in silences(x, sr) if g[1] - g[0] >= MIN_GAP]
    # 去掉首尾静音
    gaps = [g for g in gaps if g[0] > 0.01 and g[1] < len(x) / sr - 0.01]
    print(f'总长 {len(x)/sr:.1f}s，句数 {len(texts)}，应有停顿 {expect}，检测到 {len(gaps)}')
    if len(gaps) != expect:
        for i, g in enumerate(gaps): print(f'  停顿{i}: {g[0]:.2f}–{g[1]:.2f}（{g[1]-g[0]:.2f}s）')
        sys.exit('停顿数对不上，没有切。')
    bidx = []; p = -1
    for ki in k[:-1]: p += ki + 1; bidx.append(p)
    cuts = [0.0] + [(gaps[i][0] + gaps[i][1]) / 2 for i in bidx] + [len(x) / sr]
    os.makedirs(a.outdir, exist_ok=True); clips = []
    for i, t in enumerate(texts):
        seg = x[int(cuts[i] * sr):int(cuts[i + 1] * sr)]
        y = process(seg, sr); clips.append(y)
        write(os.path.join(a.outdir, names[i] + '.wav'), y, sr)
        print(f'  {names[i]:<14}{len(y)/sr:5.2f}s  {t}')
    if a.preview:
        gap = np.zeros(int(a.preview_gap * sr)); write(a.preview, np.concatenate([np.concatenate([c, gap]) for c in clips]), sr)
if __name__ == '__main__': main()
