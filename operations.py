"""Register shifts, frozen checkout totals, split bills and payment ledger."""
import secrets
import ux
import experience
from datetime import datetime
from decimal import Decimal,ROUND_HALF_UP

METHODS=('เงินสด','โอนเงิน','บัตร')

def initialize(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS shifts(id INTEGER PRIMARY KEY,opened TEXT NOT NULL,opened_by TEXT NOT NULL,opening INTEGER NOT NULL CHECK(opening>=0),closed TEXT,closed_by TEXT,counted INTEGER,expected INTEGER,difference INTEGER,note TEXT NOT NULL DEFAULT '');
    CREATE UNIQUE INDEX IF NOT EXISTS one_register_shift ON shifts((1)) WHERE closed IS NULL;
    CREATE TABLE IF NOT EXISTS cash_events(id INTEGER PRIMARY KEY,shift_id INTEGER NOT NULL REFERENCES shifts(id),amount INTEGER NOT NULL,reason TEXT NOT NULL,username TEXT NOT NULL,created TEXT NOT NULL,request_key TEXT UNIQUE NOT NULL);
    CREATE TABLE IF NOT EXISTS checkout_totals(order_id INTEGER PRIMARY KEY REFERENCES orders(id),subtotal INTEGER NOT NULL,discount INTEGER NOT NULL,service INTEGER NOT NULL,tax INTEGER NOT NULL,total INTEGER NOT NULL,created TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS receipt_rates(order_id INTEGER PRIMARY KEY REFERENCES orders(id),service TEXT NOT NULL,tax TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS bill_parts(id INTEGER PRIMARY KEY,order_id INTEGER NOT NULL REFERENCES orders(id),label TEXT NOT NULL,amount INTEGER NOT NULL CHECK(amount>=0));
    CREATE TABLE IF NOT EXISTS payments(id INTEGER PRIMARY KEY,order_id INTEGER NOT NULL REFERENCES orders(id),part_id INTEGER REFERENCES bill_parts(id),shift_id INTEGER REFERENCES shifts(id),amount INTEGER NOT NULL CHECK(amount>=0),method TEXT NOT NULL,tendered INTEGER NOT NULL,change INTEGER NOT NULL CHECK(change>=0),username TEXT NOT NULL,created TEXT NOT NULL,request_key TEXT UNIQUE NOT NULL);
    CREATE INDEX IF NOT EXISTS payment_order ON payments(order_id);
    CREATE INDEX IF NOT EXISTS payment_shift ON payments(shift_id);
    ''')
    columns={r[1] for r in db.execute('PRAGMA table_info(expenses)')}
    if 'shift_id' not in columns: db.execute('ALTER TABLE expenses ADD COLUMN shift_id INTEGER REFERENCES shifts(id)')
    if 'method' not in columns: db.execute("ALTER TABLE expenses ADD COLUMN method TEXT NOT NULL DEFAULT 'อื่นๆ'")
    if 'request_key' not in columns: db.execute('ALTER TABLE expenses ADD COLUMN request_key TEXT')
    db.execute('CREATE UNIQUE INDEX IF NOT EXISTS expense_request_key ON expenses(request_key)')
    for o in db.execute("SELECT * FROM orders WHERE status='paid' AND NOT EXISTS (SELECT 1 FROM payments p WHERE p.order_id=orders.id)").fetchall():
        tender=o['received'] if o['received'] is not None else o['total']
        db.execute('INSERT INTO payments(order_id,amount,method,tendered,change,username,created,request_key) VALUES (?,?,?,?,?,?,?,?)',(o['id'],o['total'],o['method'] or 'อื่นๆ',tender,max(0,tender-o['total']),'ประวัติก่อนใช้ระบบกะ',o['closed'] or o['opened'],f'legacy-{o["id"]}'))

def active(db): return db.execute('SELECT * FROM shifts WHERE closed IS NULL').fetchone()
def paid(db,oid): return db.execute('SELECT COALESCE(SUM(amount),0) FROM payments WHERE order_id=?',(oid,)).fetchone()[0]
def part_paid(db,pid): return db.execute('SELECT COALESCE(SUM(amount),0) FROM payments WHERE part_id=?',(pid,)).fetchone()[0]
def locked(db,oid): return db.execute('SELECT * FROM checkout_totals WHERE order_id=?',(oid,)).fetchone()
def cash_summary(db,s):
    cash=db.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE shift_id=? AND method='เงินสด'",(s['id'],)).fetchone()[0]
    expense=db.execute("SELECT COALESCE(SUM(amount),0) FROM expenses WHERE shift_id=? AND method='เงินสด'",(s['id'],)).fetchone()[0]
    adjustments=db.execute('SELECT COALESCE(SUM(amount),0) FROM cash_events WHERE shift_id=?',(s['id'],)).fetchone()[0]
    return {'cash':cash,'expenses':expense,'adjustments':adjustments,'expected':s['opening']+cash-expense+adjustments}

def calculate(a,db,oid,discount):
    if db.execute("SELECT 1 FROM items WHERE order_id=? AND prep_status IN ('received','preparing','ready')",(oid,)).fetchone():raise ValueError('ยังมีรายการรอทำหรือเสิร์ฟ กรุณาตรวจคิวครัว / บาร์ก่อนชำระ')
    items=db.execute('SELECT * FROM items WHERE order_id=?',(oid,)).fetchall()
    if not items: raise ValueError('เพิ่มรายการก่อนชำระเงิน')
    if db.execute("SELECT 1 FROM customer_requests WHERE order_id=? AND status IN ('received','preparing','ready')",(oid,)).fetchone(): raise ValueError('ยังมีออเดอร์ลูกค้ารอเสิร์ฟ กรุณาจัดการคิวก่อนชำระ')
    subtotal=sum(r['price']*r['qty'] for r in items)
    if discount>subtotal: raise ValueError('ส่วนลดเกินยอดรายการ')
    settings=dict(db.execute('SELECT key,value FROM settings').fetchall()); base=subtotal-discount
    service=int((Decimal(base)*Decimal(settings['service'])/100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
    tax=int((Decimal(base+service)*Decimal(settings['tax'])/100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
    return {'subtotal':subtotal,'discount':discount,'service':service,'tax':tax,'total':base+service+tax}

def freeze(h,db,oid,discount):
    a=h.api
    order=db.execute("SELECT * FROM orders WHERE id=? AND status='open'",(oid,)).fetchone()
    if not order: raise ValueError('บิลปิดแล้วหรือไม่พบบิล')
    current=locked(db,oid)
    if current:
        if current['discount']!=discount: raise ValueError('บิลล็อกยอดแล้ว หากยังไม่รับเงินให้ปลดล็อกก่อนเปลี่ยนส่วนลด')
        return current
    if discount and h.s['role']!='manager': raise ValueError('ส่วนลดต้องดำเนินการโดยผู้จัดการ')
    quote=calculate(a,db,oid,discount)
    db.execute('INSERT INTO checkout_totals VALUES (?,?,?,?,?,?,?)',(oid,quote['subtotal'],discount,quote['service'],quote['tax'],quote['total'],a.now()))
    rates=dict(db.execute('SELECT key,value FROM settings'))
    db.execute('INSERT OR REPLACE INTO receipt_rates VALUES (?,?,?)',(oid,rates['service'],rates['tax']))
    db.execute('INSERT INTO bill_parts(order_id,label,amount) VALUES (?,?,?)',(oid,'บิลหลัก',quote['total']))
    return locked(db,oid)

def tender(h,db,part_id,value,method,received,key,deposit=False):
    a=h.api
    if method not in METHODS and not (deposit and method=='มัดจำ'): raise ValueError('ช่องทางชำระไม่ถูกต้อง')
    if not 16<=len(key)<=100: raise ValueError('รหัสทำรายการไม่ถูกต้อง กรุณาเปิดหน้าใหม่')
    old=db.execute('SELECT * FROM payments WHERE request_key=?',(key,)).fetchone()
    if old:
        if (old['part_id'],old['amount'],old['method'],old['tendered'])!=(part_id,value,method,received): raise ValueError('รหัสทำรายการถูกใช้แล้ว กรุณารีเฟรช')
        return old['order_id']
    part=db.execute("SELECT p.* FROM bill_parts p JOIN orders o ON o.id=p.order_id WHERE p.id=? AND o.status='open'",(part_id,)).fetchone()
    if not part: raise ValueError('บิลนี้ปิดแล้วหรือไม่พบบิลย่อย')
    quote=locked(db,part['order_id'])
    if not quote: raise ValueError('ยังไม่ได้ยืนยันยอดบิล')
    if value<0 or (value==0 and quote['total']!=0) or value>part['amount']-part_paid(db,part_id): raise ValueError('ยอดชำระต้องมากกว่า 0 และไม่เกินยอดค้างของบิลย่อย')
    if received<value or (method!='เงินสด' and received!=value): raise ValueError('ยอดรับเงินไม่ถูกต้อง เงินโอนหรือบัตรต้องตรงยอดชำระ')
    shift=active(db)
    if not shift: raise ValueError('กรุณาเปิดกะก่อนรับชำระเงิน')
    db.execute('INSERT INTO payments(order_id,part_id,shift_id,amount,method,tendered,change,username,created,request_key) VALUES (?,?,?,?,?,?,?,?,?,?)',(part['order_id'],part_id,shift['id'],value,method,received,received-value,h.s['username'],a.now(),key))
    if deposit:db.execute('UPDATE payments SET shift_id=NULL WHERE request_key=?',(key,))
    oid=part['order_id']
    if paid(db,oid)==quote['total']:
        methods=[r[0] for r in db.execute('SELECT DISTINCT method FROM payments WHERE order_id=?',(oid,))]
        total_received=db.execute('SELECT SUM(tendered) FROM payments WHERE order_id=?',(oid,)).fetchone()[0]
        db.execute("UPDATE orders SET status='paid',closed=?,discount=?,service=?,tax=?,total=?,method=?,received=? WHERE id=?",(a.now(),quote['discount'],quote['service'],quote['tax'],quote['total'],methods[0] if len(methods)==1 else 'หลายช่องทาง',total_received,oid))
        db.execute("UPDATE service_requests SET status='done' WHERE order_id=?",(oid,))
    return oid

def mutate(h,db,path,d):
    a=h.api
    if path=='/shift-open':
        if active(db): raise ValueError('มีกะเปิดอยู่แล้ว กรุณาใช้กะปัจจุบัน')
        db.execute('INSERT INTO shifts(opened,opened_by,opening) VALUES (?,?,?)',(a.now(),h.s['username'],a.amount(d['opening'])))
        return '/shifts'
    if path=='/shift-close':
        s=active(db)
        if not s or s['id']!=a.integer(d['shift_id']): raise ValueError('กะนี้ถูกปิดแล้วหรือเปลี่ยนกะแล้ว')
        if h.s['role']!='manager' and s['opened_by']!=h.s['username']: raise ValueError('ให้ผู้เปิดกะหรือผู้จัดการเป็นผู้ปิดกะ')
        if db.execute("SELECT 1 FROM payments p JOIN orders o ON o.id=p.order_id WHERE p.shift_id=? AND o.status='open'",(s['id'],)).fetchone(): raise ValueError('ยังมีบิลแบ่งชำระไม่ครบ กรุณารับชำระให้ครบก่อนปิดกะ')
        expected=cash_summary(db,s)['expected']; counted=a.amount(d['counted']); diff=counted-expected; note=d.get('note','').strip()[:300]
        if diff and not note: raise ValueError('เงินไม่ตรง กรุณาระบุเหตุผลหรือหมายเหตุ')
        db.execute('UPDATE shifts SET closed=?,closed_by=?,counted=?,expected=?,difference=?,note=? WHERE id=?',(a.now(),h.s['username'],counted,expected,diff,note,s['id']))
        return '/shifts'
    if path=='/cash-event':
        if h.s['role']!='manager': raise ValueError('เฉพาะผู้จัดการปรับเงินลิ้นชักได้')
        s=active(db)
        if not s or s['id']!=a.integer(d['shift_id']): raise ValueError('กรุณาเปิดหน้ากะปัจจุบันใหม่')
        amount=a.amount(d['amount']); kind=d['kind']; reason=d.get('reason','').strip()[:300]; key=d.get('request_key','')
        if amount<=0 or kind not in ['in','out'] or not reason or not 16<=len(key)<=100: raise ValueError('ระบุจำนวนเงิน ประเภท และเหตุผลให้ครบ')
        amount=amount if kind=='in' else -amount
        old=db.execute('SELECT * FROM cash_events WHERE request_key=?',(key,)).fetchone()
        if old:
            if (old['shift_id'],old['amount'],old['reason'])!=(s['id'],amount,reason): raise ValueError('คำขอซ้ำไม่ตรงกัน')
            return '/shifts'
        if cash_summary(db,s)['expected']+amount<0: raise ValueError('เงินออกเกินยอดที่ควรมีในลิ้นชัก')
        db.execute('INSERT INTO cash_events(shift_id,amount,reason,username,created,request_key) VALUES (?,?,?,?,?,?)',(s['id'],amount,reason,h.s['username'],a.now(),key)); return '/shifts'
    if path=='/expense':
        value=a.amount(d['amount']); method=d.get('method','อื่นๆ'); title=d.get('title','').strip()
        if not title or value<=0 or method not in ['เงินสด','โอนเงิน','อื่นๆ']: raise ValueError('ระบุรายจ่าย จำนวนเงิน และช่องทางให้ถูกต้อง')
        key=d.get('request_key') or secrets.token_urlsafe(24)
        if not 16<=len(key)<=100: raise ValueError('รหัสทำรายการไม่ถูกต้อง')
        old=db.execute('SELECT * FROM expenses WHERE request_key=?',(key,)).fetchone()
        if old:
            if (old['title'],old['amount'],old['method'])!=(title[:200],value,method): raise ValueError('คำขอซ้ำไม่ตรงกัน')
            return '/expenses'
        s=active(db)
        if method=='เงินสด' and not s: raise ValueError('เปิดกะก่อนบันทึกรายจ่ายเงินสด')
        if method=='เงินสด' and cash_summary(db,s)['expected']<value: raise ValueError('รายจ่ายเกินยอดเงินสดในลิ้นชัก')
        db.execute('INSERT INTO expenses(title,amount,created,shift_id,method,request_key) VALUES (?,?,?,?,?,?)',(title[:200],value,a.now(),s['id'] if s else None,method,key)); return '/expenses'
    if path=='/checkout-freeze':
        oid=a.integer(d['order_id']); freeze(h,db,oid,a.amount(d.get('discount','0')))
        return f'/checkout?id={oid}'
    if path=='/checkout-unlock':
        oid=a.integer(d['order_id'])
        if paid(db,oid) or db.execute('SELECT 1 FROM payments WHERE order_id=?',(oid,)).fetchone(): raise ValueError('รับเงินแล้ว ไม่สามารถปลดล็อกหรือเปลี่ยนรายการได้')
        if not db.execute("SELECT 1 FROM orders WHERE id=? AND status='open'",(oid,)).fetchone(): raise ValueError('บิลปิดแล้ว')
        db.execute('DELETE FROM bill_parts WHERE order_id=?',(oid,)); db.execute('DELETE FROM checkout_totals WHERE order_id=?',(oid,));db.execute('DELETE FROM receipt_rates WHERE order_id=?',(oid,)); return f'/order?id={oid}'
    if path=='/bill-split':
        oid=a.integer(d['order_id']); quote=locked(db,oid)
        if not quote: raise ValueError('ยืนยันยอดรวมก่อนแยกบิล')
        if db.execute('SELECT 1 FROM payments WHERE order_id=?',(oid,)).fetchone(): raise ValueError('รับเงินแล้ว ไม่สามารถเปลี่ยนการแยกบิลได้')
        if d['mode']=='equal':
            count=a.integer(d['count'])
            if count>20 or (quote['total']>0 and count>quote['total']): raise ValueError('แยกได้สูงสุด 20 บิลและแต่ละบิลต้องมียอดอย่างน้อย 0.01 บาท')
            base,rem=divmod(quote['total'],count); amounts=[base+(i<rem) for i in range(count)]
        elif d['mode']=='custom':
            amounts=[a.amount(v.strip()) for v in d.get('amounts','').split(',')]
            if not 1<=len(amounts)<=20 or any(v<=0 for v in amounts) or sum(amounts)!=quote['total']: raise ValueError('ยอดแต่ละบิลต้องมากกว่า 0 และรวมเท่ากับยอดสุทธิ แยกได้สูงสุด 20 บิล')
        else: raise ValueError('รูปแบบแยกบิลไม่ถูกต้อง')
        db.execute('DELETE FROM bill_parts WHERE order_id=?',(oid,))
        db.executemany('INSERT INTO bill_parts(order_id,label,amount) VALUES (?,?,?)',[(oid,f'บิลย่อย {i+1}',value) for i,value in enumerate(amounts)])
        return f'/checkout?id={oid}'
    if path=='/payment-add':
        value=a.amount(d['amount']); received=a.amount(d['received']) if d.get('received') else value
        oid=tender(h,db,a.integer(d['part_id']),value,d['method'],received,d.get('request_key',''))
        closed=db.execute('SELECT status FROM orders WHERE id=?',(oid,)).fetchone()[0]=='paid'
        return f'/receipt?id={oid}' if closed else f'/checkout?id={oid}'
    if path=='/pay':
        oid=a.integer(d['order_id']); quote=freeze(h,db,oid,a.amount(d['discount']))
        parts=db.execute('SELECT * FROM bill_parts WHERE order_id=?',(oid,)).fetchall()
        if len(parts)!=1 or db.execute('SELECT 1 FROM payments WHERE order_id=?',(oid,)).fetchone(): raise ValueError('บิลนี้แบ่งชำระอยู่ กรุณาจัดการในหน้าชำระเงิน')
        received=a.amount(d['received']) if d.get('received') else quote['total']
        tender(h,db,parts[0]['id'],quote['total'],d['method'],received,secrets.token_urlsafe(24)); return f'/receipt?id={oid}'
    return None

def payment_table(h,db,oid=None,shift_id=None):
    a=h.api
    where='p.order_id=?' if oid is not None else 'p.shift_id=?'; value=oid if oid is not None else shift_id
    rows=db.execute(f'SELECT p.*,b.label FROM payments p LEFT JOIN bill_parts b ON b.id=p.part_id WHERE {where} ORDER BY p.id',(value,)).fetchall()
    return a.grid(['เวลา','บิลย่อย','ช่องทาง','ชำระ','รับมา','ทอน','ผู้รับ'],[(a.esc(r['created'][11:19]),a.esc(r['label'] or 'บิลเดิม'),a.esc(r['method']),a.money(r['amount']),a.money(r['tendered']),a.money(r['change']),a.esc(r['username'])) for r in rows])

def order_link(h,db,oid):
    a=h.api; quote=locked(db,oid)
    body=f'<section class="panel noprint"><h2>ชำระเงินและแยกบิล</h2>'
    if quote: body+=f'<p>ยอดสุทธิ ฿{a.money(quote["total"])} · รับชำระแล้ว ฿{a.money(paid(db,oid))} · ค้าง ฿{a.money(quote["total"]-paid(db,oid))}</p><p class=muted>ยืนยันยอดแล้ว รายการจะถูกล็อกระหว่างรับชำระ</p>'
    body+=f'<a class=button href="/checkout?id={oid}">เปิดหน้าชำระเงิน →</a> <a class="button secondary" href="/qr?order_id={oid}">แสดง QR</a> <a class="button secondary" href=/customer-queue>ดูคิว</a></section>'
    return body

def get(h,db,path):
    if path not in ['/shifts','/checkout','/part-receipt']: return False
    a=h.api; manager=h.s['role']=='manager'
    if path=='/shifts':
        s=active(db); body=''
        if not s:
            body='<section class=panel><h2>เริ่มกะใหม่</h2><p class=muted>นับเงินทอนตั้งต้นก่อนเปิดกะ ใช้หนึ่งกะร่วมกันต่อเครื่องรับเงิน</p>'+h.form('/shift-open',a.field('เงินสดตั้งต้น (บาท)','opening',0,'number','min=0 step=0.01 required')+'<button>เปิดกะ</button>')+'</section>'
        else:
            summary=cash_summary(db,s)
            body=f'<section class=panel><h2>กะ #{s["id"]} · เปิดโดย {a.esc(s["opened_by"])}</h2><small>{a.esc(s["opened"])}</small><div class=cards>'+''.join(f'<div class=card><small>{label}</small><p class=stat>฿{a.money(value)}</p></div>' for label,value in [('เงินตั้งต้น',s['opening']),('รับเงินสดสุทธิ',summary['cash']),('รายจ่ายเงินสด',summary['expenses']),('เงินสดที่ควรมี',summary['expected'])])+'</div>'
            channels=db.execute('SELECT method,SUM(amount) amount FROM payments WHERE shift_id=? GROUP BY method',(s['id'],)).fetchall()
            body+=a.grid(['ช่องทางรับชำระ','ยอดสุทธิ'],[(a.esc(r['method']),a.money(r['amount'])) for r in channels])+'</section>'
            if manager:
                body+='<section class=panel><h2>เงินเข้า / ออกจากลิ้นชัก</h2><p class=muted>ใช้กับเงินเติมทอนหรือเงินนำส่ง ไม่ใช่รายจ่ายซื้อสินค้า รายจ่ายให้บันทึกในหน้ารายจ่ายเพื่อไม่หักซ้ำ</p>'+h.form('/cash-event',f'<input type=hidden name=shift_id value={s["id"]}><input type=hidden name=request_key value="{secrets.token_urlsafe(24)}"><label>ประเภท<select name=kind><option value=in>เงินเข้า</option><option value=out>เงินออก</option></select></label>'+a.field('จำนวนเงิน','amount','','number','min=0.01 step=0.01 required')+a.field('เหตุผล','reason',extra='required maxlength=300')+'<button>บันทึกเงินลิ้นชัก</button>')+'</section>'
            body+='<section class=panel><h2>ปิดกะและตรวจเงิน</h2>'+h.form('/shift-close',f'<input type=hidden name=shift_id value={s["id"]}>'+a.field('เงินสดที่นับได้จริง','counted','','number','min=0 step=0.01 required')+a.field('หมายเหตุ / เหตุผลเงินต่าง','note',extra='maxlength=300')+'<button>ยืนยันปิดกะ</button>')+'</section>'
            body+='<section class=panel><h2>รับชำระในกะนี้</h2>'+payment_table(h,db,shift_id=s['id'])+'</section>'
            events=db.execute('SELECT * FROM cash_events WHERE shift_id=? ORDER BY id DESC',(s['id'],)).fetchall()
            body+='<section class=panel><h2>ประวัติเงินลิ้นชัก</h2>'+a.grid(['เวลา','จำนวน (+เข้า / −ออก)','เหตุผล','ผู้ทำ'],[(a.esc(r['created']),a.money(r['amount']),a.esc(r['reason']),a.esc(r['username'])) for r in events])+'</section>'
        body=experience.cash_help(a,s,cash_summary(db,s) if s else None)+body
        rows=db.execute('SELECT * FROM shifts WHERE closed IS NOT NULL AND (?=1 OR opened_by=?) ORDER BY id DESC LIMIT 100',(int(manager),h.s['username'])).fetchall()
        body+='<section class=panel><h2>ประวัติกะที่ปิดแล้ว</h2>'+a.grid(['กะ','เปิด','ปิด','ควรมี','นับจริง','ส่วนต่าง','หมายเหตุ'],[(r['id'],a.esc(r['opened']),a.esc(r['closed']),a.money(r['expected']),a.money(r['counted']),a.money(r['difference']),a.esc(r['note'])) for r in rows])+'</section>'
        h.page('เปิด–ปิดกะและเงินสด',body); return True
    if path=='/part-receipt':
        part=db.execute('SELECT p.*,o.status,t.name table_name FROM bill_parts p JOIN orders o ON o.id=p.order_id JOIN order_labels t ON t.id=o.id WHERE p.id=?',(a.integer(h.query.get('id',['0'])[0]),)).fetchone()
        if not part: raise ValueError('ไม่พบบิลย่อย')
        body=f'<section class=panel><h2>{a.esc(part["label"])} · โต๊ะ {a.esc(part["table_name"])}</h2><p>บิลหลัก #{part["order_id"]} · ใบรับเงินส่วนแบ่งของบิลหลัก</p><p class=total>ยอดส่วนนี้ ฿{a.money(part["amount"])}</p><p>รับชำระแล้ว ฿{a.money(part_paid(db,part["id"]))} · ค้าง ฿{a.money(part["amount"]-part_paid(db,part["id"]))}</p>'
        rows=db.execute('SELECT * FROM payments WHERE part_id=? ORDER BY id',(part['id'],)).fetchall()
        body+=a.grid(['เวลา','ช่องทาง','ยอดชำระ','รับมา','เงินทอน'],[(a.esc(r['created']),a.esc(r['method']),a.money(r['amount']),a.money(r['tendered']),a.money(r['change'])) for r in rows])+f'<p class=noprint>พิมพ์ด้วย Ctrl+P · <a href="/checkout?id={part["order_id"]}">กลับหน้าชำระ</a></p></section>'
        h.page('ใบรับเงินบิลย่อย',body); return True
    oid=a.integer(h.query.get('id',['0'])[0]); o=db.execute('SELECT o.*,t.name FROM orders o JOIN order_labels t ON t.id=o.id WHERE o.id=?',(oid,)).fetchone()
    if not o: raise ValueError('ไม่พบบิล')
    if o['status']=='paid': h.redirect(f'/receipt?id={oid}'); return True
    if o['status']!='open': raise ValueError('บิลถูกยกเลิกแล้ว')
    body=f'<section class=panel><h2>โต๊ะ {a.esc(o["name"])} · บิล #{oid}</h2><a class="button secondary" href="/order?id={oid}">กลับไปดูรายการ</a></section>'
    quote=locked(db,oid); shift=active(db)
    import deposits
    body+=deposits.checkout(h,db,oid)
    pending=db.execute("SELECT COUNT(*) FROM items WHERE order_id=? AND prep_status IN ('received','preparing','ready')",(oid,)).fetchone()[0]
    if pending:body+=f'<div class=notice>ยังมีออเดอร์รอเสิร์ฟ {pending} รายการ ต้องจัดการคิวให้เรียบร้อยก่อนยืนยันยอดและรับเงิน <a class="button secondary" href=/customer-queue>กลับไปจัดการคิว →</a></div>'
    body+=ux.progress(2 if paid(db,oid) else 1) if quote else '<p class=muted>ตรวจยอด → รับชำระ → ใบเสร็จ</p>'
    if not shift: body+='<div class=notice>ยังไม่มีกะเปิดอยู่ <a class=button href=/shifts>เปิดกะก่อนรับเงิน</a></div>'
    if not quote:
        import streamline
        body+=streamline.checkout(h,db,oid)
        subtotal=db.execute('SELECT COALESCE(SUM(price*qty),0) FROM items WHERE order_id=?',(oid,)).fetchone()[0]
        settings=dict(db.execute('SELECT key,value FROM settings').fetchall())
        body+=f'<details class=panel><summary>ตัวเลือกเพิ่มเติม: ส่วนลด / แบ่งบิล / ยืนยันยอดก่อนรับเงิน</summary><h2>ตรวจยอดก่อนรับชำระ</h2><p>รวมรายการ ฿{a.money(subtotal)} · ค่าบริการ {a.esc(settings["service"])}% · ภาษี {a.esc(settings["tax"])}%</p><p class=muted>ยืนยันแล้วจะล็อกราคา รายการ และค่าบริการก่อนแบ่งชำระ</p>'+h.form('/checkout-freeze',f'<input type=hidden name=order_id value={oid}>'+a.field('ส่วนลด (เฉพาะผู้จัดการ)','discount',0,'number','min=0 step=0.01 required' if manager else 'readonly')+'<button>ยืนยันยอดและไปต่อ</button>')+'</details>'
    else:
        received=paid(db,oid); remaining=quote['total']-received
        body+=f'<section class=panel><h2>ยอดบิลที่ยืนยันแล้ว</h2><p>ยอดสินค้า {a.money(quote["subtotal"])} − ส่วนลด {a.money(quote["discount"])} + ค่าบริการ {a.money(quote["service"])} + ภาษี {a.money(quote["tax"])}</p><p class=total>ยอดสุทธิ ฿{a.money(quote["total"])}</p><p>รับชำระแล้ว ฿{a.money(received)} · คงเหลือ ฿{a.money(remaining)}</p></section>'
        any_payment=db.execute('SELECT 1 FROM payments WHERE order_id=?',(oid,)).fetchone()
        if not any_payment:
            hidden=f'<input type=hidden name=order_id value={oid}>'
            body+='<details class=panel><summary>ตัวเลือกเพิ่มเติม: แบ่งบิล / ปลดล็อกยอด</summary><h2>เลือกวิธีแยกบิล</h2><p class=muted>หารตามจำนวนคนหรือกำหนดยอดเอง ยอดรวมต้องเท่ากับยอดสุทธิ แก้การแยกได้ก่อนรับเงินครั้งแรก</p>'+h.form('/bill-split',hidden+'<input type=hidden name=mode value=equal>'+a.field('จำนวนคน / บิล','count',2,'number','min=1 max=20 required')+'<button>หารเท่ากัน</button>')+'<br>'+h.form('/bill-split',hidden+'<input type=hidden name=mode value=custom>'+a.field('ยอดแต่ละบิล คั่นด้วย , เช่น 100, 150.50','amounts',extra='required')+'<button>แยกตามยอดที่กำหนด</button>')+'<br>'+h.form('/checkout-unlock',hidden+'<button class=secondary>ปลดล็อกเพื่อแก้รายการ / ส่วนลด</button>')+'</details>'
        for part in db.execute('SELECT * FROM bill_parts WHERE order_id=? ORDER BY id',(oid,)).fetchall():
            balance=part['amount']-part_paid(db,part['id'])
            body+=f'<section class=panel><h2>{a.esc(part["label"])} · ฿{a.money(part["amount"])}</h2><p>ค้างชำระ ฿{a.money(balance)}</p>'
            if (balance>0 or quote['total']==0 and not any_payment) and shift:
                body+=h.form('/payment-add',f'<input type=hidden name=order_id value={oid}><input type=hidden name=part_id value={part["id"]}><input type=hidden name=request_key value="{secrets.token_urlsafe(24)}">'+a.field('ยอดที่จ่ายครั้งนี้','amount',f'{balance/100:.2f}','number','min=0 step=0.01 required')+'<label>ช่องทาง<select name=method>'+''.join(f'<option>{m}</option>' for m in METHODS)+'</select></label>'+a.field('รับเงิน (เว้นว่าง = ยอดจ่ายครั้งนี้)','received','','number','min=0 step=0.01')+'<button>บันทึกรับชำระ</button>')
            body+=f'<p><a class="button secondary" href="/part-receipt?id={part["id"]}">ใบรับเงินส่วนนี้</a></p></section>'
        body+='<section class=panel><h2>รายการรับชำระ</h2>'+payment_table(h,db,oid=oid)+'</section>'
    h.page('ชำระเงิน / แยกบิล',body+CASH_SCRIPT); return True

CASH_SCRIPT=r'''<style>.cash-shortcuts{display:flex;gap:8px;flex-wrap:wrap;grid-column:1/-1}.cash-shortcuts button{padding:10px 16px}.cash-preview{grid-column:1/-1;font-size:20px;color:#efd098;padding:15px;background:#203728;border-radius:12px}</style><script>(()=>{const cents=value=>{const match=/^(\d+)(?:\.(\d{1,2}))?$/.exec(value.trim());return match?Number(match[1])*100+Number((match[2]||'').padEnd(2,'0')):null},money=n=>(n/100).toLocaleString('th-TH',{minimumFractionDigits:2,maximumFractionDigits:2});document.querySelectorAll('form[action="/payment-add"],form[action="/checkout-simple"]').forEach(form=>{const amount=form.elements.amount,received=form.elements.received,method=form.elements.method,box=document.createElement('div'),preview=document.createElement('p');box.className='cash-shortcuts';preview.className='cash-preview';preview.setAttribute('role','status');preview.setAttribute('aria-live','polite');for(const [label,value] of [['พอดี',null],['+฿1',1],['+฿5',5],['+฿10',10],['+฿20',20],['+฿50',50],['+฿100',100],['+฿500',500],['+฿1,000',1000],['ล้างยอด',0]]){const b=document.createElement('button');b.type='button';b.className='secondary';b.textContent=label;b.addEventListener('click',()=>{if(value===null){received.value=amount.value}else if(value===0){received.value='0.00'}else{const current=received.value.trim()?cents(received.value):0;if(current===null){update();received.focus();return}received.value=((current+value*100)/100).toFixed(2)}received.dispatchEvent(new Event('input',{bubbles:true}));update()});box.append(b)}received.closest('label').after(box,preview);function update(){const cash=method.value==='เงินสด',due=cents(amount.value),got=received.value.trim()?cents(received.value):due;box.hidden=!cash;if(!cash){received.value=amount.value;received.readOnly=true;preview.textContent='ยอดรับชำระ ฿'+(due===null?'—':money(due));return}received.readOnly=false;preview.textContent=due===null||got===null?'กรุณากรอกยอดเงินให้ถูกต้อง':got<due?'รับเงินยังไม่ครบ · ขาด ฿'+money(due-got):'เงินทอน ฿'+money(got-due)}form.addEventListener('input',update);method.addEventListener('change',update);update()})})();</script>'''
