"""Reservation deposits: separate liability ledger, verified manually by a manager."""
from datetime import datetime,timedelta
import secrets
import operations
import deposit_qr
import deposit_slips

LABELS={'pending':'รอแจ้งโอน','review':'รอตรวจสอบยอดโอน','confirmed':'ยืนยันมัดจำแล้ว','refund_due':'รอคืนเงิน','refunded':'คืนเงินแล้ว','forfeited':'ไม่คืนตามเงื่อนไข','expired':'หมดเวลาชำระ','cancelled':'ยกเลิกก่อนชำระ','applied':'หักบิลแล้ว'}

def initialize(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS booking_deposits(reservation_id INTEGER PRIMARY KEY REFERENCES reservations(id),amount INTEGER NOT NULL CHECK(amount>0),state TEXT NOT NULL,deadline TEXT NOT NULL,instructions TEXT NOT NULL,cancel_hours INTEGER NOT NULL,reference TEXT NOT NULL DEFAULT '',verified_by TEXT,verified_at TEXT,order_id INTEGER REFERENCES orders(id),applied INTEGER NOT NULL DEFAULT 0 CHECK(applied>=0),refunded INTEGER NOT NULL DEFAULT 0 CHECK(refunded>=0),resolution TEXT NOT NULL DEFAULT '');
    CREATE TABLE IF NOT EXISTS deposit_events(id INTEGER PRIMARY KEY,reservation_id INTEGER NOT NULL REFERENCES reservations(id),action TEXT NOT NULL,amount INTEGER NOT NULL,actor TEXT NOT NULL,note TEXT NOT NULL,created TEXT NOT NULL);
    ''')
    for key,value in [('deposit_amount','0'),('deposit_min_guests','1'),('deposit_hold_minutes','15'),('deposit_cancel_hours','24'),('deposit_instructions','')]:db.execute('INSERT OR IGNORE INTO settings VALUES (?,?)',(key,value))
    deposit_qr.initialize(db)
    deposit_slips.initialize(db)

def settings(db):return dict(db.execute('SELECT key,value FROM settings'))
def event(db,rid,action,value,actor,note=''):
    db.execute('INSERT INTO deposit_events(reservation_id,action,amount,actor,note,created) VALUES (?,?,?,?,?,?)',(rid,action,value,actor,note,datetime.now().isoformat(timespec='seconds')))
def expire(db):
    for r in db.execute("SELECT reservation_id FROM booking_deposits WHERE state='pending' AND deadline<?",(datetime.now().isoformat(),)).fetchall():
        db.execute("UPDATE booking_deposits SET state='expired' WHERE reservation_id=?",(r[0],));db.execute("UPDATE reservations SET status='cancelled' WHERE id=? AND status='booked'",(r[0],));event(db,r[0],'expired',0,'system')
def policy(h,db):
    a=h.api;s=settings(db);amount=int(s['deposit_amount'])
    if not amount:return '<p class=notice>การจองนี้ไม่มีค่ามัดจำ</p>'
    return f'<section class=notice><h3>เงื่อนไขมัดจำก่อนจอง</h3><p>ตั้งแต่ {int(s["deposit_min_guests"])} คนขึ้นไป มัดจำ {a.money(amount)} บาทต่อการจอง · แจ้งโอนภายใน {int(s["deposit_hold_minutes"])} นาที ไม่เช่นนั้นคืนโต๊ะให้ผู้อื่น<br>ร้านยืนยันเมื่อพนักงานตรวจยอดจริงแล้ว · มัดจำนำไปหักค่าอาหารและเครื่องดื่ม<br>ยกเลิกล่วงหน้าอย่างน้อย {int(s["deposit_cancel_hours"])} ชั่วโมง: คืนเต็มจำนวน · ช้ากว่านั้นหรือไม่มา: ไม่คืนมัดจำ<br>มาสายเกิน 15 นาที กรุณาติดต่อร้าน · หากร้านยกเลิกให้คืนเต็มจำนวน · ส่วนมัดจำเกินยอดบิลคืนให้ลูกค้า</p><p>{a.esc(s["deposit_instructions"])}</p></section><label><input type=checkbox name=deposit_consent value=1 required> อ่านและยอมรับเงื่อนไขมัดจำข้างต้น</label>'
def create(h,db,rid,guests,d):
    s=settings(db);value=int(s['deposit_amount'])
    if not value or guests<int(s['deposit_min_guests']):return
    if d.get('deposit_consent')!='1':raise ValueError('กรุณายอมรับเงื่อนไขมัดจำก่อนจอง')
    db.execute('INSERT INTO booking_deposits(reservation_id,amount,state,deadline,instructions,cancel_hours) VALUES (?,?,?,?,?,?)',(rid,value,'pending',(datetime.now()+timedelta(minutes=int(s['deposit_hold_minutes']))).isoformat(timespec='seconds'),s['deposit_instructions'],int(s['deposit_cancel_hours'])))
    event(db,rid,'created',value,'customer')
    db.execute('UPDATE booking_deposits SET payment_qr=?,payment_bank=?,payment_payee=? WHERE reservation_id=?',(s['deposit_qr'],s['deposit_bank'],s['deposit_payee'],rid))
def cancel(db,rid,actor,shop=False):
    r=db.execute('SELECT d.*,r.time FROM booking_deposits d JOIN reservations r ON r.id=d.reservation_id WHERE reservation_id=?',(rid,)).fetchone()
    if not r:return
    if r['order_id']:raise ValueError('การจองนี้ใช้มัดจำกับบิลแล้ว กรุณาจัดการที่บิล')
    if r['state'] in ['pending','expired']:state='cancelled'
    elif r['state']=='review':raise ValueError('มีการแจ้งโอนรอตรวจสอบ กรุณาให้ร้านตรวจยอดก่อนยกเลิก')
    elif r['state']=='confirmed':state='refund_due' if shop or datetime.now()<=datetime.fromisoformat(r['time'])-timedelta(hours=r['cancel_hours']) else 'forfeited'
    else:return
    db.execute('UPDATE booking_deposits SET state=? WHERE reservation_id=?',(state,rid));event(db,rid,state,r['amount'],actor)
def customer_mutate(h,db,path,d):
    if path!='/customer/deposit-reference':return False
    expire(db);rid=h.api.integer(d['id'])
    r=db.execute('SELECT d.* FROM booking_deposits d JOIN customer_bookings c ON c.reservation_id=d.reservation_id JOIN reservations r ON r.id=c.reservation_id WHERE d.reservation_id=? AND c.session_token=? AND r.status=\'booked\'',(rid,h.c['token'])).fetchone()
    if not r or r['state'] not in ['pending','review']:raise ValueError('การจองหมดเวลาหรือยืนยันแล้ว กรุณาติดต่อร้านก่อนโอนเงิน')
    ref=d.get('reference','').strip()
    raw=getattr(h,'uploads',{}).get('photo')
    if ref and not 6<=len(ref)<=160:raise ValueError('เลขอ้างอิงการโอนต้องยาว 6–160 ตัวอักษร')
    if not ref and not raw:raise ValueError('กรุณาแนบสลิปหรือกรอกเลขอ้างอิงการโอน')
    if raw:deposit_slips.save(h,db,rid,raw)
    if not ref:ref=r['reference'] or 'แนบสลิปให้ร้านตรวจสอบ'
    db.execute("UPDATE booking_deposits SET state='review',reference=? WHERE reservation_id=?",(ref,rid));event(db,rid,'submitted',r['amount'],'customer',ref);return True
def customer_card(h,db,rid):
    a=h.api;r=db.execute('SELECT * FROM booking_deposits WHERE reservation_id=?',(rid,)).fetchone()
    if not r:return ''
    out=f'<section class=notice><h3>มัดจำ {a.money(r["amount"])} บาท · {LABELS[r["state"]]}</h3><p>{a.esc(r["instructions"])}</p><p>ยกเลิกก่อนเวลาเข้าร้าน {r["cancel_hours"]} ชั่วโมงคืนเต็มจำนวน หลังจากนั้นหรือไม่มาไม่คืน · ร้านยกเลิกคืนเต็มจำนวน</p>'
    if r['state']=='pending':out+=f'<p>แจ้งโอนภายใน {a.esc(r["deadline"].replace("T"," "))} · อย่าโอนหลังหมดเวลา</p>'
    if r['state']=='pending':out+=deposit_qr.image(h,r['payment_qr'],r['payment_bank'],r['payment_payee'],r['amount'])
    out+=deposit_slips.links(h,db,rid)
    if r['state'] in ['pending','review']:out+=h.customer_form('/customer/deposit-reference',f'<input type=hidden name=id value={rid}><label>แนบสลิปโอนมัดจำ<input type=file name=photo accept="image/jpeg,image/png,image/webp"></label><p>JPG, PNG หรือ WebP ไม่เกิน 5 MB · แนบสลิปหรือระบุเลขอ้างอิงอย่างใดอย่างหนึ่ง · ผู้จัดการต้องตรวจยอดเงินจริงก่อนยืนยัน</p>'+a.field('เลขอ้างอิงรายการโอน / เวลาโอน (ถ้ามี)','reference',extra='minlength=6 maxlength=160')+'<button>ส่งสลิป / แจ้งโอนให้ร้านตรวจสอบ</button>')
    if r['state']=='review':out+='<p>ยังไม่ยืนยันการจองจนกว่าร้านตรวจยอดเงินจริง กรุณารอหรือติดต่อร้าน</p>'
    return out+'</section>'
def configuration(h,db):
    if h.s['role']!='manager':return ''
    a=h.api;s=settings(db)
    out='<section class=panel><h2>มัดจำการจอง</h2><p>เงินรับล่วงหน้าแยกจากยอดขายอาหาร · ตรวจยอดในบัญชีจริงก่อนยืนยัน · ตั้งยอด 0 เพื่อปิดระบบ</p><details><summary>ตั้งยอดและเงื่อนไขมัดจำ</summary>'+h.form('/deposit-settings',a.field('บาทต่อการจอง (0 = ไม่เก็บ)','amount',str(int(s['deposit_amount'])/100),'number','min=0 step=0.01 required')+a.field('เริ่มเก็บตั้งแต่จำนวนคน','min_guests',s['deposit_min_guests'],'number','min=1 max=100 required')+a.field('เวลาแจ้งโอน (นาที)','hold',s['deposit_hold_minutes'],'number','min=5 max=60 required')+a.field('ยกเลิกก่อนกี่ชั่วโมงจึงคืนเงิน','cancel_hours',s['deposit_cancel_hours'],'number','min=0 max=168 required')+a.field('บัญชีรับโอน / ชื่อบัญชี / วิธีติดต่อร้าน','instructions',s['deposit_instructions'],extra='maxlength=1000')+'<button>บันทึกนโยบายสำหรับการจองใหม่</button>')+'</details>'
    return out+deposit_qr.admin(h,db)+'</section>'

def admin(h,db):
    if h.s['role']!='manager':return ''
    a=h.api
    out='<section class=panel><h2>ตรวจมัดจำการจอง</h2><p>ตรวจสลิป ยืนยันยอด และคืนเงินจากรายการด้านล่าง</p><a class="button secondary" href="/settings?tab=shop#deposit-settings">ตั้งค่ามัดจำ / บัญชีรับโอน →</a>'
    sums=db.execute("SELECT COALESCE(SUM(CASE WHEN verified_at IS NOT NULL THEN amount-applied-refunded ELSE 0 END),0),COALESCE(SUM(applied),0),COALESCE(SUM(refunded),0) FROM booking_deposits WHERE state!='forfeited'").fetchone()
    out+=f'<p>รับล่วงหน้าคงเหลือ ฿{a.money(sums[0])} · หักบิลแล้ว ฿{a.money(sums[1])} · คืนแล้ว ฿{a.money(sums[2])}</p>'
    selected=getattr(h,'query',{}).get('deposits',['review'])[0]
    if selected not in ['review','pending','confirmed','refund_due','all']:selected='review'
    out+='<div id=deposit-workspace class=filters>'
    for value,label in [('review','รอตรวจสลิป'),('pending','รอแจ้งโอน'),('confirmed','ยืนยันแล้ว'),('refund_due','รอคืนเงิน'),('all','ทั้งหมด')]:
        count=db.execute('SELECT COUNT(*) FROM booking_deposits WHERE (?=\'all\' OR state=?)',(value,value)).fetchone()[0]
        out+=f'<a class="button {"" if selected==value else "secondary"}" href="/reservations?deposits={value}#deposit-workspace">{label} ({count})</a> '
    out+='</div>'
    rows=db.execute('SELECT d.*,r.name,r.phone,r.guests,r.time,r.status booking_status,t.name table_name,c.code FROM booking_deposits d JOIN reservations r ON r.id=d.reservation_id JOIN tables t ON t.id=r.table_id LEFT JOIN customer_bookings c ON c.reservation_id=r.id WHERE (?=\'all\' OR d.state=?) ORDER BY r.time DESC LIMIT 100',(selected,selected)).fetchall()
    if not rows:out+='<p>ไม่มีรายการในกลุ่มนี้</p>'
    for r in rows:
        out+=f'<details {"open" if selected=="review" else ""}><summary>#{r["reservation_id"]} {a.esc(r["name"])} · {a.esc(r["table_name"])} · {LABELS[r["state"]]} · {a.money(r["amount"])} บาท</summary><p>รหัส {a.esc(r["code"] or "จองโดยพนักงาน")} · {r["guests"]} คน · {a.esc(r["phone"])}<br>เวลา {a.esc(a.ux.date(r["time"]))} · อ้างอิง {a.esc(r["reference"])} · หักแล้ว {a.money(r["applied"])} · คืนแล้ว {a.money(r["refunded"])}</p>'
        slip=db.execute('SELECT id FROM deposit_slips WHERE reservation_id=? ORDER BY id DESC LIMIT 1',(r['reservation_id'],)).fetchone()
        if slip:out+=f'<a href="/deposit-slip?id={slip[0]}" target=_blank rel=noopener><img src="/deposit-slip?id={slip[0]}" alt="สลิปที่ลูกค้าแนบ กดเพื่อดูรูปเต็ม" style="display:block;max-width:100%;width:280px;height:auto;margin:15px 0"></a>'
        out+=deposit_slips.links(h,db,r['reservation_id'])
        actions=[]
        if r['state']=='review':actions=[('verify','ตรวจยอดเงินจริงแล้ว / ยืนยัน'),('retry','ไม่พบยอด / ให้แจ้งโอนใหม่')]
        if r['state']=='confirmed' and r['booking_status']=='booked':actions=[('shop-cancel','ร้านยกเลิก / คืนเต็มจำนวน'),('no-show','ไม่มาตามจอง')]
        if r['state']=='refund_due':actions=[('refund','โอนคืนเงินจริงแล้ว')]
        if actions:out+=h.form('/deposit-action',f'<input type=hidden name=id value={r["reservation_id"]}><input type=hidden name=expected value={r["state"]}>'+a.field('หมายเหตุ / เลขอ้างอิงการตรวจยอดหรือคืนเงิน','note',extra='required maxlength=300')+'<label>ดำเนินการ<select name=action>'+''.join(f'<option value={v}>{label}</option>' for v,label in actions)+'</select></label><button>ยืนยันดำเนินการ</button>')
        for e in db.execute('SELECT * FROM deposit_events WHERE reservation_id=? ORDER BY id DESC LIMIT 12',(r['reservation_id'],)):out+=f'<p><small>{a.esc(e["created"])} · {a.esc(e["actor"])} · {a.esc(e["action"])} · {a.esc(e["note"])}</small></p>'
        out+='</details>'
    return out+'</section>'
def linked_to(db,rid,oid,tid):
    link=db.execute('SELECT order_id FROM reservation_orders WHERE reservation_id=?',(rid,)).fetchone()
    return link[0]==oid if link else bool(db.execute('SELECT 1 FROM table_assignments WHERE order_id=? AND table_id=?',(oid,tid)).fetchone())

def checkout(h,db,oid):
    if h.s['role']!='manager' or not operations.locked(db,oid):return ''
    a=h.api;out='<section class=panel><h2>หักมัดจำการจอง</h2><p>ตรวจชื่อและรหัสจองให้ตรงลูกค้าก่อนหัก หักได้ครั้งเดียวต่อการจอง ส่วนเกินรอคืนเงิน</p>'
    for r in db.execute("SELECT d.*,r.name,r.table_id,c.code FROM booking_deposits d JOIN reservations r ON r.id=d.reservation_id LEFT JOIN customer_bookings c ON c.reservation_id=r.id WHERE d.state='confirmed' AND d.order_id IS NULL AND r.status='arrived' "):
        if not linked_to(db,r['reservation_id'],oid,r['table_id']):continue
        out+=h.form('/deposit-apply',f'<input type=hidden name=id value={r["reservation_id"]}><input type=hidden name=order_id value={oid}><p>{a.esc(r["name"])} · {a.esc(r["code"] or "พนักงานจอง")} · {a.money(r["amount"])} บาท</p><button>ยืนยันหักมัดจำการจองนี้</button>')
    return out+'</section>'
def mutate(h,db,path,d):
    if not path.startswith('/deposit-'):return None
    if h.s['role']!='manager':raise ValueError('เฉพาะผู้จัดการดำเนินการมัดจำ')
    if path=='/deposit-qr':return deposit_qr.save(h,db,d)
    a=h.api;expire(db)
    if path=='/deposit-settings':
        value=a.amount(d['amount']);g=int(d['min_guests']);hold=int(d['hold']);hours=int(d['cancel_hours']);info=d.get('instructions','').strip()
        if not 1<=g<=100 or not 5<=hold<=60 or not 0<=hours<=168 or len(info)>1000 or value and not info:raise ValueError('ตรวจยอด จำนวนคน เวลา และระบุบัญชีรับโอน / ช่องทางติดต่อก่อนเปิดใช้')
        for k,v in [('deposit_amount',value),('deposit_min_guests',g),('deposit_hold_minutes',hold),('deposit_cancel_hours',hours),('deposit_instructions',info)]:db.execute('UPDATE settings SET value=? WHERE key=?',(str(v),k))
        return '/settings?tab=shop#deposit-settings'
    rid=a.integer(d['id']);r=db.execute('SELECT d.*,r.time,r.status booking_status,r.table_id FROM booking_deposits d JOIN reservations r ON r.id=d.reservation_id WHERE reservation_id=?',(rid,)).fetchone()
    if not r:raise ValueError('ไม่พบมัดจำ')
    if path=='/deposit-apply':
        oid=a.integer(d['order_id']);o=db.execute("SELECT * FROM orders WHERE id=? AND status='open'",(oid,)).fetchone()
        if not o or r['state']!='confirmed' or r['order_id'] or r['booking_status']!='arrived' or not linked_to(db,rid,oid,r['table_id']):raise ValueError('มัดจำไม่พร้อมใช้ กรุณาตรวจการมาถึง โต๊ะ และบิล')
        quote=operations.locked(db,oid)
        if not quote:raise ValueError('ยืนยันยอดบิลก่อนหักมัดจำ')
        value=min(r['amount'],quote['total']-operations.paid(db,oid))
        if value<=0:raise ValueError('บิลไม่มีค้างชำระ')
        left=value
        for part in db.execute('SELECT * FROM bill_parts WHERE order_id=? ORDER BY id',(oid,)).fetchall():
            take=min(left,part['amount']-operations.part_paid(db,part['id']))
            if take:operations.tender(h,db,part['id'],take,'มัดจำ',take,f'deposit-{rid}-{part["id"]}-payment',deposit=True);left-=take
            if not left:break
        db.execute('UPDATE booking_deposits SET applied=?,order_id=?,state=? WHERE reservation_id=?',(value,oid,'refund_due' if value<r['amount'] else 'applied',rid));event(db,rid,'applied',value,h.s['username'],f'บิล #{oid}')
        return f'/receipt?id={oid}' if db.execute('SELECT status FROM orders WHERE id=?',(oid,)).fetchone()[0]=='paid' else f'/checkout?id={oid}'
    note=d.get('note','').strip();action=d.get('action')
    if d.get('expected')!=r['state'] or not note or len(note)>300:raise ValueError('สถานะเปลี่ยนหรือไม่ได้ระบุหมายเหตุ กรุณาเปิดหน้าใหม่')
    if action=='verify' and r['state']=='review' and r['booking_status']=='booked':db.execute("UPDATE booking_deposits SET state='confirmed',verified_by=?,verified_at=? WHERE reservation_id=?",(h.s['username'],datetime.now().isoformat(),rid))
    elif action=='retry' and r['state']=='review':db.execute("UPDATE booking_deposits SET state='pending',deadline=? WHERE reservation_id=?",((datetime.now()+timedelta(minutes=15)).isoformat(),rid))
    elif action=='shop-cancel' and r['state']=='confirmed' and not r['order_id']:
        cancel(db,rid,h.s['username'],shop=True);db.execute("UPDATE reservations SET status='cancelled' WHERE id=?",(rid,))
    elif action=='no-show' and r['state']=='confirmed' and r['booking_status']=='booked' and datetime.now()>datetime.fromisoformat(r['time'])+timedelta(minutes=15):
        db.execute("UPDATE booking_deposits SET state='forfeited',resolution=? WHERE reservation_id=?",(note,rid));db.execute("UPDATE reservations SET status='cancelled' WHERE id=?",(rid,))
    elif action=='refund' and r['state']=='refund_due':db.execute("UPDATE booking_deposits SET state='refunded',refunded=amount-applied,resolution=? WHERE reservation_id=?",(note,rid))
    else:raise ValueError('ไม่สามารถดำเนินการจากสถานะนี้ได้ / ยังไม่ถึงเวลาที่ถือว่าไม่มา')
    event(db,rid,action,r['amount']-r['applied'],h.s['username'],note);return '/reservations'
