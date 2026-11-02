"""Current JUPITER manual using measured typography from the supplied PDF."""
from pathlib import Path
import shutil
from copy import deepcopy
from PIL import Image
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_TAB_ALIGNMENT
from docx.enum.section import WD_SECTION_START
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from build_manual import TOPICS
from figure_callouts import legend,CALLOUTS

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/docx/JUPITER_User_Manual.docx'
FONT='TH Sarabun PSK'
T=deepcopy(TOPICS)

def revise(index, *, title=None, screen=None, steps=None, note=None):
    a=list(T[index])
    if title is not None:a[0]=title
    if screen is not None:a[1]=screen
    if steps is not None:a[3]=steps
    if note is not None:a[5]=note
    T[index]=tuple(a)

revise(7,steps=[
 'หลังยืนยันส่งออเดอร์ ระบบแสดงผลสำเร็จพร้อมรายการ ยอด และคำแนะนำว่าต้องทำอะไรต่อ ไม่ต้องกดส่งซ้ำ',
 'กลับหน้าเมนูแล้วดูกรอบ ออเดอร์ล่าสุด ซึ่งอัปเดตสถานะอัตโนมัติทุก 5 วินาที เฉพาะออเดอร์ของบิลและเบราว์เซอร์นี้',
 'กด ดูรายละเอียด / เรียกพนักงาน หรือเปิด ออเดอร์ของฉัน เพื่อดูรายการทั้งหมดและสถานะการจัดเตรียม',
 'ใช้ส่วน ให้เราช่วยอะไรดี เลือกเรียกพนักงานหรือขอเช็กบิล แล้วกดส่งคำขอ',
 'เมื่อขอเช็กบิลแล้วให้รอพนักงานตรวจยอด การส่งคำขอยังไม่ใช่การจ่ายเงิน และลูกค้าไม่ยืนยันรับเงินแทนร้าน'])
revise(12,steps=[
 'เปิด การจองโต๊ะ แล้วเลือกแท็บ รายการจอง / รับลูกค้า ค้นหาชื่อ เบอร์โทร โต๊ะ หรือรหัสจอง',
 'ตรวจวัน เวลา จำนวนคน และสถานะมัดจำ หากต้องเก็บมัดจำให้ผู้จัดการยืนยันก่อนรับลูกค้า',
 'ตรวจโต๊ะที่จะรับลูกค้า หากโต๊ะเดิมไม่พร้อม เลือกโต๊ะว่างที่รองรับจำนวนคนได้',
 'กด รับลูกค้า / เปิดโต๊ะ ระบบบันทึกว่ามาแล้ว เปิดบิลพร้อมจำนวนคน และพาไปหน้าดูแลโต๊ะ',
 'แสดง QR ของบิลใหม่ให้ลูกค้าสแกน การกดรับลูกค้าซ้ำจะกลับไปบิลเดิมโดยไม่สร้างซ้ำ'])
revise(13,steps=[
 'เปิด โต๊ะและออเดอร์ แล้วเลือกโต๊ะที่กำลังใช้งาน ตรวจชื่อโต๊ะ จำนวนคน และเลขบิล',
 'ให้ลูกค้าสแกน QR สั่งอาหารสำหรับโต๊ะนี้ หรือกด เปิด / บันทึก QR เพื่อพิมพ์ใช้งาน',
 'ปุ่ม QR ในการ์ดโต๊ะพาไปยัง QR ในหน้าดูแลโต๊ะได้โดยตรง ไม่ต้องผ่านหน้ารวม QR',
 'ดูงานครัวและบาร์ ตอบคำขอลูกค้า หรือเพิ่มรายการแทนลูกค้าจากบิลเดียวกัน',
 'ใช้ ตรวจบิล / พิมพ์ เมื่อต้องการตรวจรายการ และ เช็กบิล / ชำระเงิน เมื่อพร้อมรับชำระ'],
 note='เมนู พิมพ์ QR / ลิงก์ร้าน ใช้พิมพ์หลายโต๊ะและตั้ง URL สำหรับมือถือ QR สั่งอาหารของบิลเก่าจะใช้ไม่ได้เมื่อปิดบิล')
revise(24,steps=[
 'เปิด การจองโต๊ะ แล้วเลือกแท็บ ตรวจมัดจำ / คืนเงิน จากนั้นเลือก รอตรวจสลิป รอแจ้งโอน ยืนยันแล้ว รอคืนเงิน หรือทั้งหมด',
 'ตรวจชื่อ รหัสจอง เวลา ยอดมัดจำ และเลขอ้างอิง แล้วเปิดรูปสลิปเต็มเพื่อตรวจ',
 'ตรวจเงินเข้าจริงในบัญชีธนาคาร ระบุหมายเหตุหรือเลขอ้างอิง แล้วเลือกยืนยัน หรือให้ลูกค้าแจ้งใหม่ตามผลตรวจ',
 'กรณีคืนเงิน ตรวจเงื่อนไขที่บันทึกตอนจอง คืนเงินจริงก่อนบันทึกว่าโอนคืนแล้ว',
 'หากต้องแก้ยอดหรือบัญชี กด ตั้งค่ามัดจำ / บัญชีรับโอน เพื่อไปยัง ตั้งค่าและพนักงาน หมวด ร้านและมัดจำ'])
revise(25,steps=[
 'เปิด ตั้งค่าและพนักงาน แล้วเลือกหมวด ร้านและมัดจำ พนักงาน ความปลอดภัย สำรองข้อมูล หรือประวัติการทำรายการ',
 'หมวด ร้านและมัดจำ ใช้แก้ชื่อร้าน ที่อยู่ ค่าบริการ ภาษี เงื่อนไขมัดจำ และบัญชีรับโอน',
 'หมวด พนักงาน ใช้สร้างบัญชีด้วยชื่อผู้ใช้และรหัสผ่านที่เหมาะสม แล้วกำหนดสิทธิ์และหน้าที่',
 'กำหนดหน้าที่ บริการหน้าร้าน ครัว บาร์ หรือแคชเชียร์ ให้ตรงกับงาน โดยแต่ละคนใช้บัญชีของตนเอง',
 'เมื่อบันทึกหรือพบข้อมูลไม่ถูกต้อง ระบบกลับมาที่หมวดเดิมพร้อมข้อความผลลัพธ์ ให้ตรวจข้อความก่อนทำต่อ'])
revise(30,screen='settings-backup',steps=[
 'เปิด ตั้งค่าและพนักงาน หมวด สำรองข้อมูล แล้วดาวน์โหลดฐานข้อมูล SQLite เก็บไว้ในที่ปลอดภัย',
 'หากสำรองด้วยการคัดลอกไฟล์ ให้หยุดเซิร์ฟเวอร์ก่อน และเก็บโฟลเดอร์ data กับ assets ไปพร้อมกัน',
 'เมื่อต้องกู้คืน ให้สำรองชุดปัจจุบันก่อน แล้วตรวจว่าเป็นไฟล์ของร้านและรุ่นโปรแกรมที่ต้องการ',
 'ทดสอบเปิดสำเนาข้อมูลและตรวจบิล รายการจอง และรูปเมนูก่อนนำกลับไปใช้งานจริง',
 'เปิดครั้งถัดไปด้วย START.bat หรือ START-LAN.bat และตรวจ IP เครือข่ายก่อนให้มือถือสแกน QR'])
revise(3,steps=[
 'ใช้แถบ การอ่าน ด้านบน กด ตัวอักษรใหญ่ เพื่อขยายข้อความและส่วนควบคุม กดซ้ำเพื่อกลับขนาดปกติ',
 'กด สีชัดขึ้น เพื่อเพิ่มความแตกต่างระหว่างข้อความกับพื้นหลัง การตั้งค่าจำในเบราว์เซอร์เดียวกัน',
 'ปุ่มเปิดรายละเอียดมีกรอบ เครื่องหมาย + และคำว่า กดเพื่อเปิดดู เมื่อเปิดจะเปลี่ยนเป็นเครื่องหมาย − และคำแนะนำให้ย่อเก็บ',
 'หน้าเมนูกด รายการ เพื่อดูหลายเมนู หรือ รูปภาพ เพื่อดูการ์ดภาพใหญ่ ปุ่มที่เลือกแสดงสีทอง',
 'บนมือถือเมื่อมีแถบตะกร้าด้านล่าง ปุ่มตะกร้าด้านบนจะซ่อนเพื่อลดความซ้ำซ้อน หน้าไม่มีแถบล่างยังเข้าตะกร้าจากเมนูบนได้'])
CONFIG=('ตั้งค่ามัดจำและบัญชีรับโอน','deposit-settings',
 'ค่ามัดจำและข้อมูลรับโอนรวมอยู่ในหมวดร้านและมัดจำ แยกจากงานตรวจสลิปประจำวัน',[
 'เปิด ตั้งค่าและพนักงาน เลือก ร้านและมัดจำ แล้วเปิด ตั้งยอดและเงื่อนไขมัดจำ',
 'กรอกยอดต่อการจอง จำนวนคนที่เริ่มเก็บ เวลาแจ้งโอน และจำนวนชั่วโมงที่ยกเลิกก่อนแล้วคืนได้',
 'ระบุบัญชี ชื่อบัญชี หรือช่องทางติดต่อร้าน แล้วบันทึกนโยบายสำหรับการจองใหม่',
 'เปิด QR ธนาคาร / เปลี่ยนบัญชีรับโอน กรอกธนาคาร ชื่อบัญชี และแนบภาพ QR จากแอปธนาคาร',
 'ตรวจชื่อผู้รับและภาพ QR หลังบันทึก ไม่เปลี่ยนลาย QR หรือใช้ภาพจำลองเพื่อรับเงินจริง'],
 'ลูกค้าเห็นเงื่อนไขและข้อมูลรับโอนที่ร้านกำหนด',
 'การเปลี่ยนค่ามีผลกับการจองใหม่ การจองเก่าเก็บเงื่อนไขเดิม ระบบตรวจสลิปด้วยผู้จัดการ ไม่ยืนยันยอดกับธนาคารอัตโนมัติ')
SECURITY=('ความปลอดภัยและประวัติการทำรายการ','settings-security',
 'ผู้จัดการดูแลความปลอดภัยและตรวจประวัติผ่านหมวดที่แยกจากข้อมูลร้านและพนักงาน',[
 'เปิด ตั้งค่าและพนักงาน เลือก ความปลอดภัย เพื่อเปลี่ยนรหัสผ่านของตนตามแนวทางร้าน',
 'กด จัดการการกู้คืนบัญชี เมื่อต้องตั้งหรือดูวิธีการกู้คืนบัญชี เมนูนี้รวมอยู่ในหมวดความปลอดภัย',
 'ใช้รหัสผ่านของตนเอง ไม่ใช้บัญชีผู้จัดการร่วมกัน และออกจากระบบเมื่อใช้เครื่องสาธารณะ',
 'เลือก ประวัติการทำรายการ เพื่อตรวจเวลา ผู้ใช้ และการดำเนินการล่าสุดเมื่อพบยอดหรือสถานะผิดปกติ',
 'ไม่เผยแพร่รหัสผ่าน รหัสกู้คืน ข้อมูลลูกค้า หรือสลิปจริงในภาพส่งอาจารย์'],
 'ผู้จัดการเข้าถึงการกู้คืนและประวัติได้จากตำแหน่งเดียวกัน',
 'ภาพในคู่มือเป็นข้อมูลจำลอง ไม่ใช่ข้อมูลรับรองการเข้าใช้ร้านจริง')
CHAPTERS=[('การเตรียมใช้งานและเข้าสู่ระบบ',T[:4]),
          ('การใช้งานสำหรับลูกค้า',T[4:12]),
          ('การใช้งานสำหรับพนักงานและผู้จัดการ',T[12:26]+[CONFIG,SECURITY,T[26]]),
          ('ฐานข้อมูลและการดูแลระบบ',T[27:])]

def style_font(style,size,bold=False):
    style.font.name=FONT;style.font.size=Pt(size);style.font.bold=bold;style.font.color.rgb=RGBColor(0,0,0)
    r=style.element.get_or_add_rPr();fonts=r.find(qn('w:rFonts'))
    if fonts is None:fonts=OxmlElement('w:rFonts');r.insert(0,fonts)
    fonts.attrib.clear()
    for k in ['ascii','hAnsi','eastAsia','cs']:fonts.set(qn('w:'+k),FONT)
    for old in list(r.findall(qn('w:szCs'))):r.remove(old)
    sz=OxmlElement('w:szCs');sz.set(qn('w:val'),str(int(size*2)));r.append(sz)

def para(doc,text='',style=None,bold=None,align=None,after=0,before=0,indent=36):
    p=doc.add_paragraph(style=style);r=p.add_run(text)
    if bold is not None:r.bold=bold
    f=p.paragraph_format;f.left_indent=Pt(indent);f.space_after=Pt(after);f.space_before=Pt(before)
    if align is not None:p.alignment=align
    return p

def number_header(sec,text=None,start=None):
    sec.header.is_linked_to_previous=False;sec.footer.is_linked_to_previous=False
    sec.different_first_page_header_footer=False
    p=sec.header.paragraphs[0];p.alignment=WD_ALIGN_PARAGRAPH.RIGHT
    p.paragraph_format.space_after=Pt(0);p.paragraph_format.line_spacing=Pt(19.5)
    if text is not None:p.add_run(text)
    elif start is not None:
        f=OxmlElement('w:fldSimple');f.set(qn('w:instr'),'PAGE');p._p.append(f)
        n=OxmlElement('w:pgNumType');n.set(qn('w:start'),str(start));sec._sectPr.append(n)

def section(doc, *, left=72,top=72,header=None,start=None):
    s=doc.add_section(WD_SECTION_START.NEW_PAGE)
    s.page_width=Pt(612);s.page_height=Pt(792)
    s.top_margin=Pt(top);s.bottom_margin=Pt(54);s.left_margin=Pt(left);s.right_margin=Pt(left)
    s.header_distance=Pt(41.1);s.footer_distance=Pt(36)
    number_header(s,header,start)
    return s

def floating_picture(par,path,x,y,w,h):
    inline=par.add_run().add_picture(str(path),width=Pt(w),height=Pt(h))._inline
    a=OxmlElement('wp:anchor')
    for k,v in dict(distT='0',distB='0',distL='0',distR='0',simplePos='0',relativeHeight='0',behindDoc='1',locked='0',layoutInCell='1',allowOverlap='1').items():a.set(k,v)
    sp=OxmlElement('wp:simplePos');sp.set('x','0');sp.set('y','0');a.append(sp)
    for axis,value in [('H',x),('V',y)]:
        pos=OxmlElement('wp:position'+axis);pos.set('relativeFrom','page')
        off=OxmlElement('wp:posOffset');off.text=str(int(value*12700));pos.append(off);a.append(pos)
    for tag in ['wp:extent']:
        a.append(deepcopy(inline.find(qn(tag))))
    a.append(OxmlElement('wp:wrapNone'))
    for tag in ['wp:docPr','wp:cNvGraphicFramePr','a:graphic']:
        item=inline.find(qn(tag))
        if item is not None:a.append(deepcopy(item))
    inline.getparent().replace(inline,a)

def cover(doc,sec):
    sec.top_margin=Pt(251);sec.bottom_margin=Pt(54);sec.left_margin=sec.right_margin=Pt(72)
    floating_picture(sec.header.paragraphs[0],ROOT/'tmp/manual/reference-assets/faculty-crest.png',245,108,122,122)
    # The two cover pages use the same positions and sizes as the reference.
    p=para(doc,'เอกสารคู่มือและคำอธิบายการใช้งาน','Title',align=WD_ALIGN_PARAGRAPH.CENTER,indent=0)
    p.paragraph_format.line_spacing=Pt(32.4)
    p=para(doc,'เว็บระบบจัดการร้านอาหารและบาร์ ( JUPITER )','Title',align=WD_ALIGN_PARAGRAPH.CENTER,indent=0)
    p.paragraph_format.line_spacing=Pt(32.4)
    lines=[('โดย',32.1),('นายกลภพ ราศรีนวล  683050389-0',0),('เสนอ',27.5),('ผศ.ดร.นฏกร ประมายันต์',0),
           ('เอกสารคู่มือการใช้งานเล่มนี้เป็นส่วนหนึ่งของรายวิชา ED251007',55),('( การเขียนโปรแกรมคอมพิวเตอร์สำหรับครู )',0),
           ('คณะศึกษาศาสตร์ สาขาคอมพิวเตอร์ศึกษา มหาวิทยาลัยขอนแก่น',0),
           ('ภาคเรียนที่ 1 ชั้นปีที่ 2 ปีการศึกษา 2569',0)]
    for text,before in lines:
        p=para(doc,text,'Cover Body',align=WD_ALIGN_PARAGRAPH.CENTER,before=before,indent=0);p.paragraph_format.line_spacing=Pt(30)

def figure(doc,name):
    path=ROOT/'manual/screens-current'/(name+'.png')
    if not path.exists():path=ROOT/'manual/screens'/(name+'.png')
    if not path.exists():return
    with Image.open(path) as im:w,h=im.size
    limit=310 if name=='receipt' else 265 if name=='floor-plan' else 223
    width=min(396,limit*w/h)
    p=doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before=Pt(0);p.paragraph_format.space_after=Pt(8);p.paragraph_format.line_spacing=1
    # Match the already verified base PDF; keep a shorter replacement image's
    # original paragraph footprint so the following steps retain their positions.
    import json
    manifest_path=ROOT/'tmp/manual/callouts.json'
    if manifest_path.exists():
        bounds=next((b for b in json.loads(manifest_path.read_text(encoding='utf-8')) if b['screen']==name),None)
        if bounds:
            width=bounds['width']
            p.paragraph_format.space_after=Pt(8+max(0,bounds['height']-width*h/w))
    sh=p.add_run().add_picture(str(path),width=Pt(width));sh._inline.docPr.set('descr','ภาพหน้าจอระบบสาธิต '+name)

def bookmark(p,name,ident):
    a=OxmlElement('w:bookmarkStart');a.set(qn('w:id'),str(ident));a.set(qn('w:name'),name)
    b=OxmlElement('w:bookmarkEnd');b.set(qn('w:id'),str(ident))
    p._p.insert(0,a);p._p.append(b)

def build():
    if OUT.exists():
        old=OUT.with_name('JUPITER_User_Manual_before_reference_revision.docx')
        if not old.exists():shutil.copy2(OUT,old)
    oldpdf=ROOT/'output/pdf/JUPITER_User_Manual.pdf'
    if oldpdf.exists():
        backup=oldpdf.with_name('JUPITER_User_Manual_before_reference_revision.pdf')
        if not backup.exists():shutil.copy2(oldpdf,backup)
    doc=Document();s=doc.sections[0];s.page_width=Pt(612);s.page_height=Pt(792);s.header_distance=Pt(36);s.footer_distance=Pt(36)
    sizes=[('Normal',16,False),('Title',20,True),('Heading 1',22,True),('Heading 2',18,True),('Caption',13,False),('Cover Body',18,False),('Preface',18,False)]
    for name,size,bold in sizes:
        if name not in doc.styles:doc.styles.add_style(name,1)
        style_font(doc.styles[name],size,bold)
        f=doc.styles[name].paragraph_format;f.line_spacing=Pt(19.5);f.space_after=Pt(0);f.space_before=Pt(0)
    for name in ['Heading 1','Heading 2']:doc.styles[name].paragraph_format.keep_with_next=True
    doc.styles['Preface'].paragraph_format.line_spacing=Pt(22)
    doc.styles['Preface'].paragraph_format.first_line_indent=Pt(36)
    for st in doc.styles:
        for border in list(st.element.iter(qn('w:pBdr'))):border.getparent().remove(border)
    doc.core_properties.title='เอกสารคู่มือและคำอธิบายการใช้งานเว็บ JUPITER'
    doc.core_properties.author='นายกลภพ ราศรีนวล'
    doc.core_properties.subject='การใช้งานระบบฉบับปรับปรุง 29 ตุลาคม 2569'
    cover(doc,s);s=section(doc);cover(doc,s)
    s=section(doc,left=108,top=112)
    para(doc,'คำนำ','Heading 1',align=WD_ALIGN_PARAGRAPH.CENTER,after=27.5,indent=0)
    preface=[
      'เอกสารคู่มือและคำอธิบายการใช้งานเว็บระบบจัดการร้านอาหารและบาร์ JUPITER ฉบับนี้ จัดทำขึ้นเพื่อประกอบรายวิชา ED251007 การเขียนโปรแกรมคอมพิวเตอร์สำหรับครู โดยอธิบายการใช้งานสำหรับลูกค้า พนักงาน และผู้จัดการ ตั้งแต่การดูเมนู จองโต๊ะ สั่งอาหาร ดูแลออเดอร์ รับชำระเงิน จนถึงการตรวจรายงานและสำรองข้อมูล',
      'คู่มือแบ่งเนื้อหาเป็นการเตรียมใช้งาน การใช้งานสำหรับลูกค้า การใช้งานสำหรับพนักงานและผู้จัดการ และฐานข้อมูลกับการดูแลระบบ แต่ละหัวข้อใช้ภาพหน้าจอร่วมกับคำอธิบายตามลำดับ เพื่อให้ผู้เริ่มใช้งานเลือกอ่านและทำตามงานของตนได้ ภาพและเส้นทางเมนูปรับให้ตรงกับระบบที่ตรวจสอบวันที่ 29 ตุลาคม 2569',
      'ชื่อผู้ใช้ ชื่อลูกค้า เบอร์โทร รหัสจอง และยอดเงินในภาพเป็นข้อมูลจำลองสำหรับอธิบายเท่านั้น QR ในเอกสารไม่ใช่ QR สำหรับชำระเงินจริง การแนบสลิปต้องรอผู้จัดการตรวจเงินเข้าจริงก่อนยืนยัน และการเปลี่ยนหน้าหรือเปิดรายละเอียดไม่ถือเป็นการบันทึกรายการ',
      'ผู้จัดทำหวังว่าคู่มือฉบับนี้จะช่วยให้ผู้ใช้เข้าใจขั้นตอนและผลของการทำงานได้ชัดเจน หากมีการพัฒนาโปรแกรมเพิ่มเติม ควรปรับชื่อปุ่ม ภาพประกอบ และขั้นตอนในเอกสารให้สอดคล้องกับรุ่นที่ใช้งานจริงต่อไป']
    for text in preface:para(doc,text,'Preface',after=12,indent=0)
    para(doc,'นายกลภพ ราศรีนวล','Preface',align=WD_ALIGN_PARAGRAPH.RIGHT,before=14,indent=0)
    para(doc,'ผู้จัดทำ','Preface',align=WD_ALIGN_PARAGRAPH.RIGHT,indent=0)
    # Two contents pages retain the reference's Thai front-matter numbering.
    contents_groups=[[(1,CHAPTERS[0][0],CHAPTERS[0][1],1),
                      (2,CHAPTERS[1][0],CHAPTERS[1][1],1),
                      (3,CHAPTERS[2][0],CHAPTERS[2][1][:4],1)],
                     [(3,CHAPTERS[2][0]+' ( ต่อ )',CHAPTERS[2][1][4:],5),
                      (4,CHAPTERS[3][0],CHAPTERS[3][1],1)]]
    for part,groups in enumerate(contents_groups):
        section(doc,left=108,top=112,header='ก' if part==0 else 'ข')
        para(doc,'สารบัญ' if part==0 else 'สารบัญ ( ต่อ )','Heading 1',align=WD_ALIGN_PARAGRAPH.CENTER,after=27.5,indent=0)
        for chapter,title,topics,first in groups:
            p=para(doc,title,'Cover Body',bold=True,before=8,after=3,indent=0)
            for j,topic in enumerate(topics,first):
                p=para(doc,f'{chapter}.{j}  {topic[0]}\t',indent=12)
                p.paragraph_format.line_spacing=Pt(24.5);p.paragraph_format.tab_stops.add_tab_stop(Pt(384),WD_TAB_ALIGNMENT.RIGHT)
                fld=OxmlElement('w:fldSimple');fld.set(qn('w:instr'),f'PAGEREF topic_{chapter}_{j} \\h');p._p.append(fld)
    section(doc,start=1)
    ident=10
    for chapter,(title,topics) in enumerate(CHAPTERS,1):
        for j,(heading,screen,intro,steps,result,note) in enumerate(topics,1):
            if chapter!=1 or j!=1:doc.add_page_break()
            if j==1:para(doc,title,'Heading 1',align=WD_ALIGN_PARAGRAPH.CENTER,before=12,after=39,indent=0)
            p=para(doc,f'{chapter}.{j}  {heading}','Heading 2',before=0,after=10,indent=0)
            bookmark(p,f'topic_{chapter}_{j}',ident);ident+=1
            if screen:figure(doc,screen)
            else:para(doc,intro,after=10)
            for k,step in enumerate(steps,1):
                p=para(doc,f'{k}.\t{step}',after=0,indent=54)
                p.paragraph_format.first_line_indent=Pt(-18);p.paragraph_format.tab_stops.add_tab_stop(Pt(54))
            para(doc,'ผลการทำงาน : '+result,bold=True,before=8)
            para(doc,'( '+note+'\u00a0)',before=8)
    # No institution, semester or year is invented from someone else's cover.
    doc.save(OUT)
    print(OUT)
    print('Topics',sum(len(t) for _,t in CHAPTERS))

if __name__=='__main__':build()
