"""Nightbar — Python standard-library POS. Run: python app.py"""
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from http.cookies import SimpleCookie
from urllib.parse import parse_qs, urlparse, urlencode
from pathlib import Path
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import datetime, timedelta
import sqlite3, secrets, hashlib, hmac, html, json, csv, io, os
import customer
import visuals
import auth_ui
import operations
import ux
import floor_plan
import experience
import menu_uploads
import stock_batch
import convenience
import polish
import table_management
import menu_options
import workstations
import deposits
import readability
import reservation_seating
import deposit_slips
import streamline
import accessibility

ROOT = Path(__file__).resolve().parent
DB = ROOT / 'data' / 'nightbar.sqlite3'
SESSIONS = {}
class Connection(sqlite3.Connection):
    def __exit__(self, *args):
        try: return super().__exit__(*args)
        finally: self.close()
def connect():
    db = sqlite3.connect(DB, timeout=15, factory=Connection)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    return db
def password(value, salt=None):
    salt = salt or secrets.token_hex(16)
    return salt + ':' + hashlib.pbkdf2_hmac('sha256', value.encode(), salt.encode(), 240000).hex()
def verify(value, saved):
    return hmac.compare_digest(password(value, saved.split(':')[0]), saved)
def initialize():
    DB.parent.mkdir(exist_ok=True)
    with connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('manager','staff')));
        CREATE TABLE IF NOT EXISTS tables(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, seats INTEGER NOT NULL CHECK(seats>0));
        CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL, price INTEGER NOT NULL CHECK(price>=0), cost INTEGER NOT NULL CHECK(cost>=0), stock INTEGER NOT NULL CHECK(stock>=0), minimum INTEGER NOT NULL CHECK(minimum>=0), active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY, table_id INTEGER NOT NULL REFERENCES tables(id), opened TEXT NOT NULL, closed TEXT, status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','paid','void')), discount INTEGER NOT NULL DEFAULT 0, service INTEGER NOT NULL DEFAULT 0, tax INTEGER NOT NULL DEFAULT 0, total INTEGER NOT NULL DEFAULT 0, method TEXT, received INTEGER, note TEXT NOT NULL DEFAULT '');
        CREATE UNIQUE INDEX IF NOT EXISTS one_open_order ON orders(table_id) WHERE status='open';
        CREATE TABLE IF NOT EXISTS items(id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL REFERENCES orders(id), product_id INTEGER NOT NULL REFERENCES products(id), name TEXT NOT NULL, price INTEGER NOT NULL, cost INTEGER NOT NULL, qty INTEGER NOT NULL CHECK(qty>0));
        CREATE TABLE IF NOT EXISTS movements(id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL REFERENCES products(id), qty INTEGER NOT NULL, reason TEXT NOT NULL, created TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS reservations(id INTEGER PRIMARY KEY, name TEXT NOT NULL, phone TEXT NOT NULL, table_id INTEGER NOT NULL REFERENCES tables(id), time TEXT NOT NULL, guests INTEGER NOT NULL CHECK(guests>0), status TEXT NOT NULL DEFAULT 'booked');
        CREATE TABLE IF NOT EXISTS expenses(id INTEGER PRIMARY KEY, title TEXT NOT NULL, amount INTEGER NOT NULL CHECK(amount>0), created TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, username TEXT NOT NULL, action TEXT NOT NULL, created TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        ''')
        if not db.execute('SELECT 1 FROM tables').fetchone():
            db.executemany('INSERT INTO tables(name,seats) VALUES (?,?)', [(f'T{i:02}', 4 if i<9 else 6) for i in range(1,13)])
            db.executemany('INSERT INTO products(name,category,price,cost,stock,minimum) VALUES (?,?,?,?,?,?)', [
                ('เบียร์ Lager 330 ml','เบียร์',9500,4800,72,12),('เบียร์ Craft IPA','เบียร์',18000,9500,36,8),
                ('Whisky ขวด 700 ml','สุรา',149000,85000,20,5),('Gin Tonic','ค็อกเทล',22000,8000,40,8),
                ('Mojito','ค็อกเทล',24000,8500,40,8),('น้ำดื่ม','มิกเซอร์',3000,1000,100,20),
                ('โซดา','มิกเซอร์',4000,1500,100,20),('น้ำแข็งถัง','มิกเซอร์',6000,1500,60,10),
                ('เฟรนช์ฟรายส์','อาหาร',12000,4000,30,5),('ปีกไก่ทอด','อาหาร',16000,6500,30,5)])
        for key,value in [('shop','NIGHTBAR'),('address','ระบุที่อยู่ร้านในหน้าตั้งค่า'),('service','0'),('tax','0')]:
            db.execute('INSERT OR IGNORE INTO settings VALUES (?,?)',(key,value))
        customer.initialize(db)
        visuals.initialize(db)
        auth_ui.initialize(db)
        operations.initialize(db)
        stock_batch.initialize(db)
        table_management.initialize(db)
        menu_options.initialize(db)
        workstations.initialize(db)
        deposits.initialize(db)
        reservation_seating.initialize(db)
def now(): return datetime.now().astimezone().isoformat(timespec='seconds')
def esc(value): return html.escape(str(value), quote=True)
def money(value): return f'{value/100:,.2f}'
def amount(value):
    try:
        result = Decimal(value)
        if not result.is_finite() or result < 0 or result > 100000000: raise ValueError('จำนวนเงินไม่ถูกต้อง')
        return int((result*100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
    except (InvalidOperation, TypeError): raise ValueError('กรุณาระบุจำนวนเงินให้ถูกต้อง')
def integer(value, minimum=1):
    n=int(value)
    if n<minimum or n>1000000: raise ValueError('จำนวนไม่อยู่ในช่วงที่กำหนด')
    return n
def field(label,name,value='',kind='text',extra=''):
    return f'<label>{label}<input type="{kind}" name="{name}" value="{esc(value)}" {extra}></label>'
def options(rows, key='id', label='name'):
    return ''.join(f'<option value="{r[key]}">{esc(r[label])}</option>' for r in rows)
def grid(headers, rows):
    return '<div class="scroll"><table><thead><tr>'+''.join(f'<th>{esc(h)}</th>' for h in headers)+'</tr></thead><tbody>'+(''.join('<tr>'+''.join(f'<td>{v}</td>' for v in row)+'</tr>' for row in rows) or f'<tr><td colspan="{len(headers)}" class="muted">ยังไม่มีข้อมูล</td></tr>')+'</tbody></table></div>'
CSS='''
:root{color-scheme:dark;--bg:#0d1118;--panel:#171d27;--muted:#8f9aab;--gold:#e4bd76;--border:#29313e}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:#edf1f7;font:15px "Segoe UI",Tahoma,sans-serif}a{color:inherit;text-decoration:none}aside{width:225px;position:fixed;inset:0 auto 0 0;background:#111721;border-right:1px solid var(--border);padding:30px 20px}aside h2{color:var(--gold);letter-spacing:3px}aside small{color:var(--muted)}nav{display:grid;gap:8px;margin-top:35px}nav a{padding:12px;border-radius:8px;color:#aeb8c8}nav a:hover,nav a.active{background:#2b2930;color:var(--gold)}main{margin-left:225px;padding:34px 40px;max-width:1550px}header{display:flex;justify-content:space-between;align-items:center;margin-bottom:30px}h1{font-size:28px;margin:8px 0}h2{font-size:20px}h3{margin-top:0}.eyebrow{color:var(--gold);font-size:11px;letter-spacing:2px}.muted,small{color:var(--muted)}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(205px,1fr));gap:18px}.card,.panel{background:var(--panel);border:1px solid var(--border);border-radius:14px;padding:22px;margin-bottom:20px}.stat{font-size:30px;font-weight:650;margin:16px 0 0}.tables{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:16px}.tablecard{display:block;padding:24px;border:1px solid #285344;border-radius:12px;background:#132822}.tablecard.busy{border-color:#6b5635;background:#2b241b}.badge{display:inline-block;color:#9be0bd;background:#214535;padding:4px 10px;border-radius:20px;font-size:12px}.busy .badge{color:var(--gold);background:#4b3c24}button,.button{display:inline-block;background:var(--gold);color:#171717;border:0;border-radius:7px;padding:11px 17px;cursor:pointer;font-weight:650;font-size:14px}.secondary{background:#303a49;color:#fff}.danger{background:#5c3036;color:#ffcad0}input,select{background:#0d131d;border:1px solid #354052;color:#fff;border-radius:7px;padding:11px;width:100%;font:inherit}label{display:grid;gap:7px;color:#aeb8c8;font-size:13px}form.fields{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));align-items:end;gap:14px}form.inline{display:inline-flex;gap:8px;align-items:center}form.inline input{width:90px}table{width:100%;border-collapse:collapse;font-size:14px}th{text-align:left;color:var(--muted);font-size:12px;font-weight:500}th,td{padding:15px 12px;border-bottom:1px solid var(--border)}.scroll{overflow:auto}.split{display:grid;grid-template-columns:1.4fr 1fr;gap:22px}.notice{background:#343021;border:1px solid #725c31;color:#f8dca1;padding:14px;border-radius:8px;margin-bottom:20px}.total{font-size:30px;color:var(--gold)}.login{max-width:440px;margin:10vh auto}.login form{display:grid;gap:18px}footer{margin-top:36px;color:var(--muted);font-size:12px}@media(max-width:850px){aside{position:static;width:auto;padding:15px}aside h2{margin:0}nav{display:flex;overflow:auto;margin:12px 0 0}nav a{white-space:nowrap}main{margin:0;padding:20px}.split{grid-template-columns:1fr}header{align-items:flex-start;gap:12px}}@media print{aside,.noprint,footer{display:none!important}main{margin:0;padding:0}body{background:white;color:black}.panel{background:white;border:0}small,.muted,th{color:#444}.total{color:black}td,th{border-color:#ccc}}
'''

CSS += visuals.BRAND_CSS
CSS += experience.CSS
CSS += polish.CSS

class Handler(customer.CustomerMixin, BaseHTTPRequestHandler):
    @property
    def api(self):
        import sys
        return sys.modules[__name__]
    @property
    def cookie_name(self): return f'nightbar_{self.server.server_port}'
    def anonymous(self,role):
        if self.s and self.s['role']==role:
            return self.session_token
        token=secrets.token_hex(32)
        SESSIONS[token]={'csrf':secrets.token_hex(32),'expires':datetime.now()+timedelta(minutes=30),'role':role,'username':role}
        return token
    def log_message(self, fmt, *args): pass
    def respond(self, body, status=200, content='text/html; charset=utf-8', headers=None):
        if isinstance(body,str) and content.startswith('text/html'):body=accessibility.decorate(body)
        data=body.encode() if isinstance(body,str) else body
        self.send_response(status)
        for key,value in [('Content-Type',content),('Content-Length',str(len(data))),('Cache-Control','no-store'),('X-Content-Type-Options','nosniff'),('X-Frame-Options','DENY'),('Referrer-Policy','same-origin')]+(headers or []): self.send_header(key,value)
        self.end_headers(); self.wfile.write(data)
    def redirect(self, path, message='', headers=None):
        if message:
            target, separator, fragment=path.partition('#')
            target+=('&' if '?' in target else '?')+urlencode({'message':message})
            path=target+(separator+fragment if separator else '')
        self.respond(b'',303,headers=[('Location',path)]+(headers or []))
    def session(self):
        cookie=SimpleCookie()
        try: cookie.load(self.headers.get('Cookie',''))
        except Exception: return None
        token=cookie.get(self.cookie_name)
        self.session_token=token.value if token else None
        s=SESSIONS.get(token.value) if token else None
        return s if s and s['expires']>datetime.now() else None
    def form(self,action,body,cls='fields'):
        if action=='/expense': body=f'<input type=hidden name=request_key value="{secrets.token_urlsafe(24)}">'+body
        encoding=' enctype="multipart/form-data"' if action in ['/product','/product-presentation','/product-save','/deposit-qr'] else ''
        return f'<form method="post" action="{action}" class="{cls}"{encoding}><input type="hidden" name="csrf" value="{self.s["csrf"]}">{body}</form>'
    def page(self,title,body):
        nav=[('/','ภาพรวม'),('/tables','โต๊ะและออเดอร์'),('/customer-queue','คิวออเดอร์ลูกค้า'),('/shifts','เปิด–ปิดกะ / เงินสด'),('/qr','พิมพ์ QR / ลิงก์ร้าน'),('/products','เมนูและสต็อก'),('/reservations','การจองโต๊ะ'),('/menu','เปิดหน้าลูกค้า ↗')]
        if self.s['role']=='manager': nav +=[('/reports','รายงานยอดขาย'),('/expenses','รายจ่าย'),('/settings','ตั้งค่าและพนักงาน'),('/account-security','กู้คืนบัญชี')]
        nav.append(('/production','คิวครัว / บาร์ / เสิร์ฟ'))
        if self.s['role']=='manager':nav.append(('/menu-options','ตัวเลือกเมนู'))
        nav=[(url,'ออเดอร์และบริการ' if url=='/production' else 'จัดการเมนู' if url=='/products' else label) for url,label in nav if url not in ['/customer-queue','/menu-options','/account-security'] and workstations.allowed(self,url)]
        if workstations.position(self) in ['kitchen','bar']:nav=[(url,'งานของฉัน') for url,label in nav if url!='/']
        links=convenience.navigation(nav,self.path.split('?')[0])
        msg=self.query.get('message',[''])[0]
        notice=f'<div class="notice">{esc(msg)}</div>' if msg else ''
        body+=convenience.SCRIPT+convenience.drafts(self)
        import workspace
        if workstations.allowed(self,'/qr'):body+=workspace.QR_DIALOG
        import re
        hidden=[action for action in set(re.findall(r'<form[^>]*\baction="([/a-z-]+)"',body)) if not workstations.allowed(self,action,True)]
        if hidden:body+='<style>'+','.join('form[action="'+action+'"]' for action in hidden)+'{display:none!important}</style>'
        if self.s['role']=='staff':body='<p class=muted>หน้าที่: '+esc(workstations.LABELS.get(workstations.position(self),'พนักงาน'))+'</p>'+body
        self.respond(f'<!doctype html><html lang="th"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)} · JUPITER</title><style>{CSS}{ux.CSS}{convenience.CSS}</style><aside><h2>{visuals.brand()}</h2><small>ระบบจัดการร้าน</small><nav>{links}</nav></aside><main><header><div><div class="eyebrow">OPERATIONS / JUPITER</div><h1>{esc(title)}</h1><small>{datetime.now():%d/%m/%Y} · ระบบจัดการร้าน</small></div><div><small>{esc(self.s["username"])} · {"ผู้จัดการ" if self.s["role"]=="manager" else "พนักงาน"}</small> {self.form("/logout","<button class=secondary>ออกจากระบบ</button>","inline")}</div></header>{notice}{body}<footer>JUPITER · Python + SQLite · ราคาทั้งหมดเป็นบาท</footer></main></html>')
    def do_GET(self):
        parsed=urlparse(self.path); self.query=parse_qs(parsed.query); path=parsed.path; self.s=self.session()
        if visuals.serve(self,path): return
        if path=='/favicon.ico': self.respond(b'',204); return
        with connect() as db:
            if deposit_slips.serve(self,db,path):return
            if self.customer_get(db,path): return
            if auth_ui.public_get(self,db,path): return
            if not db.execute('SELECT 1 FROM users').fetchone():
                token=self.anonymous('setup')
                self.respond(f'<!doctype html><meta charset=utf-8><title>ตั้งค่า NIGHTBAR</title><style>{CSS}</style><div class="login panel">{visuals.brand()}<div class=eyebrow style="margin-top:24px">WELCOME TO NIGHTBAR</div><h1>สร้างผู้จัดการร้าน</h1><p class=muted>ตั้งบัญชีของคุณเพื่อเริ่มใช้งานครั้งแรก</p><form method=post action=/setup><input type=hidden name=csrf value="{SESSIONS[token]["csrf"]}">{field("ชื่อผู้ใช้","username","",extra="required maxlength=40")}{field("รหัสผ่านอย่างน้อย 10 ตัว","password","","password","required minlength=10")}<button>เริ่มใช้งาน</button></form></div>',headers=[('Set-Cookie',f'{self.cookie_name}={token}; HttpOnly; SameSite=Strict; Path=/')]); return
            if not self.s or self.s['role'] in ['setup','guest']:
                token=self.anonymous('guest')
                auth_ui.login(self,token); return
            if path=='/login': self.redirect('/'); return
            try: self.render(db,path)
            except (ValueError,TypeError): self.page('ไม่พบข้อมูล','<div class=panel>ข้อมูลที่ร้องขอไม่ถูกต้อง <a href=/tables>กลับไปหน้าโต๊ะ</a></div>')
    def render(self,db,path):
        deposits.expire(db)
        if path=='/customer-queue':self.redirect('/production');return
        if not workstations.allowed(self,path):self.respond('Forbidden',403);return
        if path=='/live/order-hub':
            html,ids=streamline.board(self,db,integer(self.query.get('id',['0'])[0]))
            self.respond(json.dumps({'html':html,'ids':ids},ensure_ascii=False),content='application/json; charset=utf-8');return
        if path=='/' and workstations.home(self):self.redirect(workstations.home(self));return
        if path=='/order' and workstations.position(self)=='cashier':self.redirect('/checkout?id='+self.query.get('id',['0'])[0]);return
        if workstations.get(self,db,path):return
        if path=='/menu-options':
            if self.s['role']!='manager':self.respond('Forbidden',403);return
            self.redirect('/products?view=edit'+('&product_id='+str(integer(self.query['product_id'][0])) if 'product_id' in self.query else ''));return
        if operations.get(self,db,path): return
        if auth_ui.admin_get(self,db,path): return
        if self.customer_admin_get(db,path): return
        manager=self.s['role']=='manager'
        if path in ['/reports','/expenses','/settings','/export','/backup'] and not manager: self.respond('Forbidden',403); return
        if path=='/':
            sales=db.execute("SELECT COALESCE(SUM(total),0),COUNT(*) FROM orders WHERE status='paid' AND substr(closed,1,10)=?",(datetime.now().date().isoformat(),)).fetchone()
            busy=db.execute('SELECT COUNT(*) FROM table_usage').fetchone()[0]
            low=db.execute('SELECT * FROM products WHERE stock<=minimum AND active=1').fetchall()
            body='<div class=cards>'+''.join(f'<div class=card><small>{k}</small><div class=stat>{v}</div></div>' for k,v in [('ยอดขายวันนี้','฿ '+money(sales[0])),('บิลชำระแล้ว',sales[1]),('โต๊ะกำลังใช้งาน',busy),('สินค้าใกล้หมด',len(low))])+'</div><div class=split><section class=panel><h2>ออเดอร์ที่กำลังเปิด</h2>'
            body+=grid(['บิล','โต๊ะ','เปิดเมื่อ',''],[(f'#{r["id"]}',esc(r['name']),esc(r['opened'][11:16]),f'<a class="button secondary" href="/order?id={r["id"]}">จัดการบิล</a>') for r in db.execute("SELECT o.*,t.name FROM orders o JOIN tables t ON t.id=o.table_id WHERE status='open' ORDER BY o.id DESC")])+'</section><section class=panel><h2>แจ้งเตือนสต็อก</h2>'+grid(['สินค้า','คงเหลือ'],[(esc(r['name']),r['stock']) for r in low])+'</section></div>'
            self.page('ภาพรวมร้าน',experience.priorities(self,db)+body)
        elif path=='/tables':
            body=convenience.filters('tables')+'<p class=muted>เลือกโต๊ะเพื่อเปิดบิลหรือจัดการออเดอร์ · ยอดรายการก่อนยืนยันชำระยังไม่รวมค่าบริการและภาษี</p><div class=table-legend><span>🟢 ว่าง</span><span>🟡 กำลังใช้งาน</span><span>🟣 กำลังชำระ</span></div><div class=tables>'
            body=table_management.plan(self,db)+body
            for r in db.execute("SELECT t.*,o.id AS oid,o.opened,o.guests,COALESCE(s.cleaning,0) cleaning FROM tables t LEFT JOIN table_usage u ON u.table_id=t.id LEFT JOIN orders o ON o.id=u.order_id LEFT JOIN table_state s ON s.table_id=t.id"):
                quote=operations.locked(db,r['oid']) if r['oid'] else None
                state='กำลังชำระเงิน' if quote else 'กำลังใช้งาน' if r['oid'] else 'รอทำความสะอาด' if r['cleaning'] else 'ว่าง พร้อมรับลูกค้า'
                details='<p class=table-meta>เปิดโต๊ะเมื่อมีลูกค้านั่ง<br>สร้าง QR สำหรับบิลใหม่ได้ทันที</p>'
                warning,ack=convenience.table_warning(self.api,db,r['id'])
                if r['oid']:
                    subtotal=db.execute('SELECT COALESCE(SUM(price*qty),0) FROM items WHERE order_id=?',(r['oid'],)).fetchone()[0]
                    pending=db.execute("SELECT COUNT(*) FROM items WHERE order_id=? AND prep_status IN ('received','preparing','ready')",(r['oid'],)).fetchone()[0]
                    value=quote['total']-operations.paid(db,r['oid']) if quote else subtotal
                    opened=datetime.fromisoformat(r['opened']); elapsed=max(0,int((datetime.now(opened.tzinfo)-opened).total_seconds()/60))
                    details=f'<div class=table-amount>฿{money(value)}</div><small>{"ค้างชำระ" if quote else "ยอดรายการ"} · บิล #{r["oid"]}</small><p class=table-meta>เปิดมา {elapsed//60} ชม. {elapsed%60} นาที<br>ออเดอร์รอเสิร์ฟ {pending} รายการ</p>'
                tag='settling' if quote else 'busy' if r['oid'] else 'cleaning' if r['cleaning'] else 'free'
                action=(f'<a class=button href="/{"checkout" if quote else "order"}?id={r["oid"]}">{"รับชำระต่อ" if quote else "เปิดดูบิล"}</a><div class=table-shortcuts><a href="/order?id={r["oid"]}">รายการ</a><a href="/order?id={r["oid"]}#table-qr">QR โต๊ะนี้</a><a href="/checkout?id={r["oid"]}">ชำระ</a></div>' if r['oid'] else self.form('/open',f'<input type=hidden name=table_id value={r["id"]}>{ack}<button>เปิดโต๊ะ</button>'))
                if not r['oid']:
                    action=self.form('/table-ready',f'<input type=hidden name=table_id value={r["id"]}><button>ทำความสะอาดแล้ว พร้อมใช้งาน</button>') if r['cleaning'] else self.form('/open',f'<input type=hidden name=table_id value={r["id"]}>{ack}'+field('จำนวนลูกค้า','guests',1,'number',f'min=1 max={r["seats"]} required')+'<button>เปิดโต๊ะ</button>')
                else:
                    label=db.execute('SELECT name FROM order_labels WHERE id=?',(r['oid'],)).fetchone()[0]
                    details+=f'<p>{esc(label)} · ลูกค้า {r["guests"]} คน<br><a href=/order?id={r["oid"]}>จัดการโต๊ะ / ย้าย / รวม →</a></p>'
                body+=f'<div id=table-{r["id"]} class="tablecard {tag}" data-state={tag}><h2>{esc(r["name"])}</h2><p class=muted>{r["seats"]} ที่นั่ง</p><span class=badge>{state}</span>{details}{warning}{action}</div>'
            self.page('โต๊ะและออเดอร์',body+'</div>')
        elif path in ['/order','/receipt']:
            oid=integer(self.query.get('id',['0'])[0]); o=db.execute('SELECT o.*,t.name FROM orders o JOIN order_labels t ON t.id=o.id WHERE o.id=?',(oid,)).fetchone()
            if not o: raise ValueError()
            if o['status']=='paid' or path=='/receipt' and o['status']=='open':
                self.page('ใบเสร็จรับเงิน' if o['status']=='paid' else 'ตรวจบิลก่อนชำระ',readability.receipt(self,db,o));return
            items=db.execute('SELECT * FROM items WHERE order_id=?',(oid,)).fetchall(); subtotal=sum(r['price']*r['qty'] for r in items)
            setting=dict(db.execute('SELECT key,value FROM settings').fetchall())
            body=f'<section class=panel><h2>{esc(setting["shop"])} · {esc(o["name"])}</h2><p class=muted>{esc(setting["address"])}<br>บิล #{oid:06} · {ux.date(o["opened"])} · {ux.status(o["status"])}</p>'
            rows=[]
            for r in items:
                remove=''
                if o['status']=='open' and manager and not operations.locked(db,oid):
                    remove='<details><summary>ยกเลิกรายการ</summary>'+self.form('/item-cancel',f'<input type=hidden name=order_id value={oid}><input type=hidden name=revision value={o["table_revision"]}><input type=hidden name=item_id value={r["id"]}>'+field('เหตุผล','reason',extra='required maxlength=300')+'<label>วัตถุดิบ<select name=disposition><option value=waste>ใช้ไปแล้ว / บันทึกของเสีย</option><option value=return>ยังไม่ได้ใช้ / คืนสต็อก</option></select></label><button class=danger>ยืนยันยกเลิกรายการ</button>')+'</details>'
                rows.append((esc(r['name']),r['qty'],money(r['price']),money(r['price']*r['qty']),remove))
            body+=grid(['รายการ','จำนวน','ราคา','รวม',''],rows)+f'<p>รวมรายการ <strong>฿ {money(subtotal)}</strong></p>'
            if o['status']=='paid':
                body+='<p class=noprint><button type=button onclick="window.print()">พิมพ์ใบเสร็จ</button> <a class="button secondary" href=/tables>กลับหน้าโต๊ะ</a></p>'
                body=ux.progress(4)+body
                body+=f'<p>ส่วนลด {money(o["discount"])} · ค่าบริการ {money(o["service"])} · ภาษี {money(o["tax"])}</p><p class=total>ยอดสุทธิ ฿ {money(o["total"])}</p><p>ชำระ: {esc(o["method"])} · รับเงิน {money(o["received"])} · เงินทอน {money(o["received"]-o["total"])}</p><p class=muted>ขอบคุณที่ใช้บริการ · เอกสารนี้เป็นใบรับเงินทั่วไป</p><p class=noprint>พิมพ์ใบเสร็จด้วย Ctrl+P</p>'
                body+=operations.payment_table(self,db,oid=oid)
            body+='</section>'
            cancellations=db.execute('SELECT * FROM item_cancellations WHERE order_id=? ORDER BY id',(oid,)).fetchall()
            if cancellations:body+='<section class=panel><h2>รายการที่ยกเลิก (ไม่คิดเงิน)</h2>'+grid(['เมนู','จำนวน','การจัดการ','เหตุผล'],[(esc(r['name']),r['qty'],'ของเสีย' if r['disposition']=='waste' else 'คืนสต็อก',esc(r['reason'])) for r in cancellations])+'</section>'
            if o['status']=='open':
                body=streamline.hub(self,db,o)+body
                body+=table_management.controls(self,db,o)
                products=db.execute('SELECT id,name FROM products WHERE active=1 AND stock>0 ORDER BY category,name').fetchall()
                hidden=f'<input type=hidden name=order_id value={oid}>'
                if not operations.locked(db,oid): body+='<section class="panel noprint"><h2>เพิ่มรายการ</h2>'+self.form('/add',hidden+'<input type=hidden name=prep_required value=1>'+f'<label>สินค้า<select name=product_id>{options(products)}</select></label>'+field('จำนวน','qty',1,'number','min=1 required')+'<button>เพิ่มในบิล</button>')+'</section>'
                if manager and not operations.locked(db,oid): body+='<section class=panel><h2>ยกเลิกทั้งบิล</h2><p>ออเดอร์ลูกค้าที่ยังไม่เริ่มทำคืนสต็อกได้ รายการเริ่มทำหรือเสิร์ฟแล้วบันทึกของเสีย ส่วนรายการเพิ่มโดยพนักงานให้เลือกตามจริง</p>'+self.form('/void',hidden+f'<input type=hidden name=revision value={o["table_revision"]}>'+field('เหตุผลยกเลิกบิล','reason',extra='required')+'<label>รายการเพิ่มโดยพนักงาน<select name=disposition><option value=waste>ใช้ไปแล้ว / บันทึกของเสีย</option><option value=return>ยังไม่ได้ใช้ / คืนสต็อก</option></select></label><label><span><input type=checkbox required style="width:auto"> ตรวจรายการและยืนยันยกเลิกทั้งบิล</span></label><button class=danger>ยืนยันยกเลิกบิล</button>')+'</section>'
            self.page('ใบเสร็จ' if o['status']=='paid' else f'ออเดอร์ {o["name"]}',body)
        elif path=='/products':
            body=stock_batch.render(self,db,manager)
            if manager:
                photos='<option value="">ใช้ภาพประกอบตามหมวด</option>'+''.join(f'<option value="{esc(p.name)}">{esc(p.stem)}</option>' for p in sorted(visuals.ASSETS.glob('*.webp')))
                body+='<section class=panel><h2>รูปภาพและคำอธิบายหน้าเมนูลูกค้า</h2>'+self.form('/product-presentation','<label>สินค้า<select name=product_id>'+options(db.execute('SELECT * FROM products ORDER BY category,name').fetchall())+'</select></label><label>ภาพเมนู<select name=image>'+photos+'</select></label>'+field('คำอธิบายเมนู','description',extra='maxlength=300')+'<label>ป้ายแนะนำ<select name=featured><option value=0>เมนูทั่วไป</option><option value=1>เมนูแนะนำ</option></select></label>'+menu_uploads.controls()+'<button>บันทึกหน้าตาเมนู</button>')+'</section>'
                body+='<section class=panel><h2>เพิ่มเมนูพร้อมรูปภาพ</h2>'+self.form('/product',field('ชื่อสินค้า','name',extra='required maxlength=100')+field('หมวดหมู่','category',extra='required')+field('ราคา','price',0,'number','min=0 step=0.01 required')+field('ต้นทุน','cost',0,'number','min=0 step=0.01 required')+field('สต็อกเริ่มต้น','stock',0,'number','min=0 required')+field('แจ้งเตือนขั้นต่ำ','minimum',5,'number','min=0 required')+field('คำอธิบายเมนู','description',extra='maxlength=300')+'<label>ป้ายแนะนำ<select name=featured><option value=0>เมนูทั่วไป</option><option value=1>เมนูแนะนำ</option></select></label>'+menu_uploads.controls()+'<button>เพิ่มสินค้า</button>')+'</section>'
                body+='<section class=panel><h2>แก้ไขราคาหรือข้อมูลเมนู</h2>'+self.form('/product-edit','<label>สินค้า<select name=product_id>'+options(db.execute('SELECT * FROM products').fetchall())+'</select></label>'+field('ชื่อเมนู','name',extra='required maxlength=120')+field('หมวด','category',extra='required maxlength=80')+field('ต้นทุน','cost',0,'number','min=0 step=0.01 required')+field('ขั้นต่ำแจ้งเตือน','minimum',0,'number','min=0 step=1 required')+field('ราคาใหม่','price',0,'number','min=0 step=0.01 required')+'<label>สถานะ<select name=active><option value=1>จำหน่าย</option><option value=0>ซ่อนจากเมนู</option></select></label><button>บันทึก</button>')+'</section>'
            self.page('เมนูและสต็อก',polish.menu_tabs(self,db,body)+(menu_uploads.script(db) if manager else ''))
        elif path=='/reservations':
            body='<section class=panel><h2>จองโต๊ะ</h2>'+self.form('/reserve',field('ชื่อลูกค้า','name',extra='required')+field('เบอร์โทร','phone',extra='required')+'<label>โต๊ะ<select name=table_id>'+options(db.execute('SELECT * FROM tables').fetchall())+'</select></label>'+field('วันและเวลา','time','','datetime-local','required')+field('จำนวนคน','guests',2,'number','min=1 required')+'<button>บันทึกการจอง</button>')+'</section><section class=panel>'+convenience.filters('reservations')
            body+=grid(['ลูกค้า / รหัสจอง','ติดต่อ','โต๊ะ','เวลา','จำนวน','สถานะ',''],[(esc(r['name'])+f'<br><small>{esc(r["code"] or "จองโดยพนักงาน")} · {esc(r["booking_note"] or "")}</small>',esc(r['phone']),esc(r['table_name']),esc(r['time']),r['guests'],esc({'booked':'จองแล้ว','arrived':'มาแล้ว','cancelled':'ยกเลิกแล้ว'}.get(r['status'],r['status'])),reservation_seating.controls(self,db,r)) for r in db.execute('SELECT r.*,t.name table_name,c.code,c.note booking_note FROM reservations r JOIN tables t ON t.id=r.table_id LEFT JOIN customer_bookings c ON c.reservation_id=r.id ORDER BY time DESC')])+'</section>'
            import simpler_ui
            self.page('การจองโต๊ะ',simpler_ui.reservations_page(self,db,body))
        elif path in ['/reports','/export']:
            start=self.query.get('start',[datetime.now().date().isoformat()])[0]; end=self.query.get('end',[datetime.now().date().isoformat()])[0]
            datetime.fromisoformat(start); datetime.fromisoformat(end)
            rows=db.execute("SELECT * FROM orders WHERE status='paid' AND substr(closed,1,10) BETWEEN ? AND ? ORDER BY id DESC",(start,end)).fetchall()
            if path=='/export':
                out=io.StringIO(); w=csv.writer(out); w.writerow(['Bill','Closed','Payment','Subtotal','Discount','Service','Tax','Total'])
                for r in rows: w.writerow([r['id'],r['closed'],r['method'],money(r['total']-r['service']-r['tax']+r['discount']),money(r['discount']),money(r['service']),money(r['tax']),money(r['total'])])
                self.respond('\ufeff'+out.getvalue(),content='text/csv; charset=utf-8',headers=[('Content-Disposition','attachment; filename="sales.csv"')]); return
            total=sum(r['total'] for r in rows)
            cost=db.execute("SELECT COALESCE(SUM(i.cost*i.qty),0) FROM items i JOIN orders o ON o.id=i.order_id WHERE o.status='paid' AND substr(o.closed,1,10) BETWEEN ? AND ?",(start,end)).fetchone()[0]
            expense=db.execute('SELECT COALESCE(SUM(amount),0) FROM expenses WHERE substr(created,1,10) BETWEEN ? AND ?',(start,end)).fetchone()[0]
            waste=db.execute("SELECT COALESCE(SUM(qty*cost),0) FROM item_cancellations WHERE disposition='waste' AND substr(created,1,10) BETWEEN ? AND ?",(start,end)).fetchone()[0]
            net=total-sum(r['tax'] for r in rows)-cost-expense-waste
            body=f'<section class=panel><form class=fields method=get>{field("ตั้งแต่","start",start,"date")}{field("ถึง","end",end,"date")}<button>ดูรายงาน</button></form></section><div class=cards>'+''.join(f'<div class=card><small>{k}</small><p class=stat>฿ {money(v)}</p></div>' for k,v in [('รับชำระรวม',total),('ต้นทุนสินค้า',cost),('ค่าใช้จ่าย',expense),('กำไรประมาณการก่อนภาษีเงินได้',net)])+'</div>'
            body+=f'<section class=panel><a class="button secondary" href="/export?{urlencode({"start":start,"end":end})}">ส่งออก CSV</a>'+grid(['บิล','เวลาชำระ','ช่องทาง','ยอดสุทธิ',''],[(r['id'],esc(r['closed']),esc(r['method']),money(r['total']),f'<a href="/receipt?id={r["id"]}">ใบเสร็จ →</a>') for r in rows])+'</section>'
            popular=db.execute("SELECT i.name,SUM(i.qty) qty,SUM(i.qty*i.price) revenue FROM items i JOIN orders o ON o.id=i.order_id WHERE o.status='paid' AND substr(o.closed,1,10) BETWEEN ? AND ? GROUP BY i.product_id ORDER BY qty DESC LIMIT 10",(start,end)).fetchall()
            body+='<section class=panel><h2>สินค้าขายดี</h2>'+grid(['สินค้า','จำนวน','ยอดก่อนส่วนลด'],[(esc(r['name']),r['qty'],money(r['revenue'])) for r in popular])+'</section>'
            channels=db.execute('SELECT method,SUM(amount) amount,COUNT(*) transactions FROM payments WHERE substr(created,1,10) BETWEEN ? AND ? GROUP BY method',(start,end)).fetchall()
            body+='<section class=panel><h2>รับชำระตามวันที่รับเงินจริง</h2><p class=muted>รวมเงินที่รับจากบิลแบ่งชำระที่ยังไม่ปิดด้วย จึงอาจต่างจากยอดขายบิลปิดด้านบน</p>'+grid(['ช่องทาง','จำนวนครั้ง','ยอดรับสุทธิ'],[(esc(r['method']),r['transactions'],money(r['amount'])) for r in channels])+'</section>'
            body+=f'<section class=panel><h2>ต้นทุนของเสียจากการยกเลิก ฿{money(waste)}</h2><p>หักในกำไรประมาณการแล้ว · บันทึกตามวันที่ยกเลิก</p>'+grid(['เวลา','บิล','สินค้า','จำนวน','การจัดการ','เหตุผล'],[(esc(r['created']),f'#{r["order_id"]}',esc(r['name']),r['qty'],'ของเสีย' if r['disposition']=='waste' else 'คืนสต็อก',esc(r['reason'])) for r in db.execute('SELECT c.*,p.name FROM item_cancellations c JOIN products p ON p.id=c.product_id WHERE substr(c.created,1,10) BETWEEN ? AND ? ORDER BY c.id DESC LIMIT 100',(start,end))])+'</section>'
            self.page('รายงานยอดขาย',body)
        elif path=='/expenses':
            self.page('รายจ่าย','<section class=panel><p class=muted>เลือกเงินสดเมื่อจ่ายจากลิ้นชักของกะปัจจุบัน ระบบจะหักยอดเงินที่ควรมีให้อัตโนมัติ</p>'+self.form('/expense',field('รายการ','title',extra='required')+field('จำนวนเงิน','amount','','number','min=0.01 step=0.01 required')+'<label>ช่องทางจ่าย<select name=method><option>อื่นๆ</option><option>เงินสด</option><option>โอนเงิน</option></select></label><button>บันทึก</button>')+'</section><section class=panel>'+grid(['วันเวลา','รายการ','จำนวน','ช่องทาง','กะ'],[(esc(r['created']),esc(r['title']),money(r['amount']),esc(r['method']),r['shift_id'] or '—') for r in db.execute('SELECT * FROM expenses ORDER BY id DESC LIMIT 200')])+'</section>')
        elif path=='/settings':
            s=dict(db.execute('SELECT key,value FROM settings').fetchall())
            body='<section class=panel><h2>ข้อมูลร้านและการคิดเงิน</h2>'+self.form('/settings',field('ชื่อร้าน','shop',s['shop'],extra='required')+field('ที่อยู่','address',s['address'])+field('ค่าบริการ %','service',s['service'],'number','min=0 max=100 step=0.01 required')+field('ภาษี %','tax',s['tax'],'number','min=0 max=100 step=0.01 required')+'<button>บันทึก</button>')+'</section><section class=panel><h2>เพิ่มพนักงาน</h2>'+self.form('/user',field('ชื่อผู้ใช้','username',extra='required')+field('รหัสผ่าน','password','','password','minlength=10 required')+'<label>สิทธิ์<select name=role><option value=staff>พนักงาน</option><option value=manager>ผู้จัดการ</option></select></label><button>สร้างบัญชี</button>')+'</section><section class=panel><h2>เปลี่ยนรหัสผ่านของคุณ</h2>'+self.form('/password',field('รหัสเดิม','old','','password','required')+field('รหัสใหม่','new','','password','minlength=10 required')+'<button>เปลี่ยนรหัสผ่าน</button>')+'</section><section class=panel><h2>สำรองข้อมูล</h2><p class=muted>ดาวน์โหลดฐานข้อมูล SQLite แล้วเปิดด้วย DB Browser for SQLite ได้</p><a class=button href=/backup>ดาวน์โหลดฐานข้อมูล</a></section><section class=panel><h2>ประวัติการทำรายการล่าสุด</h2>'+grid(['เวลา','ผู้ใช้','การทำรายการ'],[(esc(r['created']),esc(r['username']),esc(r['action'])) for r in db.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 50')])+'</section>'
            import simpler_ui
            self.page('ตั้งค่าและพนักงาน',simpler_ui.settings_page(self,db,body,workstations.user_controls(self,db)))
        elif path=='/backup':
            target=sqlite3.connect(':memory:'); db.backup(target); data=target.serialize(); target.close()
            self.respond(data,content='application/octet-stream',headers=[('Content-Disposition','attachment; filename="nightbar-backup.sqlite3"')])
        else: self.respond('Not found',404)
    def do_POST(self):
        self.s=self.session()
        self.query={}
        data={}
        self.uploads={};self.created_uploads=[];self.upload_committed=False
        try:
            length=int(self.headers.get('Content-Length','0'))
            multipart=self.headers.get('Content-Type','').lower().startswith('multipart/form-data')
            if multipart:
                customer_slip=urlparse(self.path).path=='/customer/deposit-reference'
                if not customer_slip and (urlparse(self.path).path not in ['/product','/product-presentation','/product-save','/deposit-qr'] or not self.s or self.s['role']!='manager'):self.respond('Forbidden',403);return
                if length<1 or length>menu_uploads.MAX_BODY:self.respond('รูปต้องไม่เกิน 5 MB',413);return
                data,self.uploads=menu_uploads.parse(self.rfile.read(length),self.headers.get('Content-Type',''))
            else:
                if length<0 or length>32768: self.respond('Request too large',413); return
                data={k:v[0] for k,v in parse_qs(self.rfile.read(length).decode(),keep_blank_values=True).items()}
            if self.customer_post(urlparse(self.path).path,data): return
            if not self.s or not hmac.compare_digest(data.get('csrf',''),self.s['csrf']):
                self.respond('<!doctype html><meta charset=utf-8><p>เซสชันหมดอายุหรือแบบฟอร์มถูกเปลี่ยน กรุณาเปิดหน้าใหม่แล้วลองอีกครั้ง</p><a href="/">กลับหน้าหลัก</a>',403); return
            path=urlparse(self.path).path
            with connect() as db:
                db.execute('BEGIN IMMEDIATE')
                if path=='/reset-password':
                    auth_ui.reset_password(self,db,data)
                    db.commit(); self.redirect('/login','ตั้งรหัสผ่านใหม่แล้ว กรุณาเข้าสู่ระบบ'); return
                if path in ['/setup','/login']:
                    if path=='/setup':
                        if db.execute('SELECT 1 FROM users').fetchone(): raise ValueError('ตั้งค่าแล้ว กรุณาเข้าสู่ระบบ')
                        if len(data['password'])<10 or not data['username'].strip(): raise ValueError('ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง')
                        db.execute('INSERT INTO users(username,password,role) VALUES (?,?,?)',(data['username'].strip(),password(data['password']),'manager'))
                    username=data['username'].strip()
                    if len(username)>80 or len(data['password'])>256: raise ValueError('ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง')
                    if path=='/login' and auth_ui.blocked(db,username,self.client_address[0]): raise ValueError('ลองเข้าสู่ระบบหลายครั้ง กรุณารอ 10 นาทีแล้วลองใหม่')
                    user=db.execute('SELECT * FROM users WHERE username=?',(username,)).fetchone()
                    if not user or not verify(data['password'],user['password']):
                        db.execute('INSERT INTO login_failures(username,ip,created) VALUES (?,?,?)',(username,self.client_address[0],datetime.now().isoformat()))
                        db.commit(); raise ValueError('ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง')
                    db.execute('DELETE FROM login_failures WHERE username=?',(username,))
                    token=secrets.token_hex(32); SESSIONS[token]={'username':user['username'],'role':user['role'],'station':user['station'],'csrf':secrets.token_hex(32),'expires':datetime.now()+timedelta(hours=12)}
                    db.commit(); self.redirect('/',headers=[('Set-Cookie',f'{self.cookie_name}={token}; HttpOnly; SameSite=Strict; Path=/')]); return
                if self.s['role'] not in ['manager','staff']: self.respond('Forbidden',403); return
                if path=='/logout':
                    self.s['expires']=datetime.min; self.redirect('/login',headers=[('Set-Cookie',f'{self.cookie_name}=; Max-Age=0; HttpOnly; SameSite=Strict; Path=/')]); return
                restricted=['/stock','/stock-batch','/product','/product-edit','/product-presentation','/void','/settings','/user','/expense']
                if path in restricted and self.s['role']!='manager': self.respond('Forbidden',403); return
                dest=self.mutate(db,path,data)
                db.execute('INSERT INTO audit(username,action,created) VALUES (?,?,?)',(self.s['username'],path+' '+json.dumps({k:v for k,v in data.items() if k not in ['csrf','old','new','confirm','token'] and 'password' not in k},ensure_ascii=False),now()))
                db.commit()
                self.upload_committed=True
                self.s.get('form_drafts',{}).pop(path,None)
            if hasattr(self,'new_reset'): auth_ui.issued(self); return
            message='บันทึกเรียบร้อยแล้ว'
            if path=='/stock-batch':message=('รายการนี้บันทึกไปแล้ว ไม่ปรับซ้ำ' if getattr(self,'stock_was_duplicate',False) else f'ปรับสต็อกแล้ว {self.stock_saved_count} รายการ')
            import simpler_ui
            dest=simpler_ui.settings_destination(path,dest)
            self.redirect(dest,message)
        except (ValueError,KeyError,sqlite3.IntegrityError) as error:
            message='ข้อมูลซ้ำหรือไม่ถูกต้อง กรุณาตรวจสอบอีกครั้ง' if isinstance(error,(KeyError,sqlite3.IntegrityError)) else str(error)
            dest='/login' if urlparse(self.path).path in ['/login','/setup'] else '/'
            if urlparse(self.path).path=='/login': dest+='?'+urlencode({'username':data.get('username','')[:80]})
            if urlparse(self.path).path=='/reset-password': dest='/reset-password?'+urlencode({'token':data.get('token','')[:128]})
            if data.get('order_id','').isdigit(): dest='/order?id='+data['order_id']
            action=urlparse(self.path).path
            convenience.remember(self,action,data)
            if action in ['/shift-open','/shift-close','/cash-event']: dest='/shifts'
            if action in ['/checkout-simple','/checkout-deposit','/checkout-freeze','/checkout-unlock','/bill-split','/payment-add'] and data.get('order_id','').isdigit(): dest='/checkout?id='+data['order_id']
            if action in ['/queue-status','/service-done','/service-bill']: dest='/customer-queue'
            if action=='/expense': dest='/expenses'
            if action in ['/product','/product-presentation','/product-edit','/stock','/stock-batch']:dest='/products'
            if action.startswith('/deposit-'):dest='/reservations'
            if action=='/product-save':dest='/products?view=edit&product_id='+data.get('product_id','0')
            if action=='/open':dest='/tables'
            if action=='/reservation-status':dest='/reservations'
            if action=='/production-status':dest='/order?id='+data['return_order'] if data.get('return_order','').isdigit() else '/production'
            if action in ['/option-add','/option-toggle','/option-edit']:dest='/products?view=edit'+('&product_id='+data['return_product'] if data.get('return_product','').isdigit() else '')
            if action=='/product-availability':dest='/products?view=list'
            if action=='/product-station':dest='/menu-options'
            if action=='/staff-station':dest='/settings'
            import simpler_ui
            dest=simpler_ui.settings_destination(action,dest)
            self.redirect(dest,message)
        except Exception:
            self.respond('เกิดข้อผิดพลาดภายใน กรุณารีเฟรชและลองใหม่',500)
        finally:
            menu_uploads.cleanup(self)
    def mutate(self,db,path,d):
        deposit_result=deposits.mutate(self,db,path,d)
        if deposit_result:return deposit_result
        if path=='/product-save':
            if self.s['role']!='manager':raise ValueError('เฉพาะผู้จัดการ')
            pid=integer(d['product_id'])
            self.mutate(db,'/product-edit',d)
            menu_uploads.presentation(self,db,pid,d)
            workstations.mutate(self,db,'/product-station',d)
            return f'/products?view=edit&product_id={pid}'
        if not workstations.allowed(self,path,True):raise ValueError('หน้าที่ของคุณไม่มีสิทธิ์ทำรายการนี้')
        short_result=streamline.mutate(self,db,path,d)
        if short_result:return short_result
        result=workstations.mutate(self,db,path,d) or menu_options.mutate(self,db,path,d)
        if result:return result
        seating_result=table_management.mutate(self,db,path,d)
        if seating_result:return seating_result
        if path=='/stock-batch':return stock_batch.mutate(self,db,d)
        if path in ['/add','/void','/remove']:
            if path=='/remove':
                item=db.execute('SELECT order_id FROM items WHERE id=?',(integer(d['item_id']),)).fetchone()
                oid=item[0] if item else 0
            else: oid=integer(d['order_id'])
            if operations.locked(db,oid): raise ValueError('บิลอยู่ระหว่างชำระ กรุณาปลดล็อกในหน้าชำระก่อนแก้รายการ ถ้ารับเงินแล้วจะปลดล็อกไม่ได้')
        operation_result=operations.mutate(self,db,path,d)
        if operation_result: return operation_result
        auth_result=auth_ui.admin_mutate(self,db,path,d)
        if auth_result: return auth_result
        if path=='/product-presentation':
            menu_uploads.presentation(self,db,integer(d['product_id']),d)
            return '/products'
        customer_result=self.customer_admin_mutate(db,path,d)
        if customer_result: return customer_result
        if path=='/open':
            reservation=convenience.nearby_booking(db,integer(d['table_id']))
            if reservation and d.get('reservation_ack')!=str(reservation['id']):raise ValueError('โต๊ะมีการจองใกล้เวลานี้ กรุณาตรวจการจองและติ๊กยืนยันที่หน้าโต๊ะก่อนเปิด')
            oid=db.execute('INSERT INTO orders(table_id,opened) VALUES (?,?)',(integer(d['table_id']),now())).lastrowid
            customer.ensure_visit(db,oid)
            return f'/order?id={oid}'
        if path in ['/add','/void']:
            oid=integer(d['order_id']); order=db.execute("SELECT * FROM orders WHERE id=? AND status='open'",(oid,)).fetchone()
            if not order: raise ValueError('บิลปิดแล้วหรือไม่มีบิลนี้')
        if path=='/add':
            pid=integer(d['product_id']); qty=integer(d['qty']); p=db.execute('SELECT * FROM products WHERE id=? AND active=1',(pid,)).fetchone()
            if not p or p['stock']<qty: raise ValueError('สินค้าไม่เพียงพอ')
            db.execute('UPDATE products SET stock=stock-? WHERE id=?',(qty,pid))
            db.execute('INSERT INTO items(order_id,product_id,name,price,cost,qty) VALUES (?,?,?,?,?,?)',(oid,pid,p['name'],p['price'],p['cost'],qty))
            db.execute('UPDATE items SET station=?,prep_status=?,prep_created=?,prep_tracked=? WHERE id=last_insert_rowid()',(workstations.for_product(db,p),'received' if d.get('prep_required')=='1' else 'served',now(),int(d.get('prep_required')=='1')))
            db.execute('INSERT INTO movements(product_id,qty,reason,created) VALUES (?,?,?,?)',(pid,-qty,f'ออเดอร์ #{oid}',now()))
            return f'/order?id={oid}'
        if path=='/remove':
            raise ValueError('กรุณาใช้ปุ่มยกเลิกรายการ เพื่อระบุเหตุผลและการจัดการสต็อก')
            if self.s['role']!='manager':raise ValueError('ให้ผู้จัดการยืนยันยกเลิกรายการ')
            if db.execute('SELECT 1 FROM customer_lines WHERE item_id=?',(integer(d['item_id']),)).fetchone(): raise ValueError('รายการลูกค้าให้ยกเลิกผ่านหน้าคิวออเดอร์ลูกค้า')
            item=db.execute("SELECT i.* FROM items i JOIN orders o ON o.id=i.order_id WHERE i.id=? AND o.status='open'",(integer(d['item_id']),)).fetchone()
            if not item: raise ValueError('ไม่สามารถลบรายการนี้ได้')
            db.execute('UPDATE products SET stock=stock+? WHERE id=?',(item['qty'],item['product_id']))
            db.execute('INSERT INTO movements(product_id,qty,reason,created) VALUES (?,?,?,?)',(item['product_id'],item['qty'],f'ลบรายการบิล #{item["order_id"]}',now()))
            db.execute('DELETE FROM items WHERE id=?',(item['id'],)); return f'/order?id={item["order_id"]}'
        if path=='/void':
            if not d['reason'].strip(): raise ValueError('ระบุเหตุผลยกเลิก')
            for item in db.execute('SELECT * FROM items WHERE order_id=?',(oid,)).fetchall():
                db.execute('UPDATE products SET stock=stock+? WHERE id=?',(item['qty'],item['product_id']))
                db.execute('INSERT INTO movements(product_id,qty,reason,created) VALUES (?,?,?,?)',(item['product_id'],item['qty'],f'ยกเลิกบิล #{oid}',now()))
            db.execute("UPDATE customer_requests SET status='cancelled' WHERE order_id=? AND status!='cancelled'",(oid,))
            db.execute("UPDATE service_requests SET status='done' WHERE order_id=?",(oid,))
            db.execute("UPDATE orders SET status='void',closed=?,note=? WHERE id=?",(now(),d['reason'],oid)); return '/tables'
        if path=='/product':
            if self.s['role']!='manager':raise ValueError('เฉพาะผู้จัดการ')
            if not d['name'].strip() or not d['category'].strip(): raise ValueError('ระบุชื่อและหมวดสินค้า')
            pid=db.execute('INSERT INTO products(name,category,price,cost,stock,minimum) VALUES (?,?,?,?,?,?)',(d['name'].strip(),d['category'].strip(),amount(d['price']),amount(d['cost']),integer(d['stock'],0),integer(d['minimum'],0))).lastrowid
            db.execute('INSERT INTO movements(product_id,qty,reason,created) VALUES (?,?,?,?)',(pid,int(d['stock']),'สต็อกเริ่มต้น',now()))
            menu_uploads.presentation(self,db,pid,d)
            menu_options.seed(db,db.execute('SELECT * FROM products WHERE id=?',(pid,)).fetchone())
            return '/products'
        if path=='/product-edit':
            if self.s['role']!='manager':raise ValueError('เฉพาะผู้จัดการ')
            if d['active'] not in ['0','1']: raise ValueError('สถานะไม่ถูกต้อง')
            pid=integer(d['product_id']); old=db.execute('SELECT * FROM products WHERE id=?',(pid,)).fetchone()
            if not old:raise ValueError('ไม่พบเมนู')
            name=d.get('name',old['name']).strip();category=d.get('category',old['category']).strip()
            if not name or not category or len(name)>120 or len(category)>80:raise ValueError('กรุณาระบุชื่อและหมวดให้ถูกต้อง')
            db.execute('UPDATE products SET name=?,category=?,cost=?,minimum=?,price=?,active=? WHERE id=?',(name,category,amount(d['cost']) if 'cost' in d else old['cost'],integer(d['minimum'],0) if 'minimum' in d else old['minimum'],amount(d['price']),int(d['active']),pid)); return '/products?view=edit&product_id='+str(pid)
        if path=='/stock':
            pid=integer(d['product_id']); qty=int(d['qty'])
            if abs(qty)>1000000 or qty==0 or not d['reason'].strip(): raise ValueError('ระบุจำนวนและเหตุผล')
            r=db.execute('UPDATE products SET stock=stock+? WHERE id=? AND stock+?>=0',(qty,pid,qty))
            if r.rowcount!=1: raise ValueError('สต็อกไม่พอหรือไม่พบสินค้า')
            db.execute('INSERT INTO movements(product_id,qty,reason,created) VALUES (?,?,?,?)',(pid,qty,d['reason'],now())); return '/products'
        if path=='/reserve':
            t=datetime.fromisoformat(d['time']); tid=integer(d['table_id']); guests=integer(d['guests'])
            if t.tzinfo is not None or t<datetime.now(): raise ValueError('เวลาจองต้องเป็นอนาคต')
            table=db.execute('SELECT * FROM tables WHERE id=?',(tid,)).fetchone()
            if not table or guests>table['seats']: raise ValueError('จำนวนคนเกินความจุโต๊ะ')
            state,label=floor_plan.state(db,table,t,guests)
            if state!='available': raise ValueError('โต๊ะไม่พร้อมจอง: '+label)
            if not d['name'].strip() or not d['phone'].strip(): raise ValueError('ระบุชื่อลูกค้าและเบอร์โทร')
            for r in floor_plan.blocking_bookings(db,tid):
                if abs((datetime.fromisoformat(r['time'])-t).total_seconds())<7200: raise ValueError('โต๊ะมีการจองภายในช่วง 2 ชั่วโมงนี้')
            db.execute('INSERT INTO reservations(name,phone,table_id,time,guests) VALUES (?,?,?,?,?)',(d['name'],d['phone'],tid,t.isoformat(timespec='minutes'),guests)); return '/reservations'
        if path=='/reservation-status':
            if d.get('status')=='arrived':return reservation_seating.arrive(self,db,d)
            if d['status'] not in ['arrived','cancelled']: raise ValueError('สถานะไม่ถูกต้อง')
            rid=integer(d['id']);dep=db.execute('SELECT state FROM booking_deposits WHERE reservation_id=?',(rid,)).fetchone()
            old=db.execute('SELECT status FROM reservations WHERE id=?',(rid,)).fetchone()
            if not old or old[0]!='booked':raise ValueError('การจองเปลี่ยนสถานะแล้ว กรุณาเปิดหน้าใหม่')
            if d['status']=='arrived' and dep and dep[0]!='confirmed':raise ValueError('ต้องตรวจสอบและยืนยันมัดจำก่อนรับเข้าที่นั่ง')
            if d['status']=='cancelled':deposits.cancel(db,rid,self.s['username'])
            db.execute('UPDATE reservations SET status=? WHERE id=?',(d['status'],integer(d['id']))); return '/reservations'
        if path=='/settings':
            for key in ['service','tax']:
                rate=Decimal(d[key])
                if not rate.is_finite() or rate<0 or rate>100: raise ValueError('อัตราต้องอยู่ระหว่าง 0–100')
            if not d['shop'].strip(): raise ValueError('ระบุชื่อร้าน')
            for key in ['shop','address','service','tax']: db.execute('UPDATE settings SET value=? WHERE key=?',(d[key],key))
            return '/settings'
        if path=='/user':
            if len(d['password'])<10 or not d['username'].strip() or d['role'] not in ['staff','manager']: raise ValueError('บัญชีไม่ถูกต้อง หรือรหัสผ่านสั้นกว่า 10 ตัว')
            db.execute('INSERT INTO users(username,password,role) VALUES (?,?,?)',(d['username'].strip(),password(d['password']),d['role'])); return '/settings'
        if path=='/password':
            user=db.execute('SELECT * FROM users WHERE username=?',(self.s['username'],)).fetchone()
            if not verify(d['old'],user['password']) or len(d['new'])<10: raise ValueError('รหัสเดิมไม่ถูกต้องหรือรหัสใหม่สั้นเกินไป')
            db.execute('UPDATE users SET password=? WHERE id=?',(password(d['new']),user['id']))
            db.execute('UPDATE password_resets SET used=? WHERE user_id=? AND used IS NULL',(now(),user['id']))
            for s in SESSIONS.values():
                if s['username']==self.s['username'] and s is not self.s: s['expires']=datetime.min
            return '/settings'
        raise ValueError('ไม่พบคำสั่ง')

if __name__=='__main__':
    import sys, threading, webbrowser
    initialize()
    host=os.environ.get('NIGHTBAR_HOST','127.0.0.1'); port=int(os.environ.get('NIGHTBAR_PORT','8765'))
    try: server=ThreadingHTTPServer((host,port),Handler)
    except OSError as error:
        print(f'Cannot start server: {error}\nIf NIGHTBAR is already running, open http://127.0.0.1:{port}',flush=True)
        if '--open' in sys.argv: webbrowser.open(f'http://127.0.0.1:{port}')
        raise SystemExit(1)
    if '--open' in sys.argv:
        threading.Timer(1,lambda: webbrowser.open(f'http://127.0.0.1:{port}')).start()
    print(f'NIGHTBAR running at http://{host}:{port} — Ctrl+C to stop',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: print('\nServer stopped')



