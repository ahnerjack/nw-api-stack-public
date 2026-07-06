# 阶段 0 回滚手册

## 1. 回滚触发条件

任一情况触发回滚：
- `/v1/models` 非预期 5xx。
- `/v1/chat/completions` 正常 Key 无法调用。
- 流式响应卡死或明显比基线更差。
- Key 校验异常导致大量误拒绝。
- Caddy/Nginx reload 后正式入口无法访问。
- portal 登录/管理页 5xx。

## 2. 正式操作前备份

正式环境执行任何更新前：

```bash
TS=$(date +%Y%m%d-%H%M%S)
sudo mkdir -p /opt/nw-api-backups/$TS
sudo cp -a /opt/xapi-portal /opt/nw-api-backups/$TS/xapi-portal
sudo cp -a /opt/xapi-v1-wrapper /opt/nw-api-backups/$TS/xapi-v1-wrapper 2>/dev/null || true
sudo cp -a /opt/nw-api-stack /opt/nw-api-backups/$TS/nw-api-stack
sudo cp -a /etc/caddy/Caddyfile /opt/nw-api-backups/$TS/Caddyfile 2>/dev/null || true
sudo sqlite3 /opt/xapi-portal/xapi_portal.db ".backup '/opt/nw-api-backups/$TS/xapi_portal.db'"
```

## 3. 代码回滚

```bash
cd /opt/nw-api-stack
sudo git fetch --tags origin
sudo git reset --hard <GOOD_COMMIT_OR_TAG>
sudo ./scripts/deploy-aliyun.sh
```

## 4. 文件备份回滚

```bash
TS=<backup-ts>
sudo systemctl stop xapi-portal || true
sudo systemctl stop xapi-v1-wrapper || true
sudo cp -a /opt/nw-api-backups/$TS/xapi-portal/* /opt/xapi-portal/
sudo cp -a /opt/nw-api-backups/$TS/xapi-v1-wrapper/* /opt/xapi-v1-wrapper/ 2>/dev/null || true
sudo cp -a /opt/nw-api-backups/$TS/Caddyfile /etc/caddy/Caddyfile 2>/dev/null || true
sudo systemctl restart xapi-portal
sudo systemctl restart xapi-v1-wrapper || true
sudo systemctl reload caddy || sudo systemctl restart caddy
```

## 5. 回滚后验证

```bash
curl -skI https://<domain>/home
curl -skI https://<domain>/login
curl -sk https://<domain>/v1/models -H 'Authorization: Bearer <test-key>'
python3 tests/phase0/test_v1_wrapper_regression.py
```

## 6. 注意

- 代码可以回滚，账务和上游用户删除不能简单回滚。
- 阶段 0 不做真实账务改动，降低回滚复杂度。
- 后续涉及余额/扣费前，必须增加账务补偿手册。
