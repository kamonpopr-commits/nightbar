"""Atomic reservation arrival and seating; persistent link survives table moves."""
from datetime import datetime,timedelta
import table_management
import deposits

def initialize(db):
    db.execute('CREATE TABLE IF NOT EXISTS reservation_orders(reservation_id INTEGER PRIMARY KEY REFERENCES reservations(id),order_id INTEGER NOT NULL REFERENCES orders(id),checked_in TEXT NOT NULL,username TEXT NOT NULL)')

def arrive(h,db,d):
    a=h.api;rid=a.integer(d['id'])
    linked=db.execute('SELECT order_id FROM reservation_orders WHERE reservation_id=?',(rid,)).fetchone()
    if linked:return f'/order?id={linked[0]}'
    deposits.expire(db)
    r=db.execute('SELECT * FROM reservations WHERE id=?',(rid,)).fetchone()
    if not r or r['status'] not in ['booked','arrived']:raise ValueError('การจองยกเลิกหรือหมดเวลาแล้ว กรุณาตรวจใหม่')
    dep=db.execute('SELECT state FROM booking_deposits WHERE reservation_id=?',(rid,)).fetchone()
    if dep and dep[0]!='confirmed':raise ValueError('ต้องตรวจสอบและยืนยันมัดจำก่อนรับเข้าที่นั่ง')
    tid=a.integer(d.get('target') or str(r['table_id']))
    if not table_management.free(db,tid):raise ValueError('โต๊ะไม่ว่างหรือรอทำความสะอาด กรุณาเลือกโต๊ะว่างในรายการแล้วรับลูกค้าอีกครั้ง')
    table=db.execute('SELECT * FROM tables WHERE id=?',(tid,)).fetchone()
    if table['seats']<r['guests']:raise ValueError('โต๊ะที่เลือกรองรับจำนวนคนไม่พอ กรุณาเลือกโต๊ะใหญ่ขึ้น')
    current=datetime.now()
    for other in db.execute("SELECT id,time FROM reservations WHERE table_id=? AND id!=? AND status='booked'",(tid,rid)):
        if current-timedelta(hours=2)<datetime.fromisoformat(other['time'])<current+timedelta(hours=2):raise ValueError('โต๊ะนี้มีการจองอื่นใกล้เวลานี้ กรุณาเลือกโต๊ะอื่น')
    # All changes belong to the caller's BEGIN IMMEDIATE transaction.
    oid=db.execute('INSERT INTO orders(table_id,opened,guests,note) VALUES (?,?,?,?)',(tid,a.now(),r['guests'],f'รับจากการจอง #{rid} · {r["name"]}')).lastrowid
    db.execute('INSERT INTO table_assignments VALUES (?,?)',(tid,oid));a.customer.ensure_visit(db,oid)
    db.execute('INSERT INTO reservation_orders VALUES (?,?,?,?)',(rid,oid,a.now(),h.s['username']))
    db.execute("UPDATE reservations SET status='arrived',table_id=? WHERE id=?",(tid,rid))
    table_management.event(h,db,oid,'รับลูกค้า / เปิดโต๊ะ',f'การจอง #{rid} · {r["guests"]} คน · โต๊ะ {table["name"]}')
    return f'/order?id={oid}'

def controls(h,db,r):
    a=h.api;link=db.execute('SELECT order_id FROM reservation_orders WHERE reservation_id=?',(r['id'],)).fetchone()
    if link:return f'<a class=button href="/order?id={link[0]}">ดูบิล #{link[0]} →</a>'
    if r['status'] not in ['booked','arrived']:return '<span class=muted>ยกเลิกแล้ว</span>'
    choices=''
    for t in db.execute('SELECT * FROM tables ORDER BY name'):
        if t['id']!=r['table_id'] and (t['seats']<r['guests'] or not table_management.free(db,t['id'])):continue
        label=f'{t["name"]} · {t["seats"]} ที่นั่ง'+(' · โต๊ะเดิม' if t['id']==r['table_id'] else '')
        choices+=f'<option value={t["id"]} {"selected" if t["id"]==r["table_id"] else ""}>{a.esc(label)}</option>'
    body=h.form('/reservation-status',f'<input type=hidden name=id value={r["id"]}><input type=hidden name=status value=arrived><label>โต๊ะที่จะรับลูกค้า<select name=target>{choices}</select></label><button>รับลูกค้า / เปิดโต๊ะ →</button>')
    if r['status']=='booked':body+='<details><summary>ยกเลิกการจอง</summary>'+h.form('/reservation-status',f'<input type=hidden name=id value={r["id"]}><input type=hidden name=status value=cancelled><button class=danger>ยืนยันยกเลิกการจอง</button>')+'</details>'
    return body
