#!/usr/bin/env python3
"""生成 / 更新一个核心补丁（typecho-patches 仓库的唯一入口）。

用法：
    python3 tools/make_patch.py \
        --id 2026-10-php85-pregmatch-null \
        --typecho 1.3.0 \
        --path var/Widget/Contents/EditTrait.php \
        --before /tmp/pristine.php \
        --after  /tmp/patched.php \
        --title "修复 PHP 8.4+ 写入页 preg_match(null) 弃用警告" \
        --severity warn \
        --expect '/\\$name = \\(string\\) \\$item/'

它负责：建目录 → 拷 before/after → 出 change.diff（无时间戳）→ 算 sha256（统一 LF）
→ 更新 index.json。人只需要准备「原文件」和「打好补丁的文件」两份。
"""
import argparse
import difflib
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, 'index.json')

# 与客户端 Patch.php 的白名单保持一致：只允许改核心代码
ALLOWED_PREFIXES = ('var/', 'admin/')
ALLOWED_ROOT_FILES = ('index.php', 'install.php', '404.php')
DENY_MARKERS = ('..', '\\', '\x00')
DENY_PREFIXES = ('usr/', '.git/')


def die(msg):
    print('✗ ' + msg, file=sys.stderr)
    sys.exit(1)


def check_path(p):
    p = p.replace('\\', '/').lstrip('/')
    if any(m in p for m in DENY_MARKERS):
        die('路径非法：' + p)
    if p.startswith(DENY_PREFIXES):
        die('不允许改动 ' + p + '（用户资产 / 版本库）')
    if p not in ALLOWED_ROOT_FILES and not p.startswith(ALLOWED_PREFIXES):
        die('路径不在白名单内：' + p + '（只允许 var/ admin/ ' + ' '.join(ALLOWED_ROOT_FILES) + '）')
    return p


def read_lf(path):
    raw = open(path, 'rb').read()
    return raw.replace(b'\r\n', b'\n')


def write_diffs(patch_id, ver, entry):
    """把补丁目录下所有文件（同版本）的 diff 拼成一份 change.diff。"""
    base = os.path.join(ROOT, 'patches', patch_id, ver)
    chunks = []
    for f in entry.get('files', []):
        b = os.path.join(base, 'before', f['path'])
        a = os.path.join(base, 'after', f['path'])
        if not (os.path.exists(b) and os.path.exists(a)):
            continue
        tb = read_lf(b).decode('utf-8', 'replace').splitlines(keepends=True)
        ta = read_lf(a).decode('utf-8', 'replace').splitlines(keepends=True)
        if tb == ta:
            continue
        chunks.append(''.join(difflib.unified_diff(
            tb, ta, fromfile='a/' + f['path'], tofile='b/' + f['path'], n=3)))
    merged = ''.join(chunks)
    os.makedirs(base, exist_ok=True)
    open(os.path.join(base, 'change.diff'), 'w', encoding='utf-8').write(merged)
    return merged


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--id', required=True, help='补丁 id（同时也是目录名，建议 2026-10-xxx）')
    ap.add_argument('--typecho', required=True, help='目标 Typecho 版本，如 1.3.0')
    ap.add_argument('--path', required=True, help='站点内相对路径，如 var/Widget/Contents/EditTrait.php')
    ap.add_argument('--before', required=True, help='官方原版文件')
    ap.add_argument('--after', required=True, help='打好补丁的文件')
    ap.add_argument('--title', required=True)
    ap.add_argument('--severity', default='warn', choices=['info', 'warn', 'error', 'security'])
    ap.add_argument('--notes', default='', help='说明（Markdown 单段即可）')
    ap.add_argument('--expect', default='', help='可选 PCRE，打完必须命中')
    ap.add_argument('--typecho-max', default='', help='默认与 --typecho 相同')
    args = ap.parse_args()

    rel = check_path(args.path)
    before_bytes = read_lf(args.before)
    after_bytes = read_lf(args.after)
    if before_bytes == after_bytes:
        die('before 与 after 内容相同，没东西可打')

    h_before, h_after = sha(before_bytes), sha(after_bytes)
    ver = args.typecho
    base = os.path.join(ROOT, 'patches', args.id, ver)

    for kind, data in (('before', before_bytes), ('after', after_bytes)):
        dst = os.path.join(base, kind, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        open(dst, 'wb').write(data)

    # change.diff（无时间戳，仅审阅）—— 单文件先写一份，多文件时由 write_diffs() 合并重写
    text_before = before_bytes.decode('utf-8', 'replace').splitlines(keepends=True)
    text_after = after_bytes.decode('utf-8', 'replace').splitlines(keepends=True)
    diff = ''.join(difflib.unified_diff(text_before, text_after,
                                        fromfile='a/' + rel, tofile='b/' + rel, n=3))
    open(os.path.join(base, 'change.diff'), 'w', encoding='utf-8').write(diff)

    # index.json
    index = {'schema': 1, 'updated': '', 'min_ab': '', 'patches': []}
    if os.path.exists(INDEX):
        index = json.load(open(INDEX, encoding='utf-8'))
    index.setdefault('patches', [])
    index.setdefault('schema', 1)
    index.setdefault('min_ab', '2.1.62')

    entry = next((p for p in index['patches'] if p.get('id') == args.id), None)
    if entry is None:
        entry = {'id': args.id, 'files': []}
        index['patches'].append(entry)
    entry['title'] = args.title
    entry['severity'] = args.severity
    entry['typecho'] = {'min': ver, 'max': args.typecho_max or ver}
    if args.notes:
        entry['notes'] = args.notes
    entry.setdefault('refs', ['https://github.com/lhl77/typecho-patches/tree/main/patches/' + args.id])

    files = entry.setdefault('files', [])
    f = next((x for x in files if x.get('path') == rel), None)
    if f is None:
        f = {'path': rel, 'mode': 'replace', 'eol': 'lf', 'sha256_before': []}
        files.append(f)
    hashes = [h for h in f.get('sha256_before', []) if h != h_after]
    if h_before not in hashes:
        hashes.append(h_before)
    f['sha256_before'] = hashes
    f['sha256_after'] = h_after
    f['after'] = 'patches/%s/%s/after/%s' % (args.id, ver, rel)
    f['diff'] = 'patches/%s/%s/change.diff' % (args.id, ver)
    if args.expect:
        f['expect'] = args.expect

    index['updated'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    open(INDEX, 'w', encoding='utf-8').write(json.dumps(index, ensure_ascii=False, indent=2) + '\n')

    # change.diff：把本补丁下所有文件（当前版本）的 diff 合并成一份，供人工审阅
    diff = write_diffs(args.id, ver, entry)

    # meta.json（人读）—— 多文件补丁要把 entry 里累积的 files 全部列出
    meta = {
        'id': args.id, 'title': args.title, 'severity': args.severity,
        'typecho': entry['typecho'],
        'files': [{'path': x['path'], 'sha256_before': x.get('sha256_before', []),
                   'sha256_after': x.get('sha256_after', '')} for x in entry['files']],
        'updated': index['updated'],
    }
    open(os.path.join(ROOT, 'patches', args.id, 'meta.json'), 'w', encoding='utf-8').write(
        json.dumps(meta, ensure_ascii=False, indent=2) + '\n')

    print('✓ 补丁已写入 patches/%s/%s/' % (args.id, ver))
    print('  before sha256 =', h_before)
    print('  after  sha256 =', h_after)
    print('  index.json 已更新（updated=%s）' % index['updated'])
    if diff:
        print('--- change.diff ---')
        print(diff)


if __name__ == '__main__':
    main()
