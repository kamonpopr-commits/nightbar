"""One menu editor per product and one operational inbox."""
import menu_uploads
import menu_options
import workstations
import visuals
import ux

def editor(h,db):
    a=h.api;products=db.execute('SELECT * FROM products ORDER BY active DESC,category,name').fetchall()
    if not products:return '<section class=panel>เพิ่มเมนูก่อนเพื่อเริ่มแก้ไข</section>'
    draft=h.s.get('form_drafts',{}).get('/product-save',{})
    raw=h.query.get('product_id',[draft.get('product_id',str(products[0]['id']))])[0]
    pid=a.integer(raw);p=db.execute('SELECT p.*,COALESCE(v.image,\'\') image,COALESCE(v.description,\'\') description,COALESCE(v.featured,0) featured FROM products p LEFT JOIN product_presentation v ON v.product_id=p.id WHERE p.id=?',(pid,)).fetchone()
    if not p:raise ValueError('ไม่พบเมนูที่เลือก')
    h.editing_product=pid
    opts=''.join(f'<option value={r["id"]} {"selected" if r["id"]==pid else ""}>{a.esc(r["name"])}</option>' for r in products)
    body='<section class=panel><h2>เลือกเมนูที่ต้องการแก้ไข</h2><form class=fields method=get action=/products><input type=hidden name=view value=edit><label>เมนู<select name=product_id>'+opts+'</select></label><button>เปิดเมนูนี้</button></form><p class=muted>บันทึกการแก้ไขก่อนเปิดเมนูอื่น</p></section>'
    fields=f'<input type=hidden name=product_id value={pid}>'
    for label,key,kind,value,extra in [('ชื่อเมนู','name','text',p['name'],'required maxlength=120'),('หมวด','category','text',p['category'],'required maxlength=80'),('ราคา','price','number',f'{p["price"]/100:.2f}','min=0 step=0.01 required'),('ต้นทุน','cost','number',f'{p["cost"]/100:.2f}','min=0 step=0.01 required'),('ขั้นต่ำแจ้งเตือน','minimum','number',p['minimum'],'min=0 step=1 required'),('คำอธิบาย','description','text',p['description'],'maxlength=300')]:fields+=a.field(label,key,draft.get(key,value),kind,extra)
    for label,key,choices,current in [('จำหน่าย','active',[('1','จำหน่าย'),('0','ซ่อน')],str(p['active'])),('เมนูแนะนำ','featured',[('0','ทั่วไป'),('1','แนะนำ')],str(p['featured'])),('ส่งงานไป','station',[('kitchen','ครัว'),('bar','บาร์')],workstations.for_product(db,p))]:
        current=draft.get(key,current);fields+=f'<label>{label}<select name={key}>'+''.join(f'<option value={v} {"selected" if v==current else ""}>{text}</option>' for v,text in choices)+'</select></label>'
    current=draft.get('image',p['image']);fields+='<label>รูปที่ใช้อยู่<select name=image><option value="">ภาพตามหมวด</option>'+''.join(f'<option value="{a.esc(photo.name)}" {"selected" if current==photo.name else ""}>{a.esc(photo.stem)}</option>' for photo in sorted(visuals.ASSETS.glob('*.webp')))+'</select></label>'+menu_uploads.controls()+'<button>บันทึกข้อมูลและรูปเมนู</button>'
    body+='<section class=panel><h2>'+a.esc(p['name'])+'</h2><p>ชื่อ ราคา รูป และแผนก บันทึกพร้อมกัน · การแก้ไขไม่เปลี่ยนบิลเก่า</p>'+h.form('/product-save',fields)+'</section>'
    return body+menu_options.admin(h,db,pid)

def services(h,db):
    a=h.api;p=workstations.position(h)
    if p in ['kitchen','bar']:return '',[]
    rows=db.execute("SELECT s.*,l.name FROM service_requests s JOIN orders o ON o.id=s.order_id JOIN order_labels l ON l.id=o.id WHERE o.status='open' AND s.status IN ('waiting','handling') ORDER BY s.id").fetchall()
    if p=='cashier':rows=[r for r in rows if r['kind']=='bill']
    cards=[]
    for r in rows:
        bill=r['kind']=='bill';action='/service-bill' if bill else '/service-done'
        label=('รอชำระเงิน' if r['status']=='handling' else 'ขอเช็กบิล') if bill else 'เรียกพนักงาน'
        button=('ชำระต่อ →' if r['status']=='handling' else 'ไปชำระเงิน →') if bill else 'ดูแลแล้ว'
        card=f'<article class=order-card><h2>{a.esc(r["name"])}</h2><p>{label}</p><small>{ux.date(r["created"])}</small>'
        if workstations.allowed(h,action,True):card+=h.form(action,f'<input type=hidden name=id value={r["id"]}><button>{button}</button>')
        cards.append(card+'</article>')
    return '<section class=panel><h2>งานบริการ / เช็กบิล</h2><p>คำขอเช็กบิลติดตามจนรับชำระครบ การเปิดบิลยังไม่ใช่การรับเงิน</p><div class=cards>'+(''.join(cards) or '<p>ไม่มีคำขอค้าง</p>')+'</div></section>',['s'+str(r['id']) for r in rows]

def history(h,db):
    a=h.api;p=workstations.position(h);filter_station=p if p in ['kitchen','bar'] else 'all'
    rows=db.execute("SELECT i.*,l.name table_name,o.status bill_status FROM items i JOIN orders o ON o.id=i.order_id JOIN order_labels l ON l.id=o.id WHERE i.prep_status='served' AND i.prep_tracked=1 AND (?='all' OR i.station=?) ORDER BY i.id DESC LIMIT 30",(filter_station,filter_station)).fetchall()
    body='<section class=panel><h2>รายการเสิร์ฟแล้วล่าสุด</h2>'+a.grid(['โต๊ะ','รายการ','จำนวน','สถานะบิล'],[(a.esc(r['table_name']),a.esc(r['name']),r['qty'],ux.status(r['bill_status'])) for r in rows])+'</section>'
    if p not in ['kitchen','bar']:
        cancellations=db.execute('SELECT c.*,l.name table_name FROM item_cancellations c JOIN order_labels l ON l.id=c.order_id ORDER BY c.id DESC LIMIT 30').fetchall()
        body+='<section class=panel><h2>รายการยกเลิกล่าสุด</h2>'+a.grid(['โต๊ะ','รายการ','จำนวน','การจัดการ','เหตุผล'],[(a.esc(r['table_name']),a.esc(r['name']),r['qty'],'ของเสีย' if r['disposition']=='waste' else 'คืนสต็อก',a.esc(r['reason'])) for r in cancellations])+'</section>'
    return body

QR_DIALOG='''<dialog id=quick-qr aria-labelledby=quick-qr-title><button type=button class="secondary qr-close">ปิด ✕</button><h2 id=quick-qr-title>QR สำหรับบิลนี้</h2><p>ให้ลูกค้าสแกนเพื่อสั่งอาหาร</p><img alt="QR สำหรับบิลที่เลือก" width=280 height=280 style="background:white;border-radius:12px;max-width:100%"><p class=qr-error role=status hidden>QR หมดอายุหรือโหลดไม่ได้ กรุณาตรวจบิล</p><p><a class="button secondary qr-save">เปิด / บันทึก QR</a> <a class="button secondary qr-print" data-qr-page>เปิดหน้าพิมพ์ QR</a></p></dialog><style>#quick-qr{background:#1a2d22;color:#edf1e7;border:1px solid #6d805f;border-radius:18px;max-width:95vw;padding:25px;text-align:center}#quick-qr::backdrop{background:#000a}#quick-qr .qr-close{float:right}</style><script>(()=>{const dialog=document.querySelector('#quick-qr');document.addEventListener('click',e=>{const link=e.target.closest('a');if(!link||link.hasAttribute('data-qr-page'))return;const url=new URL(link.href,location.href);if(url.origin!==location.origin||url.pathname!='/qr'||!url.searchParams.has('order_id')||!dialog.showModal)return;const id=url.searchParams.get('order_id');if(!/^[1-9][0-9]*$/.test(id))return;e.preventDefault();const img=dialog.querySelector('img'),error=dialog.querySelector('.qr-error');error.hidden=true;img.onload=()=>error.hidden=true;img.onerror=()=>error.hidden=false;img.src='/qr.svg?order_id='+id;dialog.querySelector('.qr-save').href=img.src;dialog.querySelector('.qr-print').href='/qr?order_id='+id;dialog.showModal()});dialog.querySelector('.qr-close').addEventListener('click',()=>dialog.close())})();</script>'''
