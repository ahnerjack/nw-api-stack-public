#!/usr/bin/env python3
import os, html, json, secrets, sqlite3, hashlib, hmac, urllib.parse, urllib.request, time, re, smtplib, csv, io, subprocess, shlex
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from http.cookies import SimpleCookie
from email.message import EmailMessage

HOST='127.0.0.1'; PORT=18180; BRAND='NW-API'; BASE_URL='https://api.example.com/v1'; APP_VERSION='V.0.005'; REPO_DIR=os.environ.get('NW_API_REPO_DIR','/opt/nw-api-stack'); UPDATE_LOG=os.environ.get('NW_API_UPDATE_LOG','/var/log/nw-api-update.log')
DB='/opt/xapi-portal/xapi_portal.db'; DATA_BASE=os.environ.get('XAPI_DATA_BASE','http://127.0.0.1:18066/xapi-data')
ADMIN_EMAIL=os.environ.get('XAPI_ADMIN_EMAIL','admin@xapi.local'); ADMIN_PASS=os.environ.get('XAPI_ADMIN_PASS','change-me-via-env')
SMTP_HOST=os.environ.get('XAPI_SMTP_HOST',''); SMTP_PORT=int(os.environ.get('XAPI_SMTP_PORT','587')); SMTP_USER=os.environ.get('XAPI_SMTP_USER',''); SMTP_PASS=os.environ.get('XAPI_SMTP_PASS',''); SMTP_FROM=os.environ.get('XAPI_SMTP_FROM',SMTP_USER or 'noreply@xapi.local'); SMTP_TLS=os.environ.get('XAPI_SMTP_TLS','1').lower() in ('1','true','yes','on')
PAYMENT_NOTICE=os.environ.get('NW_API_PAYMENT_NOTICE','')
SESS={}; VERIFY_CODES={}; LOGIN_FAILS={}; SESSION_TTL=8*3600
CSS='''<style>:root{--brand:#0891b2;--brand2:#4f46e5;--ink:#111827;--muted:#64748b;--line:#e5e7eb;--soft:#f6f8fc;--panel:#ffffff;--dark:#07111f;--danger:#dc2626;--ok:#059669;--shadow:0 14px 42px rgba(15,23,42,.07);--font:-apple-system,BlinkMacSystemFont,"Helvetica Neue","PingFang SC","Hiragino Sans GB","Microsoft YaHei","Segoe UI",Arial,sans-serif;--mono:"SFMono-Regular",Consolas,"Liberation Mono",Menlo,monospace}*{box-sizing:border-box}html{-webkit-text-size-adjust:100%;text-rendering:optimizeLegibility}body{margin:0;font-family:var(--font);font-size:14px;font-weight:400;background:linear-gradient(180deg,#f6fbff 0%,#edf4ff 52%,#f8fafc 100%);color:var(--ink);line-height:1.62;letter-spacing:.01em}a{color:inherit;text-decoration:none}.layout{display:grid;grid-template-columns:220px minmax(0,1fr);min-height:100vh;width:100%}.side{background:linear-gradient(180deg,#020617,#0b1220 54%,#111827);color:#d8e2f0;padding:18px 12px;position:sticky;top:0;height:100vh;overflow:auto;border-right:1px solid rgba(255,255,255,.08)}.logo{display:flex;gap:10px;align-items:center;font-weight:820;font-size:17px;margin:2px 8px 18px;line-height:1.2}.logo small{font-size:11px;color:#64748b;font-weight:650}.brand-copy{display:flex;flex-direction:column;align-items:flex-start;gap:3px}.side .brand-copy{color:#f8fafc}.brand-name{font-weight:850;line-height:1.05}.brand-copy{display:flex;flex-direction:column;align-items:flex-start;gap:3px}.side .brand-copy{color:#f8fafc}.brand-name{font-weight:850;line-height:1.05}.mark{width:36px;height:36px;border-radius:17px;background:transparent;display:grid;place-items:center;color:#06101f;box-shadow:0 12px 28px rgba(15,23,42,.30);font-weight:900}.mark svg{width:36px;height:36px;display:block}.version-pill{display:inline-flex;margin-top:5px;padding:3px 9px;border-radius:999px;background:linear-gradient(135deg,#0ea5e9,#6366f1);color:#fff!important;font-size:12px!important;font-weight:900!important;line-height:1.25;letter-spacing:.02em;box-shadow:0 8px 18px rgba(37,99,235,.26)}.nav{display:grid;gap:3px}.nav a:nth-child(5),.nav a:nth-child(7),.nav a:nth-child(11){margin-top:8px}.nav a{position:relative;display:flex;align-items:center;min-height:34px;padding:7px 10px;border-radius:10px;color:#c3cedd;font-weight:620;font-size:12.5px;line-height:1.2;letter-spacing:0}.nav a:hover,.nav a.on{background:rgba(255,255,255,.10);color:#fff}.nav a:nth-child(n+11){font-size:12px;opacity:.78;min-height:31px}.nav a:nth-child(n+11):hover,.nav a:nth-child(n+11).on{opacity:1}.top .actions{margin-left:auto}.main{padding:24px 28px;width:100%;max-width:none}.top{display:flex;justify-content:space-between;gap:16px;align-items:flex-start;margin-bottom:20px}.top h1,h1{margin:0 0 6px;font-size:28px;font-weight:760;letter-spacing:-.025em;line-height:1.22}h2{font-size:18px;font-weight:720;margin:0 0 12px;letter-spacing:-.01em}h3{font-size:16px;font-weight:700;margin:0 0 10px}.grid{display:grid;grid-template-columns:repeat(4,minmax(180px,1fr));gap:14px}.card{background:rgba(255,255,255,.94);border:1px solid rgba(226,232,240,.95);border-radius:16px;padding:16px;box-shadow:var(--shadow);margin-bottom:14px;backdrop-filter:blur(10px)}.k{color:var(--muted);font-size:11px;font-weight:760;text-transform:uppercase;letter-spacing:.055em}.num{font-size:21px;font-weight:720;margin-top:5px;line-height:1.18;letter-spacing:-.01em;font-variant-numeric:tabular-nums}.btn{display:inline-flex;min-height:36px;align-items:center;justify-content:center;padding:0 13px;border-radius:10px;background:linear-gradient(135deg,var(--brand),var(--brand2));color:#fff!important;font-weight:700;font-size:13px;border:0;cursor:pointer;white-space:nowrap;box-shadow:0 10px 22px rgba(37,99,235,.18);letter-spacing:0}.btn:hover{filter:brightness(.96)}.btn2{background:#fff;color:#172033!important;border:1px solid var(--line);box-shadow:none}table{width:100%;border-collapse:separate;border-spacing:0;overflow:hidden;border-radius:14px;background:#fff;table-layout:auto}th,td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--line);font-size:13px;line-height:1.45;vertical-align:top;word-break:break-word}th{color:#64748b;font-size:11px;font-weight:760;text-transform:uppercase;letter-spacing:.045em;background:#f8fafc;white-space:nowrap}tr:hover td{background:#fbfdff}code,pre{font-family:var(--mono);font-size:12px;background:#07111f;color:#d9f99d;border-radius:14px;padding:14px;display:block;overflow:auto;line-height:1.65;letter-spacing:0}.login{min-height:100vh;display:grid;place-items:center;padding:24px;background:radial-gradient(circle at 18% 12%,rgba(34,211,238,.24),transparent 30%),radial-gradient(circle at 84% 18%,rgba(79,70,229,.24),transparent 31%),linear-gradient(180deg,#020617,#0b1220 58%,#111827)}.box{width:min(440px,94vw);background:rgba(255,255,255,.97);border:1px solid rgba(255,255,255,.68);border-radius:24px;padding:28px;box-shadow:0 34px 96px rgba(2,6,23,.34)}input,select{height:38px;border:1px solid var(--line);border-radius:10px;padding:0 11px;margin:5px 0 9px;background:#fff;color:#172033;font-family:var(--font);font-size:13px;line-height:38px}input{width:100%}textarea{font-family:var(--font);font-size:13px;line-height:1.55;border:1px solid var(--line);border-radius:10px;padding:10px}.err{color:#dc2626}.muted{color:var(--muted)}p{margin:7px 0 10px}.actions{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.actions input,.actions select{width:auto;min-width:108px}.pill{display:inline-flex;padding:5px 9px;border-radius:999px;background:#eff6ff;color:#1d4ed8;font-weight:700;font-size:12px;line-height:1.2}@media(max-width:1080px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}.layout{grid-template-columns:210px minmax(0,1fr)}.side{padding:16px 12px}.main{padding:22px}}@media(max-width:860px){body{font-size:13px}.layout{grid-template-columns:1fr}.side{height:auto;position:relative}.nav{grid-template-columns:repeat(3,minmax(0,1fr))}.main{padding:16px}.top{flex-direction:column}.grid{grid-template-columns:1fr 1fr}.card{border-radius:16px;padding:16px}table{display:block;overflow-x:auto;white-space:nowrap}td{white-space:normal;min-width:80px}}@media(max-width:560px){body{font-size:13px;line-height:1.55}.nav{grid-template-columns:repeat(2,minmax(0,1fr))}.grid{grid-template-columns:1fr}.card{padding:15px;border-radius:15px}.actions{display:grid;grid-template-columns:1fr}.actions input,.actions select,.actions .btn{width:100%}.top h1,h1{font-size:24px}.num{font-size:22px}th,td{font-size:12px;padding:8px}.box{padding:22px;border-radius:20px}}.release-menu{position:relative;display:inline-block}.release-menu summary{list-style:none;cursor:pointer;display:inline-flex}.release-menu summary::-webkit-details-marker{display:none}.release-menu>div{position:absolute;z-index:30;left:0;top:26px;min-width:118px;background:#fff;color:#111827;border:1px solid rgba(148,163,184,.35);border-radius:12px;padding:6px;box-shadow:0 16px 42px rgba(2,6,23,.18)}.release-menu a{display:block;padding:7px 9px;border-radius:9px;color:#111827!important;font-size:12px;font-weight:800;white-space:nowrap}.release-menu a:hover{background:#eff6ff;color:#2563eb!important}.version-row{display:flex;align-items:center;gap:6px;flex-wrap:wrap}.update-badge{display:inline-flex;align-items:center;padding:2px 6px;border-radius:999px;background:#ef4444;color:#fff!important;font-size:9px;font-weight:900;line-height:1.2;box-shadow:0 6px 14px rgba(239,68,68,.24)}.side .logo{display:grid!important;grid-template-columns:36px 1fr;gap:3px 10px;align-items:center}.side .logo>a{grid-column:1/3;display:grid!important;grid-template-columns:36px 1fr;gap:10px;align-items:center}.side .logo .version-row{grid-column:2;grid-row:2;margin-top:-6px}.side .logo .release-menu>div{left:0;top:28px}.side .ver-update{display:none}.ver-update{position:relative;display:inline-block}.ver-update summary{list-style:none;cursor:pointer;color:#94a3b8;font-size:11px;font-weight:850;display:inline-flex;gap:6px;align-items:center}.ver-update.has-update summary{color:#f59e0b}.ver-update summary span{font-size:9px;background:#ef4444;color:white;border-radius:999px;padding:1px 5px}.ver-update summary::-webkit-details-marker{display:none}.ver-update>div{position:absolute;z-index:20;left:0;top:24px;width:286px;background:#fff;color:#172033;border:1px solid #fde68a;border-radius:14px;padding:12px;box-shadow:0 18px 48px rgba(0,0,0,.24);font-size:12px}.ver-update p{color:#64748b;margin:6px 0}.ver-update input{height:30px;font-size:12px;margin:4px 0}.ver-update .btn{min-height:30px;font-size:12px;padding:0 10px}</style>'''
MAIL_FOOTER='''\n\n--\nNW-API 服务通知\n本邮件由系统自动发送，请勿直接回复。为保护账号安全，请不要在聊天、工单或邮件中发送完整 API Key、登录密码或验证码。'''
COMPLIANCE_LINKS='<a class="btn btn2" href="/terms">服务条款</a><a class="btn btn2" href="/privacy">隐私政策</a><a class="btn btn2" href="/docs">接入文档</a>'

def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

def init_db():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    c=db(); c.executescript('''CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,email TEXT UNIQUE NOT NULL,pass_hash TEXT NOT NULL,role TEXT NOT NULL DEFAULT 'user',sub2_user_id INTEGER NOT NULL,created_at INTEGER NOT NULL,status TEXT NOT NULL DEFAULT 'active');
CREATE TABLE IF NOT EXISTS ops_log(id INTEGER PRIMARY KEY AUTOINCREMENT,admin_email TEXT NOT NULL,action TEXT NOT NULL,target TEXT,detail TEXT,created_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS user_models(user_id INTEGER NOT NULL,model TEXT NOT NULL,enabled INTEGER NOT NULL DEFAULT 1,PRIMARY KEY(user_id,model));
CREATE TABLE IF NOT EXISTS model_prices(model TEXT PRIMARY KEY,input_price REAL NOT NULL DEFAULT 0,output_price REAL NOT NULL DEFAULT 0,cache_price REAL NOT NULL DEFAULT 0,image_price REAL NOT NULL DEFAULT 0,note TEXT);
CREATE TABLE IF NOT EXISTS billing_logs(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,admin_email TEXT NOT NULL,amount REAL NOT NULL,note TEXT,created_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS plans(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT UNIQUE NOT NULL,price REAL NOT NULL,monthly_quota REAL NOT NULL,daily_limit REAL NOT NULL,models TEXT NOT NULL,note TEXT,status TEXT NOT NULL DEFAULT 'active');
CREATE TABLE IF NOT EXISTS user_plans(user_id INTEGER PRIMARY KEY,plan_id INTEGER NOT NULL,started_at INTEGER NOT NULL,expires_at INTEGER,FOREIGN KEY(plan_id) REFERENCES plans(id));
CREATE TABLE IF NOT EXISTS recharge_orders(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,amount REAL NOT NULL,method TEXT,note TEXT,status TEXT NOT NULL DEFAULT 'pending',admin_email TEXT,created_at INTEGER NOT NULL,reviewed_at INTEGER);
CREATE TABLE IF NOT EXISTS risk_rules(id INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT NOT NULL,pattern TEXT NOT NULL,action TEXT NOT NULL DEFAULT 'block',note TEXT,status TEXT NOT NULL DEFAULT 'active',created_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS api_access_logs(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,key_id INTEGER,ip TEXT,method TEXT,path TEXT,model TEXT,status INTEGER,error_code TEXT,latency_ms INTEGER,created_at INTEGER);
CREATE TABLE IF NOT EXISTS rollback_logs(id INTEGER PRIMARY KEY AUTOINCREMENT,admin_email TEXT,action TEXT,target TEXT,snapshot TEXT,status TEXT NOT NULL DEFAULT 'recorded',created_at INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS idx_api_access_logs_created ON api_access_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_api_access_logs_status ON api_access_logs(status);
CREATE TABLE IF NOT EXISTS announcements(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL,content TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'active',pinned INTEGER NOT NULL DEFAULT 0,created_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS notifications(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,title TEXT NOT NULL,content TEXT NOT NULL,type TEXT,read_at INTEGER,created_at INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id,read_at);
CREATE TABLE IF NOT EXISTS mail_logs(id INTEGER PRIMARY KEY AUTOINCREMENT,recipient TEXT NOT NULL,subject TEXT NOT NULL,type TEXT,status TEXT NOT NULL,error TEXT,created_at INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS idx_mail_logs_created ON mail_logs(created_at);
CREATE TABLE IF NOT EXISTS payment_methods(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT UNIQUE NOT NULL,kind TEXT NOT NULL DEFAULT 'manual',instructions TEXT NOT NULL DEFAULT '',enabled INTEGER NOT NULL DEFAULT 1,sort_order INTEGER NOT NULL DEFAULT 100,updated_at INTEGER NOT NULL);''')
    c.execute('DELETE FROM api_access_logs WHERE created_at < ?', (int(time.time())-90*86400,))
    c.commit()
    if not c.execute('SELECT id FROM users WHERE email=?',(ADMIN_EMAIL,)).fetchone():
        # map admin to existing upstream root user id=1
        c.execute('INSERT INTO users(email,pass_hash,role,sub2_user_id,created_at,status) VALUES(?,?,?,?,?,?)',(ADMIN_EMAIL,hash_pw(ADMIN_PASS),'admin',1,int(time.time()),'active')); c.commit()
    for m,ip,op,cp,img,note in [('gpt-5.5',35,210,3.5,0,'主力模型'),('gpt-5.4',17.5,105,1.75,0,'均衡模型'),('gpt-5.4-mini',5.25,31.5,0.525,0,'经济模型')]:
        c.execute('INSERT OR IGNORE INTO model_prices(model,input_price,output_price,cache_price,image_price,note) VALUES(?,?,?,?,?,?)',(m,ip,op,cp,img,note))
    for name,price,quota,daily,models,note in [('普通会员',0,10,10,'gpt-5.4-mini,gpt-5.4','默认套餐'),('高级会员',99,100,50,'gpt-5.4-mini,gpt-5.4,gpt-5.5','高用量套餐'),('企业会员',499,1000,200,'gpt-5.4-mini,gpt-5.4,gpt-5.5','企业套餐')]:
        c.execute('INSERT OR IGNORE INTO plans(name,price,monthly_quota,daily_limit,models,note,status) VALUES(?,?,?,?,?,?,"active")',(name,price,quota,daily,models,note))
    for sort_order,name,kind,instructions in [(10,'支付宝','alipay','请按管理员提供的支付宝收款信息付款，并在备注填写订单号和付款流水号。'),(20,'微信','wechat','请按管理员提供的微信收款信息付款，并在备注填写订单号和付款流水号。'),(30,'银行转账','bank','请按管理员提供的银行账户转账，并在备注填写订单号和付款流水号。'),(40,'人工说明','manual','如需其他人工收款方式，请在订单备注填写联系方式和付款说明。')]:
        c.execute('INSERT OR IGNORE INTO payment_methods(name,kind,instructions,enabled,sort_order,updated_at) VALUES(?,?,?,?,?,?)',(name,kind,instructions,1,sort_order,int(time.time())))
    c.commit()
    c.close()

def hash_pw(pw, salt=None):
    salt=salt or secrets.token_hex(16); dk=hashlib.pbkdf2_hmac('sha256', pw.encode(), salt.encode(), 200000).hex(); return f'pbkdf2${salt}${dk}'

def check_pw(pw,h):
    try: _,salt,dk=h.split('$'); return hmac.compare_digest(hash_pw(pw,salt),h)
    except Exception: return False

def esc(x): return html.escape('' if x is None else str(x))

def brand_text(x): return str(x).replace('XAPI','NW-API')

def mask_key(k):
    s=str(k or '').strip()
    if not s: return ''
    if '*' in s and len(s) <= 24: return s
    if len(s) <= 12: return (s[:3] + '******' + s[-3:]) if len(s) > 6 else '******'
    return s[:6] + '******' + s[-4:]

def public_safe_text(x):
    s=str(x or '')
    for a,b in [('后台服务','上游服务'),('NVWA','服务节点'),('SMTP','邮件服务'),('203.0.113.10','公网服务地址')]:
        s=s.replace(a,b)
    return s

def mask_ip(x):
    s=str(x or '')
    if re.match(r'^\d+\.\d+\.\d+\.\d+$', s):
        a=s.split('.')
        return a[0]+'.'+a[1]+'.*.*'
    if ':' in s and s:
        return s.split(':',1)[0]+':****'
    return s

UPDATE_CACHE={'ts':0,'data':{'ok':False,'available':False,'local':'','remote':'','error':'not checked'}}

def run_cmd(args, cwd=REPO_DIR, timeout=8):
    return subprocess.run(args, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)

def update_state(force=False):
    now=time.time()
    if not force and now-UPDATE_CACHE.get('ts',0) < 120:
        return UPDATE_CACHE['data']
    data={'ok':False,'available':False,'local':'','remote':'','error':''}
    try:
        if not os.path.isdir(os.path.join(REPO_DIR,'.git')):
            raise RuntimeError('git repo not found: '+REPO_DIR)
        local=run_cmd(['git','rev-parse','--short','HEAD']).stdout.strip()
        branch=run_cmd(['git','rev-parse','--abbrev-ref','HEAD']).stdout.strip() or 'main'
        fetch=run_cmd(['git','fetch','--quiet','origin',branch], timeout=20)
        if fetch.returncode != 0:
            raise RuntimeError((fetch.stderr or fetch.stdout or 'git fetch failed').strip())
        remote=run_cmd(['git','rev-parse','--short',f'origin/{branch}']).stdout.strip()
        data={'ok':True,'available':bool(local and remote and local!=remote),'local':local,'remote':remote,'branch':branch,'error':''}
    except Exception as e:
        data['error']=str(e)[:300]
    UPDATE_CACHE['ts']=now; UPDATE_CACHE['data']=data
    return data

def ensure_admin_update_notice(st):
    if not st.get('available') or not st.get('remote'):
        return
    try:
        con=db(); now=int(time.time())
        admins=con.execute('SELECT id FROM users WHERE role="admin" AND status="active"').fetchall()
        for a in admins:
            exists=con.execute('SELECT id FROM notifications WHERE user_id=? AND type="update" AND content LIKE ? LIMIT 1',(a['id'],'%'+st['remote']+'%')).fetchone()
            if not exists:
                con.execute('INSERT INTO notifications(user_id,title,content,type,created_at) VALUES(?,?,?,?,?)',(a['id'],'NW-API 有新版本可更新','Git 已发现新版本 '+st['remote']+'，当前 '+st.get('local','')+'。请进入管理员更新页确认后执行。','update',now))
        con.commit(); con.close()
    except Exception:
        pass

def admin_update_banner(user):
    # Keep update checks inside the explicit admin update page only.
    return ''

def api_get(path, uid):
    sep='&' if '?' in path else '?'
    with urllib.request.urlopen(f'{DATA_BASE}{path}{sep}uid={uid}', timeout=25) as r: return json.loads(r.read().decode())

def api_post(path, payload):
    data=json.dumps(payload).encode(); req=urllib.request.Request(DATA_BASE+path,data=data,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req, timeout=25) as r: return json.loads(r.read().decode())

def fmt_price(v):
    try:
        x=float(v or 0)
        if abs(x-round(x))<1e-9: return f'{x:.0f}'
        return f'{x:.4f}'.rstrip('0').rstrip('.')
    except Exception:
        return esc(v)

USD_RMB_RATE=7.0

def usd_to_rmb(v):
    try: return float(v or 0) * USD_RMB_RATE
    except Exception: return 0.0

def rmb_to_usd(v):
    try: return float(v or 0) / USD_RMB_RATE
    except Exception: return 0.0

def fmt_rmb(v):
    try:
        return f'¥{fmt_price(float(v or 0))}'
    except Exception:
        return '¥'+esc(v)

def fmt_usd_as_rmb(v):
    return fmt_rmb(usd_to_rmb(v))

def fmt_usd_rmb(v):
    # Portal model_prices are stored as RMB/M Token for frontend display.
    return fmt_rmb(v)

def fmt_mtok(v):
    try:
        x=float(v or 0)/1000000
        if abs(x) < 0.000001: return '0 M'
        return f'{x:.6f}'.rstrip('0').rstrip('.') + ' M'
    except Exception:
        return esc(v or '0') + ' token'

def model_desc(m,note=''):
    mp={
        'gpt-5.5':'主力模型。适合复杂推理、代码分析、长文生成、正式报告和高稳定性生产任务。',
        'gpt-5.4':'均衡模型。适合日常问答、摘要、轻量代码、客服辅助和大多数标准文本任务。',
        'gpt-5.4-mini':'经济模型。适合批量分类、简单抽取、短文本改写、低成本测试和高频轻量请求。'
    }
    return mp.get(str(m), note or '通用模型。适合按需接入的文本处理、生成和自动化任务。')

def sync_model_prices():
    """Pull pricing from 后台服务 xapi-data and update portal DB. Best-effort, never breaks pages."""
    try:
        d=api_get('/pricing',0)
        items=d.get('pricing') or []
        if not items: return {'ok':False,'count':0,'source':'empty'}
        con=db(); now=int(time.time()); count=0
        con.execute('CREATE TABLE IF NOT EXISTS model_price_sync(id INTEGER PRIMARY KEY CHECK(id=1), source TEXT, unit TEXT, synced_at INTEGER, upstream_updated_at TEXT, status TEXT, error TEXT)')
        for it in items:
            m=str(it.get('model') or '').strip()
            if not m: continue
            note={'gpt-5.5':'主力模型','gpt-5.4':'均衡模型','gpt-5.4-mini':'经济模型'}.get(m, str(it.get('platform') or '模型'))
            con.execute('INSERT OR REPLACE INTO model_prices(model,input_price,output_price,cache_price,image_price,note) VALUES(?,?,?,?,?,?)',(
                m, float(it.get('input_price') or 0)*USD_RMB_RATE, float(it.get('output_price') or 0)*USD_RMB_RATE, float(it.get('cache_price') or 0)*USD_RMB_RATE, float(it.get('image_price') or 0)*USD_RMB_RATE, note))
            count+=1
        upstream=max([str(x.get('updated_at') or '') for x in items] or [''])
        con.execute('INSERT OR REPLACE INTO model_price_sync(id,source,unit,synced_at,upstream_updated_at,status,error) VALUES(1,?,?,?,?,?,?)',('backend','RMB per 1M tokens',now,upstream,'ok',''))
        con.commit(); con.close(); return {'ok':True,'count':count,'source':'backend'}
    except Exception as e:
        try:
            con=db(); con.execute('CREATE TABLE IF NOT EXISTS model_price_sync(id INTEGER PRIMARY KEY CHECK(id=1), source TEXT, unit TEXT, synced_at INTEGER, upstream_updated_at TEXT, status TEXT, error TEXT)')
            con.execute('INSERT OR REPLACE INTO model_price_sync(id,source,unit,synced_at,upstream_updated_at,status,error) VALUES(1,?,?,?,?,?,?)',('backend','RMB per 1M tokens',int(time.time()),'','failed',str(e)[:300])); con.commit(); con.close()
        except Exception: pass
        return {'ok':False,'error':str(e)}

def price_rows():
    sync_model_prices()
    con=db(); con.row_factory=sqlite3.Row
    rows=con.execute('SELECT model,input_price,output_price,cache_price,image_price,note FROM model_prices ORDER BY CASE model WHEN "gpt-5.5" THEN 1 WHEN "gpt-5.4" THEN 2 WHEN "gpt-5.4-mini" THEN 3 ELSE 99 END, model').fetchall()
    meta=con.execute('SELECT source,unit,synced_at,upstream_updated_at,status,error FROM model_price_sync WHERE id=1').fetchone()
    con.close(); return rows,meta

def log_mail(recipient, subject, typ, status, error=''):
    try:
        con=db(); con.execute('INSERT INTO mail_logs(recipient,subject,type,status,error,created_at) VALUES(?,?,?,?,?,?)',(recipient,subject,typ,status,error[:500],int(time.time()))); con.commit(); con.close()
    except Exception:
        pass

def send_mail(recipient, subject, body, typ='system'):
    if not (SMTP_HOST and SMTP_USER and SMTP_PASS):
        err='邮件服务暂不可用，请联系管理员'; log_mail(recipient,subject,typ,'failed',err); raise RuntimeError(err)
    msg=EmailMessage(); msg['Subject']=subject; msg['From']=SMTP_FROM; msg['To']=recipient
    msg.set_content(body)
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
            if SMTP_TLS:
                server.starttls()
            server.login(SMTP_USER, SMTP_PASS); server.send_message(msg)
        log_mail(recipient,subject,typ,'sent','')
    except Exception as e:
        log_mail(recipient,subject,typ,'failed',str(e)); raise

def safe_notify_mail(recipient, subject, body, typ='notice'):
    try:
        send_mail(recipient, subject, body, typ)
    except Exception:
        pass

def mail_body(title, lines):
    parts=[title,'']
    parts += [str(x) for x in lines if x is not None and str(x).strip()!='']
    return '\n'.join(parts)+MAIL_FOOTER

def send_verify_code(email, purpose='register'):
    code=f'{secrets.randbelow(1000000):06d}'
    key=(purpose+':'+email) if purpose!='register' else email
    VERIFY_CODES[key]=(code,time.time()+600)
    title='NW-API 注册验证码' if purpose=='register' else 'NW-API 重置密码验证码'
    text='注册' if purpose=='register' else '重置密码'
    body=mail_body(title,[f'验证码：{code}', '有效期：10 分钟。', f'用途：{text}账号。', '如非本人操作，请忽略本邮件并检查账号安全。'])
    send_mail(email, title, body, purpose)
    return code

def verify_email_code(email, code, purpose='register'):
    key=(purpose+':'+email) if purpose!='register' else email
    item=VERIFY_CODES.get(key)
    if not item: return False
    good, exp=item
    if time.time()>exp: return False
    ok=hmac.compare_digest(str(code).strip(), good)
    if ok: VERIFY_CODES.pop(key,None)
    return ok

def date_bar(start, end):
    return f'<div class="card"><form method="get" class="actions"><button class="btn btn2" name="preset" value="today">今日实时</button><input name="start" type="date" value="{esc(start)}"><input name="end" type="date" value="{esc(end)}"><button class="btn">查询</button></form></div>'

def clamp_int(v, default=1, low=1, high=500):
    try: n=int(v)
    except Exception: n=default
    return max(low,min(high,n))

def day_start(v):
    if not v: return None
    try: return int(time.mktime(time.strptime(v,'%Y-%m-%d')))
    except Exception: return None

def pager(base, qs, page, size, total, param='page'):
    pages=max(1,(int(total)+size-1)//size)
    def link(p,label,enabled=True):
        q={k:v[:] for k,v in qs.items() if k!=param}; q[param]=[str(p)]
        href=base+'?'+urllib.parse.urlencode({k:v[0] for k,v in q.items() if v and v[0] != ''})
        cls='btn btn2' if enabled else 'btn btn2 muted'
        return f'<a class="{cls}" href="{href}">{label}</a>' if enabled else f'<span class="{cls}">{label}</span>'
    return f'<div class="actions"><span class="muted">第 {page}/{pages} 页，共 {int(total)} 条</span>{link(max(1,page-1),"上一页",page>1)}{link(min(pages,page+1),"下一页",page<pages)}</div>'

def allowed_models(user_id):
    con=db(); rows=con.execute('SELECT model FROM user_models WHERE user_id=? AND enabled=1',(user_id,)).fetchall()
    if not rows:
        rows=con.execute('SELECT model FROM model_prices ORDER BY model').fetchall()
    out=[r[0] for r in rows]; con.close(); return out

def log_op(admin, action, target='', detail=''):
    con=db(); con.execute('INSERT INTO ops_log(admin_email,action,target,detail,created_at) VALUES(?,?,?,?,?)',(admin,action,target,detail,int(time.time()))); con.commit(); con.close()

def payment_methods(enabled_only=False):
    con=db()
    sql='SELECT id,name,kind,instructions,enabled,sort_order,updated_at FROM payment_methods'
    if enabled_only: sql+=' WHERE enabled=1'
    rows=con.execute(sql+' ORDER BY sort_order,id').fetchall(); con.close()
    return rows

def current(h):
    c=SimpleCookie(h.headers.get('Cookie','')); sid=c.get('sid')
    if not sid or sid.value not in SESS: return None
    rec=SESS.get(sid.value)
    if isinstance(rec, tuple) and len(rec)>=3: uid, exp, csrf = rec[0], rec[1], rec[2]
    elif isinstance(rec, tuple): uid, exp, csrf = rec[0], rec[1], secrets.token_urlsafe(24)
    else: uid, exp, csrf = rec, 0, secrets.token_urlsafe(24)
    if exp and time.time()>exp:
        SESS.pop(sid.value,None); return None
    con=db(); u=con.execute('SELECT * FROM users WHERE id=? AND status="active"',(uid,)).fetchone(); con.close()
    if not u: return None
    d=dict(u); d['sid']=sid.value; d['exp']=exp; d['csrf']=csrf; SESS[sid.value]=(uid,exp,csrf); return d

def csrf_field(u):
    return f'<input type="hidden" name="csrf" value="{esc(u.get("csrf", ""))}">' if u else ''

def sensitive_fields(u, label='操作备注'):
    return csrf_field(u)+'<input name="admin_password" type="password" placeholder="管理员密码" style="width:120px"><input name="admin_note" placeholder="'+label+'" style="width:160px" required>'

def require_sensitive(u,f):
    return u and u.get('role')=='admin' and f.get('csrf')==u.get('csrf') and check_pw(f.get('admin_password',''),u['pass_hash']) and bool(f.get('admin_note','').strip())

def release_version_menu(label):
    return f'<details class="release-menu"><summary><span class="version-pill">{label}</span></summary><div><a href="https://github.com/ahnerjack/nw-api-stack-public/releases/tag/V.0.005" target="_blank" rel="noopener">查看发布</a></div></details>'

def version_update_widget(user):
    label=f'{APP_VERSION}'
    version=release_version_menu(label)
    if not user or user.get('role')!='admin':
        return version
    st=update_state(False)
    if st.get('available'):
        ensure_admin_update_notice(st)
        return f'<span class="version-row">{version}<a class="update-badge" href="/admin-update" title="发现新版本">NEW</a></span>'
    return version

def shell(title, body, user, active='dashboard'):
    base_nav=[
        ('dashboard','/dashboard','概览'),
        ('keys','/keys','API Key'),
        ('docs','/docs','文档'),
    ]
    admin_nav=[]
    if user.get('role')=='admin':
        admin_nav=[
            ('users','/users-admin','用户管理'),
            ('admin_usage','/admin-usage','消耗统计'),
            ('risk','/risk','风控'),
        ]
    account_nav=[('profile','/profile','个人资料'),('logout','/logout','退出')]
    nav_items=base_nav+admin_nav+account_nav
    nav=''.join([f'<a class="{"on" if active==p else ""}" href="{u}">{t}</a>' for p,u,t in nav_items])
    heading='' if active=='dashboard' else f'<div><h1>{esc(title)}</h1><div class="muted">{esc(user["email"])}</div></div>'
    return f'<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{BRAND}</title>{CSS}</head><body><div class="layout"><aside class="side"><div class="logo"><a href="/dashboard" style="display:flex;gap:10px;align-items:center;color:inherit"><span class="mark"><svg class="nw-logo" viewBox="0 0 72 72" aria-hidden="true" shape-rendering="geometricPrecision"><defs><linearGradient id="portalBg" x1="8" y1="7" x2="64" y2="65" gradientUnits="userSpaceOnUse"><stop stop-color="#0F172A"/><stop offset="1" stop-color="#020617"/></linearGradient><linearGradient id="portalRing" x1="17" y1="15" x2="55" y2="57" gradientUnits="userSpaceOnUse"><stop stop-color="#67E8F9"/><stop offset="0.48" stop-color="#F8FAFC"/><stop offset="1" stop-color="#A78BFA"/></linearGradient></defs><rect x="6" y="6" width="60" height="60" rx="20" fill="url(#portalBg)"/><rect x="9" y="9" width="54" height="54" rx="18" fill="rgba(255,255,255,.035)" stroke="rgba(255,255,255,.12)" stroke-width="1.2"/><path d="M36 18C46.5 18 55 26.5 55 37C55 47.5 46.5 56 36 56C25.5 56 17 47.5 17 37C17 26.5 25.5 18 36 18Z" fill="none" stroke="url(#portalRing)" stroke-width="7" stroke-linecap="round"/><path d="M24 37C24 30.4 29.4 25 36 25C42.6 25 48 30.4 48 37" fill="none" stroke="#FFFFFF" stroke-width="4.5" stroke-linecap="round"/><circle cx="36" cy="37" r="5.5" fill="#020617" stroke="rgba(255,255,255,.86)" stroke-width="2.2"/><path d="M31 50L36 56L41 50" fill="none" stroke="#C4B5FD" stroke-width="3.8" stroke-linecap="round" stroke-linejoin="round"/></svg></span><span class="brand-copy"><span class="brand-name">{BRAND}</span></span></a>{version_update_widget(user)}</div><div class="nav">{nav}</div></aside><main class="main"><div class="top">{heading}<a class="btn btn2" href="/">返回首页</a></div>{admin_update_banner(user)}{body}</main></div></body></html>'

def public_page(title, body):
    nav='<a href="/pricing">价格</a><a href="/plans">套餐</a><a href="/risk">风控</a><a href="/docs">文档</a><a href="/privacy">隐私</a><a href="/terms">条款</a><a class="btn" href="/login">控制台</a>'
    css=CSS.replace(':root{--b:#2563eb;--v:#7c3aed;--ink:#0f172a;--m:#64748b;--line:#e2e8f0}', ':root{--b:#2563eb;--v:#475569;--ink:#0f172a;--m:#64748b;--line:#e2e8f0}')
    return f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{BRAND}</title>{css}</head><body><main class="main" style="margin:auto"><div class="top"><a class="logo" href="/home" style="color:#101828"><span class="mark"><svg class="nw-logo" viewBox="0 0 72 72" aria-hidden="true" shape-rendering="geometricPrecision"><defs><linearGradient id="portalBg" x1="8" y1="7" x2="64" y2="65" gradientUnits="userSpaceOnUse"><stop stop-color="#0F172A"/><stop offset="1" stop-color="#020617"/></linearGradient><linearGradient id="portalRing" x1="17" y1="15" x2="55" y2="57" gradientUnits="userSpaceOnUse"><stop stop-color="#67E8F9"/><stop offset="0.48" stop-color="#F8FAFC"/><stop offset="1" stop-color="#A78BFA"/></linearGradient></defs><rect x="6" y="6" width="60" height="60" rx="20" fill="url(#portalBg)"/><rect x="9" y="9" width="54" height="54" rx="18" fill="rgba(255,255,255,.035)" stroke="rgba(255,255,255,.12)" stroke-width="1.2"/><path d="M36 18C46.5 18 55 26.5 55 37C55 47.5 46.5 56 36 56C25.5 56 17 47.5 17 37C17 26.5 25.5 18 36 18Z" fill="none" stroke="url(#portalRing)" stroke-width="7" stroke-linecap="round"/><path d="M24 37C24 30.4 29.4 25 36 25C42.6 25 48 30.4 48 37" fill="none" stroke="#FFFFFF" stroke-width="4.5" stroke-linecap="round"/><circle cx="36" cy="37" r="5.5" fill="#020617" stroke="rgba(255,255,255,.86)" stroke-width="2.2"/><path d="M31 50L36 56L41 50" fill="none" stroke="#C4B5FD" stroke-width="3.8" stroke-linecap="round" stroke-linejoin="round"/></svg></span><span class="brand-copy"><span class="brand-name">{BRAND}</span><small class="muted">AI API Gateway</small></span></a>{release_version_menu(APP_VERSION)}<div class="actions">{nav}</div></div><h1>{esc(title)}</h1>{body}<footer class="muted" style="margin-top:34px">© 2026 NW-API · <a href="/privacy">隐私政策</a> · <a href="/terms">服务条款</a> · <a href="/docs">接入文档</a></footer></main></body></html>'

class H(BaseHTTPRequestHandler):
    def sendh(self, body, code=200):
        b=body.encode(); self.send_response(code); self.send_header('Content-Type','text/html; charset=utf-8'); self.send_header('Cache-Control','no-store, no-cache, must-revalidate, max-age=0'); self.send_header('Pragma','no-cache'); self.send_header('Expires','0'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)
    def redirect(self,u): self.send_response(302); self.send_header('Location',u); self.end_headers()
    def sendcsv(self,name,text):
        b=text.encode('utf-8-sig'); self.send_response(200); self.send_header('Content-Type','text/csv; charset=utf-8'); self.send_header('Content-Disposition',f'attachment; filename=\"{name}\"'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)
    def form(self):
        ln=int(self.headers.get('Content-Length','0')); return {k:v[0] for k,v in urllib.parse.parse_qs(self.rfile.read(ln).decode()).items()}
    def do_GET(self):
        path=urllib.parse.urlparse(self.path).path
        if path=='/health': return self.sendh('ok')
        if path=='/logout': self.send_response(302); self.send_header('Set-Cookie','sid=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax'); self.send_header('Location','/login'); self.end_headers(); return
        if path=='/login': return self.login()
        if path=='/register': return self.register()
        if path=='/forgot': return self.forgot()
        u=current(self)
        if path=='/plans' and not u: return self.public_plans()
        if path=='/risk' and not u: return self.public_risk()
        if path in ('/models','/models/') and not u: return self.public_models()
        if path in ('/pricing','/pricing/') and not u: return self.public_pricing()
        if path in ['/dashboard','/onboarding','/profile','/notifications','/keys','/keys/view','/usage','/billing','/docs','/users-admin','/admin-console','/admin-usage','/admin-update','/user-detail','/api-logs','/rollback','/mail-logs','/announcements','/healthz','/changelog','/export.csv'] and not u: return self.redirect('/login')
        try:
            if path=='/dashboard': return self.dashboard(u)
            if path=='/onboarding': return self.onboarding_page(u)
            if path=='/profile': return self.profile_page(u)
            if path=='/notifications': return self.notifications_page(u)
            if path=='/keys': return self.keys_page(u)
            if path=='/keys/view': return self.key_view_page(u)
            if path=='/usage': return self.usage_page(u)
            if path=='/billing': return self.redirect('/dashboard')
            if path=='/plans': return self.plans_page(u)
            if path in ('/models','/models/'): return self.models_page(u)
            if path in ('/pricing','/pricing/'): return self.pricing_page(u)
            if path=='/docs': return self.docs(u)
            if path=='/users-admin': return self.admin_users(u)
            if path=='/admin-console': return self.admin_console(u)
            if path=='/admin-usage': return self.admin_usage(u)
            if path=='/admin-update': return self.admin_update(u)
            if path=='/risk': return self.risk_page(u)
            if path=='/user-detail': return self.user_detail(u)
            if path=='/api-logs': return self.api_logs(u)
            if path=='/rollback': return self.rollback_page(u)
            if path=='/mail-logs': return self.mail_logs_page(u)
            if path=='/healthz': return self.healthz_page(u)
            if path=='/changelog': return self.changelog_page(u)
            if path=='/announcements': return self.announcements_page(u)
            if path=='/export.csv': return self.export_csv(u)
        except Exception as e: return self.sendh(shell('错误',f'<div class="card err">{esc(e)}</div>',u or {'email':'','id':'','sub2_user_id':'','role':'user'}),500)
        self.redirect('/dashboard')
    def do_POST(self):
        path=urllib.parse.urlparse(self.path).path; f=self.form()
        if path=='/login': return self.do_login(f)
        if path=='/register': return self.do_register(f)
        if path=='/send-code': return self.send_code(f)
        if path=='/forgot/send': return self.forgot_send(f)
        if path=='/forgot/reset': return self.forgot_reset(f)
        u=current(self)
        if not u: return self.redirect('/login')
        sensitive_paths={'/users-admin/update','/users-admin/delete','/users-admin/plan','/users-admin/models','/balance/change','/notifications/send'}
        if path in sensitive_paths and not require_sensitive(u,f): return self.sendh(shell('二次确认失败','<div class="card err">敏感操作需要有效 CSRF、管理员密码和操作备注。</div>',u),403)
        if path=='/profile/password':
            if f.get('csrf')!=u.get('csrf'): return self.sendh(shell('个人资料','<div class="card err">安全校验失败，请重新提交。</div>',u,'profile'),403)
            old=f.get('old_password',''); new=f.get('new_password',''); confirm=f.get('confirm_password','')
            if not check_pw(old,u['pass_hash']): return self.sendh(shell('个人资料','<div class="card err">当前密码不正确。</div><div class="card"><a class="btn btn2" href="/profile">返回个人资料</a></div>',u,'profile'),400)
            if len(new)<8 or new!=confirm: return self.sendh(shell('个人资料','<div class="card err">新密码至少 8 位，并且两次输入必须一致。</div><div class="card"><a class="btn btn2" href="/profile">返回个人资料</a></div>',u,'profile'),400)
            api_post('/users/password', {'uid':u['sub2_user_id'],'password':new})
            con=db(); con.execute('UPDATE users SET pass_hash=? WHERE id=?',(hash_pw(new),u['id'])); con.execute('INSERT INTO ops_log(admin_email,action,target,detail,created_at) VALUES(?,?,?,?,?)',(u['email'],'change_password',u['email'],'self-service',int(time.time()))); con.execute('INSERT INTO notifications(user_id,title,content,type,created_at) VALUES(?,?,?,?,?)',(u['id'],'账号密码已修改','您的登录密码已成功修改。如非本人操作，请立即联系支持。','security',int(time.time()))); con.commit(); con.close()
            return self.sendh(shell('个人资料','<div class="card"><h2>密码已更新</h2><p>下次登录请使用新密码。</p><a class="btn" href="/profile">返回个人资料</a></div>',u,'profile'))
        if path=='/notifications/read':
            nid=int(f.get('id') or 0); con=db(); con.execute('UPDATE notifications SET read_at=? WHERE id=? AND (user_id=? OR user_id IS NULL)',(int(time.time()),nid,u['id'])); con.commit(); con.close(); return self.redirect('/notifications')
        if path=='/notifications/read-all':
            con=db(); con.execute('UPDATE notifications SET read_at=? WHERE (user_id=? OR user_id IS NULL) AND read_at IS NULL',(int(time.time()),u['id'])); con.commit(); con.close(); return self.redirect('/notifications')
        if path=='/admin-update/apply':
            if u.get('role')!='admin':
                return self.sendh(shell('无权限','<div class="card err">只有管理员可以执行系统更新。</div>',u),403)
            if f.get('csrf')!=u.get('csrf'):
                return self.sendh(shell('安全校验失败','<div class="card err">请刷新页面后重试。</div>',u,'admin_update'),403)
            st=update_state(True)
            if not st.get('ok'):
                return self.sendh(shell('系统更新',f'<div class="card err">检查更新失败：{esc(st.get("error"))}</div>',u,'admin_update'),500)
            cmd='cd '+shlex.quote(REPO_DIR)+' && git pull --ff-only && ./scripts/deploy-aliyun.sh'
            log_cmd='{{ echo ==== $(date) admin={} local={} remote={}; {}; }} >> {} 2>&1'.format(shlex.quote(u['email']), shlex.quote(st.get('local','')), shlex.quote(st.get('remote','')), cmd, shlex.quote(UPDATE_LOG))
            subprocess.Popen(['bash','-lc', log_cmd], start_new_session=True)
            con=db(); con.execute('INSERT INTO ops_log(admin_email,action,target,detail,created_at) VALUES(?,?,?,?,?)',(u['email'],'apply_update','nw-api',json.dumps(st,ensure_ascii=False),int(time.time()))); con.commit(); con.close()
            return self.sendh(shell('系统更新','<div class="card"><h2>已开始更新</h2><p>系统会从 Git 拉取最新代码并重启服务，约 10-30 秒后刷新页面。</p><p class="muted">日志：/var/log/nw-api-update.log</p><a class="btn" href="/admin-update">刷新查看</a></div>',u,'admin_update'))
        if path=='/announcements/update' and u['role']=='admin':
            aid=int(f.get('id') or 0); title=f.get('title','')[:100]; content=f.get('content','')[:1000]; status=f.get('status','active'); pinned=1 if f.get('pinned')=='1' else 0
            if title and content:
                con=db()
                if aid: con.execute('UPDATE announcements SET title=?,content=?,status=?,pinned=? WHERE id=?',(title,content,status,pinned,aid))
                else: con.execute('INSERT INTO announcements(title,content,status,pinned,created_at) VALUES(?,?,?,?,?)',(title,content,status,pinned,int(time.time())))
                con.execute('INSERT INTO ops_log(admin_email,action,target,detail,created_at) VALUES(?,?,?,?,?)',(u['email'],'update_announcement',title,status,int(time.time())))
                con.commit(); con.close()
            return self.redirect('/announcements')
        if path=='/notifications/send' and u['role']=='admin':
            target=f.get('target','all'); title=f.get('title','')[:100]; content=f.get('content','')[:1000]
            if title and content:
                con=db()
                if target=='all':
                    con.execute('INSERT INTO notifications(user_id,title,content,type,created_at) VALUES(NULL,?,?,?,?)',(title,content,'broadcast',int(time.time())))
                else:
                    con.execute('INSERT INTO notifications(user_id,title,content,type,created_at) VALUES(?,?,?,?,?)',(int(target),title,content,'admin',int(time.time())))
                con.execute('INSERT INTO ops_log(admin_email,action,target,detail,created_at) VALUES(?,?,?,?,?)',(u['email'],'send_notification',str(target),title+' note:'+f.get('admin_note',''),int(time.time())))
                con.commit(); con.close()
            return self.redirect('/announcements')
        if path=='/risk/update' and u['role']=='admin':
            rid=int(f.get('id') or 0); kind=f.get('kind','ip').strip()[:20]; pattern=f.get('pattern','').strip()[:120]; action=f.get('action','block'); note=f.get('note','')[:200]; status=f.get('status','active')
            if pattern:
                con=db()
                if rid:
                    con.execute('UPDATE risk_rules SET kind=?,pattern=?,action=?,note=?,status=? WHERE id=?',(kind,pattern,action,note,status,rid))
                else:
                    con.execute('INSERT INTO risk_rules(kind,pattern,action,note,status,created_at) VALUES(?,?,?,?,?,?)',(kind,pattern,action,note,status,int(time.time())))
                con.execute('INSERT INTO ops_log(admin_email,action,target,detail,created_at) VALUES(?,?,?,?,?)',(u['email'],'update_risk',pattern,action,int(time.time())))
                con.commit(); con.close()
            return self.redirect('/risk')
        if path=='/users-admin/payment-method' and u['role']=='admin':
            pid=int(f.get('id') or 0); name=f.get('name','').strip()[:50]; kind=f.get('kind','manual').strip()[:20]
            instructions=f.get('instructions','').strip()[:1200]; enabled=1 if f.get('enabled')=='1' else 0
            try: sort_order=int(f.get('sort_order') or 100)
            except Exception: sort_order=100
            if name:
                con=db()
                if pid:
                    con.execute('UPDATE payment_methods SET name=?,kind=?,instructions=?,enabled=?,sort_order=?,updated_at=? WHERE id=?',(name,kind,instructions,enabled,sort_order,int(time.time()),pid))
                else:
                    con.execute('INSERT INTO payment_methods(name,kind,instructions,enabled,sort_order,updated_at) VALUES(?,?,?,?,?,?)',(name,kind,instructions,enabled,sort_order,int(time.time())))
                con.execute('INSERT INTO ops_log(admin_email,action,target,detail,created_at) VALUES(?,?,?,?,?)',(u['email'],'update_payment_method',name,'enabled='+str(enabled)+' note:'+f.get('admin_note',''),int(time.time())))
                con.commit(); con.close()
            return self.redirect('/users-admin')
        if path=='/orders/create':
            return self.redirect('/dashboard')
        if path=='/orders/review' and u['role']=='admin':
            return self.redirect('/users-admin')
        if path=='/plans/update' and u['role']=='admin':
            pid=int(f.get('id') or 0); name=f.get('name','').strip()[:50]
            if name:
                con=db()
                if pid:
                    con.execute('UPDATE plans SET name=?,price=?,monthly_quota=?,daily_limit=?,models=?,note=?,status=? WHERE id=?',(name,float(f.get('price') or 0),float(f.get('monthly_quota') or 0),float(f.get('daily_limit') or 0),f.get('models','')[:300],f.get('note','')[:200],f.get('status','active'),pid))
                else:
                    con.execute('INSERT INTO plans(name,price,monthly_quota,daily_limit,models,note,status) VALUES(?,?,?,?,?,?,?)',(name,float(f.get('price') or 0),float(f.get('monthly_quota') or 0),float(f.get('daily_limit') or 0),f.get('models','')[:300],f.get('note','')[:200],f.get('status','active')))
                con.commit(); con.close(); log_op(u['email'],'update_plan',name,'')
            return self.redirect('/plans')
        if path=='/users-admin/plan' and u['role']=='admin':
            target=int(f.get('id') or 0); plan_id=int(f.get('plan_id') or 0)
            con=db(); tu=con.execute('SELECT * FROM users WHERE id=? AND status!="deleted"',(target,)).fetchone(); pl=con.execute('SELECT * FROM plans WHERE id=?',(plan_id,)).fetchone()
            if tu and pl:
                now=int(time.time()); con.execute('INSERT OR REPLACE INTO user_plans(user_id,plan_id,started_at,expires_at) VALUES(?,?,?,NULL)',(target,plan_id,now))
                con.execute('DELETE FROM user_models WHERE user_id=?',(target,))
                for m in [x.strip() for x in (pl['models'] or '').split(',') if x.strip()]: con.execute('INSERT OR REPLACE INTO user_models(user_id,model,enabled) VALUES(?,?,1)',(target,m))
                api_post('/users/update', {'uid':tu['sub2_user_id'],'balance':'0','daily_limit':'0','weekly_limit':'0','monthly_limit':'0','concurrency':'5','status':'active'})
                con.execute('INSERT INTO ops_log(admin_email,action,target,detail,created_at) VALUES(?,?,?,?,?)',(u['email'],'assign_plan',tu['email'],pl['name'],int(time.time())))
                con.commit()
            con.close(); return self.redirect('/users-admin')
        if path=='/pricing/update' and u['role']=='admin':
            model=(f.get('model') or '').strip()
            if model:
                con=db(); con.execute('INSERT OR REPLACE INTO model_prices(model,input_price,output_price,cache_price,image_price,note) VALUES(?,?,?,?,?,?)',(model,float(f.get('input_price') or 0),float(f.get('output_price') or 0),float(f.get('cache_price') or 0),float(f.get('image_price') or 0),f.get('note','')[:200])); con.commit(); con.close()
                log_op(u['email'],'update_price',model,json.dumps({k:f.get(k,'') for k in ['input_price','output_price','cache_price','image_price','note']},ensure_ascii=False))
            return self.redirect('/pricing')
        if path=='/users-admin/models' and u['role']=='admin':
            target=int(f.get('id') or 0); models=f.get('models','').split(',') if f.get('models') else []
            con=db(); tu=con.execute('SELECT * FROM users WHERE id=? AND status!="deleted"',(target,)).fetchone()
            if tu:
                con.execute('DELETE FROM user_models WHERE user_id=?',(target,))
                for m in [x.strip() for x in models if x.strip()]: con.execute('INSERT OR REPLACE INTO user_models(user_id,model,enabled) VALUES(?,?,1)',(target,m))
                con.commit(); log_op(u['email'],'update_models',tu['email'],','.join(models))
            con.close(); return self.redirect('/users-admin')
        if path=='/keys/update':
            api_post('/keys/update', {'uid':u['sub2_user_id'],'id':f.get('id'),'quota':'0','status':f.get('status','active')})
            con=db(); con.execute('INSERT INTO notifications(user_id,title,content,type,created_at) VALUES(?,?,?,?,?)',(u['id'],'API Key 已更新','您的 API Key #'+str(f.get('id'))+' 状态/额度已更新。','key',int(time.time()))); con.commit(); con.close()
            safe_notify_mail(u['email'],'NW-API API Key 已更新',mail_body('API Key 状态变更',['Key 编号：#'+str(f.get('id')),'状态或额度已更新。','如非本人操作，请立即登录控制台禁用相关 Key 并修改密码。']),'key')
            return self.redirect('/keys')
        if path=='/keys/rotate':
            new_key=(f.get('new_key') or '').strip()
            payload={'uid':u['sub2_user_id'],'id':f.get('id')}
            if new_key: payload['key']=new_key
            res=api_post('/keys/rotate', payload)
            key=res.get('key','')
            con=db(); con.execute('INSERT INTO notifications(user_id,title,content,type,created_at) VALUES(?,?,?,?,?)',(u['id'],'API Key 已更新','您的 API Key #'+str(f.get('id'))+' 已重新生成或替换。','key',int(time.time()))); con.commit(); con.close()
            safe_notify_mail(u['email'],'NW-API API Key 已更新',mail_body('API Key 已更新',['Key 编号：#'+str(f.get('id')),'旧 Key 已失效，请立即替换为新 Key。','如非本人操作，请立即登录控制台修改密码并禁用相关 Key。']),'key')
            return self.sendh(shell('API Key 已更新',f'<div class="card"><p>请立即复制保存，新 Key 只在这里显示一次：</p><pre id="full-key">{esc(key)}</pre><div class="actions"><button class="btn" type="button" onclick="navigator.clipboard.writeText(document.getElementById(\'full-key\').innerText).then(()=>this.innerText=\'已复制\')">复制完整 Key</button><a class="btn btn2" href="/keys">返回 API Key</a></div><p class="muted">列表页会继续显示为 {esc(mask_key(key))}</p></div>',u,'keys'))
        if path=='/users-admin/update' and u['role']=='admin':
            target=int(f.get('id') or 0)
            con=db(); tu=con.execute('SELECT * FROM users WHERE id=? AND status!="deleted"',(target,)).fetchone(); con.close()
            if tu:
                payload={'uid':tu['sub2_user_id'],'balance':rmb_to_usd(f.get('balance','0')),'daily_limit':'0','weekly_limit':'0','monthly_limit':'0','concurrency':f.get('concurrency','5'),'status':f.get('status','active')}
                api_post('/users/update', payload)
                log_op(u['email'],'update_user',tu['email'],json.dumps(payload,ensure_ascii=False))
            return self.redirect('/users-admin')
        if path=='/users-admin/logs' and u['role']=='admin':
            return self.redirect('/users-admin')
        if path=='/users-admin/delete' and u['role']=='admin':
            target=int(f.get('id') or 0)
            if target==u['id']:
                return self.redirect('/users-admin')
            con=db(); tu=con.execute('SELECT * FROM users WHERE id=? AND status!="deleted"',(target,)).fetchone()
            if tu:
                try:
                    res=api_post('/users/delete', {'uid':tu['sub2_user_id']})
                    if not res.get('ok'):
                        raise RuntimeError(json.dumps(res,ensure_ascii=False))
                    con.execute('INSERT INTO rollback_logs(admin_email,action,target,snapshot,created_at) VALUES(?,?,?,?,?)',(u['email'],'delete_user',tu['email'],json.dumps(dict(tu),ensure_ascii=False),int(time.time())))
                    con.execute('INSERT INTO ops_log(admin_email,action,target,detail,created_at) VALUES(?,?,?,?,?)',(u['email'],'delete_user',tu['email'],json.dumps({'sub2_user_id':tu['sub2_user_id'],'upstream':'deleted'},ensure_ascii=False),int(time.time())))
                    con.execute('UPDATE users SET status="deleted", email=email||".deleted."||id WHERE id=?',(target,)); con.commit()
                except Exception as e:
                    con.execute('INSERT INTO ops_log(admin_email,action,target,detail,created_at) VALUES(?,?,?,?,?)',(u['email'],'delete_user_failed',tu['email'],str(e),int(time.time())))
                    con.commit(); con.close()
                    return self.sendh(shell('删除失败',f'<div class="card err">上游账号删除失败，前端账号未删除：{esc(e)}</div><div class="card"><a class="btn" href="/users-admin">返回用户管理</a></div>',u,'admin'),500)
            con.close()
            return self.redirect('/users-admin')
        if path=='/keys/create':
            res=api_post('/keys', {'uid':u['sub2_user_id'],'name':f.get('name','NW-API Key')})
            key=res.get('key','')
            return self.sendh(shell('新 API Key',f'<div class="card"><p>请立即复制保存，只显示这一次：</p><pre id="full-key">{esc(key)}</pre><div class="actions"><button class="btn" type="button" onclick="navigator.clipboard.writeText(document.getElementById(\'full-key\').innerText).then(()=>this.innerText=\'已复制\')">复制完整 Key</button><a class="btn btn2" href="/keys">返回</a></div></div>',u,'keys'))
        if path=='/keys/disable':
            api_post('/keys/disable', {'uid':u['sub2_user_id'],'id':f.get('id')})
            con=db(); con.execute('INSERT INTO notifications(user_id,title,content,type,created_at) VALUES(?,?,?,?,?)',(u['id'],'API Key 已禁用','您的 API Key #'+str(f.get('id'))+' 已禁用。','key',int(time.time()))); con.commit(); con.close()
            safe_notify_mail(u['email'],'NW-API API Key 已禁用',mail_body('API Key 状态变更',['Key 编号：#'+str(f.get('id')),'该 Key 已禁用，不再接受调用。']),'key')
            return self.redirect('/keys')
        if path=='/keys/delete':
            api_post('/keys/delete', {'uid':u['sub2_user_id'],'id':f.get('id')})
            con=db(); con.execute('INSERT INTO notifications(user_id,title,content,type,created_at) VALUES(?,?,?,?,?)',(u['id'],'API Key 已删除','您的 API Key #'+str(f.get('id'))+' 已删除。','key',int(time.time()))); con.commit(); con.close()
            safe_notify_mail(u['email'],'NW-API API Key 已删除',mail_body('API Key 状态变更',['Key 编号：#'+str(f.get('id')),'该 Key 已删除，请使用新的有效 Key 接入。']),'key')
            return self.redirect('/keys')
        self.redirect('/dashboard')
    def login(self,err=''):
        self.sendh(f'<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{BRAND}</title>{CSS}</head><body><div class="login"><form class="box" method="post"><div class="logo" style="color:#101828"><span class="mark"><svg class="nw-logo" viewBox="0 0 72 72" aria-hidden="true" shape-rendering="geometricPrecision"><defs><linearGradient id="portalBg" x1="8" y1="7" x2="64" y2="65" gradientUnits="userSpaceOnUse"><stop stop-color="#0F172A"/><stop offset="1" stop-color="#020617"/></linearGradient><linearGradient id="portalRing" x1="17" y1="15" x2="55" y2="57" gradientUnits="userSpaceOnUse"><stop stop-color="#67E8F9"/><stop offset="0.48" stop-color="#F8FAFC"/><stop offset="1" stop-color="#A78BFA"/></linearGradient></defs><rect x="6" y="6" width="60" height="60" rx="20" fill="url(#portalBg)"/><rect x="9" y="9" width="54" height="54" rx="18" fill="rgba(255,255,255,.035)" stroke="rgba(255,255,255,.12)" stroke-width="1.2"/><path d="M36 18C46.5 18 55 26.5 55 37C55 47.5 46.5 56 36 56C25.5 56 17 47.5 17 37C17 26.5 25.5 18 36 18Z" fill="none" stroke="url(#portalRing)" stroke-width="7" stroke-linecap="round"/><path d="M24 37C24 30.4 29.4 25 36 25C42.6 25 48 30.4 48 37" fill="none" stroke="#FFFFFF" stroke-width="4.5" stroke-linecap="round"/><circle cx="36" cy="37" r="5.5" fill="#020617" stroke="rgba(255,255,255,.86)" stroke-width="2.2"/><path d="M31 50L36 56L41 50" fill="none" stroke="#C4B5FD" stroke-width="3.8" stroke-linecap="round" stroke-linejoin="round"/></svg></span><span class="brand-copy"><span class="brand-name">{BRAND}</span></span></div><h1>登录控制台</h1><p class="err">{esc(err)}</p><input name="email" placeholder="邮箱" autofocus><input name="password" type="password" placeholder="密码"><button class="btn">登录</button><p class="muted">没有账号？<a href="/register">注册</a> · <a href="/forgot">忘记密码</a></p></form></div></body></html>')
    def register(self,err=''):
        self.sendh(f'<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{BRAND}</title>{CSS}</head><body><div class="login"><form class="box" method="post"><div class="logo" style="color:#101828"><span class="mark"><svg class="nw-logo" viewBox="0 0 72 72" aria-hidden="true" shape-rendering="geometricPrecision"><defs><linearGradient id="portalBg" x1="8" y1="7" x2="64" y2="65" gradientUnits="userSpaceOnUse"><stop stop-color="#0F172A"/><stop offset="1" stop-color="#020617"/></linearGradient><linearGradient id="portalRing" x1="17" y1="15" x2="55" y2="57" gradientUnits="userSpaceOnUse"><stop stop-color="#67E8F9"/><stop offset="0.48" stop-color="#F8FAFC"/><stop offset="1" stop-color="#A78BFA"/></linearGradient></defs><rect x="6" y="6" width="60" height="60" rx="20" fill="url(#portalBg)"/><rect x="9" y="9" width="54" height="54" rx="18" fill="rgba(255,255,255,.035)" stroke="rgba(255,255,255,.12)" stroke-width="1.2"/><path d="M36 18C46.5 18 55 26.5 55 37C55 47.5 46.5 56 36 56C25.5 56 17 47.5 17 37C17 26.5 25.5 18 36 18Z" fill="none" stroke="url(#portalRing)" stroke-width="7" stroke-linecap="round"/><path d="M24 37C24 30.4 29.4 25 36 25C42.6 25 48 30.4 48 37" fill="none" stroke="#FFFFFF" stroke-width="4.5" stroke-linecap="round"/><circle cx="36" cy="37" r="5.5" fill="#020617" stroke="rgba(255,255,255,.86)" stroke-width="2.2"/><path d="M31 50L36 56L41 50" fill="none" stroke="#C4B5FD" stroke-width="3.8" stroke-linecap="round" stroke-linejoin="round"/></svg></span><span class="brand-copy"><span class="brand-name">{BRAND}</span></span></div><h1>注册账号</h1><p class="err">{esc(err)}</p><input name="email" placeholder="邮箱"><button class="btn btn2" formaction="/send-code" formmethod="post">发送邮箱验证码</button><input name="code" placeholder="邮箱验证码"><input name="password" type="password" placeholder="登录密码，至少 8 位"><input name="username" placeholder="昵称，可选"><button class="btn">注册普通会员账号</button><p class="muted">已有账号？<a href="/login">登录</a></p></form></div></body></html>')
    def forgot(self,err=''):
        self.sendh(f'<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{BRAND}</title>{CSS}</head><body><div class="login"><form class="box" method="post"><div class="logo" style="color:#101828"><span class="mark"><svg class="nw-logo" viewBox="0 0 72 72" aria-hidden="true" shape-rendering="geometricPrecision"><defs><linearGradient id="portalBg" x1="8" y1="7" x2="64" y2="65" gradientUnits="userSpaceOnUse"><stop stop-color="#0F172A"/><stop offset="1" stop-color="#020617"/></linearGradient><linearGradient id="portalRing" x1="17" y1="15" x2="55" y2="57" gradientUnits="userSpaceOnUse"><stop stop-color="#67E8F9"/><stop offset="0.48" stop-color="#F8FAFC"/><stop offset="1" stop-color="#A78BFA"/></linearGradient></defs><rect x="6" y="6" width="60" height="60" rx="20" fill="url(#portalBg)"/><rect x="9" y="9" width="54" height="54" rx="18" fill="rgba(255,255,255,.035)" stroke="rgba(255,255,255,.12)" stroke-width="1.2"/><path d="M36 18C46.5 18 55 26.5 55 37C55 47.5 46.5 56 36 56C25.5 56 17 47.5 17 37C17 26.5 25.5 18 36 18Z" fill="none" stroke="url(#portalRing)" stroke-width="7" stroke-linecap="round"/><path d="M24 37C24 30.4 29.4 25 36 25C42.6 25 48 30.4 48 37" fill="none" stroke="#FFFFFF" stroke-width="4.5" stroke-linecap="round"/><circle cx="36" cy="37" r="5.5" fill="#020617" stroke="rgba(255,255,255,.86)" stroke-width="2.2"/><path d="M31 50L36 56L41 50" fill="none" stroke="#C4B5FD" stroke-width="3.8" stroke-linecap="round" stroke-linejoin="round"/></svg></span><span class="brand-copy"><span class="brand-name">{BRAND}</span></span></div><h1>重置密码</h1><p class="err">{esc(err)}</p><input name="email" placeholder="注册邮箱"><button class="btn btn2" formaction="/forgot/send" formmethod="post">发送重置验证码</button><input name="code" placeholder="邮箱验证码"><input name="password" type="password" placeholder="新密码，至少 8 位"><button class="btn" formaction="/forgot/reset" formmethod="post">确认重置</button><p class="muted"><a href="/login">返回登录</a></p></form></div></body></html>')
    def forgot_send(self,f):
        email=f.get('email','').strip().lower()
        if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email): return self.forgot('邮箱格式不正确')
        con=db(); u=con.execute('SELECT id FROM users WHERE email=? AND status="active"',(email,)).fetchone(); con.close()
        if not u: return self.forgot('如果邮箱存在，验证码会发送到该邮箱')
        try:
            send_verify_code(email,'reset')
            return self.forgot('重置验证码已发送，请查收')
        except Exception as e:
            return self.forgot('验证码发送失败：'+str(e))
    def forgot_reset(self,f):
        email=f.get('email','').strip().lower(); pw=f.get('password','')
        if len(pw)<8: return self.forgot('密码至少 8 位')
        if not verify_email_code(email, f.get('code',''), 'reset'): return self.forgot('邮箱验证码错误或已过期')
        con=db(); u=con.execute('SELECT id FROM users WHERE email=? AND status="active"',(email,)).fetchone()
        if u:
            api_post('/users/password', {'uid':con.execute('SELECT sub2_user_id FROM users WHERE id=?',(u['id'],)).fetchone()[0],'password':pw})
            con.execute('UPDATE users SET pass_hash=? WHERE id=?',(hash_pw(pw),u['id'])); con.execute('INSERT INTO ops_log(admin_email,action,target,detail,created_at) VALUES(?,?,?,?,?)',(email,'reset_password',email,'self-service',int(time.time()))); con.commit()
        con.close(); return self.login('密码已重置，请用新密码登录')
    def do_login(self,f):
        email=f.get('email','').strip().lower(); pw=f.get('password',''); now=time.time(); rec=LOGIN_FAILS.get(email,[]); rec=[x for x in rec if now-x<900]; LOGIN_FAILS[email]=rec
        if len(rec)>=5: return self.login('登录失败次数过多，请 15 分钟后再试')
        con=db(); u=con.execute('SELECT * FROM users WHERE email=? AND status="active"',(email,)).fetchone(); con.close()
        if u and not check_pw(pw,u['pass_hash']):
            try:
                au=api_post('/users/auth', {'email':email,'password':pw})
                if au.get('ok') and int(au.get('sub2_user_id'))==int(u['sub2_user_id']):
                    con=db(); con.execute('UPDATE users SET pass_hash=? WHERE id=?',(hash_pw(pw),u['id'])); con.commit(); con.close()
                    u=dict(u); u['pass_hash']=hash_pw(pw)
            except Exception:
                pass
        if not u:
            try:
                au=api_post('/users/auth', {'email':email,'password':pw})
                if au.get('ok'):
                    sub=int(au['sub2_user_id'])
                    con=db(); con.execute('INSERT INTO users(email,pass_hash,role,sub2_user_id,created_at,status) VALUES(?,?,?,?,?,?)',(email,hash_pw(pw),'user',sub,int(time.time()),'active')); con.commit(); u=con.execute('SELECT * FROM users WHERE email=? AND status="active"',(email,)).fetchone(); con.close()
            except Exception:
                u=None
        if not u or not check_pw(pw,u['pass_hash']):
            LOGIN_FAILS[email]=rec+[now]
            return self.login('邮箱或密码错误')
        LOGIN_FAILS.pop(email,None)
        sid=secrets.token_urlsafe(24); SESS[sid]=(u['id'],int(now+SESSION_TTL),secrets.token_urlsafe(24)); self.send_response(302); self.send_header('Set-Cookie',f'sid={sid}; Path=/; Max-Age={SESSION_TTL}; HttpOnly; SameSite=Lax'); self.send_header('Location','/dashboard'); self.end_headers()
    def send_code(self,f):
        email=f.get('email','').strip().lower()
        if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email): return self.register('邮箱格式不正确')
        try:
            send_verify_code(email)
            return self.register('验证码已发送到邮箱，请查收后完成注册')
        except Exception as e:
            return self.register('验证码发送失败：'+str(e))

    def do_register(self,f):
        email=f.get('email','').strip().lower(); pw=f.get('password',''); username=f.get('username','').strip()
        if len(pw)<8: return self.register('密码至少 8 位')
        if not verify_email_code(email, f.get('code','')): return self.register('邮箱验证码错误或已过期')
        if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email): return self.register('邮箱格式不正确')
        sub=None
        con=db()
        try:
            if con.execute('SELECT id FROM users WHERE email=? AND status!="deleted"',(email,)).fetchone():
                con.close(); return self.register('该邮箱已注册')
            res=api_post('/users', {'email':email,'username':username,'password':pw})
            sub=int(res['sub2_user_id'])
            try:
                api_post('/users/update', {'uid':sub,'balance':'0','status':'active'})
            except Exception:
                try: api_post('/users/delete', {'uid':sub})
                except Exception: pass
                raise
            con.execute('INSERT INTO users(email,pass_hash,role,sub2_user_id,created_at,status) VALUES(?,?,?,?,?,?)',(email,hash_pw(pw),'user',sub,int(time.time()),'active'))
            con.commit(); uid=con.execute('SELECT id FROM users WHERE email=?',(email,)).fetchone()[0]; con.close()
            sid=secrets.token_urlsafe(24); SESS[sid]=(uid,int(time.time()+SESSION_TTL),secrets.token_urlsafe(24)); self.send_response(302); self.send_header('Set-Cookie',f'sid={sid}; Path=/; HttpOnly; SameSite=Lax'); self.send_header('Location','/dashboard'); self.end_headers()
        except sqlite3.IntegrityError:
            try:
                con.rollback(); con.close()
            except Exception: pass
            if sub and sub>1:
                try: api_post('/users/delete', {'uid':sub})
                except Exception: pass
            return self.register('该邮箱已注册')
        except Exception as e:
            try:
                con.rollback(); con.close()
            except Exception: pass
            if sub and sub>1:
                try: api_post('/users/delete', {'uid':sub})
                except Exception: pass
            return self.register(str(e))
    def dashboard(self,u):
        d=api_get('/summary',u['sub2_user_id']); su=d.get('user') or ['','','','','','0','0']; st=d.get('stats') or ['0','0','0','0','0']
        today=time.strftime('%Y-%m-%d')
        td=api_get('/stats?start='+today+'&end='+today, u['sub2_user_id'])
        tt=td.get('total') or ['0','0','0','0','0','0','0','0']
        recent=api_get('/usage',u['sub2_user_id']).get('usage',[])[:8]
        keys=api_get('/keys',u['sub2_user_id']).get('keys',[])
        def money(v):
            try:
                x=usd_to_rmb(v)
                if abs(x) < 0.000001: return '¥0'
                if abs(x) < 0.01: return '¥' + f'{x:.8f}'.rstrip('0').rstrip('.')
                return '¥' + f'{x:,.2f}'.rstrip('0').rstrip('.')
            except Exception:
                return '¥' + esc(v or '0')
        def num(v):
            try: return f'{int(float(v or 0)):,}'
            except Exception: return esc(v or '0')
        req=num(st[0]); input_tok=int(float(st[1] or 0)); output_tok=int(float(st[2] or 0)); cache_tok=int(float(st[3] or 0)); total=input_tok+output_tok+cache_tok
        t_input=int(float(tt[5] or 0)); t_output=int(float(tt[6] or 0)); t_cache=int(float(tt[7] or 0)); t_total=int(float(tt[3] or 0))
        bal=float(su[5] or 0); spend=float(st[4] or 0); today_spend=float(tt[0] or 0)
        active_keys=sum(1 for k in keys if str(k[2])=='active'); key_count=len(keys)
        con=db()
        try:
            if bal<1 and not con.execute('SELECT 1 FROM notifications WHERE user_id=? AND type="balance" AND read_at IS NULL AND created_at>?',(u['id'],int(time.time())-86400)).fetchone():
                con.execute('INSERT INTO notifications(user_id,title,content,type,created_at) VALUES(?,?,?,?,?)',(u['id'],'余额不足提醒','当前余额低于 1，请联系管理员处理额度，以免影响调用。','balance',int(time.time()))); con.commit()
                if not con.execute('SELECT 1 FROM mail_logs WHERE recipient=? AND type="balance_low" AND status="sent" AND created_at>?',(u['email'],int(time.time())-86400)).fetchone():
                    safe_notify_mail(u['email'],'NW-API 余额不足提醒','当前余额低于 1，请联系管理员处理额度，以免影响调用。','balance_low')
        except Exception:
            pass
        anns=con.execute('SELECT title,content,created_at FROM announcements WHERE status="active" ORDER BY pinned DESC,id DESC LIMIT 3').fetchall(); unread=con.execute('SELECT count(*) FROM notifications WHERE (user_id=? OR user_id IS NULL) AND read_at IS NULL',(u['id'],)).fetchone()[0]; con.close()
        status_cls='ok' if bal>=10 else ('warn' if bal>=1 else 'bad')
        status_txt='余额充足' if bal>=10 else ('余额偏低' if bal>=1 else '余额不足')
        ann_html=''.join([f'<div class="notice"><div><b>{esc(a[0])}</b><p>{esc(a[1])}</p></div><span>{time.strftime("%m-%d %H:%M",time.localtime(a[2]))}</span></div>' for a in anns]) or '<div class="muted">暂无公告</div>'
        key_rows=[]
        for k in keys[:5]:
            status='启用' if str(k[2])=='active' else '停用'
            quota=fmt_usd_as_rmb(k[4] or 0); used=fmt_usd_as_rmb(k[5] or 0)
            key_rows.append(f'<tr><td>{esc(brand_text(k[1]) or "未命名 Key")}</td><td>{status}</td><td>{quota}</td><td>{used}</td><td>{esc(k[6] or "从未使用")}</td></tr>')
        key_table=''.join(key_rows) or '<tr><td colspan="5" class="muted">还没有 API Key</td></tr>'
        recent_rows=[]
        for r in recent:
            try: toks=int(r[2])+int(r[3])+int(r[4])
            except Exception: toks=0
            recent_rows.append(f'<tr><td>{esc(r[0])}</td><td>{esc(r[1])}</td><td>{fmt_mtok(toks)}</td><td>{money(r[5])}</td></tr>')
        recent_table=''.join(recent_rows) or '<tr><td colspan="4" class="muted">暂无调用记录</td></tr>'
        body=f'''<style>
        .dash-hero{{border-radius:24px;padding:24px;background:linear-gradient(135deg,#0f172a,#1e3a8a 52%,#2563eb);color:white;box-shadow:0 20px 50px rgba(15,23,42,.18)}}
        .dash-hero h2{{margin:0 0 8px;font-size:28px;letter-spacing:-.03em;color:white}} .dash-hero p{{margin:0;color:rgba(255,255,255,.78)}}
        .dash-actions{{display:flex;gap:10px;flex-wrap:wrap;margin-top:18px}} .dash-actions a{{border:1px solid rgba(255,255,255,.28);background:rgba(255,255,255,.14);color:white;padding:9px 13px;border-radius:12px;text-decoration:none;font-weight:700}}
        .metric-grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin-top:16px}} @media(max-width:980px){{.metric-grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}}} @media(max-width:560px){{.metric-grid{{grid-template-columns:1fr}}}}
        .metric{{background:white;border:1px solid #e5e7eb;border-radius:18px;padding:16px;box-shadow:0 10px 28px rgba(15,23,42,.06)}} .metric .label{{font-size:12px;color:#64748b;margin-bottom:8px}} .metric .value{{font-size:24px;line-height:1.1;font-weight:800;letter-spacing:-.02em;color:#0f172a;font-variant-numeric:tabular-nums}} .metric .sub{{font-size:12px;color:#94a3b8;margin-top:8px}}
        .status-pill{{display:inline-flex;align-items:center;gap:6px;border-radius:999px;padding:6px 10px;font-size:12px;font-weight:800}} .status-pill.ok{{background:#dcfce7;color:#166534}} .status-pill.warn{{background:#fef9c3;color:#854d0e}} .status-pill.bad{{background:#fee2e2;color:#991b1b}}
        .dash-two{{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:14px}} .dash-wide{{grid-column:1/-1}} @media(max-width:900px){{.dash-two{{grid-template-columns:1fr}}}}
        .endpoint{{background:#0b1220;color:#dbeafe;border-radius:16px;padding:14px;overflow:auto;font-size:13px}} .notice{{display:flex;justify-content:space-between;gap:14px;padding:12px 0;border-bottom:1px solid #edf2f7}} .notice:last-child{{border-bottom:0}} .notice p{{margin:4px 0 0;color:#64748b}} .notice span{{white-space:nowrap;color:#94a3b8;font-size:12px}}
        .mini-bars{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:10px}} .mini-bars div{{border:1px solid #e5e7eb;border-radius:14px;padding:10px;background:#f8fafc}} .mini-bars b{{display:block;font-size:18px;color:#0f172a}}
        </style>
        <section class="dash-hero"><div class="actions" style="justify-content:space-between;align-items:flex-start"><div><h2>控制台</h2><p>余额、今日用量、最近调用和 Key 状态集中在这一页。</p></div><span class="status-pill {status_cls}">{status_txt}</span></div><div class="dash-actions"><a href="/keys">管理 API Key</a><a href="/usage?preset=today">完整用量</a><a href="/models">模型价格</a><a href="/notifications">通知 {unread}</a></div></section>
        <section class="metric-grid"><div class="metric"><div class="label">当前余额</div><div class="value">{money(bal)}</div><div class="sub">低于 ¥1 会提醒</div></div><div class="metric"><div class="label">今日消费</div><div class="value">{money(today_spend)}</div><div class="sub">今日请求 {num(tt[1])} 次</div></div><div class="metric"><div class="label">累计消费</div><div class="value">{money(spend)}</div><div class="sub">历史请求 {req} 次</div></div><div class="metric"><div class="label">API Key</div><div class="value">{active_keys}/{key_count}</div><div class="sub">启用 / 全部</div></div></section>
        <section class="dash-two"><div class="card"><h2>今日用量</h2><div class="metric"><div class="label">今日 Token</div><div class="value">{fmt_mtok(t_total)}</div><div class="sub">按真实调用统计，共 {t_total:,} token</div></div><div class="mini-bars"><div><span class="muted">输入</span><b>{fmt_mtok(t_input)}</b></div><div><span class="muted">输出</span><b>{fmt_mtok(t_output)}</b></div><div><span class="muted">缓存</span><b>{fmt_mtok(t_cache)}</b></div></div><div class="actions" style="margin-top:12px"><a class="btn btn2" href="/usage?preset=today">查看明细</a></div></div><div class="card"><h2>接口地址</h2><div class="endpoint">{BASE_URL}</div><p class="muted">请求失败先检查 Key 状态、余额、模型权限和额度。</p><div class="actions"><a class="btn" href="/keys">创建 Key</a><a class="btn btn2" href="/docs">接入文档</a></div></div><div class="card dash-wide"><h2>最近调用</h2><table><tr><th>时间</th><th>模型</th><th>M Token</th><th>消费</th></tr>{recent_table}</table></div><div class="card"><h2>Key 状态</h2><table><tr><th>名称</th><th>状态</th><th>额度</th><th>已用</th><th>最后使用</th></tr>{key_table}</table></div><div class="card"><h2>公告与通知</h2>{ann_html}</div></section>'''
        self.sendh(shell('概览',body,u,'dashboard'))
    def keys_page(self,u):
        ks=api_get('/keys',u['sub2_user_id']).get('keys',[])
        def fmt(v):
            try: return fmt_usd_as_rmb(v)
            except Exception: return '¥'+esc(v or '0')
        rows=[]
        for x in ks:
            quota=fmt(x[4]); used=fmt(x[5]); left='-'
            try: left=fmt_usd_as_rmb(max(float(x[4] or 0)-float(x[5] or 0),0))
            except Exception: pass
            name=brand_text(x[1]) or '未命名 Key'
            status='启用' if str(x[2])=='active' else '停用'
            last=esc(x[6] or '从未使用')
            shown=mask_key(x[3])
            view=f'<a class="btn btn2" href="/keys/view?id={esc(x[0])}">查看</a>'
            rows.append(f'<tr><td><strong>#{esc(x[0])}</strong><br><span class="muted">{esc(name)}</span></td><td>{esc(status)}</td><td><code style="background:#f8fafc;color:#0f172a;padding:4px">{esc(shown)}</code><br><span class="muted">中间仅显示 6 个 *，其余隐藏</span></td><td><strong>{quota}</strong><br><span class="muted">已用 {used} / 剩余 {left}</span></td><td>{last}</td><td><form class="actions" method="post"><input type="hidden" name="id" value="{esc(x[0])}"><select name="status"><option value="active">启用</option><option value="disabled">停用</option></select><button class="btn btn2" formaction="/keys/update">保存状态</button>{view}<button class="btn btn2" formaction="/keys/disable">禁用</button><button class="btn btn2" formaction="/keys/delete">删除</button></form><form class="actions" method="post" action="/keys/rotate" style="margin-top:8px"><input type="hidden" name="id" value="{esc(x[0])}"><input name="new_key" placeholder="留空自动生成；或粘贴新 sk-..." style="min-width:240px"><button class="btn">更新 Key</button></form></td></tr>')
        empty='<tr><td colspan="6" class="muted">还没有 API Key。创建后可在本页查看、更新；列表默认中间仅显示 6 个 *。</td></tr>' if not rows else ''
        body=f'<div class="card"><form method="post" action="/keys/create" class="actions"><input name="name" placeholder="Key 名称，例如 生产服务 / 本地测试"><button class="btn">创建 API Key</button></form><p class="muted">列表中间仅显示 6 个 *；点击查看可显示完整 Key，并可一键复制。</p></div><div class="card"><table><tr><th>名称</th><th>状态</th><th>Key</th><th>额度</th><th>最后使用</th><th>操作</th></tr>{"".join(rows)}{empty}</table></div>'
        self.sendh(shell('API Key',body,u,'keys'))
    def key_view_page(self,u):
        q=urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query); kid=q.get('id',[''])[0]
        try:
            res=api_post('/keys/view', {'uid':u['sub2_user_id'],'id':kid})
            key=res.get('key','')
            body=f'<div class="card"><h2>查看 API Key #{esc(kid)}</h2><p class="muted">请妥善保存，不要在聊天、邮件或工单中发送完整 Key。</p><pre id="full-key">{esc(key)}</pre><div class="actions"><button class="btn" type="button" onclick="navigator.clipboard.writeText(document.getElementById(\'full-key\').innerText).then(()=>this.innerText=\'已复制\')">复制完整 Key</button><a class="btn btn2" href="/keys">返回</a></div><p class="muted">列表显示：{esc(mask_key(key))}</p></div>'
        except Exception as e:
            body=f'<div class="card err">无法查看 Key：{esc(e)}</div><div class="card"><a class="btn" href="/keys">返回</a></div>'
        self.sendh(shell('查看 API Key',body,u,'keys'))
    def usage_page(self,u):
        q=urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query); today=time.strftime('%Y-%m-%d')
        start=q.get('start',[today])[0] or today; end=q.get('end',[today])[0] or today; model_filter=q.get('model',[''])[0].strip(); view=q.get('view',['all'])[0]
        if q.get('preset',[''])[0]=='today': start=end=today
        d=api_get('/stats?start='+urllib.parse.quote(start)+'&end='+urllib.parse.quote(end), u['sub2_user_id'])
        t=d.get('total') or ['0','0','0','0','0','0','0','0']
        cards=f'<div class="grid"><div class="card"><div class="k">消费</div><div class="num">{fmt_usd_as_rmb(t[0])}</div></div><div class="card"><div class="k">请求数</div><div class="num">{esc(t[1])}</div></div><div class="card"><div class="k">联网搜索</div><div class="num">{esc(t[2])}</div></div><div class="card"><div class="k">总 M Token</div><div class="num">{fmt_mtok(t[3])}</div></div><div class="card"><div class="k">图片</div><div class="num">{esc(t[4])}</div></div><div class="card"><div class="k">输入 M Token</div><div class="num">{fmt_mtok(t[5])}</div></div><div class="card"><div class="k">输出 M Token</div><div class="num">{fmt_mtok(t[6])}</div></div><div class="card"><div class="k">缓存 M Token</div><div class="num">{fmt_mtok(t[7])}</div></div></div>'
        daily=''.join([f'<tr><td>{esc(x[0])}</td><td>{fmt_usd_as_rmb(x[1])}</td><td>{esc(x[2])}</td><td>{fmt_mtok(x[3])}</td><td>{esc(x[4])}</td></tr>' for x in d.get('daily',[])])
        model_rows=[x for x in d.get('models',[]) if not model_filter or model_filter.lower() in str(x[0]).lower()]
        models=''.join([f'<tr><td>{esc(x[0])}</td><td>{fmt_usd_as_rmb(x[1])}</td><td>{esc(x[2])}</td><td>{fmt_mtok(x[3])}</td></tr>' for x in model_rows])
        action=f'/export.csv?type=usage&start={urllib.parse.quote(start)}&end={urllib.parse.quote(end)}&model={urllib.parse.quote(model_filter)}'
        filters=f'<div class="card"><form method="get" class="actions"><button class="btn btn2" name="preset" value="today">今日实时</button><input name="start" type="date" value="{esc(start)}"><input name="end" type="date" value="{esc(end)}"><input name="model" placeholder="筛选模型" value="{esc(model_filter)}"><select name="view"><option value="all" {"selected" if view=="all" else ""}>全部</option><option value="daily" {"selected" if view=="daily" else ""}>按日</option><option value="model" {"selected" if view=="model" else ""}>按模型</option></select><button class="btn">查询</button><a class="btn btn2" href="{action}">导出 CSV</a></form></div>'
        daily_card=f'<div class="card"><h2>按日统计</h2><table><tr><th>日期</th><th>消费</th><th>请求</th><th>M Token</th><th>图片</th></tr>{daily}</table></div>' if view in ('all','daily') else ''
        model_card=f'<div class="card"><h2>模型统计</h2><table><tr><th>模型</th><th>消费</th><th>请求</th><th>M Token</th></tr>{models}</table></div>' if view in ('all','model') else ''
        self.sendh(shell('用量统计',filters+cards+daily_card+model_card,u,'usage'))
    def billing(self,u):
        d=api_get('/summary',u['sub2_user_id']); su=d.get('user') or ['','','','','','0','0']; st=d.get('stats') or ['0','0','0','0','0']
        qs=urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query); status=qs.get('status',[''])[0].strip(); bstart=qs.get('start',[''])[0].strip(); bend=qs.get('end',[''])[0].strip()
        con=db(); where=['user_id=?']; params=[u['id']]
        if status: where.append('status=?'); params.append(status)
        if bstart: where.append('created_at>=?'); params.append(int(time.mktime(time.strptime(bstart,'%Y-%m-%d'))))
        if bend: where.append('created_at<?'); params.append(int(time.mktime(time.strptime(bend,'%Y-%m-%d')))+86400)
        orders=con.execute('SELECT id,amount,method,note,status,admin_email,created_at,reviewed_at FROM recharge_orders WHERE '+ ' AND '.join(where)+' ORDER BY id DESC LIMIT 80',params).fetchall()
        bills=con.execute('SELECT amount,note,created_at FROM billing_logs WHERE user_id=? ORDER BY id DESC LIMIT 80',(u['id'],)).fetchall(); con.close()
        status_map={'pending':'待审核','approved':'已通过','rejected':'未通过'}
        ors=''.join([f'<tr><td>#{x[0]}</td><td>{time.strftime("%F %T",time.localtime(x[6]))}</td><td>¥{esc(x[1])}</td><td>{esc(x[2])}</td><td>{esc(status_map.get(x[4],x[4]))}</td><td>{esc(x[3])}</td><td>{"已审核" if x[5] else ""}</td><td>{time.strftime("%F %T",time.localtime(x[7])) if x[7] else ""}</td></tr>' for x in orders])
        brs=''.join([f'<tr><td>{time.strftime("%F %T",time.localtime(x[2]))}</td><td>{"入账" if float(x[0] or 0)>=0 else "扣减"}</td><td>¥{esc(x[0])}</td><td>{esc(x[1])}</td></tr>' for x in bills])
        methods=payment_methods(True)
        method_cards=''.join([f'<div class="card"><div class="k">{esc(x["name"])}</div><p>{esc(x["instructions"])}</p></div>' for x in methods])
        method_opts=''.join([f'<option value="{esc(x["name"])}">{esc(x["name"])}</option>' for x in methods])
        if not method_opts: method_opts='<option value="">暂无可用收款方式</option>'
        filters=f'<form method="get" class="actions"><select name="status"><option value="">全部记录</option><option value="pending" {"selected" if status=="pending" else ""}>待审核</option><option value="approved" {"selected" if status=="approved" else ""}>已通过</option><option value="rejected" {"selected" if status=="rejected" else ""}>未通过</option></select><input name="start" type="date" value="{esc(bstart)}"><input name="end" type="date" value="{esc(bend)}"><button class="btn btn2">筛选</button><a class="btn btn2" href="/export.csv?type=billing-user">导出流水</a></form>'
        if u.get('role')=='admin':
            recharge_block='<div class="card"><h2>增加</h2><p>订单流程已关闭。请到“用户管理”中选择用户，在“记账”里直接增加或扣减。</p><div class="actions"><a class="btn" href="/users-admin">去用户管理</a></div></div>'
        else:
            recharge_block='<div class="card"><h2>增加</h2><p class="muted">普通用户暂不开放自助增加，请联系管理员处理额度。</p></div>'
        body=f'<div class="grid"><div class="card"><div class="k">当前余额</div><div class="num">{fmt_usd_as_rmb(su[5])}</div></div><div class="card"><div class="k">累计增加</div><div class="num">{fmt_usd_as_rmb(su[6])}</div></div><div class="card"><div class="k">累计消费</div><div class="num">{fmt_usd_as_rmb(st[4])}</div></div><div class="card"><div class="k">额度</div><div class="num">管理员处理</div></div></div>{recharge_block}<div class="card"><h2>余额流水明细</h2><table><tr><th>时间</th><th>类型</th><th>金额</th><th>备注</th></tr>{brs}</table></div>'
        self.sendh(shell('计费',body,u,'billing'))

    def public_plans(self):
        body='<p class="muted">套餐用于管理账号额度、模型范围、日/月限制和运营复核策略。实际调用仍受余额、Key 状态、模型权限和价格表共同约束。</p><div class="grid"><div class="card"><h2>普通会员</h2><p>适合个人测试和小规模接入，默认开放基础模型与较低日限额。</p></div><div class="card"><h2>高级会员</h2><p>适合团队使用，提供更高月额度、日限额和主力模型权限。</p></div><div class="card"><h2>企业会员</h2><p>适合生产业务，支持人工定制额度、模型白名单、风控复核和报表需求。</p></div></div><div class="card"><h2>低余额与服务规则</h2><p>余额低于阈值时，系统最多每 24 小时发送一次站内和邮件提醒。余额不足、套餐到期、模型未授权或超过日/月额度时，调用可能被限制。</p><p>套餐变更由管理员在控制台执行；本平台不接入自动扣减或真实支付网关。</p></div>'
        self.sendh(public_page('套餐与服务规则',body))

    def public_risk(self):
        body='<p class="muted">NW-API 通过额度、并发、模型权限、登录失败限制、人工黑白名单和审计日志保护服务稳定性。公开说明不展示内部链路、内部配置或敏感信息。</p><div class="grid"><div class="card"><h2>白名单</h2><p>用于可信用户、邮箱、模型、路径或业务场景，便于稳定放行。</p></div><div class="card"><h2>黑名单</h2><p>用于确认异常来源、违规账号、攻击路径或高风险调用，必要时可限制访问。</p></div><div class="card"><h2>复核名单</h2><p>用于疑似共享 Key、短时高失败率、异常模型请求或需要人工判断的行为。</p></div></div><div class="card"><h2>异常调用限制</h2><p>平台可对滥用、攻击、绕过限制、侵犯第三方权益、违法违规内容、批量探测或明显超出约定用途的调用采取限速、暂停 Key、限制模型、冻结账号或人工复核。</p></div>'
        self.sendh(public_page('风控与合规',body))

    def plans_page(self,u):
        con=db(); plans=con.execute('SELECT id,name,price,monthly_quota,daily_limit,models,note,status FROM plans ORDER BY price').fetchall(); current=con.execute('SELECT p.name FROM user_plans up JOIN plans p ON p.id=up.plan_id WHERE up.user_id=?',(u['id'],)).fetchone(); con.close()
        cards=''.join([f'<div class="card"><div class="k">{esc(x[1])}</div><div class="num">¥{esc(x[2])}</div><p>月额度：{esc(x[3])} / 日限额：{esc(x[4])}</p><p>模型：{esc(x[5])}</p><p class="muted">{esc(x[6])}</p><p class="muted">套餐用于额度和模型权限管理；实际调用仍按价格表与账户余额核算。</p></div>' for x in plans if x[7]=='active'])
        admin=''
        if u['role']=='admin':
            rows=''.join([f'<tr><td>{x[0]}</td><td>{esc(x[1])}</td><td>{esc(x[2])}</td><td>{esc(x[3])}</td><td>{esc(x[4])}</td><td>{esc(x[5])}</td><td>{esc(x[7])}</td></tr>' for x in plans])
            admin=f'<div class="card"><h2>编辑套餐</h2><form method="post" action="/plans/update" class="actions"><input name="id" placeholder="ID 留空新增"><input name="name" placeholder="名称"><input name="price" placeholder="价格"><input name="monthly_quota" placeholder="月额度"><input name="daily_limit" placeholder="日限额"><input name="models" placeholder="模型逗号分隔"><input name="note" placeholder="说明"><select name="status"><option value="active">启用</option><option value="disabled">禁用</option></select><button class="btn">保存套餐</button></form><table><tr><th>ID</th><th>名称</th><th>价格</th><th>月额度</th><th>日限额</th><th>模型</th><th>状态</th></tr>{rows}</table></div>'
        cur=f'<div class="card"><div class="k">当前套餐</div><div class="num">{esc(current[0] if current else "普通会员")}</div></div>'
        rules=f'<div class="card"><h2>服务规则</h2><p>余额低于 1 时，系统最多每 24 小时发送一次站内与邮件提醒；余额不足、套餐到期、模型未授权或超过日/月额度时，调用可能被限制或返回明确错误。</p><p>异常调用包括短时间高失败率、疑似共享 Key、攻击路径、批量探测、违反服务条款的内容或绕过限制行为。平台可先限速、暂停 Key、调整模型权限或要求人工复核。</p><div class="actions">{COMPLIANCE_LINKS}<a class="btn btn2" href="/pricing">查看价格</a></div></div>'
        self.sendh(shell('套餐',cur+rules+f'<div class="grid">{cards}</div>'+admin,u,'plans'))

    def public_models(self):
        rows,meta=price_rows()
        cards=''.join([f'<div class="card"><div class="actions" style="justify-content:space-between"><span class="pill">{esc(x[5])}</span><span class="muted">自动同步</span></div><h2 style="margin-top:12px">{esc(x[0])}</h2><p>{esc(model_desc(x[0],x[5]))}</p><div class="grid" style="grid-template-columns:repeat(2,minmax(0,1fr));gap:10px"><div><div class="k">输入 / M</div><div class="num">{fmt_usd_rmb(x[1])}</div></div><div><div class="k">输出 / M</div><div class="num">{fmt_usd_rmb(x[2])}</div></div><div><div class="k">缓存 / M</div><div class="num">{fmt_usd_rmb(x[3])}</div></div><div><div class="k">图片</div><div class="num">{("暂未开放" if float(x[4] or 0)==0 else fmt_usd_rmb(x[4]))}</div></div></div></div>' for x in rows])
        synced=time.strftime('%F %T',time.localtime(meta['synced_at'])) if meta and meta['synced_at'] else '未同步'
        table=''.join([f'<tr><td><b>{esc(x[0])}</b></td><td>{esc(x[5])}</td><td>{fmt_usd_rmb(x[1])}</td><td>{fmt_usd_rmb(x[2])}</td><td>{fmt_usd_rmb(x[3])}</td><td>{("暂未开放" if float(x[4] or 0)==0 else fmt_usd_rmb(x[4]))}</td><td>{esc(model_desc(x[0],x[5]))}</td></tr>' for x in rows])
        body=f'<div class="card"><h2>模型、价格和适用场景</h2><p>以下价格来自后台价格配置，并在页面打开时自动同步到官网和控制台。价格、余额、消费均按人民币计；价格单位为人民币 / M Token，最终扣费以控制台流水为准。</p><p class="muted">最近同步：{esc(synced)}；上游更新时间：{esc(meta["upstream_updated_at"] if meta else "")}</p></div><div class="grid">{cards}</div><div class="card"><h2>模型价格总览</h2><table><tr><th>模型</th><th>定位</th><th>输入/M</th><th>输出/M</th><th>缓存/M</th><th>图片</th><th>介绍</th></tr>{table}</table></div>'
        self.sendh(public_page('模型',body))

    def public_pricing(self):
        rows,meta=price_rows()
        trs=''.join([f'<tr><td><b>{esc(x[0])}</b></td><td>{fmt_usd_rmb(x[1])}</td><td>{fmt_usd_rmb(x[2])}</td><td>{fmt_usd_rmb(x[3])}</td><td>{("暂未开放" if float(x[4] or 0)==0 else fmt_usd_rmb(x[4]))}</td><td>{esc(x[5])}</td></tr>' for x in rows])
        synced=time.strftime('%F %T',time.localtime(meta['synced_at'])) if meta and meta['synced_at'] else '未同步'
        body=f'<div class="card"><h2>价格表</h2><p>价格实时同步自后台价格配置，官网模型页、控制台模型页和价格表使用同一份数据。</p><p class="muted">最近同步：{esc(synced)}；价格按人民币展示，单位为人民币 / M Token。</p></div><div class="card"><table><tr><th>模型</th><th>输入/M</th><th>输出/M</th><th>缓存/M</th><th>图片</th><th>说明</th></tr>{trs}</table></div>'
        self.sendh(public_page('价格表',body))

    def models_page(self,u):
        ms=set(allowed_models(u['id']))
        rows,meta=price_rows()
        cards=[]; trs=[]
        for x in rows:
            allowed=x[0] in ms
            badge='已开放' if allowed else '未开放'
            cls='pill' if allowed else 'pill muted'
            image='暂未开放' if float(x[4] or 0)==0 else fmt_usd_rmb(x[4])
            cards.append(f'<div class="card"><div class="actions" style="justify-content:space-between"><span class="{cls}">{badge}</span><span class="muted">{esc(x[5])}</span></div><h2 style="margin-top:12px">{esc(x[0])}</h2><p>{esc(model_desc(x[0],x[5]))}</p><div class="grid" style="grid-template-columns:repeat(2,minmax(0,1fr));gap:10px"><div><div class="k">输入 / M</div><div class="num">{fmt_usd_rmb(x[1])}</div></div><div><div class="k">输出 / M</div><div class="num">{fmt_usd_rmb(x[2])}</div></div><div><div class="k">缓存 / M</div><div class="num">{fmt_usd_rmb(x[3])}</div></div><div><div class="k">图片</div><div class="num">{image}</div></div></div></div>')
            trs.append(f'<tr><td><b>{esc(x[0])}</b></td><td>{badge}</td><td>{esc(x[5])}</td><td>{fmt_usd_rmb(x[1])}</td><td>{fmt_usd_rmb(x[2])}</td><td>{fmt_usd_rmb(x[3])}</td><td>{image}</td><td>{esc(model_desc(x[0],x[5]))}</td></tr>')
        synced=time.strftime('%F %T',time.localtime(meta['synced_at'])) if meta and meta['synced_at'] else '未同步'
        explain=f'<div class="card"><h2>模型说明</h2><p>模型与价格从后台价格配置自动同步；官网价格页、模型页和控制台共用同一份数据。</p><p class="muted">最近同步：{esc(synced)}；上游更新时间：{esc(meta["upstream_updated_at"] if meta else "")}</p></div>'
        table=f'<div class="card"><h2>价格总览</h2><table><tr><th>模型</th><th>状态</th><th>定位</th><th>输入/M</th><th>输出/M</th><th>缓存/M</th><th>图片</th><th>介绍</th></tr>{"".join(trs)}</table></div>'
        self.sendh(shell('可用模型',explain+f'<div class="grid">{"".join(cards)}</div>'+table,u,'models'))

    def pricing_page(self,u):
        rows,meta=price_rows()
        trs=''.join([f'<tr><td>{esc(x[0])}</td><td>{fmt_usd_rmb(x[1])}</td><td>{fmt_usd_rmb(x[2])}</td><td>{fmt_usd_rmb(x[3])}</td><td>{("暂未开放" if float(x[4] or 0)==0 else fmt_usd_rmb(x[4]))}</td><td>{esc(x[5])}</td></tr>' for x in rows])
        form=''
        if u['role']=='admin':
            opts=''.join([f'<option value="{esc(x[0])}">{esc(x[0])}</option>' for x in rows])
            form=f'<div class="card"><h2>编辑价格</h2><p class="muted">主价格源为后台价格配置；本页金额单位为人民币 / M Token。这里的手工编辑会在下次同步时被后台配置覆盖。</p><form method="post" action="/pricing/update" class="actions"><select name="model">{opts}</select><input name="input_price" placeholder="输入/M"><input name="output_price" placeholder="输出/M"><input name="cache_price" placeholder="缓存/M"><input name="image_price" placeholder="图片"><input name="note" placeholder="说明"><button class="btn">保存</button></form></div>'
        synced=time.strftime('%F %T',time.localtime(meta['synced_at'])) if meta and meta['synced_at'] else '未同步'
        explain=f'<div class="card"><h2>计价说明</h2><p>价格以每百万 Token 展示，自动同步自后台价格配置；最终扣费以控制台流水为准。</p><p class="muted">最近同步：{esc(synced)}；上游更新时间：{esc(meta["upstream_updated_at"] if meta else "")}</p></div>'
        self.sendh(shell('价格表',form+explain+f'<div class="card"><table><tr><th>模型</th><th>输入/M</th><th>输出/M</th><th>缓存/M</th><th>图片</th><th>说明</th></tr>{trs}</table></div>',u,'pricing'))

    def mail_logs_page(self,u):
        if u['role']!='admin': return self.redirect('/dashboard')
        qs=urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query); page=clamp_int(qs.get('page',['1'])[0]); size=50; status=qs.get('status',[''])[0].strip(); typ=qs.get('type',[''])[0].strip(); q=qs.get('q',[''])[0].strip()
        where=[]; params=[]
        if status: where.append('status=?'); params.append(status)
        if typ: where.append('type=?'); params.append(typ)
        if q: where.append('(recipient LIKE ? OR subject LIKE ? OR error LIKE ?)'); params += ['%'+q+'%']*3
        wh=' WHERE '+ ' AND '.join(where) if where else ''
        con=db(); total=con.execute('SELECT count(*) FROM mail_logs'+wh,params).fetchone()[0]; rows=con.execute('SELECT recipient,subject,type,status,error,created_at FROM mail_logs'+wh+' ORDER BY id DESC LIMIT ? OFFSET ?',params+[size,(page-1)*size]).fetchall(); con.close()
        trs=''.join([f'<tr><td>{time.strftime("%F %T",time.localtime(x[5]))}</td><td>{esc(x[0])}</td><td>{esc(x[1])}</td><td>{esc(x[2])}</td><td>{esc(x[3])}</td><td>{esc(public_safe_text(x[4]))}</td></tr>' for x in rows])
        filters=f'<div class="card"><form method="get" class="actions"><input name="q" placeholder="收件人/主题/错误" value="{esc(q)}"><select name="status"><option value="">全部状态</option><option value="sent" {"selected" if status=="sent" else ""}>sent</option><option value="failed" {"selected" if status=="failed" else ""}>failed</option></select><input name="type" placeholder="类型" value="{esc(typ)}"><button class="btn btn2">筛选</button></form></div>'
        self.sendh(shell('邮件日志',filters+f'<div class="card">{pager("/mail-logs",qs,page,size,total)}<table><tr><th>时间</th><th>收件人</th><th>主题</th><th>类型</th><th>状态</th><th>错误</th></tr>{trs}</table>{pager("/mail-logs",qs,page,size,total)}</div>',u,'mail-logs'))

    def docs(self,u):
        body=f"""<div class="card"><h2>Base URL</h2><pre>{BASE_URL}</pre><p>所有请求必须使用本平台 API Key。系统会自动校验 Key 状态、额度和模型权限。</p></div>
<div class="card"><h2>curl 示例</h2><pre>curl {BASE_URL}/chat/completions \\
  -H "Authorization: Bearer sk-你的KEY" \\
  -H "Content-Type: application/json" \\
  -d '{{"model":"gpt-5.4-mini","messages":[{{"role":"user","content":"hello"}}]}}'</pre></div>
<div class="card"><h2>Python 示例</h2><pre>from openai import OpenAI
client = OpenAI(base_url="{BASE_URL}", api_key="sk-你的KEY")
res = client.chat.completions.create(
    model="gpt-5.4-mini",
    messages=[{{"role":"user","content":"hello"}}]
)
print(res.choices[0].message.content)</pre></div>
<div class="card"><h2>Node.js 示例</h2><pre>import OpenAI from "openai";
const client = new OpenAI({{ baseURL: "{BASE_URL}", apiKey: "sk-你的KEY" }});
const res = await client.chat.completions.create({{
  model: "gpt-5.4-mini",
  messages: [{{ role: "user", content: "hello" }}]
}});
console.log(res.choices[0].message.content);</pre></div>
<div class="card"><h2>模型权限</h2><p>可用模型以“可用模型”页面为准。未授权模型会返回 <code>MODEL_NOT_ALLOWED</code>。</p><pre>curl {BASE_URL}/models \\
  -H "Authorization: Bearer sk-你的KEY"</pre></div>
<div class="card"><h2>错误与限制</h2><p>常见限制包括 Key 禁用、余额不足、模型未授权、套餐额度不足、请求过快、异常路径或违反服务条款。请根据返回错误码、控制台用量和通知记录排查。</p><p class="muted">请勿在客户端、截图、日志或工单中暴露完整 API Key。公开接入仅展示 OpenAI-compatible 协议，不披露内部服务实现和内部链路。</p><div class="actions">{COMPLIANCE_LINKS}<a class="btn btn2" href="/plans">查看套餐</a></div></div>"""
        self.sendh(shell('文档',body,u,'docs'))
    def admin_console(self,u):
        if u['role']!='admin': return self.redirect('/dashboard')
        con=db(); now=int(time.time()); week=now-7*86400
        total_users=con.execute('SELECT count(*) FROM users WHERE status!="deleted"').fetchone()[0]
        active_users=con.execute('SELECT count(*) FROM users WHERE status="active"').fetchone()[0]
        new_users=con.execute('SELECT count(*) FROM users WHERE status!="deleted" AND created_at>=?',(week,)).fetchone()[0]
        order_total=con.execute('SELECT count(*),COALESCE(sum(amount),0) FROM recharge_orders').fetchone()
        order_pending=con.execute('SELECT count(*) FROM recharge_orders WHERE status="pending"').fetchone()[0]
        order_approved=con.execute('SELECT count(*) FROM recharge_orders WHERE status="approved"').fetchone()[0]
        income=con.execute('SELECT COALESCE(sum(amount),0) FROM billing_logs WHERE amount>0').fetchone()[0]
        debit=con.execute('SELECT COALESCE(sum(amount),0) FROM billing_logs WHERE amount<0').fetchone()[0]
        api_total=con.execute('SELECT count(*) FROM api_access_logs').fetchone()[0]
        api_err=con.execute('SELECT count(*) FROM api_access_logs WHERE status>=400').fetchone()[0]
        api_week_users=con.execute('SELECT count(DISTINCT user_id) FROM api_access_logs WHERE created_at>=? AND user_id IS NOT NULL',(week,)).fetchone()[0]
        risk_active=con.execute('SELECT count(*) FROM risk_rules WHERE status="active"').fetchone()[0]
        allow_active=con.execute('SELECT count(*) FROM risk_rules WHERE status="active" AND action="allow"').fetchone()[0]
        block_active=con.execute('SELECT count(*) FROM risk_rules WHERE status="active" AND action="block"').fetchone()[0]
        review_active=con.execute('SELECT count(*) FROM risk_rules WHERE status="active" AND action="review"').fetchone()[0]
        pending_mail=con.execute('SELECT count(*) FROM mail_logs WHERE status="failed"').fetchone()[0]
        recent=con.execute('SELECT u.email,COALESCE(sum(b.amount),0) s FROM billing_logs b JOIN users u ON u.id=b.user_id GROUP BY u.email ORDER BY s DESC LIMIT 8').fetchall()
        orders=con.execute('SELECT status,count(*),COALESCE(sum(amount),0) FROM recharge_orders GROUP BY status').fetchall()
        days=con.execute('SELECT date(created_at,\'unixepoch\',\'localtime\') d, COALESCE(sum(amount),0), count(*) FROM billing_logs WHERE amount>0 GROUP BY d ORDER BY d DESC LIMIT 14').fetchall()[::-1]
        api_days=con.execute('SELECT date(created_at,\'unixepoch\',\'localtime\') d, count(*), sum(CASE WHEN status>=400 THEN 1 ELSE 0 END) FROM api_access_logs GROUP BY d ORDER BY d DESC LIMIT 14').fetchall()[::-1]
        ops=con.execute('SELECT admin_email,action,target,detail,created_at FROM ops_log ORDER BY id DESC LIMIT 10').fetchall()
        con.close()
        top=''.join([f'<tr><td>{esc(x[0])}</td><td>{esc(x[1])}</td></tr>' for x in recent])
        ors=''.join([f'<tr><td><span class="badge {"ok" if x[0]=="approved" else "bad" if x[0]=="rejected" else ""}">{esc(x[0])}</span></td><td>{esc(x[1])}</td><td>{esc(x[2])}</td></tr>' for x in orders])
        max_income=max([float(x[1] or 0) for x in days] or [1]) or 1
        bars=''.join([f'<div style="display:flex;align-items:end;gap:6px"><div style="height:{int(float(x[1] or 0)/max_income*120)+6}px;width:24px;background:linear-gradient(180deg,#2563eb,#7c3aed);border-radius:8px" title="{esc(x[0])}: {esc(x[1])}"></div><small>{esc(x[0][-5:])}</small></div>' for x in days])
        api_bars=''.join([f'<tr><td>{esc(x[0])}</td><td>{esc(x[1])}</td><td>{esc(x[2] or 0)}</td></tr>' for x in api_days])
        err_rate=(api_err/api_total*100) if api_total else 0
        op_rows=''.join([f'<tr><td>{time.strftime("%F %T",time.localtime(x[4]))}</td><td>{esc(x[0])}</td><td>{esc(x[1])}</td><td>{esc(x[2])}</td><td>{esc(x[3])}</td></tr>' for x in ops])
        approval=(order_approved/(order_total[0] or 1)*100) if order_total[0] else 0
        governance=f'<div class="card"><h2>商业规则与合规入口</h2><p>当前采用管理员手动调整余额，不开放用户自助订单，额度问题请联系管理员；套餐只控制额度、模型范围和运营策略，实际消费以价格表和流水为准。</p><p>风控启用 {risk_active} 条：allow {allow_active}、block {block_active}、review {review_active}。管理员可在风控页维护黑白名单、复核名单和异常调用说明。</p><div class="actions"><a class="btn" href="/risk">风控规则</a><a class="btn btn2" href="/plans">套餐规则</a><a class="btn btn2" href="/pricing">价格表</a>{COMPLIANCE_LINKS}</div></div>'
        body=f'<div class="grid"><div class="card"><div class="k">用户数</div><div class="num">{total_users}</div><p class="muted">近7天新增 {new_users}</p></div><div class="card"><div class="k">活跃用户</div><div class="num">{active_users}</div><p class="muted">近7天调用用户 {api_week_users}</p></div><div class="card"><div class="k">余额增加</div><div class="num">¥{esc(income)}</div><p class="muted">扣减 {esc(debit)}</p></div><div class="card"><div class="k">API 错误率</div><div class="num">{err_rate:.1f}%</div></div><div class="card"><div class="k">启用风控</div><div class="num">{risk_active}</div></div><div class="card"><div class="k">邮件失败</div><div class="num">{pending_mail}</div></div></div>{governance}<div class="card"><h2>收入趋势</h2><div style="height:160px;display:flex;gap:12px;align-items:end">{bars}</div></div><div class="card"><h2>API 调用/错误</h2><table><tr><th>日期</th><th>调用</th><th>错误</th></tr>{api_bars}</table></div><div class="card"><h2>最近操作</h2><table><tr><th>时间</th><th>管理员</th><th>动作</th><th>对象</th><th>详情</th></tr>{op_rows}</table></div>'
        self.sendh(shell('管理概览',body,u,'admin'))

    def risk_page(self,u):
        if u['role']!='admin': return self.redirect('/dashboard')
        qs=urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query); page=clamp_int(qs.get('page',['1'])[0]); size=50; kind=qs.get('kind',[''])[0].strip(); action=qs.get('action',[''])[0].strip(); status=qs.get('status',[''])[0].strip(); q=qs.get('q',[''])[0].strip()
        where=[]; params=[]
        if kind: where.append('kind=?'); params.append(kind)
        if action: where.append('action=?'); params.append(action)
        if status: where.append('status=?'); params.append(status)
        if q: where.append('(pattern LIKE ? OR note LIKE ?)'); params += ['%'+q+'%','%'+q+'%']
        wh=' WHERE '+ ' AND '.join(where) if where else ''
        con=db(); total=con.execute('SELECT count(*) FROM risk_rules'+wh,params).fetchone()[0]; rows=con.execute('SELECT id,kind,pattern,action,note,status,created_at FROM risk_rules'+wh+' ORDER BY id DESC LIMIT ? OFFSET ?',params+[size,(page-1)*size]).fetchall(); stats=con.execute('SELECT kind,action,status,count(*) FROM risk_rules GROUP BY kind,action,status ORDER BY kind,action,status').fetchall(); con.close()
        trs=''.join([f'<tr><td>{x[0]}</td><td>{esc(x[1])}</td><td>{esc(x[2])}</td><td>{esc(x[3])}</td><td>{esc(x[5])}</td><td>{esc(x[4])}</td><td>{time.strftime("%F %T",time.localtime(x[6]))}</td></tr>' for x in rows])
        stat_rows=''.join([f'<tr><td>{esc(x[0])}</td><td>{esc(x[1])}</td><td>{esc(x[2])}</td><td>{esc(x[3])}</td></tr>' for x in stats])
        guide='<div class="card"><h2>风控说明</h2><p>allow 表示白名单，适用于可信邮箱、模型或路径；block 表示黑名单，适用于已确认异常来源；review 表示观察名单，适用于需要人工复核但暂不直接拦截的场景。</p><p>平台同时保留额度、并发、登录失败次数、余额提醒、API 错误率和操作审计等运营控制。新增规则默认只进入门户规则库，不改变既有 /v1 路由行为。</p></div>'
        body=f'{guide}<div class="card"><h2>规则维护</h2><p class="muted">支持 IP/CIDR、邮箱、路径、模型、国家/地区标记等人工规则；allow 用于放行名单，block 用于拦截名单，review 用于人工关注。</p><form method="post" action="/risk/update" class="actions"><input name="id" placeholder="ID 留空新增"><select name="kind"><option value="ip">IP/CIDR</option><option value="email">邮箱</option><option value="path">路径</option><option value="model">模型</option><option value="region">地区</option><option value="note">备注关键字</option></select><input name="pattern" placeholder="规则内容"><select name="action"><option value="block">block</option><option value="allow">allow</option><option value="review">review</option></select><input name="note" placeholder="备注"><select name="status"><option value="active">启用</option><option value="disabled">禁用</option></select><button class="btn">保存规则</button></form></div><div class="card"><form method="get" class="actions"><input name="q" placeholder="规则/备注" value="{esc(q)}"><select name="kind"><option value="">全部类型</option><option value="ip" {"selected" if kind=="ip" else ""}>IP/CIDR</option><option value="email" {"selected" if kind=="email" else ""}>邮箱</option><option value="path" {"selected" if kind=="path" else ""}>路径</option><option value="model" {"selected" if kind=="model" else ""}>模型</option><option value="region" {"selected" if kind=="region" else ""}>地区</option><option value="note" {"selected" if kind=="note" else ""}>备注</option></select><select name="action"><option value="">全部动作</option><option value="block" {"selected" if action=="block" else ""}>block</option><option value="allow" {"selected" if action=="allow" else ""}>allow</option><option value="review" {"selected" if action=="review" else ""}>review</option></select><select name="status"><option value="">全部状态</option><option value="active" {"selected" if status=="active" else ""}>启用</option><option value="disabled" {"selected" if status=="disabled" else ""}>禁用</option></select><button class="btn btn2">筛选</button></form></div><div class="card"><h2>规则汇总</h2><table><tr><th>类型</th><th>动作</th><th>状态</th><th>数量</th></tr>{stat_rows}</table></div><div class="card">{pager("/risk",qs,page,size,total)}<table><tr><th>ID</th><th>类型</th><th>规则</th><th>动作</th><th>状态</th><th>备注</th><th>时间</th></tr>{trs}</table>{pager("/risk",qs,page,size,total)}</div>'
        self.sendh(shell('风控',body,u,'risk'))

    def onboarding_page(self,u):
        ks=api_get('/keys',u['sub2_user_id']).get('keys',[])
        sample_key=ks[0][3] if ks else '请先在 API Key 页面创建 Key'
        body=f'<div class="grid"><div class="card"><div class="k">步骤 1</div><h2>创建 API Key</h2><p>进入 API Key 页面创建并复制 Key。</p><a class="btn" href="/keys">去创建</a></div><div class="card"><div class="k">步骤 2</div><h2>复制接口地址</h2><pre>{BASE_URL}</pre></div><div class="card"><div class="k">步骤 3</div><h2>测试调用</h2><pre>curl {BASE_URL}/models \\\n  -H "Authorization: Bearer {esc(sample_key)}"</pre></div></div><div class="card"><h2>Python 示例</h2><pre>from openai import OpenAI\nclient = OpenAI(api_key="你的Key", base_url="{BASE_URL}")\nprint(client.models.list())</pre></div>'
        self.sendh(shell('新手引导',body,u,'onboarding'))

    def healthz_page(self,u):
        if u['role']!='admin': return self.redirect('/dashboard')
        checks=[]
        try:
            d=api_get('/health',0); checks.append(('数据服务','ok',str(d)[:120]))
        except Exception as e: checks.append(('数据服务','fail',str(e)))
        try:
            con=db(); counts=[('users',con.execute('SELECT count(*) FROM users').fetchone()[0]),('notifications',con.execute('SELECT count(*) FROM notifications').fetchone()[0]),('api_logs',con.execute('SELECT count(*) FROM api_access_logs').fetchone()[0])]; con.close(); checks.append(('门户数据库','ok',str(counts)))
        except Exception as e: checks.append(('门户数据库','fail',str(e)))
        rows=''.join([f'<tr><td>{esc(a)}</td><td>{esc(b)}</td><td>{esc(c)}</td></tr>' for a,b,c in checks])
        self.sendh(shell('健康检查',f'<div class="card"><table><tr><th>项目</th><th>状态</th><th>详情</th></tr>{rows}</table></div><div class="card"><p>版本：{APP_VERSION}</p><p>Base URL：{BASE_URL}</p></div>',u,'admin'))

    def changelog_page(self,u):
        if u['role']!='admin': return self.redirect('/dashboard')
        items=['V0.0.002：概览页精简为控制台；移除左侧系统更新菜单；左上角版本号承载更新提示与更新入口；删除 API Console 文案；更新说明强调只更新功能代码，不覆盖用户、数据库、Sub2API 连接和密钥配置。','V0.0.001：统一站点标题为 NW-API；版本号显示为 v.0.001；保留 Git 更新能力。','第十批：每日备份、健康页、版本页、新手引导、自动通知','第九批：公告栏与站内通知']
        lis=''.join([f'<li>{esc(x)}</li>' for x in items])
        self.sendh(shell('版本更新',f'<div class="card"><h2>{APP_VERSION}</h2><ul>{lis}</ul></div>',u,'admin'))

    def notifications_page(self,u):
        qs=urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query); typ=qs.get('type',[''])[0].strip(); state=qs.get('state',[''])[0].strip()
        con=db(); where=['(user_id=? OR user_id IS NULL)']; params=[u['id']]
        if typ: where.append('type=?'); params.append(typ)
        if state=='unread': where.append('read_at IS NULL')
        elif state=='read': where.append('read_at IS NOT NULL')
        rows=con.execute('SELECT id,title,content,type,read_at,created_at FROM notifications WHERE '+ ' AND '.join(where)+' ORDER BY read_at IS NOT NULL,id DESC LIMIT 100',params).fetchall()
        unread=con.execute('SELECT count(*) FROM notifications WHERE (user_id=? OR user_id IS NULL) AND read_at IS NULL',(u['id'],)).fetchone()[0]
        types=con.execute('SELECT DISTINCT type FROM notifications WHERE (user_id=? OR user_id IS NULL) AND type IS NOT NULL ORDER BY type',(u['id'],)).fetchall(); con.close()
        opts='<option value="">全部类型</option>'+''.join([f'<option value="{esc(x[0])}" {"selected" if typ==x[0] else ""}>{esc(x[0])}</option>' for x in types])
        filters=f'<div class="card"><form method="get" class="actions"><select name="state"><option value="" {"selected" if not state else ""}>全部状态</option><option value="unread" {"selected" if state=="unread" else ""}>未读</option><option value="read" {"selected" if state=="read" else ""}>已读</option></select><select name="type">{opts}</select><button class="btn">筛选</button></form><form method="post" action="/notifications/read-all" class="actions"><button class="btn btn2">全部标记已读</button><span class="muted">未读 {unread}</span></form></div>'
        trs=''.join([f'<tr><td>{"已读" if x[4] else "未读"}</td><td><strong>{esc(x[1])}</strong><br><span class="muted">{esc(x[2])}</span></td><td>{esc(x[3])}</td><td>{time.strftime("%F %T",time.localtime(x[5]))}</td><td>{time.strftime("%F %T",time.localtime(x[4])) if x[4] else ""}</td><td><form method="post" action="/notifications/read"><input type="hidden" name="id" value="{x[0]}"><button class="btn btn2">标记已读</button></form></td></tr>' for x in rows])
        empty='<tr><td colspan="6" class="muted">暂无通知</td></tr>' if not rows else ''
        self.sendh(shell('通知',filters+f'<div class="card"><table><tr><th>状态</th><th>通知</th><th>类型</th><th>发送时间</th><th>阅读时间</th><th>操作</th></tr>{trs}{empty}</table></div>',u,'notifications'))

    def announcements_page(self,u):
        if u['role']!='admin': return self.redirect('/dashboard')
        con=db(); anns=con.execute('SELECT id,title,content,status,pinned,created_at FROM announcements ORDER BY id DESC LIMIT 50').fetchall(); users=con.execute('SELECT id,email FROM users WHERE status="active" ORDER BY id').fetchall(); notes=con.execute('SELECT n.id,COALESCE(u.email,"全体"),n.title,n.type,n.read_at,n.created_at FROM notifications n LEFT JOIN users u ON u.id=n.user_id ORDER BY n.id DESC LIMIT 50').fetchall(); con.close()
        arows=''.join([f'<tr><td>{x[0]}</td><td>{esc(x[1])}</td><td>{esc(x[3])}</td><td>{esc(x[4])}</td><td>{time.strftime("%F %T",time.localtime(x[5]))}</td><td>{esc(x[2])}</td></tr>' for x in anns])
        opts='<option value="all">全体用户</option>'+''.join([f'<option value="{x[0]}">{esc(x[1])}</option>' for x in users])
        nrows=''.join([f'<tr><td>{x[0]}</td><td>{esc(x[1])}</td><td>{esc(x[2])}</td><td>{esc(x[3])}</td><td>{"已读" if x[4] else "未读"}</td><td>{time.strftime("%F %T",time.localtime(x[5]))}</td></tr>' for x in notes])
        body=f'<div class="card"><h2>发布公告</h2><form method="post" action="/announcements/update" class="actions"><input name="id" placeholder="ID 留空新增"><input name="title" placeholder="标题"><input name="content" placeholder="内容"><select name="status"><option value="active">启用</option><option value="disabled">停用</option></select><label><input type="checkbox" name="pinned" value="1">置顶</label><button class="btn">保存公告</button></form></div><div class="card"><h2>发送通知</h2><form method="post" action="/notifications/send" class="actions"><select name="target">{opts}</select><input name="title" placeholder="标题"><input name="content" placeholder="内容">{sensitive_fields(u)}<button class="btn">发送</button></form></div><div class="card"><h2>公告列表</h2><table><tr><th>ID</th><th>标题</th><th>状态</th><th>置顶</th><th>时间</th><th>内容</th></tr>{arows}</table></div><div class="card"><h2>最近通知</h2><table><tr><th>ID</th><th>用户</th><th>标题</th><th>类型</th><th>状态</th><th>时间</th></tr>{nrows}</table></div>'
        self.sendh(shell('公告通知',body,u,'admin'))

    def profile_page(self,u):
        d=api_get('/summary',u['sub2_user_id']); su=d.get('user') or ['','','','','','0','0']; st=d.get('stats') or ['0','0','0','0','0']
        con=db(); plan=con.execute('SELECT p.name,p.monthly_quota,p.daily_limit FROM user_plans up JOIN plans p ON p.id=up.plan_id WHERE up.user_id=?',(u['id'],)).fetchone(); models=con.execute('SELECT model FROM user_models WHERE user_id=? ORDER BY model',(u['id'],)).fetchall(); orders=con.execute('SELECT count(*),COALESCE(sum(amount),0) FROM recharge_orders WHERE user_id=? AND status="approved"',(u['id'],)).fetchone(); con.close()
        ms=', '.join([x[0] for x in models]) or '默认模型'; pn=plan[0] if plan else '普通会员'; daily=plan[2] if plan else '按默认策略'; monthly=plan[1] if plan else '按默认策略'
        security=f'<div class="card"><h2>修改密码</h2><form method="post" action="/profile/password" class="actions">{csrf_field(u)}<input name="old_password" type="password" placeholder="当前密码"><input name="new_password" type="password" placeholder="新密码，至少 8 位"><input name="confirm_password" type="password" placeholder="再次输入新密码"><button class="btn">更新密码</button></form><p class="muted">修改成功后，新密码将在下次登录时生效。</p></div>'
        body=f'<div class="grid"><div class="card"><div class="k">邮箱</div><div class="num" style="font-size:18px">{esc(u["email"])}</div></div><div class="card"><div class="k">套餐</div><div class="num">{esc(pn)}</div></div><div class="card"><div class="k">余额</div><div class="num">{fmt_usd_as_rmb(su[5])}</div></div><div class="card"><div class="k">累计消费</div><div class="num">{fmt_usd_as_rmb(st[4])}</div></div><div class="card"><div class="k">日限额</div><div class="num">{esc(daily)}</div></div><div class="card"><div class="k">月额度</div><div class="num">{esc(monthly)}</div></div><div class="card"><div class="k">注册时间</div><div class="num" style="font-size:18px">{time.strftime("%F",time.localtime(u["created_at"]))}</div></div></div><div class="card"><h2>模型权限</h2><p>{esc(ms)}</p></div>{security}'
        self.sendh(shell('个人资料',body,u,'profile'))

    def rollback_page(self,u):
        if u['role']!='admin': return self.redirect('/dashboard')
        con=db(); rows=con.execute('SELECT id,admin_email,action,target,status,created_at FROM rollback_logs ORDER BY id DESC LIMIT 80').fetchall(); con.close()
        trs=''.join([f'<tr><td>{x[0]}</td><td>{esc(x[1])}</td><td>{esc(x[2])}</td><td>{esc(x[3])}</td><td>{esc(x[4])}</td><td>{time.strftime("%F %T",time.localtime(x[5]))}</td></tr>' for x in rows])
        self.sendh(shell('回滚记录',f'<div class="card"><p>当前为回滚审计框架：危险操作先记录快照，自动撤销后续再启用。</p><table><tr><th>ID</th><th>管理员</th><th>动作</th><th>对象</th><th>状态</th><th>时间</th></tr>{trs}</table></div>',u,'admin'))

    def export_csv(self,u):
        typ=urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get('type',['users'])[0]
        qs=urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        con=db(); out=io.StringIO(); w=csv.writer(out)
        if typ=='usage':
            today=time.strftime('%Y-%m-%d'); start=qs.get('start',[today])[0] or today; end=qs.get('end',[today])[0] or today; model_filter=qs.get('model',[''])[0].strip()
            d=api_get('/stats?start='+urllib.parse.quote(start)+'&end='+urllib.parse.quote(end), u['sub2_user_id'])
            w.writerow(['section','date_or_model','cost','request','token','image'])
            for r in d.get('daily',[]): w.writerow(['daily',r[0],r[1],r[2],r[3],r[4]])
            for r in d.get('models',[]):
                if not model_filter or model_filter.lower() in str(r[0]).lower(): w.writerow(['model',r[0],r[1],r[2],r[3],''])
            con.close(); return self.sendcsv('usage.csv',out.getvalue())
        if typ=='billing-user':
            w.writerow(['created_at','direction','amount','note'])
            for r in con.execute('SELECT amount,note,created_at FROM billing_logs WHERE user_id=? ORDER BY id DESC',(u['id'],)):
                w.writerow([time.strftime('%F %T',time.localtime(r[2])),'credit' if float(r[0] or 0)>=0 else 'debit',r[0],r[1]])
            con.close(); return self.sendcsv('billing-user.csv',out.getvalue())
        if u['role']!='admin':
            con.close(); return self.redirect('/dashboard')
        if typ=='orders':
            w.writerow(['id','email','amount','method','note','status','admin_email','created_at','reviewed_at'])
            method=qs.get('method',[''])[0].strip()
            if method:
                order_iter=con.execute('SELECT o.id,u.email,o.amount,o.method,o.note,o.status,o.admin_email,o.created_at,o.reviewed_at FROM recharge_orders o JOIN users u ON u.id=o.user_id WHERE o.method=? ORDER BY o.id DESC',(method,))
            else:
                order_iter=con.execute('SELECT o.id,u.email,o.amount,o.method,o.note,o.status,o.admin_email,o.created_at,o.reviewed_at FROM recharge_orders o JOIN users u ON u.id=o.user_id ORDER BY o.id DESC')
            for r in order_iter:
                w.writerow([r[0],r[1],r[2],r[3],r[4],r[5],r[6],time.strftime('%F %T',time.localtime(r[7])), time.strftime('%F %T',time.localtime(r[8])) if r[8] else ''])
            name='orders.csv'
        elif typ=='billing':
            w.writerow(['id','user_id','email','admin_email','amount','note','created_at'])
            for r in con.execute('SELECT b.id,b.user_id,u.email,b.admin_email,b.amount,b.note,b.created_at FROM billing_logs b LEFT JOIN users u ON u.id=b.user_id ORDER BY b.id DESC'):
                w.writerow([r[0],r[1],r[2],r[3],r[4],r[5],time.strftime('%F %T',time.localtime(r[6]))])
            name='billing.csv'
        else:
            w.writerow(['id','email','role','status','created_at'])
            for r in con.execute('SELECT id,email,role,status,created_at FROM users WHERE status!="deleted" ORDER BY id DESC'):
                w.writerow([r[0],r[1],r[2],r[3],time.strftime('%F %T',time.localtime(r[4]))])
            name='users.csv'
        con.close(); return self.sendcsv(name,out.getvalue())

    def user_detail(self,u):
        if u['role']!='admin': return self.redirect('/dashboard')
        uid=int(urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get('id',['0'])[0] or 0)
        con=db(); tu=con.execute('SELECT * FROM users WHERE id=? AND status!="deleted"',(uid,)).fetchone()
        if not tu: con.close(); return self.sendh(shell('用户详情','<div class="card err">用户不存在</div>',u,'admin'),404)
        orders=con.execute('SELECT id,amount,method,note,status,created_at FROM recharge_orders WHERE user_id=? ORDER BY id DESC LIMIT 20',(uid,)).fetchall()
        bills=con.execute('SELECT amount,note,created_at FROM billing_logs WHERE user_id=? ORDER BY id DESC LIMIT 20',(uid,)).fetchall()
        models=con.execute('SELECT model FROM user_models WHERE user_id=? ORDER BY model',(uid,)).fetchall()
        con.close()
        summ=api_get('/summary',tu['sub2_user_id']); keys=api_get('/keys',tu['sub2_user_id']).get('keys',[]); usage=api_get('/usage',tu['sub2_user_id']).get('usage',[])
        su=summ.get('user') or ['','','','','','0','0']; st=summ.get('stats') or ['0','0','0','0','0']
        krows=''.join([f'<tr><td>{esc(x[0])}</td><td>{esc(brand_text(x[1]))}</td><td>{esc(x[2])}</td><td>{fmt_usd_as_rmb(x[4])}</td><td>{fmt_usd_as_rmb(x[5])}</td><td>{esc(x[6])}</td></tr>' for x in keys])
        urows=''.join([f'<tr><td>{esc(x[0])}</td><td>{esc(x[1] or x[6])}</td><td>{esc(x[2])}</td><td>{esc(x[3])}</td><td>{fmt_usd_as_rmb(x[5])}</td></tr>' for x in usage[:30]])
        orows=''.join([f'<tr><td>{x[0]}</td><td>{esc(brand_text(x[1]))}</td><td>{esc(x[2])}</td><td>{esc(x[4])}</td><td>{esc(x[3])}</td><td>{time.strftime("%F %T",time.localtime(x[5]))}</td></tr>' for x in orders])
        brows=''.join([f'<tr><td>{esc(x[0])}</td><td>{esc(x[1])}</td><td>{time.strftime("%F %T",time.localtime(x[2]))}</td></tr>' for x in bills])
        m=', '.join([x[0] for x in models]) or '默认模型'
        body=f'<div class="grid"><div class="card"><div class="k">邮箱</div><div class="num" style="font-size:18px">{esc(tu["email"])}</div></div><div class="card"><div class="k">状态</div><div class="num">{esc(tu["status"])}</div></div><div class="card"><div class="k">余额</div><div class="num">{fmt_usd_as_rmb(su[5])}</div></div><div class="card"><div class="k">累计消费</div><div class="num">{fmt_usd_as_rmb(st[4])}</div></div></div><div class="card"><p>模型：{esc(m)}</p></div><div class="card"><h2>Key</h2><table><tr><th>ID</th><th>名称</th><th>状态</th><th>额度</th><th>已用</th><th>最后使用</th></tr>{krows}</table></div><div class="card"><h2>最近调用</h2><table><tr><th>时间</th><th>模型</th><th>输入</th><th>输出</th><th>费用</th></tr>{urows}</table></div>'
        self.sendh(shell('用户详情',body,u,'admin'))


    def admin_update(self,u):
        if not u: return self.redirect('/login')
        if u.get('role')!='admin': return self.redirect('/dashboard')
        st=update_state(True)
        log_tail=''
        try:
            if os.path.exists(UPDATE_LOG):
                with open(UPDATE_LOG,'r',errors='replace') as f:
                    log_tail=''.join(f.readlines()[-40:])
        except Exception as e:
            log_tail=str(e)
        if st.get('available'):
            status=f'<div class="card" style="border-color:#fde68a;background:#fffbeb"><h2>发现新版本</h2><p>当前版本：<b>{esc(APP_VERSION)}</b></p><p>本地提交：{esc(st.get("local"))}</p><p>Git 最新：{esc(st.get("remote"))}</p><form method="post" action="/admin-update/apply" class="actions">{csrf_field(u)}<button class="btn">拉取 Git 并更新</button></form></div>'
        elif st.get('ok'):
            status=f'<div class="card"><h2>已是最新</h2><p>当前版本：<b>{esc(APP_VERSION)}</b></p><p>当前提交：{esc(st.get("local"))}</p><p class="muted">分支：{esc(st.get("branch","main"))}</p></div>'
        else:
            status=f'<div class="card err"><h2>检查失败</h2><p>{esc(st.get("error"))}</p></div>'
        body=status+f'<div class="card"><h2>更新说明</h2><p>此入口仅管理员可见；点击更新后直接执行：Git 拉取最新代码 → 部署脚本覆盖文件 → 重启门户服务。无需再次输入管理员密码。</p><p class="muted">仓库目录：{esc(REPO_DIR)}</p></div><div class="card"><h2>最近更新日志</h2><pre>{esc(log_tail or "暂无日志")}</pre></div>'
        self.sendh(shell('系统更新',body,u,'admin_update'))

    def admin_usage(self,u):
        if u['role']!='admin': return self.redirect('/dashboard')
        qs=urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        today=time.strftime('%Y-%m-%d', time.localtime())
        start=qs.get('start',[today])[0].strip() or today
        end=qs.get('end',[today])[0].strip() or today
        q=qs.get('q',[''])[0].strip().lower()
        con=db()
        rows=con.execute('SELECT id,email,sub2_user_id,role,status,created_at FROM users WHERE status!="deleted" ORDER BY id').fetchall()
        con.close()
        data=[]
        totals={'cost':0.0,'req':0,'input':0,'output':0,'cache':0,'total_tokens':0}
        for r in rows:
            if q and q not in (r['email'] or '').lower(): continue
            try:
                st=api_get('/stats?start='+urllib.parse.quote(start)+'&end='+urllib.parse.quote(end), r['sub2_user_id'])
                t=st.get('total') or []
                cost=float(t[0] or 0) if len(t)>0 else 0.0; req=int(float(t[1] or 0)) if len(t)>1 else 0
                total_tokens=int(float(t[3] or 0)) if len(t)>3 else 0; input_tokens=int(float(t[5] or 0)) if len(t)>5 else 0
                output_tokens=int(float(t[6] or 0)) if len(t)>6 else 0; cache_tokens=int(float(t[7] or 0)) if len(t)>7 else 0
            except Exception:
                cost=0.0; req=0; total_tokens=0; input_tokens=0; output_tokens=0; cache_tokens=0
            totals['cost']+=cost; totals['req']+=req; totals['input']+=input_tokens; totals['output']+=output_tokens; totals['cache']+=cache_tokens; totals['total_tokens']+=total_tokens
            data.append((r['id'],r['email'],r['role'],r['status'],r['sub2_user_id'],cost,req,input_tokens,cache_tokens,output_tokens,total_tokens))
        data.sort(key=lambda x:x[5], reverse=True)
        def nfmt(v):
            try: return f'{int(v):,}'
            except Exception: return esc(v)
        trs=''.join([f'<tr><td>{x[0]}</td><td><a href="/user-detail?id={x[0]}">{esc(x[1])}</a><br><span class="muted">用户编号 {x[4]} · {esc(x[2])}/{esc(x[3])}</span></td><td>{fmt_usd_as_rmb(x[5])}<br><span class="muted">${fmt_price(x[5])}</span></td><td>{nfmt(x[6])}</td><td>{nfmt(x[7])}</td><td>{nfmt(x[8])}</td><td>{nfmt(x[9])}</td><td>{nfmt(x[10])}</td></tr>' for x in data])
        if not trs: trs='<tr><td colspan="8" class="muted">无数据</td></tr>'
        body=f'''<div class="grid"><div class="card"><div class="k">实际消耗</div><div class="num">{fmt_usd_as_rmb(totals['cost'])}</div><p class="muted">${fmt_price(totals['cost'])}</p></div><div class="card"><div class="k">请求数</div><div class="num">{nfmt(totals['req'])}</div></div><div class="card"><div class="k">总 Token</div><div class="num">{nfmt(totals['total_tokens'])}</div></div><div class="card"><div class="k">输入/缓存/输出</div><div class="num" style="font-size:17px">{nfmt(totals['input'])} / {nfmt(totals['cache'])} / {nfmt(totals['output'])}</div></div></div><div class="card"><form method="get" class="actions"><input name="start" type="date" value="{esc(start)}"><input name="end" type="date" value="{esc(end)}"><input name="q" placeholder="邮箱搜索" value="{esc(q)}"><button class="btn">查询</button><a class="btn btn2" href="/admin-usage">今天</a></form><p class="muted">按后台实际扣费记录汇总；金额按 1 USD = 7 RMB 折算。输入/缓存/输出分别对应输入、缓存读取、输出 token。</p></div><div class="card"><table><tr><th>门户ID</th><th>账号</th><th>实际消耗</th><th>请求</th><th>输入Token</th><th>缓存Token</th><th>输出Token</th><th>总Token</th></tr>{trs}</table></div>'''
        self.sendh(shell('账号消耗统计',body,dict(u),'admin_usage'))

    def api_logs(self,u):
        if u['role']!='admin': return self.redirect('/dashboard')
        qs=urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        uid=int(qs.get('id',['0'])[0] or 0); model=qs.get('model',[''])[0].strip(); ip=qs.get('ip',[''])[0].strip(); status=qs.get('status',[''])[0].strip(); start=qs.get('start',[''])[0].strip(); end=qs.get('end',[''])[0].strip(); page=clamp_int(qs.get('page',['1'])[0]); size=100
        con=db(); users=con.execute('SELECT id,email,sub2_user_id FROM users WHERE status!="deleted" ORDER BY id').fetchall()
        where=[]; params=[]
        if uid: where.append('l.user_id=?'); params.append(uid)
        if model: where.append('l.model LIKE ?'); params.append('%'+model+'%')
        if ip: where.append('l.ip LIKE ?'); params.append('%'+ip+'%')
        if status: where.append('l.status=?'); params.append(int(status))
        ds=day_start(start); de=day_start(end)
        if ds: where.append('l.created_at>=?'); params.append(ds)
        if de: where.append('l.created_at<?'); params.append(de+86400)
        sql='SELECT l.created_at,u.email,l.ip,l.method,l.path,l.model,l.status,l.error_code,l.latency_ms FROM api_access_logs l LEFT JOIN users u ON u.id=l.user_id'
        if where: sql+=' WHERE '+ ' AND '.join(where)
        wh=(' WHERE '+ ' AND '.join(where)) if where else ''
        total=con.execute('SELECT count(*) FROM api_access_logs l LEFT JOIN users u ON u.id=l.user_id'+wh,params).fetchone()[0]
        sql+=' ORDER BY l.id DESC LIMIT ? OFFSET ?'
        rows=con.execute(sql,params+[size,(page-1)*size]).fetchall(); con.close()
        opts='<option value="0">全部用户</option>'+''.join([f'<option value="{x[0]}" {"selected" if uid==x[0] else ""}>{esc(x[1])}</option>' for x in users])
        trs=''.join([f'<tr><td>{time.strftime("%F %T",time.localtime(x[0]))}</td><td>{esc(x[1])}</td><td>{esc(mask_ip(x[2]))}</td><td>{esc(x[3])}</td><td>{esc(x[4])}</td><td>{esc(x[5])}</td><td>{esc(x[6])}</td><td>{esc(x[7])}</td><td>{esc(x[8])}</td></tr>' for x in rows])
        body=f'<div class="card"><form method="get" class="actions"><select name="id">{opts}</select><input name="model" placeholder="模型" value="{esc(model)}"><input name="ip" placeholder="IP" value="{esc(ip)}"><input name="status" placeholder="状态码" value="{esc(status)}"><input name="start" type="date" value="{esc(start)}"><input name="end" type="date" value="{esc(end)}"><button class="btn">查询</button></form><p class="muted">API 日志保留 90 天，自动清理旧记录。</p></div><div class="card">{pager("/api-logs",qs,page,size,total)}<table><tr><th>时间</th><th>用户</th><th>IP</th><th>方法</th><th>路径</th><th>模型</th><th>状态</th><th>错误</th><th>耗时ms</th></tr>{trs}</table>{pager("/api-logs",qs,page,size,total)}</div>'
        self.sendh(shell('调用日志',body,u,'admin'))

    def admin_users(self,u):
        if u['role']!='admin': return self.redirect('/dashboard')
        qs=urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query); q=qs.get('q',[''])[0].strip(); method_filter=qs.get('method',[''])[0].strip(); role_filter=qs.get('role',[''])[0].strip(); user_status=qs.get('user_status',[''])[0].strip(); order_status=qs.get('order_status',[''])[0].strip(); audit_q=qs.get('audit_q',[''])[0].strip(); audit_type=qs.get('audit_type',[''])[0].strip(); log_q=qs.get('log_q',[''])[0].strip(); log_action=qs.get('log_action',[''])[0].strip(); user_page=clamp_int(qs.get('user_page',['1'])[0]); order_page=clamp_int(qs.get('order_page',['1'])[0]); audit_page=clamp_int(qs.get('audit_page',['1'])[0]); log_page=clamp_int(qs.get('log_page',['1'])[0]); size=40
        con=db(); prices=[r[0] for r in con.execute('SELECT model FROM model_prices ORDER BY model').fetchall()]; plans=con.execute('SELECT id,name FROM plans WHERE status="active" ORDER BY price').fetchall(); methods=con.execute('SELECT id,name,kind,instructions,enabled,sort_order,updated_at FROM payment_methods ORDER BY sort_order,id').fetchall()
        user_where=['status!="deleted"']; user_params=[]
        if q: user_where.append('email LIKE ?'); user_params.append('%'+q+'%')
        if role_filter: user_where.append('role=?'); user_params.append(role_filter)
        if user_status: user_where.append('status=?'); user_params.append(user_status)
        user_wh=' WHERE '+ ' AND '.join(user_where)
        user_total=con.execute('SELECT count(*) FROM users'+user_wh,user_params).fetchone()[0]
        us=con.execute('SELECT id,email,role,sub2_user_id,status,created_at FROM users'+user_wh+' ORDER BY id DESC LIMIT ? OFFSET ?',user_params+[size,(user_page-1)*size]).fetchall()
        oq='%'+q+'%'; order_where=['(?="" OR u.email LIKE ? OR o.note LIKE ? OR o.method LIKE ? OR o.status LIKE ?)']; order_params=[q,oq,oq,oq,oq]
        if method_filter: order_where.append('o.method=?'); order_params.append(method_filter)
        if order_status: order_where.append('o.status=?'); order_params.append(order_status)
        order_wh=' WHERE '+ ' AND '.join(order_where)
        order_total=con.execute('SELECT count(*) FROM recharge_orders o JOIN users u ON u.id=o.user_id'+order_wh,order_params).fetchone()[0]
        orders=con.execute('SELECT o.id,u.email,o.amount,o.method,o.note,o.status,o.admin_email,o.created_at,o.reviewed_at FROM recharge_orders o JOIN users u ON u.id=o.user_id '+order_wh+' ORDER BY CASE o.status WHEN "pending" THEN 0 WHEN "rejected" THEN 1 ELSE 2 END,o.id DESC LIMIT ? OFFSET ?',order_params+[size,(order_page-1)*size]).fetchall()
        bill_where=[]; bill_params=[]
        if audit_q: bill_where.append('(u.email LIKE ? OR b.admin_email LIKE ? OR b.note LIKE ?)'); bill_params += ['%'+audit_q+'%']*3
        if audit_type=='credit': bill_where.append('b.amount>=0')
        if audit_type=='debit': bill_where.append('b.amount<0')
        bill_wh=' WHERE '+ ' AND '.join(bill_where) if bill_where else ''
        bill_total=con.execute('SELECT count(*) FROM billing_logs b LEFT JOIN users u ON u.id=b.user_id'+bill_wh,bill_params).fetchone()[0]
        bills=con.execute('SELECT b.id,b.user_id,u.email,b.admin_email,b.amount,b.note,b.created_at FROM billing_logs b LEFT JOIN users u ON u.id=b.user_id'+bill_wh+' ORDER BY b.id DESC LIMIT ? OFFSET ?',bill_params+[size,(audit_page-1)*size]).fetchall()
        log_where=[]; log_params=[]
        if log_q: log_where.append('(admin_email LIKE ? OR target LIKE ? OR detail LIKE ?)'); log_params += ['%'+log_q+'%']*3
        if log_action: log_where.append('action LIKE ?'); log_params.append('%'+log_action+'%')
        log_wh=' WHERE '+ ' AND '.join(log_where) if log_where else ''
        log_total=con.execute('SELECT count(*) FROM ops_log'+log_wh,log_params).fetchone()[0]
        logs=con.execute('SELECT id,admin_email,action,target,detail,created_at FROM ops_log'+log_wh+' ORDER BY id DESC LIMIT ? OFFSET ?',log_params+[size,(log_page-1)*size]).fetchall(); con.close()
        plan_opts=''.join([f'<option value="{p[0]}">{esc(p[1])}</option>' for p in plans])
        def pill_status(v):
            m={'active':('启用','ok'),'disabled':('停用','bad'),'pending':('待审核','warn'),'approved':('已通过','ok'),'rejected':('未通过','bad'),'admin':('管理员','warn'),'user':('用户','ok')}
            text,cls=m.get(str(v),(str(v),'warn'))
            return f'<span class="ua-pill {cls}">{esc(text)}</span>'
        def short_dt(ts):
            try: return time.strftime('%m-%d %H:%M',time.localtime(ts))
            except Exception: return ''
        def money_rmb(v):
            try: return fmt_rmb(float(v or 0))
            except Exception: return '¥'+esc(v or '0')
        user_bal={}
        for x in us:
            try:
                sd=api_get('/summary',x[3]); su=sd.get('user') or []
                user_bal[x[0]]=fmt_usd_as_rmb(su[5] if len(su)>5 else 0)
            except Exception:
                user_bal[x[0]]='-'
        rows=[]
        for x in us:
            action=f'<div class="ua-actions"><a class="btn btn2" href="/user-detail?id={x[0]}">详情</a></div>'
            if x[2] != 'admin':
                model_opts=','.join(prices)
                action=(f'<details><summary>账户</summary><form method="post" action="/users-admin/update" class="ua-form"><input type="hidden" name="id" value="{x[0]}"><input name="balance" placeholder="余额，人民币"><input name="daily_limit" placeholder="日限额，人民币"><input name="weekly_limit" placeholder="周限额，人民币"><input name="monthly_limit" placeholder="月限额，人民币"><input name="concurrency" placeholder="并发" value="5"><select name="status"><option value="active">启用</option><option value="disabled">禁用</option></select>{sensitive_fields(u)}<button class="btn btn2">保存</button></form></details>'
                        f'<details><summary>权限</summary><form method="post" action="/users-admin/plan" class="ua-form"><input type="hidden" name="id" value="{x[0]}"><select name="plan_id">{plan_opts}</select>{sensitive_fields(u)}<button class="btn btn2">分配套餐</button></form><form method="post" action="/users-admin/models" class="ua-form"><input type="hidden" name="id" value="{x[0]}"><input name="models" value="{esc(model_opts)}">{sensitive_fields(u)}<button class="btn btn2">模型权限</button></form></details>'
                        f'<div class="ua-actions"><a class="btn btn2" href="/user-detail?id={x[0]}">详情</a><form method="post" action="/users-admin/delete" onsubmit="return confirm(&quot;确认删除该用户？&quot;)"><input type="hidden" name="id" value="{x[0]}">{sensitive_fields(u)}<button class="btn btn2">删除</button></form></div>')
            rows.append(f'<tr><td><b>#{x[0]}</b><br><span class="muted">Sub {x[3]}</span></td><td><b>{esc(brand_text(x[1]))}</b><br><span class="muted">{short_dt(x[5])}</span></td><td>{pill_status(x[2])}</td><td>{pill_status(x[4])}</td><td><b>{user_bal.get(x[0],"-")}</b></td><td>{action}</td></tr>')
        trs=''.join(rows)
        status_map={'pending':'待审核','approved':'已通过','rejected':'未通过'}
        order_rows=[]
        for x in orders:
            op='<span class="muted">只读</span>'
            reviewed=time.strftime('%F %T',time.localtime(x[8])) if x[8] else ''
            order_rows.append(f'<tr><td><b>#{x[0]}</b><br><span class="muted">{short_dt(x[7])}</span></td><td>{esc(x[1])}</td><td><b>{money_rmb(x[2])}</b><br><span class="muted">{esc(x[3])}</span></td><td>{pill_status(x[5])}</td><td>{esc(x[4])}</td><td>{esc(x[6] or "")}<br><span class="muted">{reviewed}</span></td><td>{op}</td></tr>')
        ors=''.join(order_rows)
        lrs=''.join([f'<tr><td>#{x[0]}<br><span class="muted">{short_dt(x[5])}</span></td><td>{esc(x[1])}</td><td>{esc(x[2])}</td><td>{esc(x[3])}</td><td>{esc(x[4])}</td></tr>' for x in logs])
        brs=''.join([f'<tr><td>#{x[0]}<br><span class="muted">{short_dt(x[6])}</span></td><td>{esc(x[2])}<br><span class="muted">ID {esc(x[1])}</span></td><td>{esc(x[3])}</td><td><b>{money_rmb(x[4])}</b></td><td>{esc(x[5])}</td></tr>' for x in bills])
        method_opts='<option value="">全部收款方式</option>'+''.join([f'<option value="{esc(x["name"])}" {"selected" if method_filter==x["name"] else ""}>{esc(x["name"])}</option>' for x in methods])
        payment_rows=''.join([f'<tr><td>{x["id"]}</td><td><b>{esc(x["name"])}</b><br><span class="muted">{esc(x["kind"])}</span></td><td>{esc(x["instructions"])}</td><td>{"启用" if x["enabled"] else "停用"}</td><td>{esc(x["sort_order"])}</td><td><form method="post" action="/users-admin/payment-method" class="ua-form inline"><input type="hidden" name="id" value="{x["id"]}"><input name="name" value="{esc(x["name"])}"><select name="kind"><option value="alipay" {"selected" if x["kind"]=="alipay" else ""}>支付宝</option><option value="wechat" {"selected" if x["kind"]=="wechat" else ""}>微信</option><option value="bank" {"selected" if x["kind"]=="bank" else ""}>银行</option><option value="manual" {"selected" if x["kind"]=="manual" else ""}>人工</option></select><input name="instructions" value="{esc(x["instructions"])}"><select name="enabled"><option value="1" {"selected" if x["enabled"] else ""}>启用</option><option value="0" {"selected" if not x["enabled"] else ""}>停用</option></select><input name="sort_order" value="{esc(x["sort_order"])}">{sensitive_fields(u)}<button class="btn btn2">保存</button></form></td></tr>' for x in methods])
        new_payment=f'<form method="post" action="/users-admin/payment-method" class="ua-form inline"><input name="name" placeholder="方式名称"><select name="kind"><option value="alipay">支付宝</option><option value="wechat">微信</option><option value="bank">银行</option><option value="manual">人工</option></select><input name="instructions" placeholder="前台展示说明"><select name="enabled"><option value="1">启用</option><option value="0">停用</option></select><input name="sort_order" placeholder="排序">{sensitive_fields(u)}<button class="btn">新增收款方式</button></form>'
        export_orders='/export.csv?type=orders' + (('&method='+urllib.parse.quote(method_filter)) if method_filter else '')
        user_filters=f'<form method="get" action="/users-admin" class="ua-filter"><input name="q" placeholder="搜索邮箱/备注" value="{esc(q)}"><select name="role"><option value="">全部角色</option><option value="user" {"selected" if role_filter=="user" else ""}>用户</option><option value="admin" {"selected" if role_filter=="admin" else ""}>管理员</option></select><select name="user_status"><option value="">全部状态</option><option value="active" {"selected" if user_status=="active" else ""}>启用</option><option value="disabled" {"selected" if user_status=="disabled" else ""}>停用</option></select><button class="btn btn2">筛选用户</button><a class="btn btn2" href="/users-admin">重置</a></form>'
        order_filters=f'<form method="get" action="/users-admin" class="ua-filter"><input name="q" placeholder="搜索邮箱/备注/状态" value="{esc(q)}"><select name="method">{method_opts}</select><select name="order_status"><option value="">全部记录</option><option value="pending" {"selected" if order_status=="pending" else ""}>待审核</option><option value="approved" {"selected" if order_status=="approved" else ""}>已通过</option><option value="rejected" {"selected" if order_status=="rejected" else ""}>未通过</option></select><button class="btn btn2">筛选订单</button></form>'
        audit_filters=f'<form method="get" action="/users-admin" class="ua-filter"><input name="audit_q" placeholder="用户/管理员/备注" value="{esc(audit_q)}"><select name="audit_type"><option value="">全部流水</option><option value="credit" {"selected" if audit_type=="credit" else ""}>增加</option><option value="debit" {"selected" if audit_type=="debit" else ""}>扣减</option></select><button class="btn btn2">筛选流水</button></form>'
        log_filters=f'<form method="get" action="/users-admin" class="ua-filter"><input name="log_q" placeholder="管理员/对象/详情" value="{esc(log_q)}"><input name="log_action" placeholder="动作" value="{esc(log_action)}"><button class="btn btn2">筛选日志</button></form>'
        summary=f'<section class="ua-summary"><div class="metric"><div class="label">用户</div><div class="value">{user_total}</div><div class="sub">当前筛选</div></div><div class="metric"><div class="label">日志</div><div class="value">{log_total}</div><div class="sub">管理操作</div></div></section>'
        css='<style>.ua-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin-bottom:14px}.ua-card h2{display:flex;justify-content:space-between;align-items:center}.ua-filter,.ua-form,.ua-actions{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.ua-filter{background:#f8fafc;border:1px solid #e5e7eb;border-radius:14px;padding:10px;margin:10px 0}.ua-form{margin:8px 0}.ua-form.inline{margin:0}.ua-form input,.ua-form select{width:auto;min-width:88px}.ua-form input[name="models"],.ua-form input[name="instructions"]{min-width:260px}.ua-pill{display:inline-flex;border-radius:999px;padding:4px 9px;font-size:12px;font-weight:800}.ua-pill.ok{background:#dcfce7;color:#166534}.ua-pill.warn{background:#fef9c3;color:#854d0e}.ua-pill.bad{background:#fee2e2;color:#991b1b}details{border:1px solid #e5e7eb;border-radius:12px;padding:7px 9px;margin:5px 0;background:#fbfdff}summary{cursor:pointer;font-weight:800;color:#334155}@media(max-width:900px){.ua-summary{grid-template-columns:1fr 1fr}}@media(max-width:560px){.ua-summary{grid-template-columns:1fr}.ua-filter,.ua-form{display:grid}.ua-form input,.ua-form select,.ua-filter input,.ua-filter select{width:100%}}</style>'
        body=css+summary+f'<div class="card ua-card"><h2>用户列表 <span class="actions"><a class="btn btn2" href="/export.csv?type=users">导出用户</a></span></h2>{user_filters}{pager("/users-admin",qs,user_page,size,user_total,"user_page")}<table><tr><th>ID</th><th>用户</th><th>角色</th><th>状态</th><th>余额</th><th>操作</th></tr>{trs}</table>{pager("/users-admin",qs,user_page,size,user_total,"user_page")}</div><div class="card ua-card"><h2>操作日志</h2>{log_filters}{pager("/users-admin",qs,log_page,size,log_total,"log_page")}<table><tr><th>ID/时间</th><th>管理员</th><th>动作</th><th>对象</th><th>详情</th></tr>{lrs}</table>{pager("/users-admin",qs,log_page,size,log_total,"log_page")}</div>'
        self.sendh(shell('用户管理',body,u,'admin'))


if __name__=='__main__': init_db(); ThreadingHTTPServer((HOST,PORT),H).serve_forever()
