#!/usr/bin/env python3
import json, secrets, subprocess, urllib.parse, re, bcrypt, time, sys, os
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

def sh(cmd, input_text=None):
    r=subprocess.run(cmd,shell=True,text=True,input=input_text,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=25)
    if r.returncode!=0: raise RuntimeError(r.stderr.strip() or r.stdout.strip())
    return r.stdout

def sql(q):
    return sh("sudo docker exec -i sub2api-postgres psql -U sub2api -d sub2api -AtF '|' -v ON_ERROR_STOP=1", q)

def log_slow(name, start):
    dt=time.monotonic()-start
    if dt > 1:
        print(f'xapi-data slow {name} {dt:.3f}s', file=sys.stderr, flush=True)

def sections(q):
    out=sql(q).strip('\n')
    data={}; cur=None
    for line in out.splitlines() if out else []:
        if line.startswith('__') and line.endswith('__'):
            cur=line.strip('_').lower(); data[cur]=[]
        elif cur:
            data[cur].append(line.split('|'))
    return data

def rows(q):
    out=sql(q).strip('\n')
    return [] if not out else [line.split('|') for line in out.splitlines()]

def one(q):
    r=rows(q); return r[0] if r else None

def esc_sql(s): return str(s).replace("'","''")

def js(o): return json.dumps(o,ensure_ascii=False).encode()

def bcrypt_hash(pw):
    return bcrypt.hashpw(str(pw).encode(), bcrypt.gensalt()).decode()

def bcrypt_check(pw, ph):
    try:
        return bcrypt.checkpw(str(pw).encode(), str(ph).encode())
    except Exception:
        return False

def strong_pw(): return secrets.token_urlsafe(36)

def clear_cache():
    try:
        sh('sudo docker exec sub2api-redis redis-cli FLUSHDB >/dev/null 2>&1 || true')
    except Exception:
        pass

def restart_gateway():
    try:
        sh('sudo docker restart sub2api >/dev/null && sleep 3')
    except Exception:
        pass

def create_user(email, username, password=None):
    email=email.strip().lower(); username=(username.strip() or email.split('@')[0])[:64]
    if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email): raise RuntimeError('invalid email')
    old=one(f"SELECT id,password_hash,status FROM users WHERE email='{esc_sql(email)}' AND deleted_at IS NULL")
    if old:
        if password and not bcrypt_check(password, old[1]): raise RuntimeError('password mismatch for existing sub2 user')
        return {'sub2_user_id': old[0], 'existed': True, 'status': old[2]}
    pw=password or strong_pw(); ph=bcrypt_hash(pw)
    q=f"""
    WITH u AS (
      INSERT INTO users (email,username,password_hash,role,balance,concurrency,status,notes,signup_source)
      VALUES ('{esc_sql(email)}','{esc_sql(username)}','{esc_sql(ph)}','user',0,5,'active','created by XAPI portal','email')
      RETURNING id
    )
    INSERT INTO user_allowed_groups (user_id, group_id) SELECT id, 2 FROM u
    ON CONFLICT DO NOTHING
    RETURNING user_id;
    """
    r=one(q)
    uid=(r and r[0]) or one(f"SELECT id FROM users WHERE email='{esc_sql(email)}' AND deleted_at IS NULL")[0]
    sql(f"INSERT INTO user_platform_quotas (user_id,platform,daily_limit_usd,weekly_limit_usd,monthly_limit_usd,daily_usage_usd,weekly_usage_usd,monthly_usage_usd) VALUES ({uid},'openai',NULL,NULL,NULL,0,0,0) ON CONFLICT DO NOTHING")
    sql(f"INSERT INTO user_subscriptions (user_id,group_id,starts_at,expires_at,status,daily_usage_usd,weekly_usage_usd,monthly_usage_usd,assigned_by,assigned_at,notes) VALUES ({uid},2,now(),now()+interval '365 days','active',0,0,0,1,now(),'created by XAPI portal') ON CONFLICT DO NOTHING")
    return {'sub2_user_id': uid, 'existed': False}

def user_clause(uid):
    uid=int(uid); return f"user_id={uid}"

def auth_user(email, password):
    email=email.strip().lower()
    if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email): raise RuntimeError('invalid email')
    r=one(f"SELECT id,password_hash,status,role FROM users WHERE email='{esc_sql(email)}' AND deleted_at IS NULL")
    if not r or r[2] != 'active' or not bcrypt_check(password or '', r[1]):
        return {'ok': False}
    return {'ok': True, 'sub2_user_id': r[0], 'status': r[2], 'role': r[3]}

def set_user_password(uid, password):
    uid=int(uid)
    if uid<=0 or not password: raise RuntimeError('invalid password')
    ph=bcrypt_hash(password)
    sql(f"UPDATE users SET password_hash='{esc_sql(ph)}',updated_at=now() WHERE id={uid} AND deleted_at IS NULL")
    return {'ok': True}


class H(BaseHTTPRequestHandler):
    def sendj(self,o,code=200):
        b=js(o); self.send_response(code); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)
    def body(self):
        ln=int(self.headers.get('Content-Length','0')); return json.loads(self.rfile.read(ln) or b'{}')
    def do_GET(self):
        p=urllib.parse.urlparse(self.path); path=p.path; qs=urllib.parse.parse_qs(p.query); uid=int(qs.get('uid',['1'])[0])
        try:
            if path=='/xapi-data/health': return self.sendj({'ok':True})
            if path=='/xapi-data/dashboard':
                start=time.monotonic()
                today=time.strftime('%Y-%m-%d')
                where=f"user_id={uid}"
                today_where=where + f" AND created_at >= '{esc_sql(today)} 00:00:00+08' AND created_at < ('{esc_sql(today)} 00:00:00+08'::timestamptz + interval '1 day')"
                data=sections(f"""
SELECT '__USER__';
SELECT id,email,COALESCE(username,''),role,status,balance,total_recharged FROM users WHERE id={uid} AND deleted_at IS NULL;
SELECT '__STATS__';
SELECT count(*),COALESCE(sum(input_tokens),0),COALESCE(sum(output_tokens),0),COALESCE(sum(cache_read_tokens+cache_creation_tokens),0),COALESCE(sum(total_cost),0) FROM usage_logs WHERE {where};
SELECT '__TODAY__';
SELECT COALESCE(sum(total_cost),0),count(*),COALESCE(sum(CASE WHEN COALESCE(request_type,0)=1 THEN 1 ELSE 0 END),0),COALESCE(sum(COALESCE(input_tokens,0)+COALESCE(output_tokens,0)+COALESCE(cache_creation_tokens,0)+COALESCE(cache_read_tokens,0)+COALESCE(image_output_tokens,0)),0),COALESCE(sum(COALESCE(image_count,0)),0),COALESCE(sum(input_tokens),0),COALESCE(sum(output_tokens),0),COALESCE(sum(cache_creation_tokens+cache_read_tokens),0) FROM usage_logs WHERE {today_where};
SELECT '__USAGE__';
SELECT COALESCE(to_char(created_at AT TIME ZONE 'Asia/Shanghai','YYYY-MM-DD HH24:MI'),''),COALESCE(model,''),COALESCE(input_tokens,0),COALESCE(output_tokens,0),COALESCE(cache_read_tokens+cache_creation_tokens,0),COALESCE(total_cost,0),COALESCE(requested_model,'') FROM usage_logs WHERE {where} ORDER BY id DESC LIMIT 8;
SELECT '__KEYS__';
SELECT id,name,status,CASE WHEN length(key)>10 THEN left(key,6)||repeat('*',GREATEST(length(key)-10,4))||right(key,4) ELSE left(key,1)||'****'||right(key,1) END,COALESCE(quota,0),COALESCE(quota_used,0),COALESCE(to_char(last_used_at AT TIME ZONE 'Asia/Shanghai','YYYY-MM-DD HH24:MI'),'') FROM api_keys WHERE deleted_at IS NULL AND user_id={uid} ORDER BY id DESC LIMIT 50;
""")
                log_slow('dashboard', start)
                return self.sendj({'user':(data.get('user') or [None])[0], 'stats':(data.get('stats') or [['0','0','0','0','0']])[0], 'today':(data.get('today') or [['0','0','0','0','0','0','0','0']])[0], 'usage':data.get('usage') or [], 'keys':data.get('keys') or []})
            if path=='/xapi-data/summary':
                u=one(f"SELECT id,email,COALESCE(username,''),role,status,balance,total_recharged FROM users WHERE id={uid} AND deleted_at IS NULL")
                s=one(f"SELECT count(*),COALESCE(sum(input_tokens),0),COALESCE(sum(output_tokens),0),COALESCE(sum(cache_read_tokens+cache_creation_tokens),0),COALESCE(sum(total_cost),0) FROM usage_logs WHERE user_id={uid}")
                return self.sendj({'user':u,'stats':s or ['0','0','0','0','0']})
            if path=='/xapi-data/keys':
                k=rows(f"SELECT id,name,status,CASE WHEN length(key)>10 THEN left(key,6)||repeat('*',GREATEST(length(key)-10,4))||right(key,4) ELSE left(key,1)||'****'||right(key,1) END,COALESCE(quota,0),COALESCE(quota_used,0),COALESCE(to_char(last_used_at AT TIME ZONE 'Asia/Shanghai','YYYY-MM-DD HH24:MI'),'') FROM api_keys WHERE deleted_at IS NULL AND user_id={uid} ORDER BY id DESC LIMIT 50")
                return self.sendj({'keys':k})
            if path=='/xapi-data/usage':
                u=rows(f"SELECT COALESCE(to_char(created_at AT TIME ZONE 'Asia/Shanghai','YYYY-MM-DD HH24:MI'),''),COALESCE(model,''),COALESCE(input_tokens,0),COALESCE(output_tokens,0),COALESCE(cache_read_tokens+cache_creation_tokens,0),COALESCE(total_cost,0),COALESCE(requested_model,'') FROM usage_logs WHERE user_id={uid} ORDER BY id DESC LIMIT 60")
                return self.sendj({'usage':u})
            if path=='/xapi-data/stats':
                start=(qs.get('start',[''])[0] or '').strip(); end=(qs.get('end',[''])[0] or '').strip()
                where=f"user_id={uid}"
                if start: where += f" AND created_at >= '{esc_sql(start)} 00:00:00+08'"
                if end: where += f" AND created_at < ('{esc_sql(end)} 00:00:00+08'::timestamptz + interval '1 day')"
                total=one(f"SELECT COALESCE(sum(total_cost),0),count(*),COALESCE(sum(CASE WHEN COALESCE(request_type,0)=1 THEN 1 ELSE 0 END),0),COALESCE(sum(COALESCE(input_tokens,0)+COALESCE(output_tokens,0)+COALESCE(cache_creation_tokens,0)+COALESCE(cache_read_tokens,0)+COALESCE(image_output_tokens,0)),0),COALESCE(sum(COALESCE(image_count,0)),0),COALESCE(sum(input_tokens),0),COALESCE(sum(output_tokens),0),COALESCE(sum(cache_creation_tokens+cache_read_tokens),0) FROM usage_logs WHERE {where}") or ['0','0','0','0','0','0','0','0']
                daily=rows(f"SELECT to_char(created_at AT TIME ZONE 'Asia/Shanghai','YYYY-MM-DD'),COALESCE(sum(total_cost),0),count(*),COALESCE(sum(COALESCE(input_tokens,0)+COALESCE(output_tokens,0)+COALESCE(cache_creation_tokens,0)+COALESCE(cache_read_tokens,0)+COALESCE(image_output_tokens,0)),0),COALESCE(sum(COALESCE(image_count,0)),0) FROM usage_logs WHERE {where} GROUP BY 1 ORDER BY 1 DESC LIMIT 31")
                models=rows(f"SELECT COALESCE(requested_model,model,''),COALESCE(sum(total_cost),0),count(*),COALESCE(sum(COALESCE(input_tokens,0)+COALESCE(output_tokens,0)+COALESCE(cache_creation_tokens,0)+COALESCE(cache_read_tokens,0)+COALESCE(image_output_tokens,0)),0) FROM usage_logs WHERE {where} GROUP BY 1 ORDER BY 2 DESC,3 DESC LIMIT 20")
                return self.sendj({'total':total,'daily':daily,'models':models})
            if path=='/xapi-data/models':
                m=rows("SELECT DISTINCT COALESCE(requested_model,model) FROM usage_logs WHERE COALESCE(requested_model,model)<>'' ORDER BY 1 LIMIT 100")
                defaults=[['gpt-5.5'],['gpt-5.4'],['gpt-5.4-mini']]
                seen=set(); out=[]
                for row in defaults+m:
                    v=row[0]
                    if v and v not in seen:
                        seen.add(v); out.append(v)
                return self.sendj({'models':out})
            if path=='/xapi-data/pricing':
                q = """
                SELECT m.model,
                       COALESCE(cmp.input_price,0)*1000000 AS input_price,
                       COALESCE(cmp.output_price,0)*1000000 AS output_price,
                       COALESCE(cmp.cache_read_price,cmp.cache_write_price,0)*1000000 AS cache_price,
                       COALESCE(cmp.cache_write_price,0)*1000000 AS cache_write_price,
                       COALESCE(cmp.image_output_price,0)*1000000 AS image_price,
                       COALESCE(cmp.platform,'openai') AS platform,
                       COALESCE(to_char(cmp.updated_at AT TIME ZONE 'Asia/Shanghai','YYYY-MM-DD HH24:MI:SS'),'') AS updated_at
                FROM channel_model_pricing cmp
                CROSS JOIN LATERAL jsonb_array_elements_text(cmp.models) AS m(model)
                JOIN channels c ON c.id=cmp.channel_id
                WHERE c.status='active'
                  AND m.model IN ('gpt-5.5','gpt-5.4','gpt-5.4-mini','gpt-image-2')
                ORDER BY CASE m.model WHEN 'gpt-5.5' THEN 1 WHEN 'gpt-5.4' THEN 2 WHEN 'gpt-5.4-mini' THEN 3 WHEN 'gpt-image-2' THEN 4 ELSE 99 END
                """
                data=[]
                for r in rows(q):
                    data.append({
                        'model':r[0],
                        'input_price':r[1],
                        'output_price':r[2],
                        'cache_price':r[3],
                        'cache_write_price':r[4],
                        'image_price':r[5],
                        'platform':r[6],
                        'updated_at':r[7]
                    })
                return self.sendj({'source':'backend_model_pricing','unit':'USD per 1M tokens','pricing':data})
        except Exception as e: return self.sendj({'error':str(e)},500)
        self.sendj({'error':'not found'},404)
    def do_POST(self):
        p=urllib.parse.urlparse(self.path).path; data=self.body()
        try:
            if p=='/xapi-data/users': return self.sendj(create_user(data.get('email',''), data.get('username',''), data.get('password')))
            if p=='/xapi-data/users/auth':
                return self.sendj(auth_user(data.get('email',''), data.get('password','')))
            if p=='/xapi-data/users/password':
                return self.sendj(set_user_password(data.get('uid') or 0, data.get('password') or ''))
            if p=='/xapi-data/keys/verify':
                key=esc_sql(data.get('key') or '')
                r=one(f"SELECT k.id,k.user_id,k.status,COALESCE(k.quota,0),COALESCE(k.quota_used,0),u.status,u.deleted_at IS NOT NULL FROM api_keys k JOIN users u ON u.id=k.user_id WHERE k.key='{key}' AND k.deleted_at IS NULL")
                if not r: return self.sendj({'ok':False,'code':'INVALID_API_KEY','message':'Invalid API key'},401)
                if r[2]!='active' or r[5]!='active' or r[6]=='t': return self.sendj({'ok':False,'code':'ACCOUNT_DISABLED','message':'Account or key disabled'},403)
                try:
                    quota=float(r[3] or 0); used=float(r[4] or 0)
                    if quota>0 and used>=quota: return self.sendj({'ok':False,'code':'KEY_QUOTA_EXCEEDED','message':'Key quota exceeded'},403)
                except Exception: pass
                return self.sendj({'ok':True,'key_id':r[0],'user_id':r[1]})
            if p=='/xapi-data/keys':
                uid=int(data.get('uid') or 0); name=esc_sql((data.get('name') or 'XAPI Key')[:64]); key='sk-'+secrets.token_urlsafe(32).replace('-','').replace('_','')[:48]
                if uid<=0: raise RuntimeError('invalid uid')
                sql(f"INSERT INTO api_keys (user_id,name,key,group_id,status,quota,quota_used) VALUES ({uid},'{name}','{key}',2,'active',0,0)")
                return self.sendj({'key':key})
            if p=='/xapi-data/keys/view':
                uid=int(data.get('uid') or 0); kid=int(data.get('id') or 0)
                r=one(f"SELECT key FROM api_keys WHERE id={kid} AND user_id={uid} AND deleted_at IS NULL")
                if not r: return self.sendj({'ok':False,'error':'key not found'},404)
                return self.sendj({'ok':True,'key':r[0]})
            if p=='/xapi-data/keys/rotate':
                uid=int(data.get('uid') or 0); kid=int(data.get('id') or 0)
                key=(data.get('key') or '').strip()
                if not key:
                    key='sk-'+secrets.token_urlsafe(32).replace('-','').replace('_','')[:48]
                if not re.match(r'^sk-[A-Za-z0-9][A-Za-z0-9_-]{15,}$', key):
                    raise RuntimeError('invalid key format')
                r=one(f"SELECT id FROM api_keys WHERE id={kid} AND user_id={uid} AND deleted_at IS NULL")
                if not r: return self.sendj({'ok':False,'error':'key not found'},404)
                sql(f"UPDATE api_keys SET key='{esc_sql(key)}',updated_at=now() WHERE id={kid} AND user_id={uid} AND deleted_at IS NULL")
                clear_cache()
                return self.sendj({'ok':True,'key':key})
            if p=='/xapi-data/keys/update':
                uid=int(data.get('uid') or 0); kid=int(data.get('id') or 0)
                fields=[]
                if 'quota' in data: fields.append("quota=0")
                if 'status' in data:
                    st=esc_sql(data.get('status') or 'active')
                    if st not in ('active','disabled'): raise RuntimeError('invalid status')
                    fields.append(f"status='{st}'")
                if fields:
                    sql(f"UPDATE api_keys SET {','.join(fields)},updated_at=now() WHERE id={kid} AND user_id={uid} AND deleted_at IS NULL")
                clear_cache()
                return self.sendj({'ok':True})
            if p=='/xapi-data/keys/disable':
                uid=int(data.get('uid') or 0); kid=int(data.get('id') or 0)
                sql(f"UPDATE api_keys SET status='disabled',updated_at=now() WHERE id={kid} AND user_id={uid} AND deleted_at IS NULL")
                clear_cache()
                return self.sendj({'ok':True})
            if p=='/xapi-data/keys/delete':
                uid=int(data.get('uid') or 0); kid=int(data.get('id') or 0)
                sql(f"UPDATE api_keys SET deleted_at=now(),updated_at=now() WHERE id={kid} AND user_id={uid} AND deleted_at IS NULL")
                clear_cache()
                return self.sendj({'ok':True})
            if p=='/xapi-data/users/balance':
                uid=int(data.get('uid') or 0); amount=float(data.get('amount') or 0)
                if uid<=0: raise RuntimeError('invalid uid')
                sql(f"UPDATE users SET balance=balance+({amount}), total_recharged=CASE WHEN {amount}>0 THEN total_recharged+({amount}) ELSE total_recharged END, updated_at=now() WHERE id={uid} AND deleted_at IS NULL")
                return self.sendj({'ok':True})
            if p=='/xapi-data/users/update':
                uid=int(data.get('uid') or 0)
                if uid<=0: raise RuntimeError('invalid uid')
                fields=[]
                if 'balance' in data: fields.append(f"balance={float(data.get('balance') or 0)}")
                if 'concurrency' in data: fields.append(f"concurrency={int(data.get('concurrency') or 5)}")
                if 'status' in data:
                    st=esc_sql(data.get('status') or 'active')
                    if st not in ('active','disabled'): raise RuntimeError('invalid status')
                    fields.append(f"status='{st}'")
                    if st=='disabled': sql(f"UPDATE api_keys SET status='disabled',updated_at=now() WHERE user_id={uid} AND deleted_at IS NULL")
                if fields:
                    sql(f"UPDATE users SET {','.join(fields)},updated_at=now() WHERE id={uid} AND deleted_at IS NULL AND role!='admin'")
                if any(k in data for k in ('daily_limit','weekly_limit','monthly_limit')):
                    sql(f"UPDATE user_platform_quotas SET daily_limit_usd=NULL,weekly_limit_usd=NULL,monthly_limit_usd=NULL,updated_at=now() WHERE user_id={uid} AND platform='openai' AND deleted_at IS NULL")
                    sql(f"INSERT INTO user_platform_quotas (user_id,platform,daily_limit_usd,weekly_limit_usd,monthly_limit_usd,daily_usage_usd,weekly_usage_usd,monthly_usage_usd) SELECT {uid},'openai',NULL,NULL,NULL,0,0,0 WHERE NOT EXISTS (SELECT 1 FROM user_platform_quotas WHERE user_id={uid} AND platform='openai' AND deleted_at IS NULL)")
                clear_cache()
                return self.sendj({'ok':True})
            if p=='/xapi-data/users/delete':
                uid=int(data.get('uid') or 0)
                if uid<=1: raise RuntimeError('refuse to delete protected user')
                sql(f"UPDATE api_keys SET deleted_at=now(),updated_at=now(),status='disabled' WHERE user_id={uid} AND deleted_at IS NULL")
                sql(f"UPDATE users SET deleted_at=now(),updated_at=now(),status='disabled',email=email||'.deleted.'||id WHERE id={uid} AND deleted_at IS NULL AND role!='admin'")
                clear_cache()
                restart_gateway()
                return self.sendj({'ok':True})
        except Exception as e: return self.sendj({'error':str(e)},500)
        self.sendj({'error':'not found'},404)

ThreadingHTTPServer((os.environ.get('XAPI_DATA_HOST','127.0.0.1'), int(os.environ.get('XAPI_DATA_PORT','18181'))),H).serve_forever()
