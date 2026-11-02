"""Staff workspaces and individual kitchen/bar preparation stages."""
import operations
import live_ui
import convenience

LABELS={'general':'พนักงานทั่วไป','floor':'บริการหน้าร้าน','kitchen':'ครัว','bar':'บาร์','cashier':'แคชเชียร์'}

def station(category):return 'kitchen' if 'อาหาร' in category or 'ข้าว' in category else 'bar'

def for_product(db,p):
    row=db.execute('SELECT station FROM product_stations WHERE product_id=?',(p['id'],)).fetchone()
    return row[0] if row else station(p['category'])

def initialize(db):
    db.execute("CREATE TABLE IF NOT EXISTS product_stations(product_id INTEGER PRIMARY KEY REFERENCES products(id),station TEXT NOT NULL CHECK(station IN ('kitchen','bar')))")
    for p in db.execute('SELECT * FROM products').fetchall():db.execute('INSERT OR IGNORE INTO product_stations VALUES (?,?)',(p['id'],station(p['category'])))
    cols={r['name'] for r in db.execute('PRAGMA table_info(users)')}
    if 'station' not in cols:db.execute("ALTER TABLE users ADD COLUMN station TEXT NOT NULL DEFAULT 'general'")
    cols={r['name'] for r in db.execute('PRAGMA table_info(items)')}
    fresh='prep_status' not in cols
    for name,definition in [('station',"TEXT NOT NULL DEFAULT ''"),('prep_status',"TEXT NOT NULL DEFAULT 'served'"),('prep_created','TEXT'),('prep_tracked','INTEGER NOT NULL DEFAULT 0')]:
        if name not in cols:db.execute(f'ALTER TABLE items ADD COLUMN {name} {definition}')
    for r in db.execute("SELECT i.id,p.category FROM items i JOIN products p ON p.id=i.product_id WHERE i.station='' ").fetchall():db.execute('UPDATE items SET station=? WHERE id=?',(station(r['category']),r['id']))
    if fresh:
        db.execute("UPDATE items SET prep_status=COALESCE((SELECT r.status FROM customer_lines l JOIN customer_requests r ON r.id=l.request_id WHERE l.item_id=items.id),'served')")
    db.execute('UPDATE items SET prep_tracked=1 WHERE prep_tracked=0 AND EXISTS (SELECT 1 FROM customer_lines WHERE item_id=items.id)')

def position(h):return 'general' if h.s['role']=='manager' else h.s.get('station','general')

def allowed(h,path,write=False):
    if h.s['role']=='manager':return True
    p=position(h)
    if p=='general':return True
    if path in ['/logout','/password']:return True
    if p in ['kitchen','bar']:return path in (['/production-status'] if write else ['/','/production','/live/production'])
    if p=='floor':return path in (['/open','/add','/table-ready','/table-move','/table-join','/table-link','/table-guests','/table-release','/table-cancel','/table-ungroup','/reserve','/reservation-status','/service-done','/service-bill','/production-status'] if write else ['/','/tables','/order','/receipt','/live/order-hub','/production','/live/production','/customer-queue','/live/queue','/qr','/qr.svg','/reservations','/products','/checkout'])
    if p=='cashier':return path in (['/checkout-simple','/shift-open','/shift-close','/cash-event','/checkout-freeze','/checkout-unlock','/bill-split','/payment-add','/pay','/service-bill','/table-ready'] if write else ['/','/tables','/order','/checkout','/receipt','/part-receipt','/shifts','/customer-queue','/live/queue','/production','/live/production'])
    return False

def home(h):
    p=position(h)
    return '/production' if p in ['kitchen','bar'] else '/tables' if p=='floor' else '/shifts' if p=='cashier' else None

def user_controls(h,db):
    a=h.api
    body='<section class=panel><h2>หน้าที่ของพนักงาน</h2><p>ผู้จัดการเข้าถึงทุกงาน บัญชีพนักงานเดิมยังเป็นพนักงานทั่วไปจนกว่าจะกำหนดหน้าที่</p>'
    for r in db.execute("SELECT * FROM users WHERE role='staff' ORDER BY username"):
        opts=''.join(f'<option value={k} {"selected" if r["station"]==k else ""}>{v}</option>' for k,v in LABELS.items())
        body+=h.form('/staff-station',f'<input type=hidden name=id value={r["id"]}><p>{a.esc(r["username"])}</p><label>หน้าที่<select name=station>{opts}</select></label><button>บันทึกหน้าที่</button>')
    return body+'</section>'

def routing_controls(h,db):
    a=h.api;body='<section class=panel><h2>ส่งเมนูเข้าครัวหรือบาร์</h2><p>กำหนดแผนกที่รับงาน มีผลกับออเดอร์ใหม่ รายการที่กำลังทำอยู่ยังอยู่ในแผนกเดิม</p>'
    for p in db.execute('SELECT * FROM products WHERE active=1 ORDER BY category,name'):
        current=for_product(db,p);opts=''.join(f'<option value={key} {"selected" if key==current else ""}>{label}</option>' for key,label in [('kitchen','ครัว'),('bar','บาร์')])
        body+=h.form('/product-station',f'<input type=hidden name=product_id value={p["id"]}><p>{a.esc(p["name"])}</p><label>แผนก<select name=station>{opts}</select></label><button>บันทึกแผนก</button>')
    return body+'</section>'

def sync(db,oid):
    for request in db.execute('SELECT id FROM customer_requests WHERE order_id=?',(oid,)).fetchall():
        states=[r[0] for r in db.execute('SELECT i.prep_status FROM customer_lines l JOIN items i ON i.id=l.item_id WHERE l.request_id=?',(request['id'],))]
        status=min(states,key=['received','preparing','ready','served'].index) if states else 'cancelled'
        db.execute('UPDATE customer_requests SET status=? WHERE id=?',(status,request['id']))

def mutate(h,db,path,d):
    a=h.api
    if path=='/product-station':
        if h.s['role']!='manager' or d.get('station') not in ['kitchen','bar']:raise ValueError('เฉพาะผู้จัดการกำหนดแผนกได้')
        db.execute('INSERT INTO product_stations VALUES (?,?) ON CONFLICT(product_id) DO UPDATE SET station=excluded.station',(a.integer(d['product_id']),d['station']))
        return '/menu-options'
    if path=='/staff-station':
        if h.s['role']!='manager' or d.get('station') not in LABELS:raise ValueError('สิทธิ์หรือหน้าที่ไม่ถูกต้อง')
        row=db.execute("SELECT username FROM users WHERE id=? AND role='staff'",(a.integer(d['id']),)).fetchone()
        if not row:raise ValueError('ไม่พบบัญชีพนักงาน')
        db.execute('UPDATE users SET station=? WHERE id=?',(d['station'],a.integer(d['id'])))
        for s in a.SESSIONS.values():
            if s.get('username')==row['username']:s['station']=d['station']
        return '/settings'
    if path!='/production-status':return None
    item=db.execute("SELECT i.* FROM items i JOIN orders o ON o.id=i.order_id WHERE i.id=? AND o.status='open'",(a.integer(d['item_id']),)).fetchone()
    if not item or item['prep_status']!=d.get('expected'):raise ValueError('รายการเปลี่ยนแล้ว กรุณาโหลดคิวใหม่')
    next_state={'received':'preparing','preparing':'ready','ready':'served'}.get(item['prep_status'])
    if next_state!=d.get('status'):raise ValueError('ไม่สามารถข้ามขั้นตอนหรือย้อนสถานะ')
    p=position(h)
    if p in ['kitchen','bar'] and (p!=item['station'] or next_state=='served'):raise ValueError('ทำได้เฉพาะคิวของแผนกตนเอง ส่วนการเสิร์ฟให้พนักงานหน้าร้านยืนยัน')
    if p=='floor' and next_state!='served':raise ValueError('พนักงานหน้าร้านยืนยันได้เฉพาะรายการพร้อมเสิร์ฟ')
    if p=='cashier':raise ValueError('แคชเชียร์ไม่มีสิทธิ์เปลี่ยนสถานะครัว')
    if operations.locked(db,item['order_id']):raise ValueError('บิลกำลังชำระ ไม่สามารถแก้คิว')
    db.execute('UPDATE items SET prep_status=? WHERE id=?',(next_state,item['id']));sync(db,item['order_id'])
    return '/order?id='+str(item['order_id']) if d.get('return_order')==str(item['order_id']) else '/production'

def board(h,db):
    a=h.api;p=position(h);chosen=p if p in ['kitchen','bar'] else h.query.get('station',['all'])[0]
    if chosen not in ['all','kitchen','bar']:chosen='all'
    wanted=h.query.get('stage',[''])[0]
    if p=='floor' and not wanted:wanted='ready'
    if wanted not in ['','received','preparing','ready']:wanted=''
    body='<div class=workspace-tabs>'
    if p not in ['kitchen','bar']:
        for key,label in [('all','ทุกแผนก'),('kitchen','ครัว'),('bar','บาร์')]:body+=f'<a href="/production?station={key}" aria-current={"page" if key==chosen else "false"}>{label}</a>'
    body+='</div><style>.workspace-tabs:empty{display:none}.order-board:has(>.order-lane:only-child){grid-template-columns:1fr}</style><form method=get class=fields><input type=hidden name=station value='+chosen+'><label>ขั้นตอน<select name=stage>'+''.join(f'<option value="{key}" {"selected" if key==wanted else ""}>{label}</option>' for key,label in [('', 'ทุกขั้นตอน'),('received','รอจัดเตรียม'),('preparing','กำลังทำ'),('ready','พร้อมเสิร์ฟ')])+'</select></label><button>กรองคิว</button></form><p>อัปเดตทีละรายการ · ครัวและบาร์ทำงานแยกกัน · รายการรอเกิน 15 นาทีมีข้อความเตือน</p><div class=order-board>'
    ids=[];states={'received':('preparing','เริ่มทำ'),'preparing':('ready','พร้อมเสิร์ฟ'),'ready':('served','เสิร์ฟแล้ว')}
    for state,(next_state,label) in states.items():
        if wanted and state!=wanted:continue
        cards=[]
        rows=db.execute("SELECT i.*,l.name table_name,COALESCE(i.prep_created,r.created,o.opened) created,COALESCE(r.note,'') customer_note FROM items i JOIN orders o ON o.id=i.order_id JOIN order_labels l ON l.id=o.id LEFT JOIN customer_lines c ON c.item_id=i.id LEFT JOIN customer_requests r ON r.id=c.request_id WHERE o.status='open' AND i.prep_status=? AND (?='all' OR i.station=?) ORDER BY created,i.id",(state,chosen,chosen)).fetchall()
        for r in rows:
            ids.append(r['id']);card=f'<article class=order-card><small>{"ครัว" if r["station"]=="kitchen" else "บาร์"} · บิล #{r["order_id"]}</small><h2>{a.esc(r["table_name"])}</h2><p><strong>{r["qty"]} × {a.esc(r["name"])}</strong></p>'+convenience.wait_label(r['created'])
            if r['customer_note']:card+='<p class=order-note>'+a.esc(r['customer_note'])+'</p>'
            moved=db.execute("SELECT detail FROM table_events WHERE order_id=? AND action IN ('/table-move','/table-merge') ORDER BY id DESC LIMIT 1",(r['order_id'],)).fetchone()
            if moved:card+='<p class=order-note>'+a.esc(moved[0])+'</p>'
            can=(p=='general' or p in ['kitchen','bar'] and next_state!='served' or p=='floor' and next_state=='served')
            if can:card+=h.form('/production-status',f'<input type=hidden name=item_id value={r["id"]}><input type=hidden name=expected value={state}><input type=hidden name=status value={next_state}><button>{label}</button>')
            else:card+='<p class=muted>รอพนักงาน'+('หน้าร้านยืนยันเสิร์ฟ' if next_state=='served' else 'ครัว / บาร์จัดเตรียม')+'</p>'
            cards.append(card+'</article>')
        body+=f'<section class="order-lane lane-{state}"><h2>{dict(received="รอจัดเตรียม",preparing="กำลังทำ",ready="พร้อมเสิร์ฟ")[state]} <span>{len(cards)}</span></h2>'+(''.join(cards) or '<p class=lane-empty>ไม่มีรายการ</p>')+'</section>'
    return body+'</div>',ids

def get(h,db,path):
    if path not in ['/production','/live/production']:return False
    body,ids=board(h,db)
    import workspace
    p=position(h);view=h.query.get('view',['services' if p=='cashier' else 'prep'])[0]
    if view not in ['prep','services','history']:view='prep'
    if p in ['kitchen','bar'] and view=='services':view='prep'
    service_body,service_ids=workspace.services(h,db)
    tabs='<style>.workspace-tabs a[aria-current=page]{background:#e7bd7c;color:#14261a;font-weight:650}</style><div class=workspace-tabs>'
    for key,label in [('prep','งานทั้งหมด' if p not in ['kitchen','bar'] else 'เตรียม / เสิร์ฟ'),('services','งานบริการ / เช็กบิล'),('history','ประวัติ')]:
        if key=='services' and p in ['kitchen','bar']:continue
        tabs+=f'<a href="/production?view={key}" aria-current={"page" if key==view else "false"}>{label}'+(f' ({len(service_ids)})' if key=='services' else '')+'</a>'
    tabs+='</div>'
    if view=='services':body=service_body;ids=service_ids
    elif view=='history':body=workspace.history(h,db);ids=[]
    else:
        body=body.replace('<input type=hidden name=station','<input type=hidden name=view value=prep><input type=hidden name=station',1)
        if service_ids:body=service_body+body
        ids+=service_ids
    body=tabs+body
    if path=='/live/production':
        import json
        h.respond(json.dumps({'html':body,'ids':ids},ensure_ascii=False),content='application/json; charset=utf-8')
    else:
        from urllib.parse import urlencode
        query=urlencode({k:v[0] for k,v in h.query.items() if k in ['station','stage','view']})
        h.page('ออเดอร์และบริการ',live_ui.controls(True)+f'<div id=live-content>{body}</div>'+live_ui.script('/live/production'+('?' +query if query else ''),ids,True))
    return True
