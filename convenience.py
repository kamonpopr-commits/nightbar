"""Small workflow conveniences, session drafts, and consistent navigation."""
from datetime import datetime,timedelta
from html import escape
import json
import ux

def nearby_booking(db,tid):
    current=datetime.now()
    for r in db.execute("SELECT * FROM reservations WHERE table_id=? AND status='booked' ORDER BY time",(tid,)):
        t=datetime.fromisoformat(r['time'])
        if t.tzinfo is None and current-timedelta(hours=2)<t<current+timedelta(hours=2):return r

def table_warning(a,db,tid):
    r=nearby_booking(db,tid)
    if not r:return '',''
    notice=f'<p class=reservation-warning>มีการจองใกล้เวลานี้<br><b>{ux.date(r["time"])}</b> · {r["guests"]} คน<br><a href=/reservations>ตรวจการจองก่อนเปิดโต๊ะ →</a></p>'
    ack=f'<label class=reservation-ack><span><input type=checkbox name=reservation_ack value={r["id"]} required> ตรวจการจองและยืนยันเปิดโต๊ะนี้</span></label>'
    return notice,ack

def wait_label(value):
    try:
        start=datetime.fromisoformat(value); minutes=max(0,int((datetime.now(start.tzinfo)-start).total_seconds()/60))
    except (TypeError,ValueError):return ''
    return f'<span class="wait-label {"late" if minutes>=15 else ""}">รอมา {minutes} นาที'+(' · ควรตรวจออเดอร์' if minutes>=15 else '')+'</span>'

def remember(h,path,data):
    if not getattr(h,'s',None) or path not in ['/stock-batch','/product','/product-presentation','/product-edit','/product-save','/reserve','/expense']:return
    allowed={'/stock-batch':lambda k:k.startswith(('qty_','reason_')) or k=='common_reason',
        '/product':lambda k:k in ['name','category','price','cost','stock','minimum','description','featured'],
        '/product-presentation':lambda k:k in ['product_id','image','description','featured'],
        '/product-save':lambda k:k in ['product_id','name','category','price','cost','minimum','active','description','featured','image','station'],
        '/product-edit':lambda k:k in ['product_id','name','category','cost','minimum','price','active'],
        '/reserve':lambda k:k in ['name','phone','table_id','time','guests'],
        '/expense':lambda k:k in ['title','amount','method']}
    draft={k:v[:500] for k,v in data.items() if allowed[path](k)}
    h.s.setdefault('form_drafts',{})[path]=draft

def drafts(h):
    data=getattr(h,'s',{}).get('form_drafts',{})
    if not data:return ''
    encoded=json.dumps(data,ensure_ascii=False).replace('<',chr(92)+'u003c')
    return '<script type=application/json id=form-drafts>'+encoded+'</script><script>(()=>{const drafts=JSON.parse(document.querySelector("#form-drafts").textContent);for(const [action,values] of Object.entries(drafts)){const form=[...document.forms].find(f=>f.getAttribute("action")===action);if(!form)continue;for(const [name,value] of Object.entries(values)){const input=[...form.elements].find(el=>el.name===name);if(input&&input.type!=="file"){input.value=value;input.dispatchEvent(new Event(input.tagName==="SELECT"?"change":"input",{bubbles:true}))}}const hint=document.createElement("p");hint.className="notice";hint.textContent="เก็บข้อมูลที่กรอกไว้ให้แล้ว แก้รายการที่ผิดแล้วบันทึกอีกครั้ง"+(form.enctype==="multipart/form-data"?" · หากต้องการอัปโหลด กรุณาเลือกรูปอีกครั้ง":"");form.prepend(hint)}})();</script>'

def thumbnail(image,name):
    if not image:return ''
    return f'<img class=menu-thumb src="/assets/{escape(image,quote=True)}" alt="{escape(name,quote=True)}" loading=lazy width=56 height=56>'

ICONS={'/':'⌂','/tables':'▦','/customer-queue':'☷','/qr':'▥','/reservations':'▤','/menu':'↗','/products':'▧','/shifts':'▣','/reports':'▥','/expenses':'▤','/settings':'⚙','/account-security':'♙'}
def navigation(nav,path):
    groups=[('งานหน้าร้าน',['/','/tables','/customer-queue','/qr','/reservations','/menu']),('การเงิน',['/shifts','/reports','/expenses']),('จัดการร้าน',['/products','/settings','/account-security'])]
    groups[0][1].insert(2,'/production');groups[2][1].append('/menu-options')
    available=dict(nav);body=''
    for title,urls in groups:
        shown=[url for url in urls if url in available]
        if not shown:continue
        body+=f'<div class=nav-group><span class=nav-heading>{title}</span>'
        for url in shown:body+=f'<a class="{"active" if path==url else ""}" href={url}><span class=nav-icon aria-hidden=true>{ICONS.get(url,"▤")}</span>{available[url]}</a>'
        body+='</div>'
    return body

def filters(kind):
    extra=''
    if kind=='products':extra='<label>หมวด<select class=filter-category><option value="">ทุกหมวด</option></select></label><label>สต็อก<select class=filter-status><option value="">ทั้งหมด</option><option value=low>ต่ำกว่าหรือเท่าขั้นต่ำ</option><option value=empty>หมดสต็อก</option></select></label>'
    if kind=='tables':extra='<label>สถานะ<select class=filter-status><option value="">ทุกโต๊ะ</option><option value=free>ว่าง</option><option value=busy>กำลังใช้งาน</option><option value=settling>กำลังชำระ</option><option value=cleaning>รอทำความสะอาด</option></select></label>'
    if kind=='reservations':extra='<label>สถานะ<select class=filter-status><option value="">ทั้งหมด</option><option>จองแล้ว</option><option>มาแล้ว</option><option>ยกเลิกแล้ว</option></select></label>'
    return f'<div class=list-filter data-kind={kind}><label>ค้นหา{ {"products":"เมนู","tables":"โต๊ะ / หมายเลขบิล","reservations":"ชื่อ / เบอร์ / โต๊ะ / รหัสจอง"}[kind]}<input type=search class=filter-search placeholder="พิมพ์เพื่อค้นหา"></label>{extra}<button type=button class="secondary filter-clear">ล้างตัวกรอง</button><span class=filter-count role=status aria-live=polite></span></div>'

CSS='''aside{overflow-y:auto}nav{gap:16px;margin-top:22px}.nav-group{display:grid;gap:5px}.nav-heading{font-size:12px;color:#c3b48e;padding:8px 12px;letter-spacing:.5px}.nav-icon{display:inline-block;width:23px;color:#e2c28d;font-size:18px}.list-filter{display:flex;align-items:end;gap:12px;flex-wrap:wrap;margin:18px 0 22px;padding:16px;background:#1e3126;border-radius:12px;border:1px solid #3d5544}.list-filter>label:first-child{flex:1;min-width:200px}.list-filter>label{min-width:140px}.filter-count{width:100%;font-size:13px;color:#c0d1c5}.menu-thumb{width:56px;height:56px;object-fit:cover;border-radius:10px;vertical-align:middle;margin-right:12px;flex-shrink:0}.menu-with-thumb{display:flex;align-items:center;min-width:200px;gap:0}.table-shortcuts{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}.table-shortcuts a{font-size:13px;padding:8px 10px;border:1px solid #5d7158;border-radius:8px}.reservation-warning{font-size:13px;line-height:1.8;background:#483b23;color:#f4d59e;border:1px solid #92784a;border-radius:10px;padding:12px}.reservation-ack{margin:12px 0;font-size:13px!important;line-height:1.7}.reservation-ack input{width:auto}.wait-label{display:inline-block;padding:7px 12px;background:#294533;color:#cbe7d0;border-radius:20px;font-size:14px;margin:12px 0}.wait-label.late{background:#5c4228;color:#ffe0aa}.filter-empty{padding:20px;text-align:center;border:1px dashed #58725c;border-radius:10px;color:#c9d9cc}.draft-reset{margin-bottom:15px}@media(max-width:850px){aside{overflow:visible}nav{gap:18px;align-items:start}.nav-group{display:flex;align-items:center;gap:4px}.nav-heading{white-space:nowrap;padding:8px;font-size:11px}.list-filter>label{flex:1}.table-shortcuts a{flex:1;text-align:center}}@media(prefers-reduced-motion:reduce){*,*:before,*:after{animation:none!important;transition:none!important;scroll-behavior:auto!important}}'''

SCRIPT='''<script>(()=>{document.querySelectorAll('.list-filter').forEach(filter=>{const kind=filter.dataset.kind,container=filter.parentElement,rows=kind==='tables'?[...container.querySelectorAll('.tablecard')]:[...container.querySelectorAll('tbody tr')].filter(r=>r.cells.length>1),search=filter.querySelector('.filter-search'),state=filter.querySelector('.filter-status'),category=filter.querySelector('.filter-category'),count=filter.querySelector('.filter-count');if(category){[...new Set(rows.map(row=>row.cells[1].textContent.trim()))].sort().forEach(name=>{const option=document.createElement('option');option.value=name;option.textContent=name;category.append(option)})}const empty=document.createElement('p');empty.className='filter-empty';empty.hidden=true;empty.textContent='ไม่พบรายการตามตัวกรอง ลองเปลี่ยนคำค้นหาหรือกดล้างตัวกรอง';container.append(empty);function apply(){let shown=0;rows.forEach(row=>{let visible=row.textContent.toLowerCase().includes(search.value.trim().toLowerCase());if(kind==='products'){visible=visible&&(!category.value||row.cells[1].textContent.trim()===category.value);const stock=Number(row.cells[3].textContent),minimum=Number(row.cells[4].textContent);if(state.value==='low')visible=visible&&stock<=minimum;if(state.value==='empty')visible=visible&&stock===0}if(kind==='tables'&&state.value)visible=visible&&row.dataset.state===state.value;if(kind==='reservations'&&state.value)visible=visible&&row.cells[5].textContent.trim()===state.value;row.hidden=!visible;if(visible)shown++});count.textContent='แสดง '+shown+' จาก '+rows.length+' รายการ'+(kind==='products'?' · การบันทึกสต็อกยังรวมแถวที่กรอกไว้แม้ถูกซ่อนด้วยตัวกรอง':'');empty.hidden=shown!==0}filter.addEventListener('input',apply);filter.addEventListener('change',apply);filter.querySelector('.filter-clear').addEventListener('click',()=>{search.value='';state.value='';if(category)category.value='';apply()});apply()});})();</script>'''

CSS += '[hidden]{display:none!important}'
SCRIPT += '''<script>document.addEventListener('submit',event=>{const form=event.target,action=form.getAttribute('action')||'';if(event.defaultPrevented||form.classList.contains('stock-batch')||action.startsWith('/customer/')||action==='/logout'||action==='/login')return;if(form.checkValidity()&&event.submitter)event.submitter.textContent='กำลังบันทึก…'});</script>'''
CSS += '.tables{grid-template-columns:repeat(auto-fill,minmax(230px,1fr))}.tablecard>.badge{align-self:flex-start}@media(max-width:560px){.tables{grid-template-columns:1fr}}'
