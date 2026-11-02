"""Clear next actions and readable presentation for customers and staff."""
from html import escape
import ux
import json
from urllib.parse import urlencode

def booking_live(key):
    endpoint=json.dumps('/live/booking-confirmation?'+urlencode({'confirmed':key})).replace('<','\\u003c')
    return '<script>(()=>{let busy=false;async function refresh(){if(busy||document.hidden)return;busy=true;try{const r=await fetch('+endpoint+''',{cache:'no-store'});if(r.ok){const data=await r.json();document.querySelector('#booking-confirmation').innerHTML=data.html;if(data.id){const card=document.querySelector('#booking-'+data.id),label=card?.querySelector('[data-booking-state]');if(label)label.textContent=data.label;const form=card?.querySelector('form[action="/customer/deposit-reference"]'),qr=card?.querySelector('.bank-qr-card');if(form)form.hidden=!['pending','review'].includes(data.deposit_state);if(qr)qr.hidden=data.deposit_state!=='pending'}}}catch{}finally{busy=false}}setInterval(refresh,10000);document.addEventListener('visibilitychange',refresh)})();</script>'''

CSS='''
.muted,small,th{color:#bec9c1}.customer .menu-description{font-size:15px;color:#c4d0c6;line-height:1.8}.customer .menu-note,.customer footer{font-size:14px;line-height:1.9;color:#becbc2}.customer .menu-info>small{font-size:13px}.customer .menu-bottom>.muted{font-size:13px;max-width:none}.customer .subtle{font-size:15px;line-height:1.8}.customer .badge{font-size:13px}.customer label,main label{font-size:15px;color:#c8d3cd}.customer .bottom-bar small{font-size:12px;color:#d1dcd3}.customer .eyebrow{font-size:12px;color:#e8cb9a}.tablecard .table-meta{font-size:14px}.quick-order{margin:12px 0 20px;padding:20px;background:#20392c;border:1px solid #526b50;border-radius:16px}.quick-order h1{font-size:25px;margin:5px 0 10px}.quick-order p{margin:6px 0;color:#cad6cc;line-height:1.7}.quick-order .button{margin-top:10px}.success-card{border:1px solid #79ac82!important;background:linear-gradient(130deg,#233d2c,#17281e)!important;margin:22px 0;padding:26px;border-radius:18px}.success-card h1{font-size:29px;margin:10px 0}.success-card .confirmation-code{font-size:30px;letter-spacing:3px;color:#f0d097;font-weight:650}.success-card p{font-size:16px;line-height:1.8;color:#d5e3d8}.next-actions{display:flex;gap:12px;flex-wrap:wrap;margin-top:18px}.work-priority{border:1px solid #6b6845;padding:22px;border-radius:16px;margin-bottom:24px;background:#1d3025}.work-priority h2{margin-top:0}.work-actions{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.work-action{padding:18px;border:1px solid #4c604c;border-radius:12px;background:#263c2c;display:flex;flex-direction:column;gap:9px}.work-action strong{font-size:27px;color:#f0cf96}.work-action span{font-size:16px}.work-action small{font-size:14px;line-height:1.7}.cash-guide{background:#203329;padding:18px;border:1px solid #4a6049;border-radius:12px;margin:18px 0;line-height:1.9}.cash-guide summary{cursor:pointer;font-weight:650;color:#f0d19d}.cash-guide p{margin:10px 0;color:#d1dfd4}.cash-equation{padding:14px;border-radius:10px;background:#12251a;font-size:16px;color:#ebd9b5;line-height:1.9}.booking-intro p,.plan-legend,.seat-option small{font-size:14px!important}.seat-selection{font-size:15px!important}@media(max-width:760px){.work-actions{grid-template-columns:1fr}.success-card{padding:20px}.success-card h1{font-size:25px}.customer .menu-description{font-size:14px}.customer .quick-order h1{font-size:23px}.customer .customer-nav a{font-size:13px}.customer footer{font-size:13px}}@media print{.work-priority,.cash-guide{display:none}}
'''

def priorities(h,db):
    waiting=db.execute("SELECT COUNT(*) FROM customer_requests r JOIN orders o ON o.id=r.order_id WHERE o.status='open' AND r.status IN ('received','preparing','ready')").fetchone()[0]
    staff=db.execute("SELECT COUNT(*) FROM service_requests s JOIN orders o ON o.id=s.order_id WHERE o.status='open' AND s.status='waiting' AND s.kind='staff'").fetchone()[0]
    bills=db.execute("SELECT COUNT(*) FROM service_requests s JOIN orders o ON o.id=s.order_id WHERE o.status='open' AND s.status IN ('waiting','handling') AND s.kind='bill'").fetchone()[0]
    entries=[(waiting,'ออเดอร์รอจัดเตรียม / เสิร์ฟ','/production','เปิดคิวเพื่อรับงานและอัปเดตสถานะ'),(staff,'ลูกค้าเรียกพนักงาน','/production?view=services','เปิดคิวเพื่อดูโต๊ะที่ต้องการความช่วยเหลือ'),(bills,'โต๊ะขอเช็กบิล','/production?view=services','ดูคำขอ แล้วเปิดบิลโต๊ะนั้นเพื่อชำระ')]
    body='<section class=work-priority><h2>งานที่ต้องดูแลตอนนี้</h2><p class=muted>จำนวนคำขอที่ยังค้าง · เปิดคิวเพื่อดูรายการล่าสุดและเปิดเสียงแจ้งเตือน</p><div class=work-actions>'
    for count,label,url,help_text in entries:
        body+=f'<a class=work-action href={url}><strong>{count}</strong><span>{label}</span><small>{help_text} →</small></a>'
    body+='</div><div class=next-actions><a class="button secondary" href=/tables>เปิดโต๊ะ / ดูบิล</a><a class="button secondary" href=/reservations>ตรวจการจอง</a><a class="button secondary" href=/shifts>เปิดกะ / ตรวจเงินสด</a></div></section>'
    return body

def cash_help(a,s=None,summary=None):
    body='<details class=cash-guide '+('open' if s is None else '')+'><summary>เงินสดในกะนี้คิดอย่างไร? ดูคำอธิบายและตัวอย่าง</summary><p><b>เงินตั้งต้น</b> คือเงินทอนที่มีในลิ้นชักก่อนเริ่มกะ ไม่ใช่ยอดขาย เช่น นับได้ 1,000 บาท ให้กรอก 1,000</p><div class=cash-equation>เงินสดที่ควรมี = เงินตั้งต้น + รับชำระเงินสดสุทธิ − รายจ่ายเงินสด + เงินเติม − เงินนำออก</div><p><b>ตัวอย่างสมมุติ:</b> เริ่ม 1,000 + รับเงินสดสุทธิ 500 − รายจ่าย 100 + เติมเงิน 200 − นำออก 300 = ควรมี 1,300 บาท</p><p>ลูกค้าจ่าย 500 บาทสำหรับบิล 450 และทอน 50 จะนับเงินสดสุทธิ 450 บาท ส่วนเงินโอนและบัตรไม่เพิ่มเงินสดในลิ้นชัก</p>'
    if s is not None:
        body+=f'<div class=cash-equation>กะนี้: ฿{a.money(s["opening"])} + ฿{a.money(summary["cash"])} − ฿{a.money(summary["expenses"])} + เงินเข้า/ออกสุทธิ ฿{a.money(summary["adjustments"])} = ฿{a.money(summary["expected"])}</div>'
    return body+'<p><b>ตอนปิดกะ:</b> นับเงินสดที่อยู่จริงทั้งหมด แล้วกรอกเงินที่นับได้ หากต่างจากยอดที่ควรมี ให้ตรวจรายการและระบุเหตุผลก่อนยืนยัน</p></details>'

def order_confirmation(h,db,key):
    r=db.execute('SELECT r.*,t.name FROM customer_requests r JOIN orders o ON o.id=r.order_id JOIN order_labels t ON t.id=o.id WHERE r.request_key=? AND r.session_token=?',(key,h.c['token'])).fetchone()
    if not r:return ''
    state={'received':'ส่งออเดอร์สำเร็จ','preparing':'ร้านกำลังจัดเตรียม','ready':'อาหารพร้อมเสิร์ฟแล้ว','served':'ออเดอร์นี้เสิร์ฟแล้ว','cancelled':'ออเดอร์นี้ถูกยกเลิกแล้ว'}[r['status']]
    next_step={'received':'ร้านได้รับรายการแล้ว กรุณารอครัวหรือบาร์เริ่มจัดเตรียม ไม่ต้องส่งรายการเดิมซ้ำ','preparing':'ร้านกำลังทำรายการของคุณ กรุณารอพนักงานนำมาเสิร์ฟ','ready':'รายการพร้อมแล้ว พนักงานจะนำมาเสิร์ฟที่โต๊ะ กรุณารอสักครู่','served':'รายการนี้เสิร์ฟแล้ว หากต้องการความช่วยเหลือหรือเช็กบิล ใช้ส่วนเรียกพนักงานด้านล่าง','cancelled':'รายการนี้ถูกยกเลิกแล้ว หากมีข้อสงสัยกรุณาเรียกพนักงานก่อนสั่งใหม่'}[r['status']]
    lines=db.execute('SELECT name,qty,price FROM customer_lines WHERE request_id=?',(r['id'],)).fetchall()
    summary='<ul class=confirmation-lines>'+''.join(f'<li>{escape(i["name"])} × {i["qty"]} — {i["qty"]*i["price"]/100:,.2f} บาท</li>' for i in lines)+'</ul>'
    return f'<section class="success-card" role=status><div class=eyebrow>สถานะออเดอร์</div><h1>{state}</h1><div class=confirmation-code>#{r["id"]:04}</div><p>โต๊ะ <b>{escape(r["name"])}</b> · {ux.date(r["created"])}</p>{summary}<p>รวมรายการนี้ก่อนค่าบริการและภาษี {sum(i["qty"]*i["price"] for i in lines)/100:,.2f} บาท</p><div class=next-step-box><strong>ทำต่ออย่างไร</strong><p>{next_step}</p></div><div class=next-actions><a class=button href="#request-{r["id"]}">ดูสถานะรายการนี้ →</a><a class="button secondary" href=/menu>กลับไปเลือกเมนู</a></div></section>'

def booking_confirmation(h,db,key):
    r=db.execute('SELECT r.*,c.code,t.name table_name FROM booking_submissions s JOIN reservations r ON r.id=s.reservation_id JOIN customer_bookings c ON c.reservation_id=r.id JOIN tables t ON t.id=r.table_id WHERE s.request_key=? AND s.session_token=?',(key,h.c['token'])).fetchone()
    if not r:return ''
    state={'booked':'จองโต๊ะสำเร็จ','arrived':'ร้านรับเข้าที่นั่งแล้ว','cancelled':'การจองนี้ถูกยกเลิกแล้ว'}.get(r['status'],'สถานะการจอง')
    dep=db.execute('SELECT state FROM booking_deposits WHERE reservation_id=?',(r['id'],)).fetchone()
    if dep and dep[0] in ['pending','review']:state='รับคำขอแล้ว · รอยืนยันมัดจำ'
    next_step='จองยืนยันแล้ว เก็บรหัสนี้และแจ้งพนักงานเมื่อมาถึงร้าน ไม่ต้องจองซ้ำ'
    action='<a class=button href=#my-bookings>ดูรายละเอียดการจอง →</a>'
    if r['status']=='arrived':next_step='ร้านรับเข้าที่นั่งแล้ว ขอ QR สั่งอาหารสำหรับบิลนี้จากพนักงานได้เลย'
    elif r['status']=='cancelled':next_step='การจองนี้ยกเลิกหรือหมดเวลาแล้ว อย่าโอนมัดจำเพิ่ม หากโอนไปแล้วกรุณาติดต่อร้าน'
    elif dep and dep[0]=='pending':
        state='รับคำขอแล้ว · ยังไม่ยืนยันการจอง';next_step='ชำระมัดจำและแนบสลิปภายในเวลาที่แจ้งด้านล่าง จากนั้นรอร้านตรวจยอดเงินจริง';action='<a class=button href="#booking-'+str(r['id'])+'">ชำระมัดจำ / แนบสลิป →</a>'
    elif dep and dep[0]=='review':
        state='ส่งหลักฐานแล้ว · รอร้านตรวจยอด';next_step='ยังไม่ยืนยันการจองจนกว่าร้านตรวจเงินเข้า กรุณารอหรือติดต่อร้าน ไม่ต้องโอนหรือจองซ้ำ'
    return f'<section class="success-card" role=status><div class=eyebrow>รหัสการจองของคุณ</div><h1>{state}</h1><div class=confirmation-code>{escape(r["code"])}</div><p>โต๊ะ <b>{escape(r["table_name"])}</b> · {r["guests"]} คน<br>{ux.date(r["time"])} · สำรอง 2 ชั่วโมง<br>เก็บภาพหน้าจอหรือจดรหัสนี้ไว้แจ้งพนักงานเมื่อมาถึงร้าน</p><div class=next-step-box><strong>ทำต่ออย่างไร</strong><p>{next_step}</p></div><div class=next-actions>{action}<a class="button secondary" href=/menu>ดูเมนูก่อนมา →</a></div></section>'
CSS += '.customer form[action="/menu"]{display:flex;align-items:flex-end;gap:10px}.customer form[action="/menu"]>label{flex:1;min-width:0}.customer form[action="/menu"]>button{width:auto;min-height:44px;flex-shrink:0}.quick-order{padding:14px 18px}.quick-order h1{margin:4px 0;font-size:24px}.quick-order p{font-size:14px;margin:5px 0}.quick-order .button{font-size:13px;padding:9px 12px;margin-top:5px}@media(max-width:600px){.quick-order{padding:12px 14px}.quick-order h1{font-size:22px}.customer header{margin-bottom:18px}.customer .section-title{margin-top:20px}}'
