"""Accessible compact menu and high-contrast receipts."""
CSS='''
.menu-configure{display:none}
.menu-view-tools{display:flex;gap:8px;align-items:center;margin:16px 0}.menu-view-tools button{min-height:44px;background:transparent;color:var(--gold);border:1px solid var(--gold)}.menu-view-tools [aria-pressed=true]{background:var(--gold);color:#13241b}.menu-view-tools button:focus-visible{outline:3px solid var(--gold);outline-offset:3px}
@media(min-width:761px){
.customer.compact-enabled:not(.menu-photo) .menu-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
.customer.compact-enabled:not(.menu-photo) .menu-item{display:grid;grid-template-columns:130px minmax(0,1fr);align-items:start}
.customer.compact-enabled:not(.menu-photo) .menu-art{height:130px!important;aspect-ratio:auto!important;margin:16px 0 16px 12px;border-radius:10px;overflow:hidden}
.customer.compact-enabled:not(.menu-photo) .menu-art img,.customer.compact-enabled:not(.menu-photo) .menu-art svg{height:100%!important;width:100%!important;object-fit:cover}
.customer.compact-enabled:not(.menu-photo) .detail-hint,.customer.compact-enabled:not(.menu-photo) .dish-featured{display:none}
.customer.compact-enabled:not(.menu-photo) .menu-info{padding:16px!important;min-width:0}
.customer.compact-enabled:not(.menu-photo) .menu-info h3{margin-top:0}
.customer.compact-enabled:not(.menu-photo) .menu-description{display:none}
.customer.compact-enabled:not(.menu-photo) .menu-bottom{flex-wrap:wrap;margin-top:8px}
}
@media(max-width:760px){
.customer.compact-enabled .menu-bottom .modifier-fields{display:none}
.customer .menu-grid{grid-template-columns:1fr!important;gap:12px}
.customer .menu-item{display:grid;grid-template-columns:94px minmax(0,1fr);align-items:start}
.customer .menu-art{height:100px!important;aspect-ratio:auto!important;margin:12px 0 0 10px;border-radius:10px;overflow:hidden}
.customer .menu-art img,.customer .menu-art svg{height:100%!important;width:100%!important;object-fit:cover}
.customer .menu-art .dish-featured,.customer .detail-hint{display:none}
.customer .menu-info{padding:12px!important;min-width:0}.customer .menu-info h3{font-size:19px!important;line-height:1.5;margin:2px 0 6px}
.customer .menu-info>small,.customer .menu-description,.customer .menu-info>.badge{display:none}
.customer .menu-bottom{margin-top:6px;gap:8px}.customer .menu-bottom .price{font-size:20px}
.customer .menu-bottom form.fields{margin:0}.customer.compact-enabled .menu-bottom form.fields>label{display:none}
.customer.compact-enabled .menu-bottom .quantity{display:none}.customer .menu-bottom form.fields>button{min-height:44px}
.customer.compact-enabled .menu-bottom form:has(select)>button{display:none}
.menu-configure{display:block;min-height:44px;width:100%;margin-top:8px}
.customer .menu-options-help{font-size:14px;line-height:1.6}
.customer.menu-photo .menu-item{display:block}.customer.menu-photo .menu-art{height:180px!important;margin:0;border-radius:0}
.customer .filters{top:0;border-radius:8px}.customer .chip{font-size:16px;min-height:44px}
.customer .bottom-bar small{font-size:14px}.customer .bottom-bar{bottom:8px}
}
.receipt-sheet{background:#fff!important;color:#161616!important;max-width:760px;margin:20px auto;padding:28px;border-radius:12px;font-size:20px;line-height:1.65}
.receipt-sheet h1{font-size:28px;color:#111}.receipt-sheet p{color:#222!important}.receipt-sheet .receipt-line{padding:14px 0;border-bottom:1px solid #bbb;display:flex;justify-content:space-between;gap:16px;overflow-wrap:anywhere}
.receipt-line>span:first-child{min-width:0}.receipt-line b{white-space:nowrap}.receipt-meta{font-size:18px}.receipt-sheet dl{margin:20px 0}.receipt-sheet dl div{display:flex;justify-content:space-between;gap:12px;padding:5px 0}.receipt-sheet dd{margin:0;white-space:nowrap}.receipt-sheet .receipt-total{font-size:32px;font-weight:800;border-top:2px solid #111;margin-top:12px}.receipt-sheet.receipt-large{font-size:24px}.receipt-sheet.receipt-large .receipt-meta{font-size:22px}.receipt-sheet button{min-height:48px}
@media(max-width:600px){.receipt-sheet{padding:18px 14px;margin:10px 0}.receipt-sheet .receipt-total{font-size:28px}}
@media print{@page{margin:12mm}body:has(.receipt-sheet){background:white!important;color:black!important;color-scheme:light}body:has(.receipt-sheet) aside,body:has(.receipt-sheet) main>:not(.receipt-sheet):not(style){display:none!important}body:has(.receipt-sheet) main{margin:0!important;padding:0!important;max-width:none!important}.receipt-sheet{font-size:16pt!important;line-height:1.6!important;padding:0!important;margin:0!important;max-width:none;border:0!important;box-shadow:none;border-radius:0}.receipt-sheet *{color:#000!important;text-shadow:none!important}.receipt-sheet h1{font-size:22pt!important}.receipt-sheet .receipt-total{font-size:26pt!important}.receipt-sheet .receipt-meta{font-size:14pt!important}.receipt-sheet.receipt-large{font-size:20pt!important}.receipt-sheet.receipt-large .receipt-meta{font-size:17pt!important}.receipt-line{break-inside:avoid;border-color:#555!important}.receipt-sheet dl div{break-inside:avoid}.receipt-sheet button,.receipt-sheet .noprint{display:none!important}}
'''
SCRIPT='''<script>(()=>{const root=document.querySelector('.customer'),grid=document.querySelector('.menu-grid');if(!root||!grid)return;root.classList.add('compact-enabled');const tools=document.createElement('div');tools.className='menu-view-tools';tools.innerHTML='<span>รูปแบบเมนู</span><button type="button" data-layout="list">รายการ</button><button type="button" data-layout="photo">รูปภาพ</button>';grid.before(tools);function set(v){root.classList.toggle('menu-photo',v==='photo');tools.querySelectorAll('button').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.layout===v)));try{localStorage.setItem('jupiter-menu-layout',v)}catch{}}let saved='list';try{saved=localStorage.getItem('jupiter-menu-layout')||saved}catch{}set(saved);tools.addEventListener('click',e=>{if(e.target.dataset.layout)set(e.target.dataset.layout)});grid.querySelectorAll('.menu-item').forEach(card=>{if(!card.querySelector('form select'))return;const button=document.createElement('button');button.type='button';button.className='menu-configure secondary';button.textContent='เลือกตัวเลือก / เพิ่ม';button.addEventListener('click',()=>card.querySelector('.detail-open').click());card.querySelector('.menu-bottom').append(button)});})();</script>'''

def receipt(h,db,o):
    a=h.api;s=dict(db.execute('SELECT key,value FROM settings'))
    items=db.execute('SELECT * FROM items WHERE order_id=?',(o['id'],)).fetchall()
    settled=o['status']=='paid'
    if not settled:
        from decimal import Decimal,ROUND_HALF_UP
        o=dict(o);subtotal=sum(i['price']*i['qty'] for i in items)
        o['discount']=0;o['service']=int((Decimal(subtotal)*Decimal(s['service'])/100).quantize(Decimal('1'),rounding=ROUND_HALF_UP));o['tax']=int((Decimal(subtotal+o['service'])*Decimal(s['tax'])/100).quantize(Decimal('1'),rounding=ROUND_HALF_UP));o['total']=subtotal+o['service']+o['tax']
        frozen=db.execute('SELECT * FROM checkout_totals WHERE order_id=?',(o['id'],)).fetchone()
        if frozen:
            for key in ['discount','service','tax','total']:o[key]=frozen[key]
    out='<section class=receipt-sheet id=readable-receipt><div class="noprint receipt-tools"><label>กระดาษ<select id=receipt-paper><option value=a4>A4</option><option value=thermal>ใบเสร็จ 80 มม.</option></select></label><button type=button onclick="document.getElementById(\'readable-receipt\').classList.toggle(\'receipt-large\');this.setAttribute(\'aria-pressed\',String(document.getElementById(\'readable-receipt\').classList.contains(\'receipt-large\')))" aria-pressed=false>ขยายตัวอักษร</button> <button type=button onclick="window.print()">พิมพ์ใบเสร็จ</button><p>เลือกขนาดกระดาษในหน้าต่างพิมพ์ให้ตรงกัน · สเกล 100% · ปิดหัวและท้ายกระดาษ</p></div>'
    out+=f'<h1>{a.esc(s["shop"])} · {"ใบเสร็จรับเงิน" if settled else "ใบแจ้งรายการ · ยังไม่ชำระครบ"}</h1><p class=receipt-meta>โต๊ะ {a.esc(o["name"])} · บิล #{o["id"]:06}<br>{a.esc(s["address"])}<br>{a.esc(a.ux.date(o["closed"] or o["opened"]))}</p>'
    groups={}
    for i in items:
        note=db.execute('SELECT r.note FROM customer_lines l JOIN customer_requests r ON r.id=l.request_id WHERE l.item_id=?',(i['id'],)).fetchone()
        note=note[0] if note else ''
        key=(i['product_id'],i['name'],i['price'],note)
        if key not in groups:groups[key]=dict(i,qty=0,note=note)
        groups[key]['qty']+=i['qty']
    for i in groups.values():
        out+=f'<div class=receipt-line><span>{a.esc(i["name"])}<br><span class=receipt-meta>จำนวน {i["qty"]} × {a.money(i["price"])} บาท</span>'
        if i['note']:out+='<br><span class=receipt-meta>หมายเหตุ: '+a.esc(i['note'])+'</span>'
        out+=f'</span><b>{a.money(i["price"]*i["qty"])} บาท</b></div>'
    dep=db.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE order_id=? AND method='มัดจำ'",(o['id'],)).fetchone()[0]
    out+='<dl>'
    rates=db.execute('SELECT * FROM receipt_rates WHERE order_id=?',(o['id'],)).fetchone()
    if not settled and not frozen:rates=s
    service_label='ค่าบริการ'+(' '+a.esc(rates['service'])+'%' if rates else '')
    tax_label='ภาษี'+(' '+a.esc(rates['tax'])+'%' if rates else '')
    for label,val in [('รวมรายการ',sum(i['qty']*i['price'] for i in items)),('ส่วนลด',o['discount']),(service_label,o['service']),(tax_label,o['tax']),('ยอดรวม',o['total']),('หักมัดจำที่ชำระไว้',dep)]:out+=f'<div><dt>{label}</dt><dd>{a.money(val)} บาท</dd></div>'
    paid=db.execute('SELECT COALESCE(SUM(amount),0) FROM payments WHERE order_id=?',(o['id'],)).fetchone()[0]
    due=o['total']-dep if settled else max(0,o['total']-paid)
    out+=f'<div class=receipt-total><dt>{"ยอดชำระสุทธิ" if settled else "ยอดค้างชำระ"}</dt><dd>{a.money(due)} บาท</dd></div></dl>'
    if settled:
        out+='<h2>ชำระครบแล้ว</h2>'
        channels=db.execute('SELECT method,SUM(amount) amount,SUM(tendered) tendered,SUM(change) change FROM payments WHERE order_id=? GROUP BY method ORDER BY method',(o['id'],)).fetchall()
        if len(channels)>1:out+='<p>ชำระหลายช่องทาง</p>'
        for channel in channels:
            out+=f'<div class=receipt-payment><strong>{a.esc(channel["method"])} · {a.money(channel["amount"])} บาท</strong>'
            if channel['method']=='เงินสด':out+=f'<p>รับเงินสด {a.money(channel["tendered"])} บาท<br><strong>เงินทอน {a.money(channel["change"])} บาท</strong></p>'
            out+='</div>'
        if not channels:out+=f'<p>ช่องทาง: {a.esc(o["method"])}</p>'
        out+='<p class=receipt-meta>ขอบคุณที่ใช้บริการ · ใบรับเงินทั่วไป</p>'
    else:out+=f'<p>รับชำระแล้ว {a.money(paid)} บาท</p><p>ยอดประมาณการก่อนยืนยันชำระ อาจเปลี่ยนเมื่อมีการสั่งเพิ่มหรือปรับรายการ · มัดจำที่ยังไม่หักบิลไม่รวมในยอดรับชำระนี้</p><a class=noprint href="/order?id={o["id"]}">กลับไปจัดการบิล</a> '
    out+='<a class=noprint href=/tables>กลับหน้าโต๊ะ</a></section>'
    if settled:
        import streamline
        out+=streamline.cleanup(h,db,o)
    return '<style>'+CSS+PAPER_CSS+'</style>'+out+PAPER_SCRIPT

PAPER_CSS='''
.receipt-tools{display:flex;align-items:end;flex-wrap:wrap;gap:10px}.receipt-tools label{color:#222;font-size:16px}.receipt-tools select{color:#111;background:white;border-color:#555}.receipt-tools p{flex-basis:100%;font-size:14px}.receipt-payment{border-bottom:1px solid #aaa;padding:10px 0}.receipt-payment p{margin:5px 0}.receipt-sheet.receipt-thermal{width:80mm;max-width:100%;padding:5mm;font-size:17px}.receipt-thermal h1{font-size:22px}.receipt-thermal .receipt-meta{font-size:16px}.receipt-thermal .receipt-total{font-size:23px}.receipt-thermal dl div,.receipt-thermal .receipt-total{flex-wrap:wrap}.receipt-thermal dd{margin-left:auto}.receipt-thermal .receipt-line{gap:8px}.receipt-thermal .receipt-line b{white-space:normal;text-align:right}.receipt-thermal .receipt-tools{padding-bottom:12px}.receipt-thermal .receipt-tools button{font-size:14px}
@media print{body:has(.receipt-thermal) .receipt-sheet{width:72mm!important;max-width:72mm!important;font-size:13pt!important;line-height:1.5!important}body:has(.receipt-thermal) .receipt-meta{font-size:12pt!important}body:has(.receipt-thermal) .receipt-sheet h1{font-size:17pt!important}body:has(.receipt-thermal) .receipt-total{font-size:19pt!important}body:has(.receipt-thermal) .receipt-large{font-size:15pt!important}body:has(.receipt-thermal) .receipt-large .receipt-meta{font-size:14pt!important}.receipt-payment{break-inside:avoid}}
'''
PAPER_SCRIPT='''<style id=receipt-page-size>@page{size:A4 portrait;margin:12mm}</style><script>(()=>{const sheet=document.querySelector('#readable-receipt'),select=document.querySelector('#receipt-paper'),page=document.querySelector('#receipt-page-size');if(!sheet||!select)return;function apply(value){sheet.classList.toggle('receipt-thermal',value==='thermal');select.value=value;page.textContent=value==='thermal'?'@page{size:auto;margin:4mm}':'@page{size:A4 portrait;margin:12mm}';try{localStorage.setItem('jupiter-receipt-paper',value)}catch{}}select.addEventListener('change',()=>apply(select.value));let saved='a4';try{saved=localStorage.getItem('jupiter-receipt-paper')||saved}catch{}apply(saved==='thermal'?'thermal':'a4')})();</script>'''
