#!/usr/bin/env python3
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import json, time, urllib.parse, secrets

HOST='127.0.0.1'; PORT=18184
USERS={1:{'id':1,'email':'preview-admin@example.test','username':'preview-admin','status':'active','balance':1000.0,'used':12.34},2:{'id':2,'email':'test-user@example.test','username':'test-user','status':'active','balance':100.0,'used':0.56}}
KEYS={1:[[1,'NW-API Preview Admin Key','active','sk-preview-admin',0,0,'never']],2:[[2,'NW-API Preview Test Key','active','sk-preview-test',0,0,'never']]}

def send_json(h, obj, code=200):
    b=json.dumps(obj,ensure_ascii=False).encode()
    h.send_response(code); h.send_header('Content-Type','application/json; charset=utf-8'); h.send_header('Content-Length',str(len(b))); h.end_headers(); h.wfile.write(b)

class H(BaseHTTPRequestHandler):
    def log_message(self, format, *args): return
    def uid(self, qs):
        try: return int(qs.get('uid',['1'])[0] or 1)
        except Exception: return 1
    def do_GET(self):
        u=urllib.parse.urlparse(self.path); path=u.path; qs=urllib.parse.parse_qs(u.query); uid=self.uid(qs); user=USERS.get(uid,USERS[1])
        if path.endswith('/health'): return send_json(self, {'ok':True,'mock':True})
        if path.endswith('/summary'):
            return send_json(self, {'user':[user['id'],user['email'],user['username'],user['status'],'preview',user['balance'],user['used']], 'stats':[3,1200,800,400,user['used']]})
        if path.endswith('/stats'):
            return send_json(self, {'total':[user['used'],3,0,2400,0,1200,800,400], 'daily':[], 'models':[['gpt-5.4-mini',user['used'],3,2400]]})
        if path.endswith('/usage'):
            now=time.strftime('%F %T')
            return send_json(self, {'usage':[[now,'gpt-5.4-mini',1200,800,400,0.08,'preview']]})
        if path.endswith('/keys'):
            return send_json(self, {'keys':KEYS.get(uid,[])})
        return send_json(self, {'ok':True,'mock':True})
    def do_POST(self):
        ln=int(self.headers.get('Content-Length','0') or 0)
        try: data=json.loads(self.rfile.read(ln).decode() or '{}')
        except Exception: data={}
        path=urllib.parse.urlparse(self.path).path
        if path.endswith('/users/auth'):
            email=data.get('email','')
            for u in USERS.values():
                if u['email']==email: return send_json(self, {'ok':True,'sub2_user_id':u['id']})
            return send_json(self, {'ok':False}, 403)
        if path.endswith('/users'):
            nid=max(USERS)+1; email=data.get('email') or f'test{nid}@example.test'; USERS[nid]={'id':nid,'email':email,'username':data.get('username') or 'test','status':'active','balance':0.0,'used':0.0}; KEYS[nid]=[]; return send_json(self, {'ok':True,'sub2_user_id':nid})
        if path.endswith('/keys'):
            uid=int(data.get('uid') or 1); kid=len(KEYS.get(uid,[]))+1; key='sk-preview-'+secrets.token_hex(8); KEYS.setdefault(uid,[]).append([kid,data.get('name') or 'Preview Key','active',key,0,0,'never']); return send_json(self, {'ok':True,'key':key})
        if path.endswith('/keys/rotate'):
            return send_json(self, {'ok':True,'key':'sk-preview-'+secrets.token_hex(8)})
        return send_json(self, {'ok':True,'mock':True})

if __name__=='__main__': ThreadingHTTPServer((HOST,PORT),H).serve_forever()
