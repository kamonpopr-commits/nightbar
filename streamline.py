"""Focused table workspace and guarded shortcuts for ordinary checkout."""
import hashlib,json,secrets
import operations,deposits,workstations,live_ui

def eligible(db,oid):
    return [r for r in db.execute("SELECT d.*,r.table_id,r.name,c.code FROM booking_deposits d JOIN reservations r ON r.id=d.reservation_id LEFT JOIN customer_bookings c ON c.reservation_id=r.id WHERE d.state='confirmed' AND d.order_id IS NULL AND r.status='arrived'") if deposits.linked_to(db,r['reservation_id'],oid,r['table_id'])]

def quote(db,a,oid):
    q=operations.calculate(a,db,oid,0)
    row=db.execute('SELECT status,table_revision FROM orders WHERE id=?',(oid,)).fetchone()
    if not row or row['status']!='open':raise ValueError('บิลปิดแล้ว')
    rates=dict(db.execute('SELECT key,value FROM settings'))
    payload=[oid,tuple(row),q,rates['service'],rates['tax'],bool(operations.locked(db,oid)),operations.paid(db,oid),[(r['reservation_id'],r['amount']) for r in eligible(db,oid)]]
    return q,hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()

def checkout(h,db,oid):
    a=h.api
    try:q,token=quote(db,a,oid)
    except ValueError as error:return '<p class=notice>'+a.esc(str(error))+'</p>'
    if not operations.active(db):return ''
    rows=eligible(db,oid);hidden=f'<input type=hidden name=order_id value={oid}><input type=hidden name=quote value={token}>'
    if rows:
        out='<section class=panel><h2>ตรวจมัดจำที่เชื่อมกับบิลนี้</h2><p>เลือกยืนยันยอดและหักมัดจำได้ที่นี่ ก่อนรับชำระส่วนที่เหลือ · หากต้องการแบ่งบิลหรือให้ส่วนลด ใช้ตัวเลือกเพิ่มเติมก่อนหักมัดจำ</p>'
        for r in rows:
            out+=f'<p>{a.esc(r["name"])} · รหัส {a.esc(r["code"] or str(r["reservation_id"]))} · มัดจำ {a.money(r["amount"])} บาท · ยอดบิล {a.money(q["total"])} บาท</p>'
            if h.s['role']=='manager':out+=h.form('/checkout-deposit',hidden+f'<input type=hidden name=id value={r["reservation_id"]}><button>ยืนยันยอดและหักมัดจำนี้</button>')
            else:out+='<p>ให้ผู้จัดการตรวจและหักมัดจำก่อนรับเงินส่วนที่เหลือ</p>'
        return out+'</section>'
    return '<section class=panel><h2>ตรวจยอดและรับชำระ</h2><p>รวมรายการ '+a.money(q['subtotal'])+' + ค่าบริการ '+a.money(q['service'])+' + ภาษี '+a.money(q['tax'])+f'</p><p class=total>ยอดชำระ ฿{a.money(q["total"])}</p>'+h.form('/checkout-simple',hidden+f'<input type=hidden name=request_key value="{secrets.token_urlsafe(24)}">'+a.field('ยอดที่จ่ายครั้งนี้','amount',f'{q["total"]/100:.2f}','number','readonly')+'<label>ช่องทาง<select name=method>'+''.join(f'<option>{m}</option>' for m in operations.METHODS)+'</select></label>'+a.field('รับเงิน (เว้นว่าง = ยอดจ่ายครั้งนี้)','received','','number','min=0 step=0.01')+'<button>ยืนยันยอดและรับชำระ</button>')+'<p>ตรวจยอดก่อนกด ปุ่มนี้บันทึกรับเงินจริงและเปิดใบเสร็จทันที · ส่วนลดและแบ่งบิลอยู่ในตัวเลือกเพิ่มเติม</p></section>'

def mutate(h,db,path,d):
    if path=='/product-availability':
        if h.s['role']!='manager':raise ValueError('เฉพาะผู้จัดการเปลี่ยนสถานะขาย')
        pid=h.api.integer(d['product_id']);expected=d.get('expected');row=db.execute('SELECT active FROM products WHERE id=?',(pid,)).fetchone()
        if not row or expected not in ['0','1'] or str(row[0])!=expected:raise ValueError('สถานะเมนูเปลี่ยนแล้ว กรุณาโหลดรายการใหม่')
        db.execute('UPDATE products SET active=? WHERE id=?',(1-row[0],pid));return '/products?view=list'
    if path not in ['/checkout-simple','/checkout-deposit']:return None
    a=h.api;oid=a.integer(d['order_id'])
    if path=='/checkout-simple':
        old=db.execute('SELECT * FROM payments WHERE request_key=?',(d.get('request_key',''),)).fetchone()
        if old:
            got=a.amount(d['received']) if d.get('received') else old['amount']
            if old['order_id']!=oid or old['method']!=d.get('method') or old['tendered']!=got:raise ValueError('คำขอซ้ำไม่ตรงรายการเดิม')
            return f'/receipt?id={oid}'
    else:
        if h.s['role']!='manager':raise ValueError('เฉพาะผู้จัดการหักมัดจำ')
        old=db.execute('SELECT * FROM booking_deposits WHERE reservation_id=?',(a.integer(d['id']),)).fetchone()
        if old and old['order_id']==oid and old['applied']>0:return f'/checkout?id={oid}'
    q,token=quote(db,a,oid)
    if token!=d.get('quote') or operations.locked(db,oid) or operations.paid(db,oid):raise ValueError('ยอดบิลเปลี่ยนแล้ว กรุณาตรวจยอดใหม่ก่อนรับชำระ')
    if path=='/checkout-simple' and eligible(db,oid):raise ValueError('มีมัดจำ กรุณาตรวจและหักมัดจำก่อน')
    operations.freeze(h,db,oid,0)
    if path=='/checkout-deposit':return deposits.mutate(h,db,'/deposit-apply',d)
    part=db.execute('SELECT id FROM bill_parts WHERE order_id=?',(oid,)).fetchone()[0]
    got=a.amount(d['received']) if d.get('received') else q['total']
    operations.tender(h,db,part,q['total'],d['method'],got,d.get('request_key',''))
    return f'/receipt?id={oid}'

def board(h,db,oid):
    a=h.api;o=db.execute('SELECT status FROM orders WHERE id=?',(oid,)).fetchone()
    if not o or o['status']!='open':return '<p>บิลปิดแล้ว <a href=/tables>กลับหน้าโต๊ะ</a></p>',[]
    rows=[];ids=[]
    for i in db.execute("SELECT * FROM items WHERE order_id=? AND prep_status!='served' ORDER BY id",(oid,)):
        ids.append(i['id']);next_state={'received':'preparing','preparing':'ready','ready':'served'}.get(i['prep_status']);action=''
        if not operations.locked(db,oid) and workstations.allowed(h,'/production-status',True) and (workstations.position(h)!='floor' or next_state=='served'):
            action=h.form('/production-status',f'<input type=hidden name=item_id value={i["id"]}><input type=hidden name=return_order value={oid}><input type=hidden name=expected value={i["prep_status"]}><input type=hidden name=status value={next_state}><button>{a.esc(a.customer.STATUS[next_state])}</button>','inline')
        rows.append((a.esc(i['name']),i['qty'],a.esc(workstations.LABELS.get(i['station'],i['station'])),a.esc(a.customer.STATUS.get(i['prep_status'],i['prep_status'])),action))
    out='<h2>งานครัว / บาร์ของโต๊ะนี้</h2>'+(a.grid(['รายการ','จำนวน','แผนก','สถานะ',''],rows) if rows else '<p>ไม่มีรายการรอทำหรือเสิร์ฟ</p>')
    for r in db.execute("SELECT * FROM service_requests WHERE order_id=? AND status!='done' ORDER BY id",(oid,)):
        ids.append('s'+str(r['id']));action='/service-bill' if r['kind']=='bill' else '/service-done'
        out+='<p><strong>'+('ขอเช็กบิล' if r['kind']=='bill' else 'เรียกพนักงาน')+'</strong></p>'
        if workstations.allowed(h,action,True):out+=h.form(action,f'<input type=hidden name=id value={r["id"]}><input type=hidden name=return_order value={oid}><button>{"ไปชำระเงิน →" if r["kind"]=="bill" else "ดูแลแล้ว"}</button>','inline')
    return out,ids

def hub(h,db,o):
    oid=o['id'];a=h.api;body=f'<section class="panel noprint"><h2>ดูแลโต๊ะ {a.esc(o["name"])}</h2><div style="display:flex;gap:12px;flex-wrap:wrap"><a class=button href="/checkout?id={oid}">เช็กบิล / ชำระเงิน →</a><a class="button secondary" href="/receipt?id={oid}">ตรวจบิล / พิมพ์</a></div>'
    if workstations.allowed(h,'/qr.svg'):body+=f'<details open id=table-qr><summary>QR สั่งอาหารสำหรับโต๊ะนี้</summary><p>ให้ลูกค้าสแกน QR นี้เพื่อสั่งอาหาร · สำหรับบิลปัจจุบันเท่านั้น</p><img src="/qr.svg?order_id={oid}" alt="QR สั่งอาหาร" width=180 height=180 style="background:white;max-width:100%;margin-top:12px"><p><a href="/qr.svg?order_id={oid}" target=_blank rel=noopener>เปิด / บันทึก QR</a></p></details>'
    content,_=board(h,db,oid)
    return body+'</section>'+live_ui.controls()+f'<section class=panel id=live-content>{content}</section>'+live_ui.script('/live/order-hub?id='+str(oid))

def cleanup(h,db,o):
    a=h.api;names=(o['seat_label'] or o['name']).split(' + ');body=''
    for name in names:
        t=db.execute('SELECT t.id,t.name FROM tables t JOIN table_state s ON s.table_id=t.id WHERE t.name=? AND s.cleaning=1 AND NOT EXISTS(SELECT 1 FROM table_usage u WHERE u.table_id=t.id)',(name,)).fetchone()
        if t and workstations.allowed(h,'/table-ready',True):body+=h.form('/table-ready',f'<input type=hidden name=table_id value={t["id"]}><p>โต๊ะ {a.esc(t["name"])} รอทำความสะอาด</p><button>ทำความสะอาดเสร็จ / พร้อมรับลูกค้า</button>')
    return '<section class="panel noprint"><h2>เตรียมโต๊ะสำหรับรอบถัดไป</h2>'+body+'</section>' if body else ''
