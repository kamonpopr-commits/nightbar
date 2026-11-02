"""Transactional seating, relocation, and inventory-safe cancellations."""
import secrets
import operations
import convenience
import floor_plan

def initialize(db):
    columns={r['name'] for r in db.execute('PRAGMA table_info(orders)')}
    for name,definition in [('guests','INTEGER NOT NULL DEFAULT 1'),('table_revision','INTEGER NOT NULL DEFAULT 0'),('party','TEXT'),('seat_label','TEXT')]:
        if name not in columns:db.execute(f'ALTER TABLE orders ADD COLUMN {name} {definition}')
    db.executescript('''
    CREATE TABLE IF NOT EXISTS table_assignments(table_id INTEGER PRIMARY KEY REFERENCES tables(id),order_id INTEGER NOT NULL REFERENCES orders(id));
    CREATE TABLE IF NOT EXISTS table_state(table_id INTEGER PRIMARY KEY REFERENCES tables(id),cleaning INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS visit_aliases(token TEXT PRIMARY KEY,target TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS table_events(id INTEGER PRIMARY KEY,order_id INTEGER NOT NULL,username TEXT NOT NULL,action TEXT NOT NULL,detail TEXT NOT NULL,created TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS item_cancellations(id INTEGER PRIMARY KEY,item_id INTEGER NOT NULL,order_id INTEGER NOT NULL,product_id INTEGER NOT NULL,name TEXT NOT NULL,price INTEGER NOT NULL,qty INTEGER NOT NULL,cost INTEGER NOT NULL,disposition TEXT NOT NULL,reason TEXT NOT NULL,username TEXT NOT NULL,created TEXT NOT NULL);
    CREATE VIEW IF NOT EXISTS table_usage AS SELECT a.table_id,a.order_id FROM table_assignments a JOIN orders o ON o.id=a.order_id WHERE o.status='open';
    DROP VIEW IF EXISTS order_labels;
    CREATE VIEW order_labels AS SELECT o.id,COALESCE((SELECT group_concat(name,' + ') FROM (SELECT t.name FROM table_assignments a JOIN tables t ON t.id=a.table_id WHERE a.order_id=o.id ORDER BY t.id)),o.seat_label,t.name) name FROM orders o JOIN tables t ON t.id=o.table_id;
    DROP TRIGGER IF EXISTS release_seating;
    CREATE TRIGGER release_seating AFTER UPDATE OF status ON orders WHEN OLD.status='open' AND NEW.status!='open' BEGIN
      UPDATE orders SET seat_label=COALESCE((SELECT name FROM order_labels WHERE id=NEW.id),seat_label) WHERE id=NEW.id;
      INSERT OR REPLACE INTO table_state(table_id,cleaning) SELECT table_id,1 FROM table_assignments WHERE order_id=NEW.id;
      DELETE FROM table_assignments WHERE order_id=NEW.id;
    END;
    CREATE TRIGGER IF NOT EXISTS seating_item_insert AFTER INSERT ON items BEGIN UPDATE orders SET table_revision=table_revision+1 WHERE id=NEW.order_id; END;
    CREATE TRIGGER IF NOT EXISTS seating_item_delete AFTER DELETE ON items BEGIN UPDATE orders SET table_revision=table_revision+1 WHERE id=OLD.order_id; END;
    CREATE TRIGGER IF NOT EXISTS seating_item_update AFTER UPDATE ON items BEGIN UPDATE orders SET table_revision=table_revision+1 WHERE id IN (OLD.order_id,NEW.order_id); END;
    CREATE TRIGGER IF NOT EXISTS seating_request_update AFTER UPDATE OF status ON customer_requests BEGIN UPDATE orders SET table_revision=table_revision+1 WHERE id=NEW.order_id; END;
    ''')
    db.execute("INSERT OR IGNORE INTO table_assignments SELECT table_id,id FROM orders WHERE status='open'")
    cancel_columns={r['name'] for r in db.execute('PRAGMA table_info(item_cancellations)')}
    for name,definition in [('name',"TEXT NOT NULL DEFAULT ''"),('price','INTEGER NOT NULL DEFAULT 0')]:
        if name not in cancel_columns:db.execute(f'ALTER TABLE item_cancellations ADD COLUMN {name} {definition}')

def event(h,db,oid,action,detail):
    db.execute('INSERT INTO table_events(order_id,username,action,detail,created) VALUES (?,?,?,?,?)',(oid,h.s['username'],action,detail,h.api.now()))

def rotate(db,oid,target=None):
    old=db.execute('SELECT token FROM visits WHERE order_id=?',(oid,)).fetchone()
    if not old:return
    new=target or secrets.token_urlsafe(24)
    db.execute('UPDATE visit_aliases SET target=? WHERE target=?',(new,old[0]))
    db.execute('INSERT OR REPLACE INTO visit_aliases VALUES (?,?)',(old[0],new))
    db.execute('UPDATE customer_sessions SET visit=? WHERE visit=?',(new,old[0]))
    if target:db.execute('DELETE FROM visits WHERE order_id=?',(oid,))
    else:db.execute('UPDATE visits SET token=? WHERE order_id=?',(new,oid))
    return new

def free(db,tid):
    return db.execute('SELECT * FROM tables WHERE id=?',(tid,)).fetchone() and not db.execute('SELECT 1 FROM table_usage WHERE table_id=?',(tid,)).fetchone() and not db.execute('SELECT 1 FROM table_state WHERE table_id=? AND cleaning=1',(tid,)).fetchone()

def destination(h,db,tid):
    if not free(db,tid):raise ValueError('โต๊ะปลายทางไม่ว่าง หรือยังรอทำความสะอาด กรุณาเลือกใหม่')
    if convenience.nearby_booking(db,tid):raise ValueError('โต๊ะนี้มีการจองใกล้เวลา กรุณาจัดการการจองก่อนย้ายหรือรวมโต๊ะ')

def editable(h,db,d):
    oid=h.api.integer(d['order_id']);o=db.execute("SELECT * FROM orders WHERE id=? AND status='open'",(oid,)).fetchone()
    if not o:raise ValueError('บิลปิดแล้ว กรุณาโหลดหน้าโต๊ะใหม่')
    if str(o['table_revision'])!=d.get('revision'):raise ValueError('มีพนักงานจัดการโต๊ะนี้แล้ว กรุณาโหลดใหม่ก่อนทำรายการ')
    if operations.locked(db,oid) or operations.paid(db,oid):raise ValueError('บิลอยู่ระหว่างชำระ กรุณาปลดล็อกก่อน หากรับเงินแล้วจะจัดการไม่ได้')
    return o

def cancel_item(h,db,item,disposition,reason):
    if not reason.strip():raise ValueError('กรุณาระบุเหตุผล')
    if disposition not in ['return','waste']:raise ValueError('เลือกคืนสต็อกหรือบันทึกของเสีย')
    request=db.execute('SELECT i.prep_status FROM customer_lines l JOIN items i ON i.id=l.item_id WHERE l.item_id=?',(item['id'],)).fetchone()
    if disposition=='return' and (request and request[0] in ['preparing','ready','served'] or item['prep_tracked'] and item['prep_status'] in ['preparing','ready','served']):raise ValueError('รายการเริ่มทำหรือเสิร์ฟแล้ว ต้องบันทึกของเสียเพื่อไม่คืนสต็อก')
    if disposition=='return':
        db.execute('UPDATE products SET stock=stock+? WHERE id=?',(item['qty'],item['product_id']))
        db.execute('INSERT INTO movements(product_id,qty,reason,created) VALUES (?,?,?,?)',(item['product_id'],item['qty'],reason,h.api.now()))
    db.execute('INSERT INTO item_cancellations(item_id,order_id,product_id,name,price,qty,cost,disposition,reason,username,created) VALUES (?,?,?,?,?,?,?,?,?,?,?)',(item['id'],item['order_id'],item['product_id'],item['name'],item['price'],item['qty'],item['cost'],disposition,reason,h.s['username'],h.api.now()))
    db.execute("UPDATE customer_lines SET item_id=NULL,name=name||' (ยกเลิก)' WHERE item_id=?",(item['id'],))
    db.execute('DELETE FROM items WHERE id=?',(item['id'],))
    db.execute("UPDATE customer_requests SET status='cancelled' WHERE order_id=? AND NOT EXISTS (SELECT 1 FROM customer_lines l WHERE l.request_id=customer_requests.id AND l.item_id IS NOT NULL)",(item['order_id'],))

def mutate(h,db,path,d):
    a=h.api
    if path=='/table-ready':
        tid=a.integer(d['table_id'])
        if db.execute('SELECT 1 FROM table_usage WHERE table_id=?',(tid,)).fetchone():raise ValueError('โต๊ะมีลูกค้าแล้ว ไม่สามารถเปลี่ยนเป็นว่าง')
        db.execute('UPDATE table_state SET cleaning=0 WHERE table_id=?',(tid,));return '/tables'
    if path=='/open':
        tid=a.integer(d['table_id'])
        if not free(db,tid):raise ValueError('โต๊ะไม่ว่าง หรือรอทำความสะอาด กรุณาโหลดหน้าใหม่')
        reservation=convenience.nearby_booking(db,tid)
        if reservation and d.get('reservation_ack')!=str(reservation['id']):raise ValueError('กรุณาตรวจการจองและยืนยันก่อนเปิดโต๊ะ')
        guests=a.integer(d.get('guests','1'));table=db.execute('SELECT * FROM tables WHERE id=?',(tid,)).fetchone()
        if guests>table['seats']:raise ValueError('จำนวนคนเกินความจุ ให้เปิดตามความจุแล้วเพิ่มโต๊ะร่วมก่อนเพิ่มจำนวนคน')
        oid=db.execute('INSERT INTO orders(table_id,opened,guests) VALUES (?,?,?)',(tid,a.now(),guests)).lastrowid
        db.execute('INSERT INTO table_assignments VALUES (?,?)',(tid,oid));a.customer.ensure_visit(db,oid)
        event(h,db,oid,'เปิดโต๊ะ',table['name']);return f'/order?id={oid}'
    if path not in ['/table-move','/table-join','/table-merge','/table-link','/table-guests','/table-release','/table-cancel','/table-ungroup','/item-cancel','/void']:return None
    if path in ['/void','/item-cancel','/table-merge'] and h.s['role']!='manager':raise ValueError('รายการนี้ต้องให้ผู้จัดการดำเนินการ')
    if path=='/void' and 'revision' not in d:
        # Compatibility with existing manager cancellation forms.
        o=db.execute('SELECT * FROM orders WHERE id=?',(a.integer(d['order_id']),)).fetchone()
        d=dict(d,revision=str(o['table_revision']) if o else '')
    o=editable(h,db,d);oid=o['id']
    reason=d.get('reason','').strip()
    if path!='/table-guests' and not reason:raise ValueError('กรุณาระบุเหตุผลในการจัดการโต๊ะ')
    before=db.execute('SELECT name FROM order_labels WHERE id=?',(oid,)).fetchone()[0]
    if path=='/table-ungroup':
        if not o['party']:raise ValueError('บิลไม่ได้อยู่ในกลุ่มแยกบิล')
        capacity=db.execute('SELECT SUM(t.seats) FROM table_assignments x JOIN tables t ON t.id=x.table_id WHERE x.order_id=?',(oid,)).fetchone()[0]
        if o['guests']>capacity:raise ValueError('ปรับจำนวนคนให้พอกับที่นั่งของบิลนี้ก่อนแยกกลุ่ม')
        db.execute('UPDATE orders SET party=NULL WHERE id=?',(oid,))
        remaining=db.execute("SELECT id FROM orders WHERE party=? AND status='open'",(o['party'],)).fetchall()
        if len(remaining)==1:db.execute('UPDATE orders SET party=NULL,table_revision=table_revision+1 WHERE id=?',(remaining[0]['id'],))
    elif path=='/table-guests':
        guests=a.integer(d['guests']);capacity=db.execute('SELECT SUM(t.seats) FROM table_assignments x JOIN tables t ON t.id=x.table_id WHERE x.order_id=?',(oid,)).fetchone()[0]
        if guests>capacity:raise ValueError('จำนวนคนของบิลนี้เกินที่นั่ง กรุณาเพิ่มโต๊ะร่วมก่อน')
        db.execute('UPDATE orders SET guests=? WHERE id=?',(guests,oid))
    elif path in ['/table-move','/table-join']:
        tid=a.integer(d['target']);destination(h,db,tid)
        if path=='/table-move':
            if o['party']:raise ValueError('บิลอยู่ในกลุ่มแยกบิล กรุณาแยกกลุ่มก่อนย้าย')
            capacity=db.execute('SELECT seats FROM tables WHERE id=?',(tid,)).fetchone()[0]
            if o['guests']>capacity:raise ValueError('โต๊ะใหม่รองรับจำนวนคนไม่พอ')
            db.execute('INSERT OR REPLACE INTO table_state SELECT table_id,1 FROM table_assignments WHERE order_id=?',(oid,))
            db.execute('DELETE FROM table_assignments WHERE order_id=?',(oid,))
            db.execute('UPDATE orders SET table_id=? WHERE id=?',(tid,oid))
            db.execute('INSERT INTO table_assignments VALUES (?,?)',(tid,oid));rotate(db,oid)
        elif d.get('billing')=='separate':
            guests=a.integer(d.get('new_guests','1'));capacity=db.execute('SELECT seats FROM tables WHERE id=?',(tid,)).fetchone()[0]
            if guests>capacity:raise ValueError('จำนวนคนของโต๊ะเพิ่มเกินความจุ')
            party=o['party'] or secrets.token_hex(12)
            db.execute('UPDATE orders SET party=? WHERE id=?',(party,oid))
            child=db.execute('INSERT INTO orders(table_id,opened,guests,party) VALUES (?,?,?,?)',(tid,a.now(),guests,party)).lastrowid
            db.execute('INSERT INTO table_assignments VALUES (?,?)',(tid,child));a.customer.ensure_visit(db,child)
            event(h,db,child,'รวมพื้นที่ / แยกบิล',f'ร่วมกับบิล #{oid} · '+reason)
        else:db.execute('INSERT INTO table_assignments VALUES (?,?)',(tid,oid))
    elif path=='/table-release':
        tid=a.integer(d['target'])
        if tid==o['table_id']:raise ValueError('แยกโต๊ะหลักไม่ได้ ให้ย้ายโต๊ะหรือปิดบิล')
        if not db.execute('SELECT 1 FROM table_assignments WHERE table_id=? AND order_id=?',(tid,oid)).fetchone():raise ValueError('โต๊ะไม่ได้อยู่ในบิลนี้')
        seats=db.execute('SELECT SUM(t.seats) FROM table_assignments x JOIN tables t ON t.id=x.table_id WHERE x.order_id=? AND x.table_id!=?',(oid,tid)).fetchone()[0]
        if seats<o['guests']:raise ValueError('ที่นั่งที่เหลือไม่พอ กรุณาปรับจำนวนคนก่อน')
        db.execute('DELETE FROM table_assignments WHERE table_id=?',(tid,));db.execute('INSERT OR REPLACE INTO table_state VALUES (?,1)',(tid,))
        rotate(db,oid)
    elif path=='/table-link':
        source=a.integer(d['source']);other=db.execute("SELECT * FROM orders WHERE id=? AND status='open'",(source,)).fetchone()
        if not other or source==oid or str(other['table_revision'])!=d.get('source_revision'):raise ValueError('บิลปลายทางเปลี่ยนแปลงแล้ว กรุณาโหลดใหม่')
        if operations.locked(db,source) or operations.paid(db,source):raise ValueError('บิลปลายทางอยู่ระหว่างชำระ')
        party=o['party'] or other['party'] or secrets.token_hex(12)
        for previous in [o['party'],other['party']]:
            if previous:db.execute("UPDATE orders SET party=?,table_revision=table_revision+1 WHERE party=? AND status='open'",(party,previous))
        db.execute('UPDATE orders SET party=?,table_revision=table_revision+1 WHERE id IN (?,?)',(party,oid,source))
        event(h,db,source,'รวมพื้นที่ / แยกบิล',f'ร่วมกับบิล #{oid} · '+reason)
    elif path=='/table-merge':
        source=a.integer(d['source']);other=db.execute("SELECT * FROM orders WHERE id=? AND status='open'",(source,)).fetchone()
        if not other or source==oid or str(other['table_revision'])!=d.get('source_revision'):raise ValueError('บิลที่จะรวมเปลี่ยนแปลงแล้ว กรุณาเลือกใหม่')
        if operations.locked(db,source) or operations.paid(db,source):raise ValueError('บิลที่จะรวมเริ่มชำระแล้ว ไม่สามารถรวมได้')
        source_label=db.execute('SELECT name FROM order_labels WHERE id=?',(source,)).fetchone()[0]
        db.execute('UPDATE orders SET seat_label=? WHERE id=?',(source_label,source))
        party=o['party'] or other['party']
        if party:
            for previous in [o['party'],other['party']]:
                if previous:db.execute("UPDATE orders SET party=? WHERE party=? AND status='open'",(party,previous))
            db.execute('UPDATE orders SET party=? WHERE id=?',(party,oid))
        db.execute('UPDATE items SET order_id=? WHERE order_id=?',(oid,source))
        db.execute('UPDATE customer_requests SET order_id=? WHERE order_id=?',(oid,source))
        db.execute('UPDATE reservation_orders SET order_id=? WHERE order_id=?',(oid,source))
        db.execute('UPDATE service_requests SET order_id=? WHERE order_id=?',(oid,source))
        db.execute('UPDATE table_assignments SET order_id=? WHERE order_id=?',(oid,source))
        token=rotate(db,oid);rotate(db,source,token)
        db.execute('UPDATE orders SET guests=guests+? WHERE id=?',(other['guests'],oid))
        db.execute("UPDATE orders SET status='void',closed=?,note=? WHERE id=?",(a.now(),f'รวมเข้าบิล #{oid}: '+reason,source))
        event(h,db,source,'รวมบิล',f'เข้าบิล #{oid} · '+reason)
    elif path=='/item-cancel':
        item=db.execute('SELECT * FROM items WHERE id=? AND order_id=?',(a.integer(d['item_id']),oid)).fetchone()
        if not item:raise ValueError('รายการถูกยกเลิกไปแล้ว กรุณาโหลดใหม่')
        cancel_item(h,db,item,d.get('disposition',''),reason)
        import workstations
        workstations.sync(db,oid)
    else:
        items=db.execute('SELECT * FROM items WHERE order_id=?',(oid,)).fetchall()
        history=db.execute('SELECT 1 FROM item_cancellations WHERE order_id=? UNION ALL SELECT 1 FROM customer_requests WHERE order_id=?',(oid,oid)).fetchone()
        if path=='/table-cancel' and (items or history):raise ValueError('มีประวัติรายการอาหารแล้ว ต้องให้ผู้จัดการยกเลิกบิล')
        for item in items:
            request=db.execute('SELECT i.prep_status FROM customer_lines l JOIN items i ON i.id=l.item_id WHERE l.item_id=?',(item['id'],)).fetchone()
            disposition='return' if request and request[0]=='received' else d.get('disposition','waste')
            if request and request[0] in ['preparing','ready','served']:disposition='waste'
            if item['prep_tracked'] and item['prep_status'] in ['preparing','ready','served']:disposition='waste'
            cancel_item(h,db,item,disposition,reason)
        db.execute("UPDATE service_requests SET status='done' WHERE order_id=?",(oid,))
        db.execute("UPDATE orders SET status='void',closed=?,note=? WHERE id=?",(a.now(),reason,oid))
        if path=='/table-cancel':db.execute('UPDATE table_state SET cleaning=0 WHERE table_id=?',(o['table_id'],))
    db.execute('UPDATE orders SET table_revision=table_revision+1 WHERE id=?',(oid,))
    after=db.execute('SELECT name FROM order_labels WHERE id=?',(oid,)).fetchone()[0]
    db.execute('UPDATE orders SET seat_label=? WHERE id=?',(after,oid))
    event(h,db,oid,path,f'{before} → {after} · '+reason)
    return '/tables' if path in ['/void','/table-cancel'] else f'/order?id={oid}'

def controls(h,db,o):
    a=h.api;oid=o['id'];hidden=f'<input type=hidden name=order_id value={oid}><input type=hidden name=revision value={o["table_revision"]}>'
    tables=db.execute('SELECT * FROM tables ORDER BY id').fetchall();used=db.execute('SELECT t.* FROM table_assignments x JOIN tables t ON t.id=x.table_id WHERE x.order_id=?',(oid,)).fetchall()
    capacity=sum(t['seats'] for t in used)
    body=f'<section class=panel><h2>จัดการโต๊ะ · {a.esc(" + ".join(t["name"] for t in used))}</h2><p>ลูกค้า {o["guests"]} คน · ความจุ {capacity} ที่นั่ง</p>'
    if o['party']:
        siblings=db.execute("SELECT o.id,l.name FROM orders o JOIN order_labels l ON l.id=o.id WHERE o.party=? AND o.status='open'",(o['party'],)).fetchall()
        body+='<p class=notice>รวมพื้นที่นั่ง · แยกบิล: '+ ' · '.join(f'<a href=/order?id={r["id"]}>{a.esc(r["name"])} / #{r["id"]}</a>' for r in siblings)+'</p>'
    if operations.locked(db,oid):return body+'<p>บิลอยู่ระหว่างชำระ กรุณาปลดล็อกก่อนจัดการโต๊ะ</p></section>'
    body+=h.form('/table-guests',hidden+a.field('จำนวนลูกค้าในบิลนี้','guests',o['guests'],'number','min=1 max=100 required')+'<button>บันทึกจำนวนคน</button>')
    if o['party']:body+='<details><summary>แยกบิลนี้ออกจากกลุ่มที่นั่ง</summary>'+h.form('/table-ungroup',hidden+a.field('เหตุผล','reason',extra='required maxlength=300')+'<button>ยืนยันแยกกลุ่ม</button>')+'</details>'
    opts=''.join(f'<option value={t["id"]}>{a.esc(t["name"])} · {t["seats"]} ที่นั่ง</option>' for t in tables if free(db,t['id']))
    def reason():return a.field('เหตุผล','reason',extra='required maxlength=300')
    body+='<details><summary>ย้ายโต๊ะ / เพิ่มโต๊ะร่วม</summary><p>ตรวจโต๊ะว่างล่าสุดอีกครั้งตอนยืนยัน · โต๊ะที่มีการจองใกล้เวลาจะใช้ไม่ได้</p>'
    if opts:
        for action,label in [('/table-move','ยืนยันย้ายโต๊ะ'),('/table-join','ยืนยันเพิ่มโต๊ะร่วม')]:
            choice='<label>การคิดบิล<select name=billing><option value=single>บิลเดียวกัน</option><option value=separate>รวมพื้นที่ แต่แยกบิล</option></select></label>'+a.field('จำนวนคนของบิลแยก (กรณีแยกบิล)','new_guests',1,'number','min=1 max=100 required') if action.endswith('join') else ''
            body+=h.form(action,hidden+f'<label>โต๊ะปลายทาง<select name=target>{opts}</select></label>'+choice+reason()+f'<button>{label}</button>')+'<hr>'
    else:body+='<p>ไม่มีโต๊ะว่างพร้อมใช้งาน</p>'
    body+='</details>'
    extra=[t for t in used if t['id']!=o['table_id']]
    if extra:body+='<details><summary>คืนโต๊ะร่วม</summary>'+h.form('/table-release',hidden+'<label>โต๊ะ<select name=target>'+a.options(extra)+'</select></label>'+reason()+'<button>คืนโต๊ะร่วมให้รอทำความสะอาด</button>')+'</details>'
    peers=db.execute("SELECT o.*,l.name FROM orders o JOIN order_labels l ON l.id=o.id WHERE o.status='open' AND o.id!=?",(oid,)).fetchall()
    body+='<details><summary>รวมพื้นที่กับโต๊ะที่เปิดอยู่ (แยกบิล)</summary><p>ออเดอร์และยอดเงินยังอยู่ในบิลเดิม เชื่อมเฉพาะกลุ่มที่นั่ง</p>'
    for r in peers:
        if operations.locked(db,r['id']) or o['party'] and o['party']==r['party']:continue
        body+=h.form('/table-link',hidden+f'<input type=hidden name=source value={r["id"]}><input type=hidden name=source_revision value={r["table_revision"]}><p>{a.esc(r["name"])} · บิล #{r["id"]}</p>'+reason()+'<button>ยืนยันรวมพื้นที่ แยกบิลเดิม</button>')
    body+='</details>'
    if h.s['role']=='manager':
        body+='<details><summary>รวมบิลเข้าบิลนี้</summary><p>รายการและลูกค้าจะรวมกัน โดยไม่หักสต็อกซ้ำ</p>'
        for r in db.execute("SELECT o.*,l.name,(SELECT COALESCE(SUM(price*qty),0) FROM items WHERE order_id=o.id) subtotal FROM orders o JOIN order_labels l ON l.id=o.id WHERE o.status='open' AND o.id!=?",(oid,)):
            if operations.locked(db,r['id']):continue
            own=db.execute('SELECT COALESCE(SUM(price*qty),0) FROM items WHERE order_id=?',(oid,)).fetchone()[0]
            preview=a.grid(['รายการจากบิลที่จะรวม','จำนวน','ยอด'],[(a.esc(i['name']),i['qty'],a.money(i['qty']*i['price'])) for i in db.execute('SELECT * FROM items WHERE order_id=?',(r['id'],))])
            body+=preview
            body+=f'<p>{a.esc(r["name"])} · บิล #{r["id"]} · รวมยอดรายการ ฿{a.money(own+r["subtotal"])} (ก่อนค่าบริการและภาษี)</p>'+h.form('/table-merge',hidden+f'<input type=hidden name=source value={r["id"]}><input type=hidden name=source_revision value={r["table_revision"]}>'+reason()+f'<label><span><input type=checkbox required style="width:auto"> ตรวจรายการทั้งสองบิลแล้ว ยืนยันรวมบิล #{r["id"]} เข้าบิล #{oid}</span></label><button>ยืนยันรวมบิล</button>')
        body+='</details>'
    history=db.execute('SELECT 1 FROM items WHERE order_id=? UNION ALL SELECT 1 FROM item_cancellations WHERE order_id=? UNION ALL SELECT 1 FROM customer_requests WHERE order_id=?',(oid,oid,oid)).fetchone()
    if not history:body+='<details><summary>ยกเลิกเปิดโต๊ะ (ไม่มีรายการ)</summary>'+h.form('/table-cancel',hidden+reason()+'<button class=danger>ยกเลิกเปิดโต๊ะ</button>')+'</details>'
    events=db.execute('SELECT * FROM table_events WHERE order_id=? ORDER BY id DESC LIMIT 12',(oid,)).fetchall()
    labels={'/table-move':'ย้ายโต๊ะ','/table-join':'เพิ่มโต๊ะร่วม','/table-merge':'รวมบิล','/table-link':'รวมพื้นที่ แยกบิล','/table-guests':'ปรับจำนวนคน','/table-release':'คืนโต๊ะร่วม','/table-cancel':'ยกเลิกเปิดโต๊ะ','/table-ungroup':'แยกกลุ่ม','/item-cancel':'ยกเลิกรายการ','/void':'ยกเลิกบิล'}
    body+='<details><summary>ประวัติจัดการโต๊ะ</summary>'+a.grid(['เวลา','ผู้ทำรายการ','รายละเอียด'],[(a.esc(e['created']),a.esc(e['username']),a.esc(labels.get(e['action'],e['action'])+' · '+e['detail'])) for e in events])+'</details></section>'
    body=body.replace('<details>','<details name=table-task>')
    first=body.find('<form')
    if first!=-1:body=body[:first]+'<details class=table-tools><summary>จัดการโต๊ะ</summary>'+body[first:]
    if first!=-1:body=body.rsplit('</section>',1)[0]+'</details></section>'
    return '<style>.panel details{margin:18px 0}.panel summary{cursor:pointer;padding:12px;border-radius:9px;background:#263e30}.cleaning{border-color:#74818e!important;background:#26303a!important}</style>'+body

def plan(h,db):
    a=h.api;body='<section class=panel><h2>แผนผังโต๊ะ · แตะเพื่อจัดการ</h2><div class=floor-plan><div class=plan-stage>เวที / LIVE MUSIC</div><div class=plan-bar>บาร์</div><div class=plan-entry>↑ ทางเข้า</div>'
    for t in db.execute('SELECT t.*,u.order_id,s.cleaning FROM tables t LEFT JOIN table_usage u ON u.table_id=t.id LEFT JOIN table_state s ON s.table_id=t.id'):
        if t['name'] not in floor_plan.LAYOUT:continue
        x,y,zone,desc=floor_plan.LAYOUT[t['name']];status='มีลูกค้า' if t['order_id'] else 'ทำความสะอาด' if t['cleaning'] else 'ว่าง'
        link=f'/order?id={t["order_id"]}' if t['order_id'] else f'#table-{t["id"]}'
        body+=f'<a class="plan-table {"occupied" if t["order_id"] else "capacity" if t["cleaning"] else "available"}" style="left:{x}%;top:{y}%" href="{link}"><span class=table-shape><b>{a.esc(t["name"])}</b><small>{status}</small><small>{t["seats"]} ที่นั่ง</small></span></a>'
    body=body.replace('<div class=floor-plan>','<div class=plan-wrap style="max-width:600px"><div class=floor-plan>',1)
    return '<style>'+floor_plan.CSS+'</style>'+body+'</div></div><p class=muted>ผังจำลองตำแหน่งร้าน · โต๊ะเพิ่มเติมแสดงในรายการด้านล่าง</p></section>'

CUSTOMER_SCRIPT='''<script>(()=>{const labels=[...document.querySelectorAll('[data-seating-label]')];if(!labels.length)return;let last=labels[0].textContent;async function update(){let delay=5000;try{if(document.visibilityState==='visible'){const response=await fetch('/live/seating',{headers:{Accept:'application/json'},cache:'no-store'});if(!response.ok)throw Error();const row=await response.json(),next=row.open?'โต๊ะ '+row.name:'บิลปิดแล้ว';if(next!==last){document.querySelectorAll("[data-seating-label]").forEach(el=>el.textContent=next);let notice=document.querySelector('#seating-update');if(!notice){notice=document.createElement('p');notice.id='seating-update';notice.className='notice';notice.setAttribute('role','status');labels[0].after(notice)}notice.textContent=row.open?'พนักงานอัปเดตที่นั่งของคุณเป็น '+row.name+' · สั่งอาหารต่อได้ตามเดิม':'บิลนี้ปิดแล้ว กรุณาติดต่อพนักงานหากต้องการเปิดบิลใหม่';last=next;if(!row.open)document.querySelectorAll('form[action="/customer/checkout"] button').forEach(b=>b.disabled=true)}}}catch(e){delay=30000}setTimeout(update,delay)}setTimeout(update,5000)})();</script>'''
