"""Validated variant cart keys; prices and option names are snapshotted on ordering."""
import re

def initialize(db):
    db.executescript('''CREATE TABLE IF NOT EXISTS menu_options(id INTEGER PRIMARY KEY,product_id INTEGER NOT NULL REFERENCES products(id),group_name TEXT NOT NULL,label TEXT NOT NULL,price INTEGER NOT NULL DEFAULT 0 CHECK(price>=0),cost INTEGER NOT NULL DEFAULT 0 CHECK(cost>=0),active INTEGER NOT NULL DEFAULT 1,UNIQUE(product_id,group_name,label));
    CREATE TABLE IF NOT EXISTS option_seeded(product_id INTEGER PRIMARY KEY REFERENCES products(id));''')
    for p in db.execute('SELECT * FROM products').fetchall():seed(db,p)

def seed(db,p):
    if db.execute('SELECT 1 FROM option_seeded WHERE product_id=?',(p['id'],)).fetchone():return
    rows=[];category=p['category'];name=p['name']
    if 'ข้าว' in category or 'อาหาร' in category:
        if 'ข้าว' in name or 'กะเพรา' in name:
            rows+=[('ความเผ็ด',label,0,0) for label in ['ไม่เผ็ด','เผ็ดน้อย','เผ็ดมาก']]
            if 'ไข่ดาว' not in name:rows.append(('เพิ่มพิเศษ','เพิ่มไข่ดาว',1500,600))
    elif ('เครื่องดื่ม' in category or 'ค็อกเทล' in category or 'มิกเซอร์' in category) and name not in ['น้ำดื่ม','น้ำแข็งถัง']:
        rows+=[('น้ำแข็ง',label,0,0) for label in ['น้ำแข็งน้อย','ไม่ใส่น้ำแข็ง']]
        if 'โซดา' not in name and 'โคล่า' not in name:rows+=[('ความหวาน',label,0,0) for label in ['ไม่หวาน','หวานน้อย','หวานมาก']]
    db.executemany('INSERT OR IGNORE INTO menu_options(product_id,group_name,label,price,cost) VALUES (?,?,?,?,?)',[(p['id'],*r) for r in rows])
    db.execute('INSERT INTO option_seeded VALUES (?)',(p['id'],))

def split(key):
    raw=str(key)
    if not re.fullmatch(r'[1-9][0-9]*(?::[1-9][0-9]*(?:\.[1-9][0-9]*)*)?',raw):raise ValueError('ตัวเลือกเมนูไม่ถูกต้อง')
    parts=raw.split(':');ids=[int(v) for v in parts[1].split('.')] if len(parts)>1 else []
    if len(ids)>12 or len(ids)!=len(set(ids)):raise ValueError('ตัวเลือกซ้ำหรือมากเกินไป')
    return int(parts[0]),ids

def selected(db,key,active=True):
    pid,ids=split(key);rows=[];groups=set()
    for oid in ids:
        r=db.execute('SELECT * FROM menu_options WHERE id=? AND product_id=?',(oid,pid)).fetchone()
        if not r or active and not r['active'] or r['group_name'] in groups:raise ValueError('ตัวเลือกเปลี่ยนหรือหยุดขาย กรุณาลบรายการแล้วเลือกใหม่')
        groups.add(r['group_name']);rows.append(r)
    return rows

def key(db,product_id,data):
    pid,old=split(product_id)
    if old:raise ValueError('กรุณาเลือกเมนูจากหน้าเมนู')
    ids=[]
    for name,value in data.items():
        if name.startswith('option_') and value:
            if not value.isdigit():raise ValueError('ตัวเลือกเมนูไม่ถูกต้อง')
            ids.append(int(value))
    result=str(pid)+(':'+'.'.join(map(str,sorted(ids))) if ids else '')
    selected(db,result);return result

def product(db,key,strict=False):
    pid,ids=split(key)
    p=db.execute('SELECT p.*,v.image FROM products p LEFT JOIN product_presentation v ON v.product_id=p.id WHERE p.id=?',(pid,)).fetchone()
    if not p:return None
    result=dict(p);result['valid_options']=True
    try:opts=selected(db,key)
    except ValueError:
        if strict:raise
        opts=selected(db,key,False);result['valid_options']=False
    result['price']+=sum(o['price'] for o in opts);result['cost']+=sum(o['cost'] for o in opts)
    if opts:result['name']+=' · '+', '.join(o['group_name']+': '+o['label'] for o in opts)
    result['active']=bool(result['active'] and result['valid_options'])
    return result

def controls(h,db,pid):
    a=h.api;groups={}
    for r in db.execute('SELECT * FROM menu_options WHERE product_id=? AND active=1 ORDER BY group_name,id',(pid,)):groups.setdefault(r['group_name'],[]).append(r)
    body='<div class=modifier-fields>' if groups else ''
    for index,(group,opts) in enumerate(groups.items()):
        body+=f'<label>{a.esc(group)}<select name=option_{index}><option value="" data-price=0>ตามสูตร / ไม่เพิ่ม</option>'+''.join(f'<option value={o["id"]} data-price={o["price"]}>{a.esc(o["label"])}'+(f' (+฿{a.money(o["price"])})' if o['price'] else '')+'</option>' for o in opts)+'</select></label>'
    base=db.execute('SELECT price FROM products WHERE id=?',(pid,)).fetchone()[0]
    return body+f'<p class=modifier-total data-base={base} role=status aria-live=polite>ราคาต่อรายการ ฿{a.money(base)}</p></div>' if groups else ''

def admin(h,db,pid=None):
    a=h.api
    body='<section class=panel><h2>ตัวเลือกเมนู / เพิ่มพิเศษ</h2><p>ลูกค้าเลือกได้หนึ่งตัวเลือกต่อกลุ่ม ราคาและต้นทุนเพิ่มคิดต่อจานหรือแก้ว · สต็อกนับตามจำนวนเมนูหลัก</p><p class=muted>บันทึกข้อมูลเมนูด้านบนก่อนแก้ตัวเลือก · ราคาและต้นทุนตัวเลือกบันทึกด้วยปุ่มในแต่ละแถว</p>'
    target=f'<input type=hidden name=product_id value={pid}><input type=hidden name=return_product value={pid}>' if pid else '<label>เมนู<select name=product_id>'+a.options(db.execute('SELECT * FROM products ORDER BY category,name').fetchall())+'</select></label>'
    body+=h.form('/option-add',target+a.field('กลุ่ม เช่น ความเผ็ด / เพิ่มพิเศษ','group_name',extra='required maxlength=60')+a.field('ตัวเลือก เช่น เพิ่มไข่ดาว','label',extra='required maxlength=80')+a.field('ราคาเพิ่ม','price',0,'number','min=0 step=0.01 required')+a.field('ต้นทุนเพิ่ม','cost',0,'number','min=0 step=0.01 required')+'<button>เพิ่มตัวเลือก</button>')
    rows=[]
    for r in db.execute('SELECT m.*,p.name FROM menu_options m JOIN products p ON p.id=m.product_id WHERE (? IS NULL OR m.product_id=?) ORDER BY p.name,m.group_name,m.id',(pid,pid)):
        return_field=f'<input type=hidden name=return_product value={pid}>' if pid else ''
        edit=h.form('/option-edit',return_field+f'<input type=hidden name=id value={r["id"]}>'+a.field('ราคาเพิ่ม','price',f'{r["price"]/100:.2f}','number','min=0 step=0.01 required')+a.field('ต้นทุนเพิ่ม','cost',f'{r["cost"]/100:.2f}','number','min=0 step=0.01 required')+'<button class=secondary>บันทึกราคา</button>')
        toggle=h.form('/option-toggle',return_field+f'<input type=hidden name=id value={r["id"]}><input type=hidden name=active value={0 if r["active"] else 1}><button class=secondary>{"ปิดตัวเลือก" if r["active"] else "เปิดตัวเลือก"}</button>','inline')
        rows.append((a.esc(r['name']),a.esc(r['group_name']),a.esc(r['label']),a.money(r['price']),a.money(r['cost']),'เปิด' if r['active'] else 'ปิด',edit+toggle))
    return body+a.grid(['เมนู','กลุ่ม','ตัวเลือก','ราคาเพิ่ม','ต้นทุนเพิ่ม','สถานะ',''],rows)+'</section>'

def mutate(h,db,path,d):
    if path not in ['/option-add','/option-toggle','/option-edit']:return None
    if h.s['role']!='manager':raise ValueError('เฉพาะผู้จัดการจัดการตัวเลือกเมนูได้')
    a=h.api
    if path=='/option-add':
        group=d['group_name'].strip();label=d['label'].strip();pid=a.integer(d['product_id'])
        if not group or not label or len(group)>60 or len(label)>80:raise ValueError('ชื่อกลุ่มหรือตัวเลือกไม่ถูกต้อง')
        db.execute('INSERT INTO menu_options(product_id,group_name,label,price,cost) VALUES (?,?,?,?,?)',(pid,group,label,a.amount(d['price']),a.amount(d['cost'])))
    elif path=='/option-edit':
        if db.execute('UPDATE menu_options SET price=?,cost=? WHERE id=?',(a.amount(d['price']),a.amount(d['cost']),a.integer(d['id']))).rowcount!=1:raise ValueError('ไม่พบตัวเลือก')
    else:
        if d['active'] not in ['0','1']:raise ValueError('สถานะไม่ถูกต้อง')
        if db.execute('UPDATE menu_options SET active=? WHERE id=?',(int(d['active']),a.integer(d['id']))).rowcount!=1:raise ValueError('ไม่พบตัวเลือก')
    return '/products?view=edit&product_id='+str(a.integer(d['return_product'])) if d.get('return_product') else '/menu-options'

CSS='''<style>.modifier-fields{display:grid;gap:9px;grid-column:1/-1;flex-basis:100%;width:100%}.modifier-fields select{font-size:13px;padding:9px}.menu-bottom form{flex-wrap:wrap}.modifier-fields label{font-size:13px}.dialog-order .modifier-fields{margin:15px 0}.modifier-total{font-size:14px;color:#efcd93;margin:5px 0}</style><script>document.addEventListener('change',e=>{if(!e.target.name?.startsWith('option_'))return;const form=e.target.closest('form'),preview=form.querySelector('.modifier-total');if(!preview)return;let value=Number(preview.dataset.base);form.querySelectorAll('select[name^=option_]').forEach(select=>value+=Number(select.selectedOptions[0]?.dataset.price||0));preview.textContent='ราคาต่อรายการ ฿'+(value/100).toLocaleString('th-TH',{minimumFractionDigits:2,maximumFractionDigits:2})});</script>'''
