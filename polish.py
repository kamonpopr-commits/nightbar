"""Card-based cart, menu workspace tabs, and a live order board."""
import secrets
from urllib.parse import urlencode
import convenience
import ux
import menu_options
import workstations

def menu_tabs(h,db,body):
    if h.s['role']!='manager':return body
    import stock_batch
    photo=body.index('<section class=panel><h2>รูปภาพและคำอธิบาย')
    add=body.index('<section class=panel><h2>เพิ่มเมนูพร้อมรูปภาพ')
    price=body.index('<section class=panel><h2>แก้ไขราคา')
    import workspace
    panels={'list':stock_batch.render(h,db,False),'stock':body[:photo],'add':body[add:price],'edit':workspace.editor(h,db)}
    labels={'list':'รายการเมนู','stock':'ปรับสต็อก','add':'เพิ่มเมนู','edit':'แก้ไขเมนู'}
    draft=h.s.get('form_drafts',{})
    active=h.query.get('view',[''])[0]
    if active not in panels:
        active='stock' if '/stock-batch' in draft else 'add' if '/product' in draft else 'edit' if any(k in draft for k in ['/product-presentation','/product-edit','/product-save']) else 'list'
    explicit=bool(h.query.get('view') or draft)
    result=f'<div class=menu-workspace data-initial={active} data-explicit={int(explicit)}><div class=workspace-tabs role=tablist aria-label="จัดการเมนู">'
    for key,label in labels.items():result+=f'<a id=tab-{key} role=tab aria-controls=panel-{key} aria-selected={str(key==active).lower()} tabindex={0 if key==active else -1} data-view={key} href="/products?{urlencode({"view":key})}">{label}</a>'
    result+='</div><p class=workspace-hint>เลือกงานที่ต้องการ · สลับแท็บได้โดยข้อมูลที่กำลังกรอกยังอยู่</p>'
    for key,html in panels.items():result+=f'<section id=panel-{key} role=tabpanel aria-labelledby=tab-{key} {"hidden" if key!=active else ""}>{html}</section>'
    return result+'</div>'+TABS_SCRIPT

def cart(h,db,visit):
    import json
    a=h.api;items=json.loads(h.c['cart']);subtotal=0;cards=[]
    for pid,qty in items.items():
        p=menu_options.product(db,pid)
        if not p:continue
        subtotal+=p['price']*qty
        image=convenience.thumbnail(p['image'],p['name']) or '<span class=cart-placeholder aria-hidden=true>▧</span>'
        form=h.customer_form('/customer/cart',f'<input type=hidden name=product_id value="{a.esc(pid)}"><input type=hidden name=replace value=1>{ux.quantity(qty,0,20,"จำนวน "+p["name"])}<button class=secondary>บันทึกจำนวน</button><button type=button class="secondary cart-remove">ลบรายการ</button>')
        unavailable='<p class=cart-unavailable>เมนูนี้หยุดขายแล้ว กรุณาลบหรือสอบถามพนักงาน</p>' if not p['active'] else ''
        cards.append(f'<article class=cart-card data-product="{a.esc(pid)}" data-saved={qty}><div class=cart-picture>{image}</div><div class=cart-description><h2>{a.esc(p["name"])}</h2><p>฿<span class=cart-unit-price>{a.money(p["price"])}</span> / รายการ</p>{unavailable}{form}<p class=cart-item-status role=status aria-live=polite></p></div><strong class=cart-line-total>฿{a.money(p["price"]*qty)}</strong></article>')
    body='<h1>ตะกร้าของคุณ</h1><p class=muted>ปรับจำนวนแล้วบันทึกให้อัตโนมัติ · ตรวจรายการแล้วกดยืนยันส่งออเดอร์</p>'
    if not visit:body+='<div class=notice>ยังไม่ได้เชื่อมกับโต๊ะ หรือบิลถูกปิดแล้ว กรุณาสแกน QR ปัจจุบันก่อนสั่ง</div>'
    if not cards:return body+'<section class="panel empty"><h2>เลือกเมนูที่คุณชอบก่อนครับ</h2><p>อาหารและเครื่องดื่มรอคุณอยู่</p><a class=button href=/menu>เลือกเมนู →</a></section>'
    service,tax,total=h.estimate(db,subtotal)
    body+='<div class=cart-layout><section class=cart-items>'+''.join(cards)+'<a class="button secondary" href=/menu>เลือกเมนูเพิ่ม →</a></section>'
    body+=f'<aside class=cart-checkout><section class=panel><h2>ตรวจยอดก่อนสั่ง</h2><p>ราคาเมนู <b>฿<span data-cart-subtotal>{a.money(subtotal)}</span></b></p><p>ค่าบริการ <b>฿<span data-cart-service>{a.money(service)}</span></b></p><p>ภาษี <b>฿<span data-cart-tax>{a.money(tax)}</span></b></p><p class=cart-grand-total>รวมประมาณการ<br><strong>฿<span data-cart-total>{a.money(total)}</span></strong></p><small>ยอดชำระจริงคำนวณรวมทั้งบิลที่ร้าน ตรวจราคาและสต็อกอีกครั้งเมื่อยืนยัน</small></section>'
    if visit:
        locked=__import__('operations').locked(db,visit['id'])
        if locked:body+='<section class=panel><h2>โต๊ะนี้กำลังชำระเงิน</h2><p>กรุณาติดต่อพนักงานก่อนสั่งเพิ่ม สามารถลบรายการในตะกร้าได้</p></section>'
        else:
            key=secrets.token_urlsafe(24)
            body+='<section class=panel id=confirm-order><h2>ยืนยันรายการ</h2>'+h.customer_form('/customer/checkout',f'<input type=hidden name=request_key value="{key}"><input type=hidden name=quote value="{h.quote(db,items)}">'+a.field('หมายเหตุ / ข้อจำกัดอาหาร','note',extra='maxlength=300')+'<label><span><input type=checkbox name=confirmed value=1 required style="width:auto"> ตรวจสอบโต๊ะและรายการแล้ว</span></label><button>ยืนยันส่งออเดอร์ →</button>')+'<p class=cart-save-status role=status aria-live=polite>ตรวจโต๊ะและรายการก่อนยืนยัน</p></section>'
    return body+'</aside></div>'+CART_SCRIPT

def queue(h,db,requests):
    a=h.api;lanes={'received':[],'preparing':[],'ready':[]};history=[]
    titles={'received':'รอรับออเดอร์','preparing':'กำลังจัดเตรียม','ready':'พร้อมเสิร์ฟ'}
    next_states={'received':('preparing','เริ่มจัดเตรียม →'),'preparing':('ready','เตรียมเสร็จแล้ว →'),'ready':('served','เสิร์ฟแล้ว ✓')}
    for r in sorted(requests,key=lambda row:(0 if row['bill_status']=='open' and row['status'] in lanes else 1,row['id'] if row['bill_status']=='open' and row['status'] in lanes else -row['id'])):
        active=r['bill_status']=='open' and r['status'] in lanes
        card=f'<article class="order-card state-{r["status"]}"><header><div><small>ออเดอร์ #{r["id"]:04}</small><h2>โต๊ะ {a.esc(r["name"])}</h2></div><a class="button secondary" href="/order?id={r["order_id"]}">เปิดบิล</a></header>'
        if active:card+=convenience.wait_label(r['created'])
        moved=db.execute("SELECT detail FROM table_events WHERE order_id=? AND action IN ('/table-move','/table-merge','/table-join') ORDER BY id DESC LIMIT 1",(r['order_id'],)).fetchone()
        if moved:card+=f'<p class=order-note>จัดการที่นั่ง: {a.esc(moved[0])}</p>'
        card+='<ul class=order-lines>'+''.join(f'<li><strong>{l["qty"]} ×</strong><span>{a.esc(l["name"])}</span></li>' for l in db.execute('SELECT * FROM customer_lines WHERE request_id=?',(r['id'],)))+'</ul>'
        if r['note']:card+=f'<p class=order-note>หมายเหตุ: {a.esc(r["note"])}</p>'
        card+=f'<small>{ux.date(r["created"])}</small>'
        if active and workstations.allowed(h,'/queue-status',True):
            state,label=next_states[r['status']]
            card+=h.form('/queue-status',f'<input type=hidden name=id value={r["id"]}><input type=hidden name=status value={state}><button>{label}</button>')
            if h.s['role']=='manager':card+='<details class=order-cancel><summary>ยกเลิกออเดอร์</summary><p>ยังไม่เริ่มทำ: คืนสต็อก · เริ่มทำแล้ว: บันทึกของเสีย</p>'+h.form('/queue-status',f'<input type=hidden name=id value={r["id"]}><input type=hidden name=status value=cancelled>'+a.field('เหตุผลยกเลิก','reason',extra='required maxlength=300')+'<button class=danger>ยืนยันยกเลิก</button>')+'</details>'
        else:card+=f'<p class=badge>{"เสิร์ฟแล้ว" if r["status"]=="served" else "ยกเลิกแล้ว"}</p>'
        card+='</article>'
        (lanes[r['status']] if active else history).append(card)
    body='<p class=muted>ออเดอร์ลูกค้าเข้าบิลและตัดสต็อกแล้ว · กดปุ่มขั้นตอนถัดไปเพื่อส่งต่องาน</p><div class=order-board>'
    for status,items in lanes.items():body+=f'<section class="order-lane lane-{status}"><h2>{titles[status]} <span>{len(items)}</span></h2>'+(''.join(items) or '<div class=lane-empty>ไม่มีออเดอร์ในขั้นตอนนี้</div>')+'</section>'
    body+='</div>'
    if history:body+='<details class=order-history><summary>ประวัติเสิร์ฟ / ยกเลิกล่าสุด ('+str(len(history))+')</summary><div class=history-grid>'+''.join(history)+'</div></details>'
    return body

CSS='''
.workspace-tabs{display:flex;gap:8px;flex-wrap:wrap;background:#16271d;padding:8px;border:1px solid #3b5141;border-radius:14px;margin-bottom:12px}.workspace-tabs a{padding:12px 20px;border-radius:10px;color:#c6d4ca;font-size:15px}.workspace-tabs a[aria-selected=true]{background:#e7bd7c;color:#14261a;font-weight:650}.workspace-hint{font-size:14px;color:#b8cabb;margin:15px 0 22px}.customer .cart-layout{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(290px,1fr);gap:24px;align-items:start}.customer aside.cart-checkout{position:sticky;inset:auto;top:18px;width:auto;padding:0;background:none;border:0;overflow:visible}.cart-card{display:grid;grid-template-columns:100px minmax(0,1fr) auto;gap:18px;align-items:start;padding:20px;background:#192b20;border:1px solid #3a5240;border-radius:18px;margin-bottom:16px}.cart-picture img.menu-thumb{width:100px;height:100px;margin:0;border-radius:12px}.cart-placeholder{display:grid;place-items:center;height:100px;background:#2c4030;border-radius:12px;font-size:40px}.cart-description h2{font-size:19px;margin:0 0 7px}.cart-description>p{font-size:14px;color:#c2d2c5;margin:6px 0 12px}.cart-description form.fields{display:flex;flex-wrap:wrap;align-items:center;gap:8px}.cart-description form button{font-size:13px;padding:9px 12px}.cart-line-total{font-size:21px;color:#edcd94;white-space:nowrap}.cart-grand-total{padding-top:18px;border-top:1px solid #3b5141;line-height:1.7}.cart-grand-total strong{font-size:34px;color:#efcf96}.cart-checkout .fields{display:grid!important;grid-template-columns:1fr!important}.cart-checkout small{font-size:13px;line-height:1.8}.cart-checkout p{line-height:1.8}.cart-item-status{font-size:13px!important;color:#ebcb96!important}.cart-unavailable{color:#ffbbb0!important}.order-board{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;align-items:start}.order-lane{border:1px solid #3a5442;border-radius:16px;padding:14px;background:#12251a}.order-lane>h2{display:flex;justify-content:space-between;font-size:18px;margin:5px 0 18px}.order-lane>h2 span{padding:2px 9px;border-radius:20px;background:#334938;color:#ead1a0}.lane-received{border-top:4px solid #d9ae62}.lane-preparing{border-top:4px solid #8d9bcf}.lane-ready{border-top:4px solid #7ab588}.order-card{border:1px solid #405b46;background:#1e3326;padding:18px;border-radius:14px;margin:0 0 14px}.order-card header{margin:0 0 8px;gap:10px;align-items:center}.order-card header h2{font-size:21px;margin:5px 0}.order-card header .button{font-size:12px;padding:8px}.order-card small{font-size:13px}.order-lines{list-style:none;padding:0;margin:16px 0}.order-lines li{display:flex;gap:10px;padding:9px 0;border-bottom:1px solid #3a4d3b;line-height:1.7}.order-lines strong{color:#edcb91;white-space:nowrap}.order-note{padding:12px;background:#433c27;color:#efd9ae;border-radius:9px;font-size:14px;line-height:1.8}.order-card .fields{display:block}.order-card .fields button{width:100%;margin-top:15px}.order-card .order-cancel{margin-top:14px;font-size:12px;color:#cbbbad}.order-cancel summary{cursor:pointer;padding:7px 0}.order-cancel label{margin-top:12px}.lane-empty{color:#adbfaf;padding:25px 10px;text-align:center;border:1px dashed #445a46;border-radius:12px;font-size:14px}.order-history{margin:25px 0}.order-history summary{padding:15px;background:#203527;border-radius:10px;cursor:pointer}.history-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:16px}@media(max-width:1100px){.order-board{grid-template-columns:1fr}.order-lane{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.order-lane>h2,.lane-empty{grid-column:1/-1}.history-grid{grid-template-columns:1fr 1fr}}@media(max-width:760px){.customer .cart-layout{grid-template-columns:1fr}.customer aside.cart-checkout{position:static}.cart-card{grid-template-columns:76px minmax(0,1fr);gap:12px;padding:16px}.cart-picture img.menu-thumb,.cart-placeholder{width:76px;height:76px}.cart-line-total{grid-column:2;font-size:20px}.cart-description h2{font-size:17px}.workspace-tabs{flex-wrap:nowrap;overflow:auto}.workspace-tabs a{white-space:nowrap;padding:11px 14px}.order-lane{display:block}.history-grid{grid-template-columns:1fr}}@media(prefers-reduced-motion:no-preference){.cart-card,.order-card{animation:card-appear .15s ease-out}@keyframes card-appear{from{opacity:.7;transform:translateY(4px)}to{opacity:1;transform:none}}}
'''

TABS_SCRIPT='''<script>(()=>{const root=document.querySelector('.menu-workspace');if(!root)return;const tabs=[...root.querySelectorAll('[role=tab]')];function choose(key,focus=false){if(!tabs.some(t=>t.dataset.view===key))return;tabs.forEach(tab=>{const selected=tab.dataset.view===key;tab.setAttribute('aria-selected',String(selected));tab.tabIndex=selected?0:-1;document.querySelector('#'+tab.getAttribute('aria-controls')).hidden=!selected;if(selected&&focus)tab.focus()});try{sessionStorage.setItem('jupiter-menu-view',key)}catch(e){}const url=new URL(location.href);url.searchParams.set('view',key);history.replaceState(null,'',url)}tabs.forEach((tab,i)=>{tab.addEventListener('click',e=>{e.preventDefault();choose(tab.dataset.view)});tab.addEventListener('keydown',e=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){e.preventDefault();const index=e.key==='Home'?0:e.key==='End'?tabs.length-1:(i+(e.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;choose(tabs[index].dataset.view,true)}})});let initial=root.dataset.initial;if(root.dataset.explicit!=='1'){try{initial=sessionStorage.getItem('jupiter-menu-view')||initial}catch(e){}}choose(initial)})();</script>'''

CART_SCRIPT='''<script>(()=>{const layout=document.querySelector('.cart-layout');if(!layout)return;let pending=0,chain=Promise.resolve();const timers=new Map(),checkout=document.querySelector('form[action="/customer/checkout"]'),summary=document.querySelector('.cart-save-status');function state(){layout.querySelectorAll('.cart-description form button:not([type=button])').forEach(b=>{b.style.display=b.closest('.cart-card').dataset.error==='1'?'':'none';b.textContent='ลองบันทึกอีกครั้ง'});const error=[...layout.querySelectorAll('.cart-card')].some(card=>card.dataset.error==='1'||!card.querySelector('[name=qty]').checkValidity()||Number(card.querySelector('[name=qty]').value)!==Number(card.dataset.saved));if(checkout)checkout.querySelector('button').disabled=pending>0||timers.size>0||error;if(summary)summary.textContent=pending||timers.size?'กำลังบันทึกจำนวน กรุณารอก่อนยืนยัน':error?'แก้จำนวนที่ผิด แล้วบันทึกก่อนยืนยัน':'จำนวนบันทึกแล้ว ตรวจโต๊ะและรายการก่อนยืนยัน'}function schedule(form){const card=form.closest('.cart-card'),input=form.querySelector('[name=qty]');if(!input.checkValidity()){card.dataset.error='1';card.querySelector('.cart-item-status').textContent='กรุณากรอกจำนวนเต็มในช่วง 0–20';state();return}clearTimeout(timers.get(form));const timer=setTimeout(()=>{timers.delete(form);save(form)},350);timers.set(form,timer);card.querySelector('.cart-item-status').textContent='กำลังบันทึกจำนวน…';state()}function save(form){clearTimeout(timers.get(form));timers.delete(form);const card=form.closest('.cart-card');if(!card?.isConnected){state();return}if(!form.reportValidity()){card.dataset.error='1';state();return}const body=new URLSearchParams(new FormData(form));pending++;state();chain=chain.then(async()=>{try{const response=await fetch('/customer/cart',{method:'POST',headers:{'Accept':'application/json','Content-Type':'application/x-www-form-urlencoded'},body});const data=await response.json();if(!response.ok)throw Error(data.message||'บันทึกไม่ได้');card.dataset.error='0';Object.entries(data.cart).forEach(([pid,item])=>{const row=layout.querySelector('[data-product="'+pid+'"]');if(row){row.dataset.saved=item.qty;row.querySelector('.cart-unit-price').textContent=item.price;row.querySelector('.cart-line-total').textContent='฿'+item.total}});if(!Object.hasOwn(data.cart,card.dataset.product))card.remove();else card.querySelector('.cart-item-status').textContent='บันทึกจำนวนแล้ว';for(const key of ['count','subtotal','service','tax','total'])document.querySelectorAll('[data-cart-'+key+']').forEach(el=>el.textContent=data[key]);if(checkout)checkout.querySelector('[name=quote]').value=data.quote;if(!Object.keys(data.cart).length)location.reload()}catch(error){card.dataset.error='1';card.querySelector('.cart-item-status').textContent=error.message||'เชื่อมต่อไม่ได้ ตรวจตะกร้าก่อนลองใหม่'}finally{pending--;state()}})}layout.addEventListener('input',e=>{if(e.target.name==='qty')schedule(e.target.closest('form'))});layout.addEventListener('submit',e=>{const form=e.target;if(form.getAttribute('action')==='/customer/cart'){e.preventDefault();save(form)}});layout.addEventListener('click',e=>{const remove=e.target.closest('.cart-remove');if(remove){const form=remove.closest('form');form.querySelector('[name=qty]').value=0;save(form)}});state();checkout?.addEventListener('submit',e=>{if(pending||timers.size||[...layout.querySelectorAll('.cart-card')].some(c=>c.dataset.error==='1'||!c.querySelector('[name=qty]').checkValidity()||Number(c.querySelector('[name=qty]').value)!==Number(c.dataset.saved))){e.preventDefault();state()}})})();</script>'''
