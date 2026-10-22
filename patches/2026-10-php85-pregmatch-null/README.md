# 2026-10-php85-pregmatch-null

**修复 PHP 8.4+ 写入页 `preg_match(null)` 弃用警告** · severity `warn` · Typecho `1.3.0`

## 现象

PHP 8.4 / 8.5 下进入「写文章 / 写页面」，页面顶部刷两条：

```
Deprecated: preg_match(): Passing null to parameter #2 ($subject) of type string is deprecated
in /www/wwwroot/…/var/Widget/Contents/EditTrait.php on line 257

Deprecated: preg_match(): Passing null to parameter #2 ($subject) of type string is deprecated
in /www/wwwroot/…/var/Widget/Contents/EditTrait.php on line 261
```

## 原因

`EditTrait::getDefaultFieldItems()` 渲染主题自定义字段时读 `$item->input->getAttribute('name')`：

```php
$name = $item->input->getAttribute('name');
...
if (preg_match("/^fields\[(.+)\]$/", $name, $matches)) {   // 257
    ...
    if (preg_match("/^(.+)\[\]$/", $name, $matches)) {     // 261
```

自定义字段的 `input` 没写 `name` 属性时 `getAttribute()` 返回 **null**，PHP 8.4 起把 null 传给
`preg_match()` 的 `$subject` 就发 `Deprecated`。

## 改法

只加一个显式转换，`null → ''`：

```diff
-                $name = $item->input->getAttribute('name');
+                // 自定义字段的 input 可能没有 name 属性 → getAttribute() 返回 null，
+                // PHP 8.4+ 把 null 传给 preg_match() 的 $subject 会报
+                // 「Passing null to parameter #2 of type string is deprecated」（257 / 261 行）。
+                // 转成字符串：null → ''，与下面 'fields[' . $name . ']' 的隐式转换行为一致。
+                $name = (string) $item->input->getAttribute('name');
```

行为零变化：原来的 `$inputName = 'fields[' . $name . ']'` 本身就会把 null 当 `''` 拼接，
`isset($fields->{''})`、`$defaultFields['']` 的键也完全一致。

## 受影响文件

| 路径 | before sha256 | after sha256 |
|---|---|---|
| `var/Widget/Contents/EditTrait.php` | `43cf3fb4…7dbc03` | `4c81fc44…35030d` |

## 验证

1. 打完进入「写文章」，不再出现上面两条 `Deprecated`。
2. `php -l var/Widget/Contents/EditTrait.php` → No syntax errors。
3. 自定义字段（主题 `functions.php` 里的 `themeFields()`）仍能正常显示与保存。

## 回滚

AdminBeautify 会在应用前自动备份到 `usr/plugins/AdminBeautify/.patch-backup/`，
也可直接 `do=patch-rollback&id=2026-10-php85-pregmatch-null`。
