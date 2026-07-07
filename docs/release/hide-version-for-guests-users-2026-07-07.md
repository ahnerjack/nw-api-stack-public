# NW-API 隐藏游客/普通用户版本号

时间：2026-07-07
范围：源码 `public-sanitized` + 正式站运行代码

## 要求

- `https://of.ahner.cn/pricing` 不体现版本号。
- 所有游客和普通用户都看不到版本号。
- 修改必须进入 Git 源码，不只改服务器本地文件。

## 修改

源码文件：

`services/xapi-portal/xapi_portal.py`

变更：

- `version_update_widget(user)` 对未登录用户和非管理员直接返回空字符串。
- `public_page()` 移除 `release_version_menu(APP_VERSION)`。
- 管理员侧保留版本/更新入口。

## 验证

源码渲染验证：

- `/pricing` 游客：无可见版本号，无 release menu
- `/models` 游客：无可见版本号，无 release menu
- `/plans` 游客：无可见版本号，无 release menu
- `/risk` 游客：无可见版本号，无 release menu

正式站验证：

游客：

- `/pricing`：visible_bad 0, release_menu 0
- `/models`：visible_bad 0, release_menu 0
- `/plans`：visible_bad 0, release_menu 0
- `/risk`：visible_bad 0, release_menu 0

普通用户（临时测试用户，验证后删除）：

- `/dashboard`：visible_bad 0, release_menu 0
- `/pricing`：visible_bad 0, release_menu 0
- `/models`：visible_bad 0, release_menu 0
- `/docs`：visible_bad 0, release_menu 0

回归：

- 44/44 通过
- secret scan：0 real keys
- `xapi-portal` active
- `xapi-v1-wrapper` active
- `caddy` active

正式备份：

`/root/nwapi-backups/hide-version-20260707-115516`
