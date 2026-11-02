"""Illustrative interactive seating plan and shared reservation availability."""
from datetime import datetime, timedelta
from html import escape
import secrets
import ux

# Percent positions keep the floor plan usable at any screen size.
LAYOUT={
    'T01':(20,26,'หน้าเวที','เห็นเวทีชัด เสียงค่อนข้างดัง'),
    'T02':(42,26,'หน้าเวที','เห็นเวทีชัด เสียงค่อนข้างดัง'),
    'T03':(64,26,'หน้าเวที','เห็นเวทีชัด ใกล้ทางเดินกลาง'),
    'T04':(20,46,'โซนกลาง','เหมาะกับกลุ่มเพื่อน บรรยากาศคึกคัก'),
    'T05':(42,46,'โซนกลาง','ตรงกลางร้าน ใกล้ทางเดิน'),
    'T06':(64,46,'โซนกลาง','เดินไปบาร์สะดวก'),
    'T07':(20,67,'มุมริมร้าน','ห่างจากเวที เหมาะกับนั่งคุย'),
    'T08':(42,67,'มุมริมร้าน','ห่างจากเวที เหมาะกับนั่งคุย'),
    'T09':(64,67,'ใกล้บาร์','โต๊ะกลุ่มใหญ่ ใกล้บาร์'),
    'T10':(20,86,'มุมริมร้าน','โต๊ะกลุ่มใหญ่ ใกล้ทางเข้า'),
    'T11':(42,86,'โซนกลาง','โต๊ะกลุ่มใหญ่ ห่างจากเวที'),
    'T12':(64,86,'ใกล้บาร์','โต๊ะกลุ่มใหญ่ ใกล้ทางเข้าและบาร์'),
}

def validate_time(value, guests):
    try: t=datetime.fromisoformat(value); guests=int(guests)
    except (ValueError,TypeError): raise ValueError('กรุณาเลือกวัน เวลา และจำนวนคนให้ถูกต้อง')
    if t.tzinfo is not None or t<datetime.now()+timedelta(minutes=15) or t>datetime.now()+timedelta(days=90):
        raise ValueError('จองล่วงหน้าอย่างน้อย 15 นาที และไม่เกิน 90 วัน')
    if guests<1 or guests>100: raise ValueError('กรุณาระบุจำนวนคนให้ถูกต้อง')
    return t,guests

def blocking_bookings(db,tid):
    return db.execute("""SELECT r.* FROM reservations r WHERE r.table_id=? AND
      (r.status='booked' OR (r.status='arrived' AND
        (NOT EXISTS(SELECT 1 FROM reservation_orders x WHERE x.reservation_id=r.id)
         OR EXISTS(SELECT 1 FROM reservation_orders x JOIN orders o ON o.id=x.order_id
           JOIN table_assignments a ON a.order_id=o.id WHERE x.reservation_id=r.id
           AND o.status='open' AND a.table_id=r.table_id))))""",(tid,))

def state(db,table,t,guests):
    if guests>table['seats']: return 'capacity','ที่นั่งไม่พอ'
    for r in blocking_bookings(db,table['id']):
        booked=datetime.fromisoformat(r['time'])
        if booked.tzinfo is None and abs((booked-t).total_seconds())<7200: return 'reserved','มีการจองแล้ว'
    if t<datetime.now()+timedelta(hours=2) and db.execute("SELECT 1 FROM table_usage WHERE table_id=? UNION ALL SELECT 1 FROM table_state WHERE table_id=? AND cleaning=1",(table['id'],table['id'])).fetchone():
        return 'occupied','กำลังใช้งาน'
    return 'available','ว่าง จองได้'

def available(db,t,guests):
    return [(r,*state(db,r,t,guests)) for r in db.execute('SELECT * FROM tables ORDER BY seats,name') if r['name'] in LAYOUT]

def render(h,db):
    a=h.api; q=h.query
    raw=q.get('time',[''])[0]; guests=q.get('guests',['2'])[0]
    max_seats=max((r['seats'] for r in db.execute('SELECT * FROM tables') if r['name'] in LAYOUT),default=6)
    start=(datetime.now()+timedelta(minutes=16)).strftime('%Y-%m-%dT%H:%M')
    end=(datetime.now()+timedelta(days=90)).strftime('%Y-%m-%dT%H:%M')
    body='<style>'+CSS+'</style><section class="booking-intro"><div class=eyebrow>YOUR TABLE. YOUR EVENING.</div><h1>เลือกมุมโปรดของคุณ</h1><p>จองทั้งโต๊ะ เลือกบรรยากาศที่ชอบ · สำรองครั้งละ 2 ชั่วโมง</p><span class=badge>แผนผังจำลอง · ตำแหน่งและโซนยังไม่ใช่ผังร้านจริง</span></section>'
    body+=f'<section class=panel><h2>1. เลือกวัน เวลา และจำนวนคน</h2><form method=get action=/booking class=fields>{a.field("วันและเวลาที่จะมา","time",raw,"datetime-local",f"required min={start} max={end}")}{a.field("จำนวนคน","guests",guests,"number",f"required min=1 max={max_seats}")}<button>ดูโต๊ะว่าง →</button></form><p class=muted>เวลาที่เลือกคือเวลาเริ่มจอง ใช้เวลาเครื่องร้าน · มากกว่า {max_seats} คน กรุณาติดต่อพนักงาน</p></section>'
    t=None; error=''
    if raw:
        try: t,guests=validate_time(raw,guests)
        except ValueError as e: error=str(e)
    if error: body+='<div class=notice role=alert>'+escape(error)+'</div>'
    rows=available(db,t,guests) if t else [(r,'unknown','เลือกเวลาก่อน') for r in db.execute('SELECT * FROM tables ORDER BY name') if r['name'] in LAYOUT]
    selected=q.get('table_id',[''])[0]
    eligible={str(r['id']) for r,s,_ in rows if s=='available'}
    if selected not in eligible: selected=''
    controls=''; cards=''
    for r,s,label in rows:
        x,y,zone,desc=LAYOUT[r['name']]; tid=r['id']; checked='checked' if str(tid)==selected else ''; disabled='' if s=='available' else 'disabled'
        table_label=f'{r["name"]} · {r["seats"]} ที่นั่ง · {zone} · {label}'
        controls+=f'<label class="plan-table {s}" style="left:{x}%;top:{y}%"><input type=radio name=table_id value={tid} {checked} {disabled} required aria-label="{escape(table_label,quote=True)}" data-title="{escape(r["name"],quote=True)}" data-description="{escape(zone+" · "+desc,quote=True)}" data-seats={r["seats"]}><span class=table-shape><b>{escape(r["name"])}</b><small>{r["seats"]} ที่นั่ง</small><em>{label}</em></span></label>'
        cards+=f'<label class="seat-option {s}"><input type=radio name=table_id value={tid} {disabled} {checked} required aria-label="แบบรายการ {escape(table_label,quote=True)}" data-title="{escape(r["name"],quote=True)}" data-description="{escape(zone+" · "+desc,quote=True)}" data-seats={r["seats"]}><span><b>{escape(r["name"])} · {r["seats"]} ที่นั่ง</b><small>{escape(zone)} · {label}</small><small>{escape(desc)}</small></span></label>'
    # A single form owns both plan and list radios. JS syncs the visible selection;
    # without JS the native radio group still submits exactly one table.
    plan='<div class=plan-wrap><div class=floor-plan role=group aria-label="แผนผังโต๊ะจำลอง"><div class=plan-stage>เวที / LIVE MUSIC</div><div class=plan-bar>บาร์<br>BAR</div><div class=plan-walkway>ทางเดิน</div><div class=plan-entry>↑ ทางเข้า</div><div class=plan-wc>ห้องน้ำ →</div>'+controls+'</div></div>'
    intro=f'<h2>2. เลือกโต๊ะที่ต้องการ</h2><p>{ux.date(t.isoformat())} – { (t+timedelta(hours=2)):%H:%M} · {guests} คน</p>' if t else '<h2>แผนผังร้านจำลอง</h2><p class=muted>เลือกวัน เวลา และจำนวนคนด้านบนก่อน ระบบจะแสดงโต๊ะที่จองได้</p>'
    legend='<div class=plan-legend><span class=available>● ว่าง</span><span class=reserved>● ถูกจอง / ใช้งาน</span><span class=capacity>● ที่นั่งไม่พอ</span><span class=chosen>● โต๊ะที่เลือก</span></div>'
    content='<section class=panel>'+intro+legend+plan+'<details class=seat-list><summary>เลือกโต๊ะแบบรายการ / ดูรายละเอียดโซน</summary><div class=seat-options>'+cards+'</div></details><div class=seat-selection role=status aria-live=polite>ยังไม่ได้เลือกโต๊ะ</div><p class=muted>โต๊ะจะถูกจองเมื่อยืนยันสำเร็จเท่านั้น หากมีคนจองก่อน ระบบจะแจ้งให้เลือกใหม่</p></section>'
    if t:
        if not eligible: content+='<div class=notice>ไม่มีโต๊ะว่างที่รองรับจำนวนคนในช่วงเวลานี้ กรุณาเลือกเวลาอื่น</div>'
        content+='<section class=panel><h2>3. ยืนยันการจอง</h2><input type=hidden name=request_key value="'+secrets.token_urlsafe(24)+'"><input type=hidden name=time value="'+escape(t.isoformat(timespec='minutes'),quote=True)+'"><input type=hidden name=guests value="'+str(guests)+'">'
        import deposits
        content+=deposits.policy(h,db)+a.field('ชื่อผู้จอง','name',extra='required maxlength=80 autocomplete=name')+a.field('เบอร์โทร','phone','','tel','required maxlength=20 autocomplete=tel')+a.field('หมายเหตุ / ความต้องการเพิ่มเติม','note',extra='maxlength=300')+'<label class=booking-consent><input type=checkbox name=consent value=1 required> ยินยอมให้ร้านเก็บชื่อและเบอร์โทรเพื่อจัดการการจอง</label><button class=booking-submit '+('disabled' if not eligible else '')+'>ยืนยันจองโต๊ะที่เลือก →</button><p class=muted>ตรวจชื่อโต๊ะและเวลาก่อนยืนยัน เก็บรหัสการจองไว้แจ้งพนักงานเมื่อมาถึงร้าน</p></section>'
        body+=h.customer_form('/customer/booking',content).replace('class="fields"','class="booking-layout"',1)
    else: body+=content
    return body+SCRIPT+'<h2 id=my-bookings>การจองของฉัน</h2><p class=muted>เก็บรหัสการจองไว้แจ้งพนักงาน รายการแสดงบนเบราว์เซอร์ที่จอง</p>'

CSS='''
.booking-intro{padding:35px 0 24px}.booking-intro h1{font-size:clamp(30px,5vw,46px);margin:12px 0}.booking-intro p{color:#bcc9bd}.booking-intro .badge{white-space:normal;line-height:1.8}.booking-layout{display:block!important}.booking-layout>section>label{display:block;margin:16px 0}.booking-layout input:not([type=radio]):not([type=checkbox]){width:100%;margin-top:8px}.floor-plan{position:relative;aspect-ratio:1.14;background:linear-gradient(145deg,#182c24,#101c18);border:2px solid #526b54;border-radius:20px;min-width:320px;isolation:isolate;overflow:hidden}.floor-plan:before{content:'';position:absolute;inset:0;background:repeating-linear-gradient(0deg,transparent,transparent 35px,#a0aa8410 36px);z-index:-1}.plan-stage{position:absolute;left:12%;top:3%;width:61%;height:11%;display:grid;place-items:center;background:linear-gradient(130deg,#574a32,#2f3425);border:1px solid #9f8555;border-radius:10px;color:#f2d8a8;font-size:clamp(10px,2vw,15px);letter-spacing:2px}.plan-bar{position:absolute;right:3%;top:22%;width:13%;height:49%;display:grid;align-content:center;text-align:center;background:#4b3d2c;border:1px solid #8d7755;border-radius:10px;color:#e5c799;font-size:clamp(12px,2vw,20px)}.plan-walkway{position:absolute;left:74%;top:22%;height:72%;width:7%;writing-mode:vertical-rl;display:grid;place-items:center;color:#899a8d;font-size:11px;border-left:1px dashed #526658;border-right:1px dashed #526658}.plan-entry{position:absolute;right:3%;bottom:4%;color:#ccd7c8;font-size:clamp(11px,2vw,15px)}.plan-wc{position:absolute;right:3%;top:10%;font-size:clamp(9px,1.7vw,13px);color:#9db6aa}.plan-table{position:absolute;transform:translate(-50%,-50%);width:17%;margin:0!important;cursor:pointer}.plan-table input{position:absolute;inset:0;opacity:0;width:100%;height:100%;cursor:pointer}.table-shape{position:relative;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;aspect-ratio:1.38;border:2px solid #71b28a;border-radius:13px;background:#254a36;color:#dbf1dc;pointer-events:none;box-shadow:0 6px 0 #0a120c88}.table-shape:before,.table-shape:after{content:'';position:absolute;left:25%;right:25%;height:5px;border-radius:5px;background:#668d70}.table-shape:before{top:-8px}.table-shape:after{bottom:-8px}.table-shape b{font-size:clamp(12px,2.5vw,21px)}.table-shape small{font-size:clamp(9px,1.5vw,12px)}.table-shape em{font-size:clamp(8px,1.2vw,10px);font-style:normal}.reserved .table-shape,.occupied .table-shape{background:#503637;border-color:#ac7876;color:#ead1cb}.capacity .table-shape,.unknown .table-shape{background:#29312f;border-color:#616b65;color:#aab2ad}.plan-table input:disabled{cursor:not-allowed}.plan-table input:checked+.table-shape{background:#e8c281;border-color:#ffe4b2;color:#16291e;box-shadow:0 0 0 4px #e8c28144}.plan-table input:focus-visible+.table-shape{outline:3px solid white;outline-offset:5px}.plan-legend{display:flex;gap:16px;flex-wrap:wrap;margin:18px 0;font-size:12px}.plan-legend .available{color:#9bd0a8}.plan-legend .reserved{color:#dd9b97}.plan-legend .capacity{color:#aab2ad}.plan-legend .chosen{color:#edc483}.seat-list{margin-top:22px}.seat-list summary{padding:13px;background:#24382d;border-radius:10px;cursor:pointer}.seat-options{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:14px}.seat-option{display:flex;gap:12px;align-items:center;padding:14px;border:1px solid #425546;border-radius:12px;background:#172b20}.seat-option input{width:20px!important;height:20px;flex-shrink:0;accent-color:#e8c281}.seat-option small{display:block;font-size:12px;line-height:1.7;color:#afc0b0}.seat-option:has(input:checked){border-color:#efcb8f;background:#3c3828}.seat-option:has(input:disabled){opacity:.6}.seat-selection{margin-top:20px;border-left:3px solid #e7bd7c;padding:16px;background:#23372b;line-height:1.8}.booking-consent input{width:auto!important;accent-color:#e8c281}.booking-submit{width:100%;margin-top:18px;min-height:50px}.booking-layout button:disabled{opacity:.5;cursor:not-allowed}@media(max-width:600px){.booking-intro{padding:20px 0}.booking-layout .panel{padding:18px 12px}.floor-plan{min-width:0;aspect-ratio:.83}.table-shape{aspect-ratio:.85;gap:2px;border-radius:9px}.table-shape em{font-size:8px}.seat-options{grid-template-columns:1fr}.plan-walkway{font-size:9px}.plan-legend{gap:8px;font-size:11px}.plan-stage{letter-spacing:0}.seat-selection{font-size:13px}}
'''

SCRIPT='''<script>(()=>{const form=document.querySelector('.booking-layout');if(!form)return;const inputs=[...form.querySelectorAll('[name=table_id]')],summary=form.querySelector('.seat-selection');function show(input){if(!input)return;inputs.forEach(r=>r.closest('label').classList.toggle('selected-table',r.value===input.value));summary.textContent='เลือกโต๊ะ '+input.dataset.title+' · '+input.dataset.seats+' ที่นั่ง — '+input.dataset.description;form.querySelector('.booking-submit').textContent='ยืนยันจองโต๊ะ '+input.dataset.title+' →'}inputs.forEach(r=>r.addEventListener('change',()=>show(r)));show(inputs.find(r=>r.checked));form.addEventListener('submit',e=>{if(form.dataset.sending){e.preventDefault();return}const chosen=inputs.find(r=>r.checked);if(!chosen){e.preventDefault();summary.textContent='กรุณาเลือกโต๊ะจากผังหรือรายการก่อนยืนยัน';summary.scrollIntoView({block:'center',behavior:'smooth'});return}form.dataset.sending='1';const button=form.querySelector('.booking-submit');button.disabled=true;button.textContent='กำลังตรวจโต๊ะและบันทึก…'});})();</script>'''

CSS += '.plan-table.selected-table .table-shape{background:#e8c281;border-color:#ffe4b2;color:#16291e;box-shadow:0 0 0 4px #e8c28144}.seat-option.selected-table{border-color:#efcb8f;background:#3c3828}'
CSS += '.plan-wrap{max-width:800px;margin:auto}.selected-table .table-shape small,.selected-table .table-shape em{color:inherit}.plan-table.available:hover .table-shape{outline:2px solid #ebcb97;outline-offset:4px}'
SCRIPT += '''<script>(()=>{const booking=document.querySelector('.booking-layout'),filter=document.querySelector('form[action="/booking"]');if(!booking||!filter)return;const initial=new FormData(filter),button=booking.querySelector('.booking-submit');let stale=false;filter.addEventListener('input',()=>{const current=new FormData(filter);stale=['time','guests'].some(k=>current.get(k)!==initial.get(k));button.disabled=stale;let warning=document.querySelector('#plan-stale');if(!warning){warning=document.createElement('p');warning.id='plan-stale';warning.className='notice';warning.setAttribute('role','alert');filter.after(warning)}warning.hidden=!stale;warning.textContent='วัน เวลา หรือจำนวนคนเปลี่ยน กรุณากดดูโต๊ะว่างอีกครั้งก่อนจอง'});booking.addEventListener('submit',e=>{if(stale){e.preventDefault();e.stopImmediatePropagation();filter.scrollIntoView({block:'center'})}},true)})();</script>'''
SCRIPT += '''<script>(()=>{const form=document.querySelector('.booking-layout'),filter=document.querySelector('form[action="/booking"]');if(!form||!filter)return;const query=new URLSearchParams(new FormData(filter)),info=document.createElement('p');info.className='muted';info.setAttribute('role','status');filter.after(info);let busy=false;async function refresh(){if(busy||document.hidden||form.dataset.sending)return;busy=true;try{const response=await fetch('/live/booking?'+query,{cache:'no-store'}),data=await response.json();if(!response.ok){info.textContent=data.message;return}let lost=false;for(const row of data.tables){form.querySelectorAll('input[name=table_id]').forEach(input=>{if(input.value!==row.id)return;const wrapper=input.closest('label');for(const state of ['available','reserved','occupied','capacity','unknown'])wrapper.classList.remove(state);wrapper.classList.add(row.state);input.disabled=row.state!=='available';if(input.checked&&input.disabled){input.checked=false;wrapper.classList.remove('selected-table');lost=true}const plan=wrapper.querySelector('.table-shape em'),list=wrapper.querySelector('small');if(plan)plan.textContent=row.label;else if(list)list.textContent=row.zone+' · '+row.label;input.setAttribute('aria-label',input.dataset.title+' · '+input.dataset.seats+' ที่นั่ง · '+row.label)})}if(lost){form.querySelector('.seat-selection').textContent='โต๊ะที่เลือกไม่ว่างแล้ว กรุณาเลือกโต๊ะใหม่';form.querySelector('.booking-submit').textContent='เลือกโต๊ะใหม่เพื่อจอง'}info.textContent='สถานะโต๊ะอัปเดตอัตโนมัติ · '+new Date().toLocaleTimeString('th-TH')}catch{info.textContent='อัปเดตโต๊ะไม่ได้ชั่วคราว กรุณากดดูโต๊ะว่างใหม่ก่อนจอง'}finally{busy=false}}setInterval(refresh,10000);window.addEventListener('focus',refresh);document.addEventListener('visibilitychange',refresh);refresh()})();</script>'''
