"""Staff sign-in views and manager-issued one-time password recovery."""
import hashlib
import secrets
from datetime import datetime,timedelta
from urllib.parse import urlencode
import visuals

CSS='''
.auth-page{min-height:100vh;display:grid;place-items:center;padding:38px 24px;background:radial-gradient(ellipse at 10% 20%,#2d403055,transparent 50%),#0b1411}.auth-shell{display:grid;grid-template-columns:1.08fr 1fr;max-width:1100px;width:100%;min-height:650px;background:#14201a;border:1px solid #374839;border-radius:24px;overflow:hidden;box-shadow:0 25px 100px #0005}.auth-scene{position:relative;padding:38px;display:flex;flex-direction:column;justify-content:space-between;background:linear-gradient(180deg,#08130f55 0%,#0b161118 30%,#0b1611ed 100%),url('/assets/login-bar.webp') center/cover}.auth-scene .brand-lockup{align-self:flex-start;background:#102017bb;padding:12px 15px;border:1px solid #b1a27744;border-radius:12px}.auth-scene .brand-words b{font-size:24px}.scene-copy{position:relative;z-index:1}.scene-copy h2{font-size:37px;line-height:1.4;font-weight:500;color:#f5e8d0;margin:10px 0 16px;letter-spacing:-.5px}.scene-copy p{font-size:14px;line-height:1.9;color:#c6d0c3;max-width:360px}.auth-tags{display:flex;gap:9px;margin-top:23px;flex-wrap:wrap}.auth-tags span{border:1px solid #9baf8a55;border-radius:25px;padding:7px 13px;background:#1a2e21aa;color:#dde4d2;font-size:11px}.auth-content{padding:48px 46px;display:flex;flex-direction:column;justify-content:center}.auth-topline{display:flex;align-items:center;gap:8px;color:#d4c090;font-size:10px;letter-spacing:2px;margin-bottom:21px}.auth-topline:before{content:'';height:6px;width:6px;background:#d8bd7a;border-radius:50%}.auth-content h1{font-size:31px;font-weight:600;color:#f4eddd;margin:0 0 12px;line-height:1.4}.auth-intro{color:#acbba9;font-size:14px;line-height:1.8;margin:0 0 25px}.auth-content form{display:grid;gap:19px}.auth-content label{color:#cfdbca;font-size:13px}.auth-content input{height:49px;background:#0e1a13;border:1px solid #3c4d3c;padding:13px 14px;color:#f3f1e7}.auth-content input:focus{outline:2px solid #d4ba80;outline-offset:1px}.auth-content input::placeholder{color:#6f816f}.auth-content input:-webkit-autofill{-webkit-text-fill-color:#f3f1e7;box-shadow:0 0 0 1000px #233426 inset}.password-wrap{position:relative}.password-wrap input{padding-right:78px;width:100%}.password-toggle{position:absolute;right:5px;top:5px;background:transparent;color:#dbc58f;font-size:12px;height:39px;padding:7px 12px;border:1px solid transparent}.password-toggle:hover{background:#26382a;color:#f1dba8;transform:none}.password-toggle:focus-visible{outline:2px solid #e4c78d}.auth-options{display:flex;justify-content:space-between;align-items:center;gap:10px;font-size:12px;color:#afbeaa}.auth-options a{color:#e3c48b;text-decoration:underline;text-underline-offset:4px}.auth-submit{height:49px;width:100%;font-size:14px}.auth-submit:disabled{opacity:.7;cursor:wait}.auth-back{margin-top:25px;border-top:1px solid #344531;padding-top:20px;font-size:13px;display:flex;justify-content:space-between;gap:12px;color:#afbea8}.auth-back a{color:#e4ce9f}.auth-foot{color:#83957e;font-size:11px;text-align:center;margin:22px 0 0;line-height:1.7}.auth-note{background:#1c2d20;border:1px solid #3b5038;color:#c9d6be;border-radius:10px;padding:15px;font-size:13px;line-height:1.9;margin-bottom:23px}.auth-error{background:#3a2720;border:1px solid #8b5b43;color:#f2cfb6;padding:12px 14px;border-radius:9px;font-size:13px;line-height:1.7;margin-bottom:20px}.caps-warning{color:#f1c48b;font-size:12px;margin:0}.caps-warning[hidden]{display:none}.auth-steps{padding-left:21px;color:#c4d1bb;font-size:13px;line-height:2.1}.auth-content .brand-mobile{display:none}.reset-result{overflow-wrap:anywhere;line-height:1.8}.reset-url{padding:15px;background:#101a15;border:1px solid #45533d;border-radius:10px;display:block;user-select:all;font-size:14px}.auth-content small{line-height:1.8}.auth-page .brand-words small{font-size:9px}@media(max-width:760px){.auth-page{padding:20px 15px}.auth-shell{grid-template-columns:1fr;max-width:480px;min-height:0;border-radius:19px}.auth-scene{min-height:190px;padding:22px;background-position:center 43%}.auth-scene .brand-words b{font-size:22px}.scene-copy h2{font-size:22px;margin:16px 0 0}.scene-copy p,.auth-tags{display:none}.auth-content{padding:30px 24px}.auth-content h1{font-size:27px}.auth-topline{margin-bottom:14px}.auth-intro{font-size:13px;margin-bottom:22px}.auth-foot{margin-top:18px}.auth-options{font-size:11px}}@media(prefers-reduced-motion:reduce){button,.button{transition:none!important;transform:none!important}}
'''

SCRIPT='''<script>
document.querySelectorAll('[data-password-toggle]').forEach(button=>{
 button.addEventListener('click',()=>{const input=document.getElementById(button.dataset.passwordToggle);const visible=input.type==='password';input.type=visible?'text':'password';button.textContent=visible?'ซ่อน':'แสดง';button.setAttribute('aria-pressed',String(visible));button.setAttribute('aria-label',visible?'ซ่อนรหัสผ่าน':'แสดงรหัสผ่าน');});
});
document.querySelectorAll('input[data-caps]').forEach(input=>{const update=event=>{const warning=document.getElementById('caps-warning');if(warning&&event.getModifierState)warning.hidden=!event.getModifierState('CapsLock');};input.addEventListener('keydown',update);input.addEventListener('keyup',update);input.addEventListener('blur',()=>{const warning=document.getElementById('caps-warning');if(warning)warning.hidden=true;});});
document.querySelectorAll('form[data-loading]').forEach(form=>form.addEventListener('submit',()=>{const button=form.querySelector('button[type=submit]');button.disabled=true;button.textContent='กำลังดำเนินการ…';}));
</script>'''
CSS+='@media(max-width:760px){.auth-scene .eyebrow{display:none}.scene-copy h2{font-size:20px;margin-top:12px}}'

def initialize(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS password_resets(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id), token_hash TEXT UNIQUE NOT NULL,expires TEXT NOT NULL,used TEXT,issued_by TEXT NOT NULL,created TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS login_failures(id INTEGER PRIMARY KEY,username TEXT NOT NULL,ip TEXT NOT NULL,created TEXT NOT NULL);
    ''')

def password_field(a,label,name,confirm=False):
    autocomplete='new-password' if name in ['new','confirm'] else 'current-password'
    extra='minlength=10 maxlength=256' if autocomplete=='new-password' else 'maxlength=256'
    return f'<label for="{name}">{label}</label><div class=password-wrap><input id="{name}" name="{name}" type=password required autocomplete="{autocomplete}" {extra} data-caps><button class=password-toggle type=button data-password-toggle="{name}" aria-label="แสดงรหัสผ่าน" aria-pressed=false>แสดง</button></div>'

def page(h,title,body,headers=None):
    a=h.api
    h.respond(f'<!doctype html><html lang=th><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>{a.esc(title)} · JUPITER</title><link rel=icon href=/assets/jupiter-mark.svg type=image/svg+xml><style>{a.CSS}{CSS}</style></head><body><div class=auth-page><div class=auth-shell><section class=auth-scene>{visuals.brand()}<div class=scene-copy><div class=eyebrow>GOOD COMPANY. GREAT NIGHTS.</div><h2>เบื้องหลังค่ำคืนที่ดี<br>เริ่มต้นที่ทีมของเรา</h2><p>พื้นที่สำหรับทีม JUPITER ดูแลทุกโต๊ะ ทุกออเดอร์ และทุกช่วงเวลาดี ๆ ของลูกค้า</p><div class=auth-tags><span>โต๊ะและออเดอร์</span><span>ทีมงาน</span><span>ภาพรวมร้าน</span></div></div></section><section class=auth-content>{body}<div class=auth-back><a href=/menu>← กลับหน้าเมนูลูกค้า</a><span>JUPITER TEAM</span></div><p class=auth-foot>สำหรับพนักงานและผู้จัดการร้าน<br>ใช้บัญชีของคุณเอง และออกจากระบบเมื่อใช้เครื่องร่วมกัน</p></section></div></div>{SCRIPT}</body></html>',headers=headers or [])

def login(h,token):
    a=h.api; message=h.query.get('message',[''])[0]
    notice=f'<div class=auth-error role=alert>{a.esc(message)}</div>' if message else ''
    body='<div class=auth-topline>STAFF SIGN IN</div><h1>ยินดีต้อนรับกลับ</h1><p class=auth-intro>เข้าสู่ระบบเพื่อเริ่มดูแลร้านในค่ำคืนนี้</p>'+notice
    body+=f'<form action=/login method=post data-loading><input type=hidden name=csrf value="{a.SESSIONS[token]["csrf"]}"><label for=username>ชื่อผู้ใช้</label><input id=username name=username value="{a.esc(h.query.get("username",[""])[0][:80])}" required maxlength=80 autocomplete=username autocapitalize=none spellcheck=false placeholder="ชื่อผู้ใช้ของคุณ">'+password_field(a,'รหัสผ่าน','password')+'<p id=caps-warning class=caps-warning hidden role=status>เปิด Caps Lock อยู่ ตรวจสอบตัวพิมพ์ใหญ่ก่อนเข้าสู่ระบบ</p><div class=auth-options><span>พนักงาน / ผู้จัดการ</span><a href=/forgot-password>ลืมรหัสผ่าน?</a></div><button type=submit class=auth-submit>เข้าสู่ระบบ →</button></form>'
    page(h,'เข้าสู่ระบบ',body,[('Set-Cookie',f'{h.cookie_name}={token}; HttpOnly; SameSite=Strict; Path=/')])

def public_get(h,db,path):
    if path not in ['/forgot-password','/reset-password']: return False
    a=h.api
    if h.s and h.s['role'] in ['manager','staff']:
        token=h.session_token
    else: token=h.anonymous('guest')
    headers=[('Set-Cookie',f'{h.cookie_name}={token}; HttpOnly; SameSite=Strict; Path=/')]
    if path=='/forgot-password':
        body='<div class=auth-topline>ACCOUNT RECOVERY</div><h1>ลืมรหัสผ่าน?</h1><p class=auth-intro>ให้ผู้จัดการช่วยยืนยันตัวตน แล้วออกลิงก์ตั้งรหัสผ่านใหม่ให้คุณ</p><div class=auth-note>ระบบนี้ยังไม่ส่งลิงก์ผ่านอีเมลหรือ SMS กรุณาติดต่อผู้จัดการร้านโดยตรง</div><ol class=auth-steps><li>แจ้งชื่อผู้ใช้กับผู้จัดการ</li><li>ผู้จัดการไปที่ “กู้คืนบัญชี” และออกลิงก์ให้</li><li>เปิดลิงก์และตั้งรหัสผ่านใหม่ภายใน 15 นาที</li></ol><a class=button href=/login>กลับไปเข้าสู่ระบบ →</a><p class=auth-intro style="margin-top:18px">หากคุณเป็นผู้จัดการเพียงคนเดียว ให้ใช้เครื่องมือกู้คืนบนเครื่องร้านตามคู่มือ โดยผู้ดูแลเครื่องเป็นผู้ดำเนินการ</p>'
        page(h,'ลืมรหัสผ่าน',body,headers); return True
    value=h.query.get('token',[''])[0]
    row=db.execute('SELECT id FROM password_resets WHERE token_hash=? AND used IS NULL AND expires>?',(digest(value),datetime.now().isoformat())).fetchone() if len(value)<=128 else None
    if not row:
        page(h,'ลิงก์ใช้ไม่ได้','<div class=auth-topline>ACCOUNT RECOVERY</div><h1>ลิงก์นี้ใช้ไม่ได้แล้ว</h1><p class=auth-intro>ลิงก์อาจหมดอายุ ถูกยกเลิก หรือถูกใช้แล้ว กรุณาขอลิงก์ใหม่จากผู้จัดการ</p><a class=button href=/forgot-password>วิธีกู้คืนบัญชี</a>',headers); return True
    message=h.query.get('message',[''])[0]
    notice=f'<div class=auth-error role=alert>{a.esc(message)}</div>' if message else ''
    body='<div class=auth-topline>CREATE NEW PASSWORD</div><h1>ตั้งรหัสผ่านใหม่</h1><p class=auth-intro>ใช้รหัสผ่านอย่างน้อย 10 ตัว และหลีกเลี่ยงรหัสที่เดาง่าย</p>'+notice
    body+=f'<form action=/reset-password method=post data-loading><input type=hidden name=csrf value="{a.SESSIONS[token]["csrf"]}"><input type=hidden name=token value="{a.esc(value)}">'+password_field(a,'รหัสผ่านใหม่','new')+password_field(a,'ยืนยันรหัสผ่านใหม่','confirm')+'<p id=caps-warning class=caps-warning hidden role=status>เปิด Caps Lock อยู่</p><button type=submit class=auth-submit>บันทึกรหัสผ่านใหม่</button></form><p class=auth-foot>บันทึกแล้วจะออกจากระบบในอุปกรณ์ที่เคยเข้าสู่ระบบ</p>'
    page(h,'ตั้งรหัสผ่านใหม่',body,headers); return True

def digest(value): return hashlib.sha256(value.encode()).hexdigest()

def reset_password(h,db,d):
    a=h.api
    value=d.get('token',''); new=d.get('new','')
    if len(new)<10 or len(new)>256 or new!=d.get('confirm'): raise ValueError('รหัสผ่านต้องมี 10–256 ตัว และกรอกทั้งสองช่องให้ตรงกัน')
    row=db.execute('SELECT r.*,u.username FROM password_resets r JOIN users u ON u.id=r.user_id WHERE r.token_hash=? AND r.used IS NULL AND r.expires>?',(digest(value),datetime.now().isoformat())).fetchone()
    if not row: raise ValueError('ลิงก์หมดอายุหรือถูกใช้แล้ว กรุณาขอลิงก์ใหม่')
    db.execute('UPDATE users SET password=? WHERE id=?',(a.password(new),row['user_id']))
    db.execute('UPDATE password_resets SET used=? WHERE user_id=? AND used IS NULL',(a.now(),row['user_id']))
    db.execute('DELETE FROM login_failures WHERE username=?',(row['username'],))
    db.execute('INSERT INTO audit(username,action,created) VALUES (?,?,?)',(row['username'],'ตั้งรหัสผ่านใหม่ผ่านลิงก์กู้คืน',a.now()))
    for session in a.SESSIONS.values():
        if session['username']==row['username']: session['expires']=datetime.min

def admin_get(h,db,path):
    if path!='/account-security': return False
    if h.s['role']!='manager': h.respond('Forbidden',403); return True
    a=h.api
    body='<section class=panel><h2>ออกลิงก์ตั้งรหัสผ่านใหม่</h2><p class=muted>ยืนยันตัวตนผู้ขอก่อนออกลิงก์ ใช้ได้ครั้งเดียวภายใน 15 นาที ลิงก์เก่าของบัญชีนั้นจะถูกยกเลิก</p>'
    body+=h.form('/issue-reset','<label>บัญชี<select name=user_id>'+a.options(db.execute('SELECT id,username FROM users ORDER BY username').fetchall(),label='username')+'</select></label>'+a.field('รหัสผ่านผู้จัดการที่กำลังใช้งาน','manager_password','','password','required autocomplete=current-password')+'<button>ออกลิงก์กู้คืน</button>')+'</section><section class=panel><h2>ลิงก์กู้คืนล่าสุด</h2>'
    rows=db.execute('SELECT r.*,u.username FROM password_resets r JOIN users u ON u.id=r.user_id ORDER BY r.id DESC LIMIT 30').fetchall()
    body+=a.grid(['บัญชี','ออกโดย','หมดอายุ','สถานะ',''],[(a.esc(r['username']),a.esc(r['issued_by']),a.esc(r['expires'][:16].replace('T',' ')),'ปิดใช้งานแล้ว' if r['used'] else ('หมดอายุ' if r['expires']<datetime.now().isoformat() else 'ใช้งานได้'),h.form('/revoke-reset',f'<input type=hidden name=id value={r["id"]}><button class=danger>ยกเลิกลิงก์</button>') if not r['used'] and r['expires']>datetime.now().isoformat() else '') for r in rows])+'</section>'
    h.page('กู้คืนบัญชี',body); return True

def admin_mutate(h,db,path,d):
    if path not in ['/issue-reset','/revoke-reset']: return None
    a=h.api
    if h.s['role']!='manager': raise ValueError('เฉพาะผู้จัดการ')
    if path=='/revoke-reset':
        db.execute('UPDATE password_resets SET used=? WHERE id=? AND used IS NULL',(a.now(),a.integer(d['id'])))
        return '/account-security'
    manager=db.execute('SELECT password FROM users WHERE username=?',(h.s['username'],)).fetchone()
    if not manager or not a.verify(d.get('manager_password',''),manager[0]): raise ValueError('รหัสผ่านผู้จัดการไม่ถูกต้อง')
    user=db.execute('SELECT id,username FROM users WHERE id=?',(a.integer(d['user_id']),)).fetchone()
    if not user: raise ValueError('ไม่พบบัญชี')
    raw=secrets.token_urlsafe(32); expires=(datetime.now()+timedelta(minutes=15)).isoformat()
    db.execute('UPDATE password_resets SET used=? WHERE user_id=? AND used IS NULL',(a.now(),user['id']))
    db.execute('INSERT INTO password_resets(user_id,token_hash,expires,issued_by,created) VALUES (?,?,?,?,?)',(user['id'],digest(raw),expires,h.s['username'],a.now()))
    base=db.execute("SELECT value FROM settings WHERE key='customer_url'").fetchone()[0].rstrip('/') or f'http://127.0.0.1:{h.server.server_port}'
    h.new_reset={'url':base+'/reset-password?'+urlencode({'token':raw}),'username':user['username'],'expires':expires}
    return '/account-security'

def issued(h):
    a=h.api; r=h.new_reset
    h.page('ลิงก์กู้คืนพร้อมแล้ว',f'<style>{CSS}</style><section class="panel reset-result"><h2>ตั้งรหัสผ่านใหม่ให้ {a.esc(r["username"])}</h2><p>ส่งลิงก์นี้ให้เจ้าของบัญชีโดยตรง ใช้ได้ครั้งเดียว และหมดอายุเวลา {a.esc(r["expires"][11:16])}</p><a class=reset-url href="{a.esc(r["url"])}">{a.esc(r["url"])}</a><p class=muted>ลิงก์จะแสดงเพียงครั้งนี้ หากออกจากหน้านี้ให้สร้างลิงก์ใหม่ได้</p><a class="button secondary" href=/account-security>กลับไปจัดการลิงก์</a></section>')

def blocked(db,username,ip):
    since=(datetime.now()-timedelta(minutes=10)).isoformat()
    return db.execute('SELECT COUNT(*) FROM login_failures WHERE created>? AND (username=? OR ip=?)',(since,username,ip)).fetchone()[0]>=8
