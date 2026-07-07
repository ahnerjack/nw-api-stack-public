#!/usr/bin/env python3
"""Stage 12.5 extreme-case checks for NW-API preview gateway."""
from __future__ import annotations
import concurrent.futures, hashlib, http.client, json, os, secrets, sqlite3, sys, time, urllib.parse

HOST = sys.argv[1] if len(sys.argv)>1 else '10.0.1.66'
PORT = int(sys.argv[2]) if len(sys.argv)>2 else 9088
DB = os.environ.get('NWAPI_PREVIEW_DB','/opt/nw-api-phase0-preview/state/xapi_portal.db')


def remote_call(path, method='GET', body=None, key=None, headers=None):
    conn=http.client.HTTPConnection(HOST, PORT, timeout=10)
    h=headers.copy() if headers else {}
    if key: h['Authorization']='Bearer '+key
    if body is not None:
        h['Content-Type']='application/json'
        body=json.dumps(body).encode()
    conn.request(method, path, body=body, headers=h)
    r=conn.getresponse(); data=r.read(); conn.close(); return r.status, dict(r.getheaders()), data


def make_key():
    import subprocess, base64
    code = r'''
import sqlite3, hashlib, secrets, time
DB="/opt/nw-api-phase0-preview/state/xapi_portal.db"
con=sqlite3.connect(DB); con.row_factory=sqlite3.Row
u=con.execute("SELECT id FROM users WHERE status='active' ORDER BY CASE role WHEN 'admin' THEN 0 ELSE 1 END,id LIMIT 1").fetchone()
key='nwk_extreme_'+secrets.token_urlsafe(24).replace('-','').replace('_','')[:30]
con.execute("INSERT INTO nw_api_keys(user_id,name,key_hash,key_prefix,key_suffix,status,quota,quota_used,created_at) VALUES(?,?,?,?,?,?,?,?,?)",(u['id'],'stage12-extreme',hashlib.sha256(key.encode()).hexdigest(),key[:7],key[-4:],'active',0,0,int(time.time())))
con.commit(); print(key)
'''
    b64=base64.b64encode(code.encode()).decode()
    cmd=f"python3 - <<'PY'\nimport base64; exec(base64.b64decode('{b64}'))\nPY"
    out=subprocess.check_output(['ssh','-o','BatchMode=yes','ls@10.0.1.66','sudo','bash','-lc',cmd], text=True).strip()
    return out


def query_db(sql):
    import subprocess, json as js, base64
    code = """import sqlite3,json\ncon=sqlite3.connect('/opt/nw-api-phase0-preview/state/xapi_portal.db')\nprint(json.dumps(con.execute(%r).fetchall(),ensure_ascii=False))""" % sql
    b64=base64.b64encode(code.encode()).decode()
    cmd=f"python3 - <<'PY'\nimport base64; exec(base64.b64decode('{b64}'))\nPY"
    return js.loads(subprocess.check_output(['ssh','-o','BatchMode=yes','ls@10.0.1.66','sudo','bash','-lc',cmd], text=True))


def main():
    key=make_key(); results=[]
    # 1 duplicate request id should only create one usage event / ledger
    rid='req_extreme_dup_'+str(int(time.time()))
    body={'model':'gpt-5.5','messages':[{'role':'user','content':'dup'}]}
    for _ in range(2):
        st,_,data=remote_call('/v1/chat/completions','POST',body,key,{'X-NW-Mock-Chat':'1','X-Request-Id':rid})
        results.append(('duplicate_request_http', st==200, str(st)))
    time.sleep(1)
    rows=query_db("SELECT count(*),COALESCE(sum(total_usd_micros),0) FROM nw_usage_events WHERE request_id='%s'"%rid)
    led=query_db("SELECT count(*) FROM nw_wallet_ledger WHERE request_id='%s'"%rid)
    results.append(('duplicate_request_idempotent_usage', rows[0][0]==1, str(rows)))
    results.append(('duplicate_request_idempotent_ledger', led[0][0]==1, str(led)))
    # 2 concurrent mock calls all 200 and ledger count matches
    ids=['req_extreme_conc_%d_%d'%(int(time.time()),i) for i in range(20)]
    def one(r): return remote_call('/v1/chat/completions','POST',body,key,{'X-NW-Mock-Chat':'1','X-Request-Id':r})[0]
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        sts=list(ex.map(one, ids))
    results.append(('concurrency_20_all_200', all(s==200 for s in sts), str(sts)))
    time.sleep(1)
    cnt=query_db("SELECT count(*) FROM nw_usage_events WHERE request_id LIKE 'req_extreme_conc_%'")[0][0]
    results.append(('concurrency_usage_count', cnt>=20, str(cnt)))
    # 3 disabled key must reject
    import subprocess
    disable_code="""import sqlite3,hashlib\nkey=%r\ncon=sqlite3.connect('/opt/nw-api-phase0-preview/state/xapi_portal.db')\ncon.execute('UPDATE nw_api_keys SET status=\"disabled\" WHERE key_hash=?',(hashlib.sha256(key.encode()).hexdigest(),)); con.commit()"""%key
    import base64
    b64=base64.b64encode(disable_code.encode()).decode()
    subprocess.check_call(['ssh','-o','BatchMode=yes','ls@10.0.1.66','sudo','bash','-lc',f"python3 - <<'PY'\nimport base64; exec(base64.b64decode('{b64}'))\nPY"])
    st,_,data=remote_call('/v1/models','GET',None,key)
    results.append(('disabled_key_401', st==401, str(st)+' '+data[:80].decode(errors='ignore')))
    # 4 invalid auth path
    st,_,data=remote_call('/v1/models','GET',None,'nwk_invalid_'+secrets.token_urlsafe(12))
    results.append(('invalid_key_401', st==401, str(st)))
    # 5 public pages no upstream leak keywords
    st,_,html=remote_call('/nv-api/','GET')
    leaks=[x for x in ['sk-','Bearer ','xai-','DASHSCOPE_API_KEY'] if x.encode() in html]
    results.append(('public_no_secret_leak', st in (200,302) and not leaks, str(leaks)))
    ok=all(x[1] for x in results)
    for name, passed, detail in results:
        print(('OK' if passed else 'FAIL'), name, detail)
    print('EXTREME_OK' if ok else 'EXTREME_FAIL')
    return 0 if ok else 1

if __name__=='__main__':
    raise SystemExit(main())
