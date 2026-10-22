# typecho-patches

给 Typecho 核心打的小补丁，由 **AdminBeautify ≥ 2.1.62** 自动拉取并一键应用。

- 客户端只读 `index.json`（经 `https://gh1.lhl.one/` 镜像加速，失败回退 raw / jsDelivr）。
- 补丁仓库不再分发生成式「patch 文件」，而是**整文件替换**：`before/`（原版）+ `after/`（打好版），客户端靠 `sha256` 判定能不能打。
- `change.diff` 只供人工审阅，客户端不使用。

## 目录

```
index.json                      ← 唯一入口（客户端只拉这个）
schema/index.schema.json        ← JSON Schema
tools/make_patch.py             ← 生成 / 更新补丁的唯一入口
patches/<id>/meta.json          ← 人读元数据
patches/<id>/README.md          ← 背景、影响、验证方法
patches/<id>/<typecho版本>/
    before/<相对路径>           ← 官方原版
    after/<相对路径>            ← 打好补丁的版本
    change.diff                 ← 仅供审阅
```

## 加一个新补丁

```bash
python3 tools/make_patch.py \
  --id 2026-11-example \
  --typecho 1.3.0 \
  --path var/Widget/Contents/EditTrait.php \
  --before /tmp/pristine.php \
  --after  /tmp/patched.php \
  --title "一句话标题" \
  --severity warn \
  --expect '/\$name = \(string\) \$item/'
```

脚本会：建目录 → 拷 before/after → 出 `change.diff`（无时间戳）→ 算 `sha256`（统一 LF）→ 改写 `index.json`。

## 字段说明

| 字段 | 说明 |
|---|---|
| `min_ab` | 低于该版本的 AdminBeautify 不显示补丁 |
| `typecho.min/max` | Typecho 版本闭区间（`version_compare`） |
| `files[].path` | 相对站点根目录；客户端只允许 `var/` `admin/` 与根目录白名单文件 |
| `files[].sha256_before` | **数组**：所有可接受的「干净原版」哈希（官方包 / 镜像包 / CRLF 版） |
| `files[].sha256_after` | 打完必须是它 → 幂等判定 + 写后复核 |
| `files[].expect` | 可选 PCRE；打完必须命中，防止拿错文件 |
| `files[].eol` | 校验前统一换行符，`lf`（默认）/ `crlf` |

## 安全

- 客户端只接受白名单路径，拒绝 `usr/`、`config.inc.php`、`.git`、`usr/plugins/AdminBeautify`。
- 写入前做 PHP 语法自检（`token_get_all(..., TOKEN_PARSE)`）、备份、原子写、写后复核哈希。
- 建议同时提交 `index.json.sig`（Ed25519），客户端有 sodium 时会验签。
