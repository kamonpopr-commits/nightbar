"""Original bank QR images; no resizing or regeneration of payment codes."""
import io,secrets,warnings
import visuals
import menu_uploads

def initialize(db):
    for key in ['deposit_qr','deposit_bank','deposit_payee']:db.execute('INSERT OR IGNORE INTO settings VALUES (?,?)',(key,''))
    columns={r['name'] for r in db.execute('PRAGMA table_info(booking_deposits)')}
    for name in ['payment_qr','payment_bank','payment_payee']:
        if name not in columns:db.execute(f"ALTER TABLE booking_deposits ADD COLUMN {name} TEXT NOT NULL DEFAULT ''")

def validate(raw):
    if len(raw)>menu_uploads.MAX_FILE:raise ValueError('รูป QR ต้องไม่เกิน 5 MB')
    from PIL import Image,UnidentifiedImageError
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as im:
                ext={'JPEG':'.jpg','PNG':'.png','WEBP':'.webp'}.get(im.format)
                if not ext or im.width*im.height>20000000 or getattr(im,'n_frames',1)>1:raise ValueError('ใช้รูป QR แบบ JPG, PNG หรือ WebP ภาพนิ่ง ไม่เกิน 20 ล้านพิกเซล')
                im.verify()
                return ext
    except (UnidentifiedImageError,OSError,Image.DecompressionBombWarning,Image.DecompressionBombError):raise ValueError('ไฟล์รูป QR ไม่สมบูรณ์ กรุณาเลือกรูปจากแอปธนาคาร')

def save(h,db,d):
    if h.s['role']!='manager':raise ValueError('เฉพาะผู้จัดการเปลี่ยนบัญชีรับโอนได้')
    bank=d.get('bank','').strip();payee=d.get('payee','').strip()
    if len(bank)>100 or len(payee)>150:raise ValueError('ชื่อธนาคารหรือชื่อบัญชียาวเกินกำหนด')
    raw=getattr(h,'uploads',{}).get('photo')
    if raw:
        ext=validate(raw);name='bank-qr-'+secrets.token_hex(16)+ext;target=visuals.ASSETS/name
        if not hasattr(h,'created_uploads'):h.created_uploads=[]
        h.created_uploads.append(target)
        with target.open('xb') as f:f.write(raw)
        db.execute("UPDATE settings SET value=? WHERE key='deposit_qr'",(name,))
    for k,v in [('deposit_bank',bank),('deposit_payee',payee)]:db.execute('UPDATE settings SET value=? WHERE key=?',(v,k))
    return '/settings?tab=shop#deposit-settings'

def image(h,name,bank='',payee='',amount=None):
    if not name:return ''
    # Only server-issued asset names are accepted; never render a user-supplied URL.
    from pathlib import Path
    if Path(name).name!=name or not name.startswith('bank-qr-') or Path(name).suffix not in ['.jpg','.png','.webp']:return ''
    a=h.api;url='/assets/'+a.esc(name)
    out='<section class=bank-qr-card><h3>สแกน QR เพื่อโอนมัดจำ</h3>'
    if amount is not None:out+=f'<p><strong>ยอดที่ต้องโอน {a.money(amount)} บาท</strong></p>'
    if bank:out+='<p>'+a.esc(bank)+'</p>'
    if payee:out+='<p>ชื่อบัญชี: <strong>'+a.esc(payee)+'</strong></p>'
    out+=f'<img src="{url}" alt="QR รับโอนมัดจำของร้าน ตรวจชื่อผู้รับในแอปธนาคารก่อนยืนยัน" width=885 height=1200 style="display:block;width:100%;max-width:360px;height:auto;object-fit:contain;background:white;border-radius:12px;margin:16px auto"><p><a class="button secondary" href="{url}" target=_blank rel=noopener>เปิดรูป QR</a> <a class="button secondary" href="{url}" download="jupiter-deposit-qr{Path(name).suffix}">บันทึก QR</a></p><p>ใช้มือถือเครื่องเดียวกัน: บันทึกรูป แล้วเลือกสแกนจากรูปในแอปธนาคาร<br>ตรวจชื่อผู้รับและกรอกยอดมัดจำให้ตรงก่อนโอน รูปนี้ไม่ได้ยืนยันยอดเงินเข้าร้านอัตโนมัติ</p></section>'
    return out

def admin(h,db):
    s=dict(db.execute('SELECT key,value FROM settings'))
    a=h.api
    return '<details><summary>QR ธนาคาร / เปลี่ยนบัญชีรับโอน</summary><p>ใช้ภาพ QR จากแอปธนาคาร ระบบเก็บภาพต้นฉบับโดยไม่ย่อหรือสร้างลาย QR ใหม่ การเปลี่ยนมีผลเฉพาะการจองใหม่</p>'+image(h,s['deposit_qr'],s['deposit_bank'],s['deposit_payee'])+h.form('/deposit-qr',a.field('ธนาคาร / ช่องทางรับโอน','bank',s['deposit_bank'],extra='maxlength=100')+a.field('ชื่อบัญชี (กรอกให้ตรงกับในแอปธนาคาร)','payee',s['deposit_payee'],extra='maxlength=150')+'<label>รูป QR ธนาคาร<input type=file name=photo accept="image/jpeg,image/png,image/webp"></label><p>JPG, PNG หรือ WebP ไม่เกิน 5 MB · ไม่เลือกไฟล์จะใช้ QR เดิม</p><button>บันทึก QR และบัญชีรับโอน</button>')+'</details>'
