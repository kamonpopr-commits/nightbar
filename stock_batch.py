"""Atomic, idempotent stock adjustments for multiple menu items."""
import hashlib,json,re,secrets
import convenience

def initialize(db):
    db.execute('CREATE TABLE IF NOT EXISTS stock_batches(request_key TEXT PRIMARY KEY,username TEXT NOT NULL,payload TEXT NOT NULL,created TEXT NOT NULL)')

def mutate(h,db,d):
    a=h.api
    if h.s['role']!='manager':raise ValueError('เฉพาะผู้จัดการปรับสต็อกได้')
    key=d.get('request_key','')
    if not re.fullmatch(r'[A-Za-z0-9_-]{20,100}',key):raise ValueError('แบบฟอร์มไม่ถูกต้อง กรุณาเปิดหน้าใหม่')
    common=d.get('common_reason','').strip()
    if len(common)>300:raise ValueError('เหตุผลต้องไม่เกิน 300 ตัวอักษร')
    single=d.get('only_product','');rows=[]
    if single and not single.isdigit():raise ValueError('ไม่พบสินค้าที่เลือก')
    for name,value in d.items():
        if not name.startswith('qty_'):continue
        pid=name[4:]
        if not pid.isdigit() or pid!=str(int(pid)):raise ValueError('รหัสสินค้าไม่ถูกต้อง')
        if single and pid!=single:continue
        try:qty=int(value.strip() or '0')
        except ValueError:raise ValueError('จำนวนเพิ่ม/ลดต้องเป็นจำนวนเต็ม')
        if not qty:continue
        if abs(qty)>1000000:raise ValueError('จำนวนเพิ่ม/ลดเกินกำหนด')
        reason=d.get('reason_'+pid,'').strip() or common
        if not reason or len(reason)>300:raise ValueError('กรุณาระบุเหตุผลรวม หรือเหตุผลของแต่ละรายการที่ปรับ')
        rows.append((int(pid),qty,reason))
    if not rows:raise ValueError('ยังไม่มีรายการปรับสต็อก กรอกจำนวนเพิ่ม/ลดให้ต่างจาก 0 ก่อน')
    rows.sort(); payload=hashlib.sha256(json.dumps(rows,ensure_ascii=False).encode()).hexdigest()
    old=db.execute('SELECT * FROM stock_batches WHERE request_key=?',(key,)).fetchone()
    if old:
        if old['username']!=h.s['username'] or old['payload']!=payload:raise ValueError('แบบฟอร์มนี้ใช้แล้ว กรุณาเปิดหน้าใหม่ก่อนปรับรายการอื่น')
        h.stock_saved_count=len(rows);h.stock_was_duplicate=True
        return '/products'
    for pid,qty,_ in rows:
        p=db.execute('SELECT name,stock FROM products WHERE id=?',(pid,)).fetchone()
        if not p:raise ValueError('ไม่พบสินค้า รหัส '+str(pid))
        if p['stock']+qty<0:raise ValueError(f'{p["name"]}: ลดเกินสต็อก คงเหลือจริง {p["stock"]} · ยังไม่บันทึกทั้งชุด')
    for pid,qty,reason in rows:
        db.execute('UPDATE products SET stock=stock+? WHERE id=?',(qty,pid))
        db.execute('INSERT INTO movements(product_id,qty,reason,created) VALUES (?,?,?,?)',(pid,qty,reason,a.now()))
    db.execute('INSERT INTO stock_batches VALUES (?,?,?,?)',(key,h.s['username'],payload,a.now()))
    h.stock_saved_count=len(rows);h.stock_was_duplicate=False
    return '/products'

def render(h,db,manager):
    a=h.api;rows=[];draft=h.s.get('form_drafts',{}).get('/stock-batch',{})
    for r in db.execute('SELECT p.*,v.image FROM products p LEFT JOIN product_presentation v ON v.product_id=p.id ORDER BY active DESC,category,name'):
        pid=r['id'];name=a.esc(r['name'])
        action=f'<div class=batch-row data-stock={r["stock"]} data-name="{name}"><label>เพิ่ม/ลด<input type=number name=qty_{pid} value=0 min=-1000000 max=1000000 step=1 aria-label="เพิ่ม/ลด {name}"></label><label>เหตุผลเฉพาะรายการ<input name=reason_{pid} maxlength=300 placeholder="เว้นว่างใช้เหตุผลรวม" aria-label="เหตุผล {name}"></label><button type=submit class=secondary name=only_product value={pid}>ปรับรายการนี้</button><small class=stock-result aria-live=polite>หลังปรับ: {r["stock"]}</small></div>' if manager else ''
        if manager:
            action=action.replace('name=qty_'+str(pid)+' value=0','name=qty_'+str(pid)+' value="'+a.esc(draft.get('qty_'+str(pid),'0'))+'"')
            action=action.replace('name=reason_'+str(pid)+' maxlength','name=reason_'+str(pid)+' value="'+a.esc(draft.get('reason_'+str(pid),''))+'" maxlength')
        if not manager and h.s['role']=='manager':name=f'<a href="/products?view=edit&amp;product_id={pid}" title="แก้ไขเมนู">{name} ✎</a>'
        if not manager and h.s['role']=='manager':
            action=h.form('/product-availability',f'<input type=hidden name=product_id value={pid}><input type=hidden name=expected value={r["active"]}><button class=secondary>{"หยุดขายชั่วคราว" if r["active"] else "เปิดขายอีกครั้ง"}</button>','inline')
        rows.append((f'<span class=menu-with-thumb>{convenience.thumbnail(r["image"],r["name"])}{name}</span>',a.esc(r['category']),a.money(r['price']),f'<span class=badge>{r["stock"]}</span>',r['minimum'],action))
    show_actions=manager or h.s['role']=='manager'
    table=a.grid(['สินค้า','หมวด','ราคา','คงเหลือ','ขั้นต่ำ','จัดการ'] if show_actions else ['สินค้า','หมวด','ราคา','คงเหลือ','ขั้นต่ำ'],rows if show_actions else [row[:-1] for row in rows])
    if not manager:return '<section class=panel>'+convenience.filters('products')+table+'</section>'
    content=f'<input type=hidden name=request_key value="{secrets.token_urlsafe(24)}"><div class=batch-intro><h2>ปรับสต็อกหลายรายการ</h2><p>กรอก + เพื่อเพิ่ม หรือ − เพื่อลด · แถวที่เป็น 0 หรือว่างจะไม่ถูกปรับ</p>'+a.field('เหตุผลรวมสำหรับรายการที่ปรับ','common_reason',extra='maxlength=300 placeholder="เช่น รับสินค้าเข้าร้าน / ตรวจนับสต็อก"')+'<p class=muted>ยอดหลังปรับเป็นตัวอย่างจากข้อมูลบนหน้านี้ ระบบตรวจสต็อกล่าสุดอีกครั้งก่อนบันทึก</p></div>'+table+'<div class=batch-toolbar><span class=batch-count role=status aria-live=polite>ยังไม่มีรายการเปลี่ยน</span><button type=submit>บันทึกการปรับสต็อกทั้งหมด</button></div>'
    content=content.replace(table,convenience.filters('products')+table).replace('name="common_reason" value=""','name="common_reason" value="'+a.esc(draft.get('common_reason',''))+'"')
    return '<section class=panel><style>'+CSS+'</style>'+h.form('/stock-batch',content,'stock-batch').replace('class="stock-batch"','class="stock-batch" novalidate',1)+SCRIPT+'</section>'

CSS='''.batch-intro{margin-bottom:22px;line-height:1.8}.batch-intro label{max-width:620px}.batch-row{display:grid;grid-template-columns:100px minmax(150px,1fr) auto;gap:10px;align-items:end;min-width:410px}.batch-row .stock-result{grid-column:1/-1;font-size:14px}.batch-row input{width:100%}.batch-row.changed{border-left:3px solid #e6bc78;padding-left:10px}.batch-row.invalid .stock-result{color:#ffc0b5}.batch-toolbar{position:sticky;bottom:12px;z-index:15;display:flex;justify-content:space-between;align-items:center;gap:14px;flex-wrap:wrap;padding:16px 20px;background:#223c2ef5;border:1px solid #73805b;border-radius:12px;margin-top:20px;box-shadow:0 8px 30px #0004}.batch-count{font-size:15px;color:#e4d4b2}@media(max-width:600px){.batch-toolbar{padding:12px}.batch-toolbar button{width:100%}.batch-row{min-width:350px;grid-template-columns:90px 145px auto}.batch-row button{font-size:12px;padding:10px}.stock-batch .scroll{max-height:65vh;overflow:auto}}'''

SCRIPT='''<script>(()=>{const form=document.querySelector('.stock-batch');if(!form)return;const rows=[...form.querySelectorAll('.batch-row')],count=form.querySelector('.batch-count'),common=form.querySelector('[name=common_reason]');function update(){let total=0;rows.forEach(row=>{const field=row.querySelector('[name^=qty_]'),qty=Number(field.value),next=Number(row.dataset.stock)+qty,valid=Number.isInteger(qty)&&field.checkValidity();if(qty)total++;row.classList.toggle('changed',!!qty);row.classList.toggle('invalid',!valid||next<0);row.querySelector('.stock-result').textContent=!valid?'กรุณากรอกจำนวนเต็ม':next<0?'ลดเกินสต็อกบนหน้าจอ':row.dataset.stock+' '+(qty<0?'− '+Math.abs(qty):'+ '+qty)+' → '+next});count.textContent=total?'เตรียมปรับ '+total+' รายการ · ตรวจยอดและเหตุผลก่อนบันทึก':'ยังไม่มีรายการเปลี่ยน'}form.addEventListener('keydown',e=>{if(e.key==='Enter'&&e.target.tagName==='INPUT')e.preventDefault()});form.addEventListener('input',update);form.addEventListener('submit',e=>{if(form.dataset.sending){e.preventDefault();return}const single=e.submitter?.value;const selected=rows.filter(row=>{const input=row.querySelector('[name^=qty_]');return (!single||input.name==='qty_'+single)&&Number(input.value)!==0});if(!selected.length){e.preventDefault();count.textContent='กรอกจำนวนเพิ่ม/ลดในรายการที่ต้องการก่อน';return}for(const row of selected){const qty=row.querySelector('[name^=qty_]'),reason=row.querySelector('[name^=reason_]');if(!qty.checkValidity()){e.preventDefault();qty.reportValidity();return}if(!reason.value.trim()&&!common.value.trim()){e.preventDefault();count.textContent='กรุณาระบุเหตุผลรวม หรือเหตุผลของรายการ '+row.dataset.name;common.focus();return}}form.dataset.sending='1';const button=e.submitter;if(button){const mirror=document.createElement('input');mirror.type='hidden';mirror.name=button.name;mirror.value=button.value;if(button.name)form.append(mirror)}form.querySelectorAll('button').forEach(b=>b.disabled=true);count.textContent='กำลังตรวจสต็อกและบันทึก กรุณารอ…'});update()})();</script>'''
