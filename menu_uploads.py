"""Bounded multipart uploads and verified menu image normalization."""
from email.parser import BytesParser
from email.policy import default
import io,json,secrets,warnings
import visuals

MAX_FILE=5*1024*1024
MAX_BODY=MAX_FILE+65536

def parse(body,content_type):
    if len(body)>MAX_BODY:raise ValueError('ไฟล์ใหญ่เกินกำหนด รูปต้องไม่เกิน 5 MB')
    if '\r' in content_type or '\n' in content_type or len(content_type)>500:raise ValueError('แบบฟอร์มอัปโหลดไม่ถูกต้อง')
    message=BytesParser(policy=default).parsebytes(('Content-Type: '+content_type+'\r\nMIME-Version: 1.0\r\n\r\n').encode('ascii')+body)
    if message.get_content_type()!='multipart/form-data' or not message.is_multipart() or message.defects:raise ValueError('แบบฟอร์มอัปโหลดไม่ถูกต้อง')
    fields={};files={};total=0
    for part in message.iter_parts():
        name=part.get_param('name',header='content-disposition')
        if part.is_multipart() or part.get_content_disposition()!='form-data' or not name or name in fields or name in files:raise ValueError('แบบฟอร์มอัปโหลดไม่ถูกต้อง')
        raw=part.get_payload(decode=True) or b''
        if part.get_filename() is not None:
            if name!='photo':raise ValueError('ช่องอัปโหลดไม่ถูกต้อง')
            if len(raw)>MAX_FILE:raise ValueError('รูปต้องมีขนาดไม่เกิน 5 MB')
            if raw:files[name]=raw
        else:
            total+=len(raw)
            if total>32768:raise ValueError('ข้อมูลแบบฟอร์มยาวเกินกำหนด')
            try:fields[name]=raw.decode('utf-8')
            except UnicodeError:raise ValueError('ข้อความในแบบฟอร์มไม่ถูกต้อง')
    return fields,files

def normalized(raw):
    if len(raw)>MAX_FILE:raise ValueError('รูปต้องมีขนาดไม่เกิน 5 MB')
    try:from PIL import Image,ImageOps,UnidentifiedImageError
    except ImportError:raise ValueError('ยังไม่ได้ติดตั้ง Pillow สำหรับอัปโหลดรูป กรุณาติดตั้งตาม requirements.txt')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as image:
                if image.format not in ['JPEG','PNG','WEBP']:raise ValueError('รองรับรูป JPG, PNG และ WebP เท่านั้น')
                if image.width*image.height>20000000 or min(image.size)<1:raise ValueError('ภาพใหญ่เกิน 20 ล้านพิกเซล กรุณาย่อก่อนอัปโหลด')
                if getattr(image,'n_frames',1)>1:raise ValueError('กรุณาใช้ภาพนิ่งสำหรับเมนู')
                image.load(); image=ImageOps.exif_transpose(image).convert('RGBA' if 'A' in image.getbands() else 'RGB')
                image.thumbnail((960,960));out=io.BytesIO();image.save(out,'WEBP',quality=85,method=6)
                return out.getvalue()
    except ValueError:raise
    except (UnidentifiedImageError,OSError,Image.DecompressionBombError,Image.DecompressionBombWarning):raise ValueError('อ่านรูปไม่ได้ กรุณาเลือกไฟล์ภาพ JPG, PNG หรือ WebP ที่สมบูรณ์')

def presentation(h,db,pid,d):
    if h.s['role']!='manager':raise ValueError('เฉพาะผู้จัดการอัปโหลดรูปได้')
    if not db.execute('SELECT 1 FROM products WHERE id=?',(pid,)).fetchone():raise ValueError('ไม่พบสินค้า')
    featured=d.get('featured','0')
    if featured not in ['0','1']:raise ValueError('สถานะไม่ถูกต้อง')
    image=d.get('image','')
    if image and image not in {p.name for p in visuals.ASSETS.glob('*.webp')}:raise ValueError('รูปภาพไม่ถูกต้อง')
    raw=getattr(h,'uploads',{}).get('photo')
    if raw:
        content=normalized(raw);image='menu-upload-'+secrets.token_hex(16)+'.webp'
        target=visuals.ASSETS/image
        if not hasattr(h,'created_uploads'):h.created_uploads=[]
        h.created_uploads.append(target)
        with target.open('xb') as output:output.write(content)
    db.execute('INSERT INTO product_presentation VALUES (?,?,?,?) ON CONFLICT(product_id) DO UPDATE SET image=excluded.image,description=excluded.description,featured=excluded.featured',(pid,image,d.get('description','')[:300],int(featured)))

def cleanup(h):
    if getattr(h,'upload_committed',False):return
    for path in getattr(h,'created_uploads',[]):
        if path.parent.resolve()==visuals.ASSETS.resolve() and path.name.startswith(('menu-upload-','bank-qr-')):path.unlink(missing_ok=True)

def controls():
    return '<div class=upload-control><label>อัปโหลดรูปเมนู<input type=file name=photo accept="image/jpeg,image/png,image/webp"></label><p class=muted>JPG, PNG หรือ WebP ไม่เกิน 5 MB · ระบบย่อให้สูงสุด 960 พิกเซล</p><img class=upload-preview alt="ภาพตัวอย่างเมนูก่อนบันทึก" hidden><p class=upload-status role=status aria-live=polite>ยังไม่ได้เลือกภาพใหม่</p><button type=button class="secondary clear-upload">ล้างภาพที่เลือก</button></div>'

def script(db):
    data=json.dumps({str(r['id']):dict(r) for r in db.execute("SELECT p.id,p.name,p.category,p.price,p.cost,p.minimum,p.active,COALESCE(v.image,'') image,COALESCE(v.description,'') description,COALESCE(v.featured,0) featured FROM products p LEFT JOIN product_presentation v ON v.product_id=p.id")},ensure_ascii=False).replace('<',chr(92)+'u003c')
    return '<style>.upload-control{grid-column:1/-1;padding:18px;border:1px dashed #667e64;border-radius:12px}.upload-preview{max-width:260px;width:100%;max-height:220px;object-fit:contain;border-radius:12px;margin-top:12px}.upload-control p{font-size:14px;line-height:1.8}.upload-status{color:#ead19e}</style><script type="application/json" id=menu-presentation-data>'+data+'</script>'+SCRIPT+EDIT_SCRIPT

SCRIPT='''<script>(()=>{const rows=JSON.parse(document.querySelector('#menu-presentation-data').textContent);document.querySelectorAll('form[action="/product"],form[action="/product-presentation"],form[action="/product-save"]').forEach(form=>{const file=form.querySelector('[name=photo]'),preview=form.querySelector('.upload-preview'),status=form.querySelector('.upload-status');if(!file)return;let url=null;const existing=form.querySelector('[name=image]');function showExisting(){if(url){URL.revokeObjectURL(url);url=null}const name=existing?.value;preview.hidden=!name;if(name)preview.src='/assets/'+encodeURIComponent(name);else preview.removeAttribute('src');status.textContent=name?'ภาพที่ใช้อยู่ · เลือกรูปใหม่เพื่อเปลี่ยน':'ยังไม่ได้เลือกภาพใหม่'}function clear(){file.value='';file.setCustomValidity('');showExisting()}file.addEventListener('change',()=>{if(url)URL.revokeObjectURL(url);url=null;const photo=file.files[0];file.setCustomValidity('');if(!photo){showExisting();return}if(photo.size>5*1024*1024){file.setCustomValidity('รูปต้องไม่เกิน 5 MB');file.reportValidity();preview.hidden=true;status.textContent='รูปใหญ่เกิน 5 MB กรุณาเลือกใหม่';return}url=URL.createObjectURL(photo);preview.src=url;preview.hidden=false;status.textContent='รูปใหม่: '+photo.name+' · ยังไม่บันทึก'});form.querySelector('.clear-upload').addEventListener('click',clear);existing?.addEventListener('change',clear);const select=form.querySelector('[name=product_id]');if(existing&&select&&select.tagName==="SELECT"){function load(){const row=rows[select.value];if(!row)return;existing.value=row.image;form.querySelector('[name=description]').value=row.description;form.querySelector('[name=featured]').value=row.featured;clear()}select.addEventListener('change',load);load()}if(existing&&select?.tagName!=='SELECT')showExisting();form.addEventListener('submit',()=>{if(form.checkValidity())form.querySelector('button:not([type=button])').disabled=true})})})();</script>'''

EDIT_SCRIPT='''<script>(()=>{const rows=JSON.parse(document.querySelector('#menu-presentation-data').textContent),id=new URLSearchParams(location.search).get('product_id'),edit=document.querySelector('form[action="/product-edit"]'),photo=document.querySelector('form[action="/product-presentation"]');if(!edit)return;const select=edit.querySelector('[name=product_id]');function load(){const row=rows[select.value];if(!row)return;for(const key of ['name','category','minimum','active'])edit.elements[key].value=row[key];for(const key of ['price','cost'])edit.elements[key].value=(row[key]/100).toFixed(2);if(photo){photo.elements.product_id.value=select.value;photo.elements.product_id.dispatchEvent(new Event('change'))}}select.addEventListener('change',load);if(id&&rows[id])select.value=id;load();photo?.elements.product_id.addEventListener('change',()=>{if(select.value!==photo.elements.product_id.value){select.value=photo.elements.product_id.value;load()}})})();</script>'''
