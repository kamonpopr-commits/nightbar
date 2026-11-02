"""Customer experience and staff fulfillment for Nightbar. All views rendered in Python."""
import secrets
import json
import re
import io
import sys
from pathlib import Path
from datetime import datetime, timedelta
from urllib.parse import urlencode, urlparse
from decimal import Decimal, ROUND_HALF_UP
import visuals
import operations
import live_ui
import ux
import floor_plan
import experience
import convenience
import polish
import menu_options
import workstations
import deposits
import readability
import simpler_ui


def initialize(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS visits(order_id INTEGER PRIMARY KEY REFERENCES orders(id), token TEXT UNIQUE NOT NULL);
    CREATE TABLE IF NOT EXISTS customer_sessions(token TEXT PRIMARY KEY, csrf TEXT NOT NULL, expires TEXT NOT NULL, visit TEXT, cart TEXT NOT NULL DEFAULT '{}');
    CREATE TABLE IF NOT EXISTS customer_requests(id INTEGER PRIMARY KEY, session_token TEXT NOT NULL REFERENCES customer_sessions(token), order_id INTEGER NOT NULL REFERENCES orders(id), created TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'received', note TEXT NOT NULL, request_key TEXT UNIQUE NOT NULL);
    CREATE TABLE IF NOT EXISTS customer_lines(id INTEGER PRIMARY KEY, request_id INTEGER NOT NULL REFERENCES customer_requests(id), item_id INTEGER REFERENCES items(id), name TEXT NOT NULL, qty INTEGER NOT NULL, price INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS customer_bookings(reservation_id INTEGER PRIMARY KEY REFERENCES reservations(id), session_token TEXT NOT NULL REFERENCES customer_sessions(token), code TEXT UNIQUE NOT NULL, note TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS booking_submissions(request_key TEXT PRIMARY KEY, session_token TEXT NOT NULL REFERENCES customer_sessions(token), reservation_id INTEGER NOT NULL REFERENCES reservations(id));
    CREATE TABLE IF NOT EXISTS service_requests(id INTEGER PRIMARY KEY, session_token TEXT NOT NULL REFERENCES customer_sessions(token), order_id INTEGER NOT NULL REFERENCES orders(id), kind TEXT NOT NULL, created TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'waiting');
    ''')
    db.execute("INSERT OR IGNORE INTO settings VALUES ('customer_url','')")
    for order in db.execute("SELECT id FROM orders WHERE status='open'").fetchall():
        ensure_visit(db,order['id'])


def ensure_visit(db,oid):
    db.execute('INSERT OR IGNORE INTO visits VALUES (?,?)',(oid,secrets.token_urlsafe(24)))
    return db.execute('SELECT token FROM visits WHERE order_id=?',(oid,)).fetchone()[0]


ART='''<svg viewBox="0 0 200 160" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="100" cy="78" r="66" fill="#d9aa62" fill-opacity=".07"/><path d="M58 35h84l-42 60-42-60z" fill="#d6a961" fill-opacity=".15" stroke="#d6a961" stroke-width="2"/><path d="M67 48h66L100 95 67 48z" fill="#d6a961" fill-opacity=".3"/><path d="M100 95v37m-23 0h46M112 48l27-30" stroke="#f0cd91" stroke-width="3" stroke-linecap="round"/><circle cx="134" cy="36" r="16" stroke="#89a886" stroke-width="3"/><path d="M134 21v30m-15-15h30" stroke="#89a886" stroke-width="1.5"/></svg>'''
STYLE='''
.customer{max-width:1190px;margin:auto;padding:24px 30px 110px}.customer header{border-bottom:1px solid var(--border);padding-bottom:22px;gap:20px}.brand{letter-spacing:4px;color:var(--gold);font-size:23px;font-weight:750}.customer-nav{display:flex;gap:8px;flex-wrap:wrap}.customer-nav a,.chip{padding:10px 15px;border:1px solid var(--border);border-radius:30px;font-size:13px}.customer-nav a:hover,.chip.selected{background:var(--gold);color:#171717}.hero{display:grid;grid-template-columns:1.5fr 1fr;align-items:center;min-height:310px;background:radial-gradient(ellipse at right,#393026,transparent 65%);border:1px solid #40382c;border-radius:20px;padding:35px;margin:25px 0}.hero h1{font-size:clamp(32px,5vw,54px);line-height:1.2;margin:14px 0}.hero p{line-height:1.9;color:#adb3bc;max-width:540px}.hero svg{max-height:230px;width:100%}.menu-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}.menu-item{overflow:hidden;border:1px solid var(--border);border-radius:16px;background:var(--panel)}.menu-art{height:135px;background:linear-gradient(130deg,#20251f,#21212c);display:flex;align-items:center;justify-content:center}.menu-art svg{height:120px;width:150px}.menu-info{padding:20px}.menu-info h3{font-size:18px;margin:8px 0 12px}.price{font-size:20px;color:var(--gold);font-weight:600}.menu-bottom{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-top:20px}.menu-bottom form.fields{display:flex;gap:8px}.menu-bottom input{width:65px}.filters{display:flex;gap:10px;overflow:auto;margin:20px 0 26px;padding-bottom:8px}.chip{white-space:nowrap}.customer .fields{grid-template-columns:1fr 1fr}.customer .fields button,.wide{grid-column:1/-1}.customer .summary{border-top:1px solid var(--border);padding-top:18px;margin-top:18px}.bottom-bar{position:fixed;bottom:16px;left:50%;transform:translateX(-50%);width:min(95%,650px);display:flex;justify-content:space-between;align-items:center;padding:15px 20px;background:#262c36;border:1px solid #5b4e36;border-radius:15px;box-shadow:0 12px 35px #0008;z-index:10}.steps{display:flex;gap:9px;flex-wrap:wrap;margin:18px 0}.step{padding:8px 14px;background:#242c39;border-radius:30px;font-size:12px}.step.current{background:#445339;color:#d4efb3}.ticket{font-size:30px;letter-spacing:4px;color:var(--gold)}.qr{width:220px;height:220px;background:white;padding:12px;border-radius:10px}.qr-card{text-align:center;break-inside:avoid}.customer input:focus,.customer select:focus{outline:2px solid var(--gold)}.customer .notice{line-height:1.8}.subtle{background:#0f151f;border-radius:10px;padding:16px;line-height:1.8}.customer footer{line-height:1.8}.menu-item small{font-size:11px}.empty{text-align:center;padding:50px 20px}.booking-code{font-size:24px;letter-spacing:3px;color:var(--gold)}@media(max-width:760px){.customer{padding:18px 16px 110px}.customer header{display:block}.customer-nav{margin-top:18px}.hero{padding:25px;grid-template-columns:1fr;min-height:0}.hero>svg{display:none}.menu-grid{grid-template-columns:repeat(2,1fr)}.menu-info{padding:14px}.menu-info h3{font-size:16px}.menu-bottom{align-items:start;flex-direction:column}.menu-bottom form{width:100%}.menu-bottom button{flex:1}.customer .fields{grid-template-columns:1fr}.customer .split{grid-template-columns:1fr}}@media(max-width:390px){.menu-grid{grid-template-columns:1fr}}@media print{.customer header,.bottom-bar{display:none}.qr-card{color:black}.qr-card a{color:black}}
'''
STATUS={'received':'รับออเดอร์แล้ว','preparing':'กำลังจัดเตรียม','ready':'พร้อมเสิร์ฟ','served':'เสิร์ฟแล้ว','cancelled':'ยกเลิกแล้ว'}

def product_art(category):
    if category=='ค็อกเทล': return ART
    shapes={
        'เบียร์':'<path d="M65 35h65v95H65z" fill="#d6a961" fill-opacity=".35" stroke="#e5bf79" stroke-width="3"/><path d="M130 50h18v58h-18M80 55v55m18-55v55m18-55v55" stroke="#e5bf79" stroke-width="4"/><path d="M66 35c-15-24 10-32 22-22 6-15 29-15 34 0 21-6 30 15 8 22" fill="#e8dbc2"/>',
        'อาหาร':'<ellipse cx="100" cy="88" rx="65" ry="35" fill="#d6a961" fill-opacity=".12" stroke="#d6a961" stroke-width="2"/><ellipse cx="100" cy="88" rx="46" ry="23" stroke="#d6a961"/><path d="M69 92l14-32 12 4-14 32m10-1 14-36 12 4-14 36m7-2 14-29 11 4-14 29" stroke="#e4bd76" stroke-width="7"/>',
        'สุรา':'<path d="M85 20h30v28l15 20v66H70V68l15-20V20z" fill="#d6a961" fill-opacity=".25" stroke="#e4bd76" stroke-width="3"/><path d="M82 18h36v12H82z" fill="#8fa38a"/><path d="M70 81h60v34H70z" fill="#dfcfb0"/><path d="M85 97h30" stroke="#4b412e" stroke-width="3"/>',
        'มิกเซอร์':'<path d="M76 27h48l-7 105H83L76 27z" fill="#8fa38a" fill-opacity=".15" stroke="#9eafa0" stroke-width="3"/><path d="M80 62h40" stroke="#9eafa0"/><path d="M91 50l12 3-3 14-13-3zm12 25 11 4-4 13-11-3z" fill="#c0d4db" fill-opacity=".5"/><path d="M105 62l24-48" stroke="#e4bd76" stroke-width="3"/>'}
    return '<svg viewBox="0 0 200 160" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="100" cy="78" r="66" fill="#d9aa62" fill-opacity=".07"/>'+shapes.get(category,shapes['อาหาร'])+'</svg>'


class CustomerMixin:
    @property
    def customer_cookie(self): return f'nb_customer_{self.server.server_port}'

    def customer_session(self,db):
        from http.cookies import SimpleCookie
        c=SimpleCookie()
        try: c.load(self.headers.get('Cookie',''))
        except Exception: pass
        value=c.get(self.customer_cookie)
        row=db.execute('SELECT * FROM customer_sessions WHERE token=? AND expires>?',(value.value if value else '',datetime.now().isoformat())).fetchone()
        self.customer_headers=[]
        if not row:
            token=secrets.token_urlsafe(32)
            db.execute('INSERT INTO customer_sessions(token,csrf,expires) VALUES (?,?,?)',(token,secrets.token_hex(32),(datetime.now()+timedelta(days=90)).isoformat()))
            row=db.execute('SELECT * FROM customer_sessions WHERE token=?',(token,)).fetchone()
            self.customer_headers=[('Set-Cookie',f'{self.customer_cookie}={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=7776000')]
        self.c=dict(row)

    def customer_form(self,action,body):
        a=self.api
        encoding=' enctype="multipart/form-data"' if action=='/customer/deposit-reference' else ''
        return f'<form action="{action}" method="post" class="fields"{encoding}><input type="hidden" name="csrf" value="{a.esc(self.c["csrf"])}">{body}</form>'

    def customer_page(self,db,title,body):
        a=self.api; s=dict(db.execute('SELECT key,value FROM settings').fetchall())
        cart=json.loads(self.c['cart']); count=sum(cart.values())
        visit=self.active_visit(db)
        if visit:
            changed=db.execute("SELECT detail FROM table_events WHERE order_id=? AND action IN ('/table-move','/table-merge','/table-join','/table-release') ORDER BY id DESC LIMIT 1",(visit['id'],)).fetchone()
            if changed:body='<p class=notice>พนักงานอัปเดตที่นั่งของคุณ: '+a.esc(changed[0])+'</p>'+body
        table=f'<span class=badge data-seating-label>โต๊ะ {a.esc(visit["name"])}</span>' if visit else '<span class=muted>ดูเมนู / จองโต๊ะ</span>'
        if visit:
            import table_management
            body+=table_management.CUSTOMER_SCRIPT
        message=self.query.get('message',[''])[0]
        notice=f'<div class=notice>{a.esc(message)}</div>' if message else ''
        subtotal=sum((menu_options.product(db,pid) or {'price':0})['price']*qty for pid,qty in cart.items())
        total=self.estimate(db,subtotal)[2]
        bottom=f'<div class=bottom-bar><span><span data-seating-label>โต๊ะ {a.esc(visit["name"])}</span> · <span data-cart-count>{count}</span> รายการ<small>รวมประมาณการ <strong>฿<span data-cart-total>{a.money(total)}</span></strong> · รวมบริการและภาษี</small></span><a class=button href=/cart>ดูตะกร้า →</a></div>' if visit else ''
        if title not in ['เมนู','ตะกร้า','ติดตามออเดอร์']:bottom=''
        cart_class='nav-cart-with-bottom' if bottom else ''
        if title=='ตะกร้า':
            link='href=#confirm-order>ไปยืนยันสั่ง →' if count and visit and not operations.locked(db,visit['id']) else 'href=/menu>เลือกเมนู →'
            bottom=bottom.replace('href=/cart>ดูตะกร้า →',link)
        self.respond(f'<!doctype html><html lang=th><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>{a.esc(title)} · {a.esc(s["shop"])}</title><style>{a.CSS}{STYLE}{visuals.BRAND_CSS}{ux.CSS}{experience.CSS}{convenience.CSS}@media(max-width:760px){{.customer-nav .nav-cart-with-bottom{{display:none}}}}.latest-order{{margin:16px 0}}.latest-order p{{margin:6px 0 12px}}</style></head><body><div class=customer><header><a class=brand href=/menu>{visuals.brand(s["shop"])}</a><div class=customer-nav><a href=/menu>เมนู</a><a class="{cart_class}" href=/cart>ตะกร้า (<span data-cart-count>{count}</span>)</a><a href=/my-orders>ออเดอร์ของฉัน</a><a href=/booking>จองโต๊ะ</a></div></header>{table}{notice}{body}<footer>{a.esc(s["shop"])} · {a.esc(s["address"])}<br>โปรดแจ้งพนักงานหากมีอาการแพ้อาหาร · ชำระเงินกับพนักงานที่ร้าน<br><a href=/login>สำหรับพนักงาน →</a></footer></div>{bottom}{ux.SCRIPT}</body></html>',headers=self.customer_headers)

    def active_visit(self,db):
        token=self.c['visit']
        alias=db.execute('SELECT target FROM visit_aliases WHERE token=?',(token,)).fetchone()
        if alias:token=alias[0]
        return db.execute("SELECT o.*,t.name,v.token FROM visits v JOIN orders o ON o.id=v.order_id JOIN order_labels t ON t.id=o.id WHERE v.token=? AND o.status='open'",(token,)).fetchone()

    def customer_get(self,db,path):
        if path not in ['/menu','/cart','/my-orders','/live/my-orders','/booking','/live/seating','/live/booking','/live/booking-confirmation','/live/order-summary']: return False
        deposits.expire(db)
        a=self.api; self.customer_session(db)
        if path=='/menu' and 'visit' in self.query:
            token=self.query['visit'][0]
            visit=db.execute("SELECT v.* FROM visits v JOIN orders o ON o.id=v.order_id WHERE v.token=? AND o.status='open'",(token,)).fetchone()
            if not visit:
                db.commit(); self.customer_page(db,'QR หมดอายุ','<section class="panel empty"><h1>QR นี้ใช้สั่งไม่ได้แล้ว</h1><p>กรุณาขอ QR สำหรับบิลปัจจุบันจากพนักงาน</p><a class=button href=/menu>ดูเมนู</a></section>'); return True
            if self.c['visit']!=token:
                db.execute("UPDATE customer_sessions SET visit=?,cart='{}' WHERE token=?",(token,self.c['token']))
                self.c.update(visit=token,cart='{}')
            db.commit(); self.redirect('/menu',headers=self.customer_headers); return True
        db.commit()
        visit=self.active_visit(db)
        if path=='/live/booking-confirmation':
            key=self.query.get('confirmed',[''])[0]
            row=db.execute('SELECT r.id,r.status,d.state FROM booking_submissions s JOIN reservations r ON r.id=s.reservation_id LEFT JOIN booking_deposits d ON d.reservation_id=r.id WHERE s.request_key=? AND s.session_token=?',(key,self.c['token'])).fetchone()
            payload={'html':experience.booking_confirmation(self,db,key)}
            if row:
                label={'booked':'จองสำเร็จ','arrived':'มาถึงแล้ว','cancelled':'ยกเลิกแล้ว'}.get(row['status'],row['status'])
                if row['status']=='booked' and row['state'] in ['pending','review']:label='รอยืนยันการจอง · '+deposits.LABELS[row['state']]
                payload.update(id=row['id'],label=label,deposit_state=row['state'])
            self.respond(json.dumps(payload,ensure_ascii=False),content='application/json; charset=utf-8',headers=self.customer_headers);return True
        if path=='/live/order-summary':
            self.respond(json.dumps({'html':simpler_ui.latest_order(self,db)},ensure_ascii=False),content='application/json; charset=utf-8',headers=self.customer_headers);return True
        if path=='/live/seating':
            self.respond(json.dumps({'open':bool(visit),'name':visit['name'] if visit else ''},ensure_ascii=False),content='application/json; charset=utf-8',headers=self.customer_headers);return True
        if path=='/live/booking':
            try:
                t,guests=floor_plan.validate_time(self.query.get('time',[''])[0],self.query.get('guests',[''])[0])
                rows=[{'id':str(r['id']),'state':state,'label':label,'zone':floor_plan.LAYOUT[r['name']][2]} for r,state,label in floor_plan.available(db,t,guests)]
                self.respond(json.dumps({'tables':rows},ensure_ascii=False),content='application/json; charset=utf-8',headers=self.customer_headers)
            except ValueError:self.respond(json.dumps({'message':'เวลาที่เลือกใกล้เกินไป กรุณาเลือกเวลาและดูโต๊ะว่างใหม่'},ensure_ascii=False),400,content='application/json; charset=utf-8',headers=self.customer_headers)
            return True
        if path=='/menu':
            settling=visit is not None and operations.locked(db,visit['id']) is not None
            category=self.query.get('category',[''])[0]; search=self.query.get('search',[''])[0][:100]
            s=dict(db.execute('SELECT key,value FROM settings').fetchall())
            body=f'<section class=hero><div><div class=eyebrow>GOOD COMPANY. GREAT NIGHTS.</div><h1>อาหารดี เครื่องดื่มโปรด<br>ค่ำคืนของคุณ</h1><p>เครื่องดื่ม อาหาร และช่วงเวลาดี ๆ ที่ {a.esc(s["shop"])} เลือกเมนูโปรด แล้วให้เราดูแลค่ำคืนนี้ของคุณ</p><div class=hero-actions><a class=button href="#our-menu">เลือกเมนู →</a><a class="button secondary" href=/booking>จองโต๊ะล่วงหน้า ↗</a></div><span class=hero-caption>JUPITER · BAR &amp; KITCHEN</span></div>{ART}</section>'
            if visit:
                body=f'<section class=quick-order><div class=eyebrow>สั่งอาหารที่โต๊ะ</div><h1>โต๊ะ {a.esc(visit["name"])} · เลือกเมนูได้เลย</h1><p>{"โต๊ะนี้กำลังชำระเงิน กรุณาติดต่อพนักงานก่อนสั่งเพิ่ม" if settling else "เพิ่มเมนูลงตะกร้า แล้วตรวจรายการก่อนกดยืนยันสั่ง"}</p><a class="button secondary" href=/my-orders>ติดตามออเดอร์ / เรียกพนักงาน →</a></section>'
            if visit:
                latest=simpler_ui.latest_order(self,db)
                if latest:body=body.replace('<a class="button secondary" href=/my-orders>ติดตามออเดอร์ / เรียกพนักงาน →</a>','')
                body+='<div id=latest-order aria-live=polite>'+latest+'</div>'+simpler_ui.LATEST_SCRIPT
            if not visit: body+='<div class=subtle>ดูเมนูได้ทันที หากต้องการสั่งที่ร้าน กรุณาสแกน QR บิลปัจจุบันที่พนักงานมอบให้</div>'
            body+=f'<form class=fields method=get action=/menu>{a.field("ค้นหาเมนู","search",search,"search")}<button class=secondary>ค้นหา</button></form><div class=filters><a class="chip {"selected" if not category else ""}" href=/menu>ทั้งหมด</a>'
            for r in db.execute('SELECT DISTINCT category FROM products WHERE active=1 ORDER BY category'):
                body+=f'<a class="chip {"selected" if category==r[0] else ""}" href="/menu?{urlencode({"category":r[0],"search":search})}">{a.esc(r[0])}</a>'
            body+='</div><div class=section-title id=our-menu><div><div class=eyebrow>MADE FOR YOUR EVENING</div><h2>เมนูที่อยากให้ลอง</h2></div><p>อาหารจานเดียว · เครื่องดื่ม · ทานเล่น</p></div><div class=menu-grid>'
            products=db.execute("SELECT p.*,v.image,v.description,COALESCE(v.featured,0) featured FROM products p LEFT JOIN product_presentation v ON v.product_id=p.id WHERE active=1 AND (?='' OR category=?) AND instr(lower(name),lower(?))>0 ORDER BY featured DESC,category,name",(category,category,search)).fetchall()
            for p in products:
                available=p['stock']>0
                form=self.customer_form('/customer/cart',f'<input type=hidden name=product_id value={p["id"]}>'+menu_options.controls(self,db,p['id'])+f'{ux.quantity(1,1,min(20,p["stock"]),"จำนวน "+p["name"])}<button>+ เพิ่ม</button>') if visit and available and not settling else '<span class=muted>'+('กำลังชำระเงิน' if settling else 'หมดชั่วคราว' if not available else 'สแกน QR ที่โต๊ะเพื่อสั่ง')+'</span>'
                picture=f'<img src="/assets/{a.esc(p["image"])}" alt="{a.esc(p["name"])}" loading=lazy decoding=async width=960 height=960>' if p['image'] else product_art(p['category'])
                featured='<span class=dish-featured>เมนูแนะนำ</span>' if p['featured'] else ''
                description=p['description'] or 'เลือกเมนูโปรดของคุณ แล้วให้เราดูแลค่ำคืนนี้'
                body+=f'<article class=menu-item><div class=menu-art>{picture}{featured}<button type=button class=detail-open aria-label="ดูรายละเอียด {a.esc(p["name"])}"></button><span class=detail-hint>ดูรายละเอียด ↗</span></div><div class=menu-info><small>{a.esc(p["category"])}</small><h3>{a.esc(p["name"])}</h3><p class=menu-description>{a.esc(description)}</p><span class=badge>{"พร้อมเสิร์ฟ" if available else "หมดชั่วคราว"}</span><div class=menu-bottom><span class=price>฿{a.money(p["price"])}</span>{form}</div></div></article>'
            body+='</div>' if products else '</div><div class="panel empty">ไม่พบเมนูที่ค้นหา <a href=/menu>ดูทั้งหมด</a></div>'
            body+=menu_options.CSS+'<style>'+readability.CSS+'</style>'+readability.SCRIPT
            body+=f'<p class=menu-note>ราคาเมนูก่อนค่าบริการ {a.esc(s["service"])}% และภาษี {a.esc(s["tax"])}% · ดูยอดประมาณการในตะกร้าก่อนยืนยัน<br>ภาพเป็นภาพประกอบเมนู ปริมาณและการจัดเสิร์ฟจริงอาจแตกต่าง · หากมีอาการแพ้อาหาร กรุณาแจ้งพนักงานก่อนสั่ง</p>'
            self.customer_page(db,'เมนู',body)
        elif path=='/cart':
            self.customer_page(db,'ตะกร้า',polish.cart(self,db,visit))
        elif path in ['/my-orders','/live/my-orders']:
            body='<h1>ออเดอร์ของฉัน</h1><p class=muted>สถานะอัปเดตอัตโนมัติ · แสดงเฉพาะรายการที่สั่งจากเบราว์เซอร์นี้</p>'
            requests=db.execute('SELECT r.*,t.name,o.status bill_status FROM customer_requests r JOIN orders o ON o.id=r.order_id JOIN order_labels t ON t.id=o.id WHERE session_token=? ORDER BY r.id DESC LIMIT 50',(self.c['token'],)).fetchall()
            for r in requests:
                lines=db.execute('SELECT * FROM customer_lines WHERE request_id=?',(r['id'],)).fetchall()
                steps=''.join(f'<span class="step {"current" if r["status"]==k else ""}">{v}</span>' for k,v in STATUS.items() if k!='cancelled' or r['status']==k)
                body+=f'<section class=panel id=request-{r["id"]}><small>{ux.date(r["created"])}</small><h2>ออเดอร์ #{r["id"]:04} · โต๊ะ {a.esc(r["name"])}</h2><div class=steps>{steps}</div>'+a.grid(['รายการ','จำนวน','รวม'],[(a.esc(l['name']),l['qty'],a.money(l['qty']*l['price'])) for l in lines])+f'<p class=muted>{a.esc(r["note"])}</p><small>สถานะบิล: {ux.status(r["bill_status"])}</small></section>'
            if not requests: body+='<div class="panel empty">ยังไม่มีออเดอร์ <a href=/menu>เลือกเมนู →</a></div>'
            if visit:
                body+='<section class=panel><h2>ให้เราช่วยอะไรดี?</h2>'+self.customer_form('/customer/service','<label>บริการ<select name=kind><option value=staff>เรียกพนักงาน</option><option value=bill>ขอเช็กบิล</option></select></label><button>ส่งคำขอ</button>')+'</section>'
            confirmation_key=self.query.get('confirmed',[''])[0]
            body=experience.order_confirmation(self,db,confirmation_key)+body
            if path=='/live/my-orders': self.respond(json.dumps({'html':body,'ids':[]},ensure_ascii=False),content='application/json; charset=utf-8',headers=self.customer_headers)
            else: self.customer_page(db,'ติดตามออเดอร์',live_ui.controls()+f'<div id=live-content>{body}</div>'+live_ui.script('/live/my-orders?'+urlencode({'confirmed':confirmation_key})))
        elif path=='/booking':
            confirmation_key=self.query.get('confirmed',[''])[0]
            body='<div id=booking-confirmation>'+experience.booking_confirmation(self,db,confirmation_key)+'</div>'+floor_plan.render(self,db)
            if confirmation_key:body+=experience.booking_live(confirmation_key)
            bookings=db.execute('SELECT r.*,c.code,c.note,t.name table_name FROM customer_bookings c JOIN reservations r ON r.id=c.reservation_id JOIN tables t ON t.id=r.table_id WHERE c.session_token=? ORDER BY r.time DESC LIMIT 30',(self.c['token'],)).fetchall()
            for b in bookings:
                state={'booked':'จองสำเร็จ','arrived':'มาถึงแล้ว','cancelled':'ยกเลิกแล้ว'}.get(b['status'],b['status'])
                dep=db.execute('SELECT state FROM booking_deposits WHERE reservation_id=?',(b['id'],)).fetchone()
                if dep and dep[0] in ['pending','review']:state='รอยืนยันการจอง · '+deposits.LABELS[dep[0]]
                body+=f'<section class=panel id=booking-{b["id"]}><div class=booking-code>{a.esc(b["code"])}</div><h3><span data-booking-state={b["id"]}>{a.esc(state)}</span> · โต๊ะ {a.esc(b["table_name"])}</h3><p>{ux.date(b["time"])} · {b["guests"]} คน</p><p>{a.esc(b["name"])} · {a.esc(b["phone"])}<br>{a.esc(b["note"])}</p>'
                body+=deposits.customer_card(self,db,b['id'])
                if b['status']=='booked': body+=self.customer_form('/customer/booking-cancel',f'<input type=hidden name=id value={b["id"]}><button class=danger>ยกเลิกการจองนี้</button>')
                body+='</section>'
            if not bookings: body+='<div class=panel>ยังไม่มีการจองจากเบราว์เซอร์นี้</div>'
            self.customer_page(db,'จองโต๊ะ',body)
        return True

    def estimate(self,db,subtotal):
        s=dict(db.execute('SELECT key,value FROM settings').fetchall())
        service=int((Decimal(subtotal)*Decimal(s['service'])/100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
        tax=int((Decimal(subtotal+service)*Decimal(s['tax'])/100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
        return service,tax,subtotal+service+tax

    def quote(self,db,cart):
        import hashlib
        rows=[]
        for pid,qty in sorted(cart.items()):
            p=menu_options.product(db,pid)
            rows.append((pid,qty,(p['price'],p['cost'],p['active'],p['name']) if p else None))
        settings=list(map(tuple,db.execute("SELECT key,value FROM settings WHERE key IN ('service','tax') ORDER BY key")))
        return hashlib.sha256(json.dumps([rows,settings]).encode()).hexdigest()

    def customer_post(self,path,data):
        if not path.startswith('/customer/'): return False
        a=self.api; dest='/menu'
        ajax=path=='/customer/cart' and 'application/json' in self.headers.get('Accept','')
        if path in ['/customer/checkout','/customer/cart']: dest='/cart'
        if 'booking' in path: dest='/booking'
        if path=='/customer/deposit-reference':dest='/booking'
        if path=='/customer/service': dest='/my-orders'
        try:
            with a.connect() as db:
                db.execute('BEGIN IMMEDIATE'); self.customer_session(db)
                if not secrets.compare_digest(self.c['csrf'],data.get('csrf','')): raise ValueError('แบบฟอร์มหมดอายุ กรุณาเปิดหน้าใหม่แล้วลองอีกครั้ง')
                self.customer_mutate(db,path,data)
                if ajax:
                    cart=json.loads(db.execute('SELECT cart FROM customer_sessions WHERE token=?',(self.c['token'],)).fetchone()[0])
                    subtotal=sum((menu_options.product(db,pid) or {'price':0})['price']*qty for pid,qty in cart.items())
                    service,tax,total=self.estimate(db,subtotal)
                    entries={}
                    for pid,qty in cart.items():
                        p=menu_options.product(db,pid)
                        if p:entries[pid]={'qty':qty,'price':a.money(p['price']),'total':a.money(p['price']*qty)}
                    payload={'count':sum(cart.values()),'total':a.money(total),'subtotal':a.money(subtotal),'service':a.money(service),'tax':a.money(tax),'quote':self.quote(db,cart),'cart':entries}
            if ajax:
                self.respond(json.dumps(payload),content='application/json; charset=utf-8',headers=self.customer_headers); return True
            if path=='/customer/booking':
                self.redirect('/booking?'+urlencode({'message':'รับคำขอจองแล้ว กรุณาตรวจสถานะและมัดจำด้านล่าง เก็บรหัสไว้แจ้งพนักงาน','confirmed':data.get('request_key','')}),headers=self.customer_headers); return True
            if path=='/customer/cart' and 'replace' not in data: dest='/menu'
            if path=='/customer/checkout': dest='/my-orders?'+urlencode({'confirmed':data.get('request_key','')})
            self.redirect(dest,'บันทึกเรียบร้อยแล้ว',self.customer_headers)
        except (ValueError,KeyError) as error:
            if ajax:
                self.respond(json.dumps({'message':str(error) if isinstance(error,ValueError) else 'กรุณากรอกข้อมูลให้ครบ'},ensure_ascii=False),400,content='application/json; charset=utf-8',headers=getattr(self,'customer_headers',[])); return True
            if path=='/customer/booking': dest='/booking?'+urlencode({k:data.get(k,'')[:40] for k in ['time','guests','table_id']})
            self.redirect(dest,str(error) if isinstance(error,ValueError) else 'กรุณากรอกข้อมูลให้ครบ',getattr(self,'customer_headers',[]))
        return True

    def customer_mutate(self,db,path,d):
        deposits.expire(db)
        if deposits.customer_mutate(self,db,path,d):return
        a=self.api; cart=json.loads(self.c['cart']); visit=self.active_visit(db)
        if path in ['/customer/cart','/customer/checkout','/customer/service'] and not visit: raise ValueError('บิลปิดแล้วหรือยังไม่ได้สแกน QR ประจำบิล กรุณาติดต่อพนักงาน')
        if path=='/customer/cart':
            key=d['product_id'] if 'replace' in d else menu_options.key(db,d['product_id'],d)
            pid,_=menu_options.split(key);qty=a.integer(d['qty'],0)
            if 'replace' in d and qty==0:
                cart.pop(key,None)
                db.execute('UPDATE customer_sessions SET cart=? WHERE token=?',(json.dumps(cart),self.c['token']))
                return
            if operations.locked(db,visit['id']): raise ValueError('โต๊ะนี้กำลังชำระเงิน กรุณาติดต่อพนักงานก่อนสั่งเพิ่ม')
            p=menu_options.product(db,key,True)
            if not p or not p['active']: raise ValueError('ไม่พบเมนูนี้')
            qty=qty if 'replace' in d else qty+cart.get(key,0)
            aggregate=sum(q for k,q in cart.items() if menu_options.split(k)[0]==pid and k!=key)+qty
            if qty>20 or aggregate>p['stock']: raise ValueError('จำนวนรวมของเมนูเกินสต็อก หรือเกิน 20 ต่อรูปแบบ')
            if qty: cart[key]=qty
            else: cart.pop(key,None)
            db.execute('UPDATE customer_sessions SET cart=? WHERE token=?',(json.dumps(cart),self.c['token']))
        elif path=='/customer/checkout':
            key=d.get('request_key','')
            if not re.fullmatch(r'[A-Za-z0-9_-]{20,80}',key): raise ValueError('แบบฟอร์มไม่ถูกต้อง')
            duplicate=db.execute('SELECT session_token FROM customer_requests WHERE request_key=?',(key,)).fetchone()
            if duplicate:
                if duplicate[0]!=self.c['token']: raise ValueError('แบบฟอร์มไม่ถูกต้อง')
                return
            if operations.locked(db,visit['id']): raise ValueError('โต๊ะนี้กำลังชำระเงิน กรุณาติดต่อพนักงานก่อนสั่งเพิ่ม')
            if not cart or d.get('confirmed')!='1': raise ValueError('กรุณาตรวจสอบรายการและยืนยัน')
            if not secrets.compare_digest(d.get('quote',''),self.quote(db,cart)): raise ValueError('ราคาเมนูหรือค่าบริการเปลี่ยน กรุณาตรวจสอบยอดใหม่ก่อนยืนยัน')
            if db.execute("SELECT COUNT(*) FROM customer_requests WHERE session_token=? AND created>?",(self.c['token'],(datetime.now().astimezone()-timedelta(minutes=10)).isoformat())).fetchone()[0]>=20: raise ValueError('ส่งออเดอร์หลายครั้ง กรุณาติดต่อพนักงาน')
            rid=db.execute('INSERT INTO customer_requests(session_token,order_id,created,note,request_key) VALUES (?,?,?,?,?)',(self.c['token'],visit['id'],a.now(),d.get('note','')[:300],key)).lastrowid
            for pid,qty in cart.items():
                p=menu_options.product(db,pid,True)
                if not p or not p['active'] or p['stock']<qty: raise ValueError('บางเมนูหมดหรือสต็อกไม่พอ กรุณาปรับตะกร้า')
                base=p['id'];db.execute('UPDATE products SET stock=stock-? WHERE id=?',(qty,base))
                iid=db.execute('INSERT INTO items(order_id,product_id,name,price,cost,qty,station,prep_status,prep_created,prep_tracked) VALUES (?,?,?,?,?,?,?,?,?,1)',(visit['id'],base,p['name'],p['price'],p['cost'],qty,workstations.for_product(db,p),'received',a.now())).lastrowid
                db.execute('INSERT INTO customer_lines(request_id,item_id,name,qty,price) VALUES (?,?,?,?,?)',(rid,iid,p['name'],qty,p['price']))
                db.execute('INSERT INTO movements(product_id,qty,reason,created) VALUES (?,?,?,?)',(base,-qty,f'ลูกค้าสั่ง #{rid}',a.now()))
            db.execute("UPDATE customer_sessions SET cart='{}' WHERE token=?",(self.c['token'],))
        elif path=='/customer/service':
            if d.get('kind') not in ['staff','bill']: raise ValueError('คำขอไม่ถูกต้อง')
            if db.execute("SELECT 1 FROM service_requests WHERE order_id=? AND kind=? AND status IN ('waiting','handling')",(visit['id'],d['kind'])).fetchone(): raise ValueError('ส่งคำขอแล้ว พนักงานจะมาดูแลคุณครับ')
            db.execute('INSERT INTO service_requests(session_token,order_id,kind,created) VALUES (?,?,?,?)',(self.c['token'],visit['id'],d['kind'],a.now()))
        elif path=='/customer/booking':
            key=d.get('request_key','')
            if key:
                if not re.fullmatch(r'[A-Za-z0-9_-]{20,80}',key): raise ValueError('แบบฟอร์มไม่ถูกต้อง')
                duplicate=db.execute('SELECT session_token FROM booking_submissions WHERE request_key=?',(key,)).fetchone()
                if duplicate:
                    if duplicate[0]!=self.c['token']: raise ValueError('แบบฟอร์มไม่ถูกต้อง')
                    return
            name=d.get('name','').strip(); phone=d.get('phone','').strip(); t,guests=floor_plan.validate_time(d['time'],d['guests'])
            if not name or len(name)>80 or not re.fullmatch(r'[0-9+ ()-]{8,20}',phone) or d.get('consent')!='1': raise ValueError('กรุณากรอกชื่อ เบอร์โทร และยินยอมเก็บข้อมูลการจอง')
            if t.tzinfo is not None or t<datetime.now()+timedelta(minutes=15) or t>datetime.now()+timedelta(days=90): raise ValueError('จองล่วงหน้าอย่างน้อย 15 นาที และไม่เกิน 90 วัน')
            cutoff=(datetime.now()-timedelta(hours=2)).isoformat(timespec='minutes')
            if db.execute("SELECT COUNT(*) FROM customer_bookings c JOIN reservations r ON r.id=c.reservation_id WHERE c.session_token=? AND r.status='booked' AND r.time>?",(self.c['token'],cutoff)).fetchone()[0]>=3: raise ValueError('มีการจองที่ใช้งานอยู่ครบ 3 รายการแล้ว กรุณาติดต่อร้าน')
            selected=None; requested=d.get('table_id','')
            for table,state,label in floor_plan.available(db,t,guests):
                if requested and str(table['id'])!=requested: continue
                if state=='available': selected=table; break
                if requested: raise ValueError('โต๊ะที่เลือกไม่พร้อมจอง: '+label+' กรุณาเลือกโต๊ะหรือเวลาใหม่')
            if requested and not selected: raise ValueError('ไม่พบโต๊ะที่เลือกในผัง กรุณาเลือกใหม่')
            if not selected: raise ValueError('ไม่มีโต๊ะว่างที่รองรับจำนวนคนในช่วงเวลานี้ กรุณาเลือกเวลาอื่น')
            rid=db.execute('INSERT INTO reservations(name,phone,table_id,time,guests) VALUES (?,?,?,?,?)',(name,phone,selected['id'],t.isoformat(timespec='minutes'),guests)).lastrowid
            code=secrets.token_hex(4).upper()
            db.execute('INSERT INTO customer_bookings VALUES (?,?,?,?)',(rid,self.c['token'],code,d.get('note','')[:300]))
            deposits.create(self,db,rid,guests,d)
            if key: db.execute('INSERT INTO booking_submissions VALUES (?,?,?)',(key,self.c['token'],rid))
        elif path=='/customer/booking-cancel':
            r=db.execute('SELECT r.* FROM reservations r JOIN customer_bookings c ON c.reservation_id=r.id WHERE r.id=? AND c.session_token=?',(a.integer(d['id']),self.c['token'])).fetchone()
            if not r or r['status']!='booked': raise ValueError('ไม่สามารถยกเลิกการจองนี้ได้')
            deposits.cancel(db,r['id'],'customer')
            db.execute("UPDATE reservations SET status='cancelled' WHERE id=?",(r['id'],))
        else: raise ValueError('ไม่พบคำสั่ง')

    def customer_admin_get(self,db,path):
        if path not in ['/customer-queue','/live/queue','/qr','/qr.svg']: return False
        a=self.api
        if self.s['role'] not in ['manager','staff']: self.respond('Forbidden',403); return True
        if path=='/live/queue':return workstations.get(self,db,'/live/production')
        if path in ['/customer-queue','/live/queue']:
            body='<p class=muted>ออเดอร์ลูกค้าถูกเพิ่มในบิลและตัดสต็อกแล้ว ยกเลิกผ่านคิวนี้เพื่อคืนสต็อก</p>'
            queue=db.execute("SELECT r.*,t.name,o.status bill_status FROM customer_requests r JOIN orders o ON o.id=r.order_id JOIN order_labels t ON t.id=o.id WHERE (o.status='open' AND r.status IN ('received','preparing','ready')) OR r.id IN (SELECT id FROM customer_requests WHERE status IN ('served','cancelled') ORDER BY id DESC LIMIT 30) ORDER BY CASE r.status WHEN 'received' THEN 0 WHEN 'preparing' THEN 1 ELSE 2 END,r.id DESC").fetchall()
            body=polish.queue(self,db,queue)
            services=db.execute("SELECT s.*,t.name FROM service_requests s JOIN orders o ON o.id=s.order_id JOIN order_labels t ON t.id=o.id WHERE s.status IN ('waiting','handling') AND o.status='open' ORDER BY s.id").fetchall()
            service_rows=[]
            for r in services:
                bill=r['kind']=='bill'
                label=('กำลังเช็กบิล / รอชำระ' if r['status']=='handling' else 'ขอเช็กบิล') if bill else 'เรียกพนักงาน'
                action='/service-bill' if bill else '/service-done'
                button=('ชำระต่อ →' if r['status']=='handling' else 'ไปชำระเงิน →') if bill else 'ดูแลแล้ว'
                service_rows.append((a.esc(r['name']),label,ux.date(r['created']),self.form(action,f'<input type=hidden name=id value={r["id"]}><button>{button}</button>')))
            body='<section class=panel><h2>เรียกพนักงาน / ขอเช็กบิล</h2><p class=muted>คำขอเช็กบิลจะติดตามไว้จนชำระเสร็จ การเปิดหน้าชำระยังไม่ถือว่ารับเงินแล้ว</p>'+a.grid(['โต๊ะ','คำขอ','เวลา',''],service_rows)+'</section>'+body
            ids=[f'r{r["id"]}' for r in queue if r['bill_status']=='open' and r['status'] in ['received','preparing','ready']]+[f's{r["id"]}' for r in services]
            if not ids:body='<section class="panel empty"><h2>ไม่มีงานค้างในคิวแล้ว</h2><p>เปิดหน้านี้ไว้ ระบบจะแสดงออเดอร์และคำขอใหม่ให้อัตโนมัติ</p><a class="button secondary" href=/tables>ไปดูโต๊ะ →</a></section>'+body
            if path=='/live/queue': self.respond(json.dumps({'html':body,'ids':ids},ensure_ascii=False),content='application/json; charset=utf-8')
            else: self.page('คิวออเดอร์ลูกค้า',live_ui.controls(staff=True)+f'<div id=live-content>{body}</div>'+live_ui.script('/live/queue',ids,staff=True))
            return True
        s=dict(db.execute('SELECT key,value FROM settings').fetchall()); base=s['customer_url'].rstrip('/') or f'http://127.0.0.1:{getattr(self.server,"server_port",8765)}'
        if path=='/qr.svg':
            oid=a.integer(self.query.get('order_id',['0'])[0]); v=db.execute("SELECT v.token FROM visits v JOIN orders o ON o.id=v.order_id WHERE v.order_id=? AND o.status='open'",(oid,)).fetchone()
            if not v: self.respond('QR expired',404); return True
            sys.path.insert(0,str(Path(__file__).parent/'vendor')) if str(Path(__file__).parent/'vendor') not in sys.path else None
            import qrcode
            from qrcode.image.svg import SvgPathFillImage
            qr=qrcode.make(base+'/menu?'+urlencode({'visit':v['token']}),image_factory=SvgPathFillImage,box_size=8,border=4)
            out=io.BytesIO(); qr.save(out)
            self.respond(out.getvalue(),content='image/svg+xml',headers=[('Content-Disposition',f'inline; filename="table-{oid}.svg"')]); return True
        body='<section class="panel noprint"><h2>พิมพ์ QR / ลิงก์ร้าน</h2><p>ใช้งานหน้าร้าน: เปิดโต๊ะจากหน้าโต๊ะและออเดอร์ แล้วแสดง QR ในหน้าดูแลโต๊ะได้ทันที หน้านี้สำหรับพิมพ์หลายโต๊ะและจัดการลิงก์ร้าน</p><p>เปิดโต๊ะก่อน แล้วใช้ QR ประจำบิลให้ลูกค้าสแกน เมื่อชำระหรือยกเลิกบิล QR จะหมดอายุ เปิดบิลใหม่ต้องใช้ QR ใหม่</p><p>ลูกค้าบนมือถือควรเชื่อม Wi-Fi เดียวกับเครื่องร้าน และตั้ง URL เป็น IP ของเครื่องร้าน ไม่ใช้ 127.0.0.1</p><a class="button secondary" href=/menu>ดูหน้าลูกค้า</a></section>'
        try:
            import socket,ipaddress
            hostname=urlparse(base).hostname
            current={r[4][0] for r in socket.getaddrinfo(socket.gethostname(),None,socket.AF_INET)}
            if hostname and ipaddress.ip_address(hostname).is_private and hostname not in current and hostname!='127.0.0.1':
                body+='<div class="notice noprint">URL สำหรับมือถืออาจเป็น IP เครือข่ายเดิม กรุณาตรวจ IP และอัปเดตก่อนใช้ QR · ปุ่มทดลองสั่งบนเครื่องยังใช้ได้ตามปกติ</div>'
        except (ValueError,OSError): pass
        if self.s['role']=='manager': body+='<section class="panel noprint">'+self.form('/customer-url',a.field('URL สำหรับมือถือ เช่น http://192.168.1.20:8765','url',s['customer_url'],'url')+'<button>บันทึก URL ของร้าน</button>')+'</section>'
        if '127.0.0.1' in base or 'localhost' in base: body+='<div class="notice noprint">ยังใช้ลิงก์สำหรับเครื่องนี้เท่านั้น ตั้ง IP เครือข่ายร้านก่อนพิมพ์ QR ให้มือถือสแกน</div>'
        body+='<div class=cards>'
        selected_order=a.integer(self.query.get('order_id',['0'])[0],0)
        if selected_order:body+='<p><a href=/qr>ดู QR ทุกโต๊ะ →</a></p>'
        for o in db.execute("SELECT o.id,t.name FROM orders o JOIN order_labels t ON t.id=o.id WHERE o.status='open' AND (?=0 OR o.id=?)",(selected_order,selected_order)).fetchall():
            token=ensure_visit(db,o['id']); url='/menu?'+urlencode({'visit':token})
            body+=f'<section class="panel qr-card"><h2>{a.esc(s["shop"])} · {a.esc(o["name"])}</h2><p>สแกนเพื่อดูเมนูและสั่งที่โต๊ะ</p><img class=qr alt="QR โต๊ะ {a.esc(o["name"])}" src="/qr.svg?order_id={o["id"]}"><p>บิล #{o["id"]}</p><p class=noprint><a class=button href="{a.esc(url)}">ทดลองสั่ง</a></p><p class=noprint><a href="/qr.svg?order_id={o["id"]}">เปิด / บันทึก QR</a></p></section>'
        body+='</div><p class=noprint>พิมพ์ QR ด้วย Ctrl+P · ถ้าไม่มี QR ให้เปิดโต๊ะในหน้าโต๊ะและออเดอร์ก่อน</p><style>'+STYLE+'</style>'
        self.page('QR สำหรับลูกค้า',body); return True

    def customer_admin_mutate(self,db,path,d):
        a=self.api
        if path=='/customer-url':
            if self.s['role']!='manager': raise ValueError('เฉพาะผู้จัดการ')
            url=d.get('url','').strip().rstrip('/'); parsed=urlparse(url)
            if url and (parsed.scheme not in ['http','https'] or not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment): raise ValueError('ระบุ URL ของร้าน เช่น http://192.168.1.20:8765 โดยไม่ใส่ path')
            db.execute("UPDATE settings SET value=? WHERE key='customer_url'",(url,)); return '/qr'
        if path in ['/service-done','/service-bill']:
            request=db.execute('SELECT s.*,o.status bill_status FROM service_requests s JOIN orders o ON o.id=s.order_id WHERE s.id=?',(a.integer(d['id']),)).fetchone()
            if not request:raise ValueError('ไม่พบคำขอนี้ กรุณาอัปเดตคิว')
            if path=='/service-bill' and request['kind']!='bill':raise ValueError('รายการนี้เป็นคำขอเรียกพนักงาน')
            if request['kind']=='bill':
                if request['bill_status']=='paid':return f'/receipt?id={request["order_id"]}'
                if request['bill_status']!='open':raise ValueError('บิลปิดหรือยกเลิกแล้ว กรุณาตรวจคิวอีกครั้ง')
                if request['status'] not in ['waiting','handling']:raise ValueError('คำขอนี้ดำเนินการแล้ว กรุณาอัปเดตคิว')
                db.execute("UPDATE service_requests SET status='handling' WHERE id=?",(request['id'],))
                return f'/checkout?id={request["order_id"]}'
            db.execute("UPDATE service_requests SET status='done' WHERE id=?",(request['id'],))
            return '/order?id='+str(request['order_id']) if d.get('return_order')==str(request['order_id']) else '/customer-queue'
        if path=='/queue-status':
            r=db.execute("SELECT r.* FROM customer_requests r JOIN orders o ON o.id=r.order_id WHERE r.id=? AND o.status='open'",(a.integer(d['id']),)).fetchone()
            if not r or r['status'] not in ['received','preparing','ready']: raise ValueError('รายการนี้ไม่สามารถเปลี่ยนสถานะได้แล้ว')
            status=d['status']
            if status not in {'received':['preparing','ready','served','cancelled'],'preparing':['ready','served','cancelled'],'ready':['served','cancelled']}[r['status']]: raise ValueError('สถานะไม่ถูกต้อง')
            if status=='cancelled':
                if not d.get('reason','').strip(): raise ValueError('ระบุเหตุผลการยกเลิก')
                if self.s['role']!='manager':raise ValueError('ให้ผู้จัดการยืนยันการยกเลิกออเดอร์')
                if operations.locked(db,r['order_id']):raise ValueError('บิลอยู่ระหว่างชำระ กรุณาปลดล็อกก่อนยกเลิกรายการ')
                for l in db.execute('SELECT i.* FROM customer_lines l JOIN items i ON i.id=l.item_id WHERE l.request_id=?',(r['id'],)).fetchall():
                    import table_management
                    disposition='return' if l['prep_status']=='received' else 'waste'
                    table_management.cancel_item(self,db,l,disposition,d['reason'][:300])
            if status!='cancelled':
                prior={'preparing':['received'],'ready':['received','preparing'],'served':['received','preparing','ready']}[status]
                db.execute('UPDATE items SET prep_status=? WHERE id IN (SELECT item_id FROM customer_lines WHERE request_id=?) AND prep_status IN ('+','.join('?' for _ in prior)+')',(status,r['id'],*prior))
            if status=='cancelled':db.execute('UPDATE customer_requests SET status=? WHERE id=?',(status,r['id']))
            else:workstations.sync(db,r['order_id'])
            return '/customer-queue'
        return None


