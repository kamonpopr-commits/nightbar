"""Extend the verified illustrated manual without rebuilding its existing pages."""
from pathlib import Path
from copy import deepcopy
import shutil
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.parts.hdrftr import HeaderPart
from docx.opc.constants import RELATIONSHIP_TYPE as RT

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/docx/JUPITER_User_Manual.docx'
BASE=ROOT/'tmp/manual/before_beginner_extension.docx'
if not BASE.exists():
    shutil.copy2(OUT,BASE)
    shutil.copy2(ROOT/'output/pdf/JUPITER_User_Manual.pdf',ROOT/'tmp/manual/before_beginner_extension.pdf')
doc=Document(BASE)
FONT='TH Sarabun PSK'

def p(text='',bold=False,after=6,before=0,style=None,indent=0):
    a=doc.add_paragraph(style=style)
    r=a.add_run(text); r.bold=bold or style=='Heading 2'
    f=a.paragraph_format;f.left_indent=Pt(indent);f.space_after=Pt(after);f.space_before=Pt(before);f.line_spacing=Pt(19.5)
    return a

def mark(a,key):
    b=OxmlElement('w:bookmarkStart');b.set(qn('w:id'),str(500+int(key.split('_')[-1])));b.set(qn('w:name'),key)
    e=OxmlElement('w:bookmarkEnd');e.set(qn('w:id'),b.get(qn('w:id')))
    a._p.insert(0,b);a._p.append(e)

def heading(n,title):
    doc.add_page_break()
    a=p(f'5.{n}  {title}',style='Heading 2',after=12)
    mark(a,f'topic_5_{n}')

def step(n,text):
    a=p(f'{n}.\t{text}',after=5,indent=18)
    a.paragraph_format.first_line_indent=Pt(-18)
    a.paragraph_format.tab_stops.add_tab_stop(Pt(18))

def table(headers,rows,widths):
    t=doc.add_table(rows=1,cols=len(headers));t.alignment=WD_TABLE_ALIGNMENT.CENTER;t.autofit=False
    for cell,w in zip(t.columns,widths):cell.width=Pt(w)
    for c,text in zip(t.rows[0].cells,headers):c.text=text
    for row in rows:
        for c,text in zip(t.add_row().cells,row):c.text=text
    for i,row in enumerate(t.rows):
        for j,c in enumerate(row.cells):
            c.width=Pt(widths[j]);c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            pr=c._tc.get_or_add_tcPr()
            b=OxmlElement('w:tcBorders')
            for edge in ['top','left','bottom','right']:
                e=OxmlElement('w:'+edge);e.set(qn('w:val'),'single');e.set(qn('w:sz'),'4');e.set(qn('w:color'),'D9D9D9');b.append(e)
            pr.append(b)
            m=OxmlElement('w:tcMar')
            for edge in ['top','left','bottom','right']:
                e=OxmlElement('w:'+edge);e.set(qn('w:w'),'65' if edge in ['top','bottom'] else '90');e.set(qn('w:type'),'dxa');m.append(e)
            pr.append(m)
            sh=OxmlElement('w:shd');sh.set(qn('w:fill'),'E7E6E6' if i==0 else 'FFFFFF');pr.append(sh)
            for a in c.paragraphs:
                a.paragraph_format.space_after=Pt(0);a.paragraph_format.line_spacing=Pt(19.5)
                for r in a.runs:r.bold=i==0;r.font.name=FONT;r.font.size=Pt(16);r.font.color.rgb=RGBColor(0,0,0)
        rp=row._tr.get_or_add_trPr();rp.append(OxmlElement('w:cantSplit'))
        if i==0:rp.append(OxmlElement('w:tblHeader'))
    p('',after=3)
    return t

# Add a third contents page without changing the existing illustrated page flow.
boundary=next(a for a in doc.paragraphs if a._p.xpath('./w:pPr/w:sectPr') and a._p.getprevious() is not None and '4.7' in ''.join(a._p.getprevious().itertext()))
insert_after=boundary._p
tocnodes=[]
a=p('สารบัญ ( ต่อ )',style='Heading 1',after=27.5);a.alignment=WD_ALIGN_PARAGRAPH.CENTER;tocnodes.append(a._p)
a=p('คำแนะนำเพิ่มเติมสำหรับผู้เริ่มใช้งาน',bold=True,style='Cover Body',after=6);tocnodes.append(a._p)
titles=['เริ่มอ่านตามหน้าที่ของผู้ใช้งาน','ติดตั้งและเปิดระบบครั้งแรก','เงื่อนไขและเส้นทางก่อนทำรายการ','ความหมายสถานะและสิ่งที่ต้องทำต่อ','ตัวอย่างคำนวณเงินและตรวจใบเสร็จ']
for i,(title,page) in enumerate(zip(titles,[37,38,39,40,42]),1):
    a=p(f'5.{i}  {title}\t',after=0,indent=12);a.paragraph_format.line_spacing=Pt(24.5);a.paragraph_format.tab_stops.add_tab_stop(Pt(384),WD_TAB_ALIGNMENT.RIGHT)
    fld=OxmlElement('w:fldSimple');fld.set(qn('w:instr'),f'PAGEREF topic_5_{i} \\h')
    run=OxmlElement('w:r');txt=OxmlElement('w:t');txt.text=str(page);run.append(txt);fld.append(run);a._p.append(fld);tocnodes.append(a._p)
end=p();tocnodes.append(end._p)
sect=deepcopy(boundary._p.xpath('./w:pPr/w:sectPr')[0])
for old in list(sect.findall(qn('w:headerReference'))):sect.remove(old)
hp=HeaderPart.new(doc.part.package)
hr=doc.part.relate_to(hp,RT.HEADER)
ref=OxmlElement('w:headerReference');ref.set(qn('w:type'),'default');ref.set(qn('r:id'),hr);sect.insert(0,ref)
ha=hp.element.find(qn('w:p'));pr=OxmlElement('w:pPr');jc=OxmlElement('w:jc');jc.set(qn('w:val'),'right');pr.append(jc);ha.append(pr)
rr=OxmlElement('w:r');tt=OxmlElement('w:t');tt.text='ค';rr.append(tt);ha.append(rr)
end._p.get_or_add_pPr().append(sect)
for node in tocnodes:
    node.getparent().remove(node);insert_after.addnext(node);insert_after=node

# Explain where a first-time reader should begin, within the existing preface.
pref=next(a for a in doc.paragraphs if a.text.startswith('คู่มือแบ่งเนื้อหาเป็น'))
# The third contents page leads readers to the added chapter; keep the preface's
# verified paragraph footprint unchanged.

heading(1,titles[0])
p('บทนี้ช่วยให้ผู้ที่ยังไม่เคยใช้ระบบเลือกอ่านเฉพาะงานของตน ก่อนศึกษารายละเอียดจากภาพและขั้นตอนในบทหลัก')
table(['ผู้ใช้','ลำดับที่ควรอ่านและทดลอง'],[
('ลูกค้า','ดูเมนูและสั่งอาหาร หน้า 5–8 หรือจองโต๊ะและส่งมัดจำ หน้า 9–12 ไม่ต้องสมัครบัญชี'),
('พนักงานหน้าร้าน','เข้าสู่ระบบ หน้า 3 รับลูกค้าและเปิดโต๊ะ หน้า 13–14 งานเสิร์ฟ หน้า 15 และจัดการโต๊ะ หน้า 16–17'),
('ครัวและบาร์','เข้าสู่ระบบ หน้า 3 แล้วเปิดงานครัวและบาร์ หน้า 15 เปลี่ยนสถานะตามงานที่ทำจริง'),
('แคชเชียร์','เปิดกะ หน้า 21 รับชำระและออกใบเสร็จ หน้า 18–20 แล้วปิดกะและตรวจเงินสด หน้า 21'),
('ผู้จัดการ','ตั้งร้านและสิทธิ์ หน้า 26–28 ดูมัดจำ หน้า 25 และ 27 เมนูและสต็อก หน้า 22–24 รายงาน หน้า 29 สำรองข้อมูล หน้า 33')],[100,368])
p('วิธีอ่านภาพประกอบ',bold=True,before=5)
p('วงกลมและลูกศรสีแดงระบุตำแหน่งในภาพ ให้เทียบกับคำอธิบาย “จุดในภาพ” หมายเลขนี้แยกจากลำดับขั้นตอนด้านล่าง เช่น จุดที่ 1 อาจเป็นช่องชื่อผู้ใช้ แต่ขั้นตอนที่ 1 อาจรวมทั้งการกรอกชื่อและรหัสผ่าน')
p('ฝึกด้วยข้อมูลจำลอง',bold=True,before=4)
p('เปิดโต๊ะทดลองหนึ่งโต๊ะ สั่งอาหารหนึ่งรายการ จัดเตรียมและเสิร์ฟ รับชำระ ออกใบเสร็จ แล้วทำความสะอาดโต๊ะ ตามลำดับหน้า 36 ใช้บัญชีทดลองที่ผู้ดูแลมอบให้ ไม่ใช้ QR ธนาคารจริงเพื่อทดสอบโอนเงิน')

heading(2,titles[1])
p('ใช้ขั้นตอนนี้กับเครื่อง Windows ที่ได้รับโฟลเดอร์โปรเจกต์ครบแล้ว ติดตั้ง Python 3.11 ขึ้นไปและ Visual Studio Code ก่อนเริ่ม การติดตั้งส่วนเสริมครั้งแรกต้องใช้อินเทอร์เน็ต')
for i,text in enumerate([
'เปิด Visual Studio Code เลือก File > Open Folder แล้วเลือก nightbar ตรวจว่าเห็น app.py, requirements.txt, START.bat, START-LAN.bat และโฟลเดอร์ data',
'เลือก Terminal > New Terminal ตรวจว่าตำแหน่งทำงานอยู่ในโฟลเดอร์ nightbar พิมพ์ py -3 --version แล้วกด Enter ต้องแสดงรุ่น Python หากไม่พบให้ติดตั้ง Python หรือเลือกตัวเรียก Python ที่ใช้งานได้ของเครื่อง',
'พิมพ์ py -3 -m pip install -r requirements.txt แล้วกด Enter รอจนติดตั้งเสร็จหรือแสดง Requirement already satisfied หากขึ้นข้อความผิดพลาดให้แก้ให้สำเร็จก่อนเริ่มเว็บ',
'พิมพ์ .\\START.bat แล้วกด Enter หากต้องให้มือถือเข้าใช้งาน ให้ใช้ .\\START-LAN.bat แทน ไม่ต้องเปิดทั้งสองตัวพร้อมกัน',
'เมื่อ Terminal แสดง NIGHTBAR running และที่อยู่เว็บ ให้เปิด http://127.0.0.1:8765/menu สำหรับลูกค้า หรือ http://127.0.0.1:8765/login สำหรับพนักงาน เก็บ Terminal ที่รันเว็บไว้',
'ครั้งแรกที่ยังไม่มีบัญชีผู้จัดการ ให้ทำตามหน้าตั้งค่าบัญชีแรกที่ระบบแสดง หากมีข้อมูลร้านเดิมแล้ว ให้ใช้บัญชีที่ผู้ดูแลมอบให้ ห้ามสร้างฐานข้อมูลใหม่ทับข้อมูลเดิมเพื่อแก้ปัญหาเข้าใช้',
'สำหรับมือถือ เชื่อมเครือข่ายเดียวกับเครื่องร้าน ให้ผู้จัดการตั้ง URL หน้า QR เป็น http://IP-เครื่องร้าน:8765 แล้วทดลองเปิด /menu บนมือถือก่อนสแกน รายละเอียดการแก้ปัญหาอยู่หน้า 34'],1):step(i,text)
p('ตรวจว่าสำเร็จ',bold=True,before=4)
p('หน้าเมนูแสดงรายการอาหาร และหน้าเข้าสู่ระบบแสดงช่องชื่อผู้ใช้กับรหัสผ่าน หากพอร์ตถูกใช้อยู่ ให้ตรวจโปรแกรมที่กำลังรันก่อนเริ่มซ้ำ การปิดเครื่องหรือปิด Terminal จะหยุดการให้บริการเว็บ')

heading(3,titles[2])
p('เมื่อปุ่มไม่ปรากฏหรือทำรายการไม่ได้ ให้ตรวจสิทธิ์บัญชีและเงื่อนไขด้านล่างก่อน การเปิดหน้าใหม่อย่างเดียวไม่ถือว่าบันทึกสำเร็จ')
table(['งาน','ต้องพร้อมก่อน','เส้นทางและผลที่ควรเห็น'],[
('รับลูกค้าที่จอง','มีการจองที่ยังใช้ได้ โต๊ะพร้อม และมัดจำยืนยันแล้วถ้ามี','การจองโต๊ะ > เลือกรายการ > เลือกโต๊ะ > รับลูกค้า / เปิดโต๊ะ ระบบบันทึกมาแล้วและเชื่อมบิล ไม่ต้องเปิดโต๊ะซ้ำ'),
('สั่งอาหารที่โต๊ะ','มีบิลเปิดอยู่ และใช้ QR ของบิลปัจจุบัน','สแกน QR > เลือกอาหาร > ตะกร้า > ยืนยันส่ง ต้องเห็นเลขออเดอร์หรือข้อความสำเร็จก่อนออกจากหน้า'),
('ย้ายหรือรวมโต๊ะ','บิลยังไม่เริ่มรับชำระ โต๊ะปลายทางพร้อม และไม่ชนการจอง','โต๊ะและออเดอร์ > เปิดบิล > จัดการโต๊ะ > เลือกการดำเนินการ ตรวจชื่อโต๊ะและบิลหลังบันทึก ดูหน้า 16'),
('รับชำระ','เปิดกะแล้ว ไม่มีอาหารค้างเตรียมหรือเสิร์ฟ และตรวจยอดล่าสุด','บิลโต๊ะ > รับชำระ ตรวจมัดจำหรือส่วนลดก่อนรับเงินจริง หลังบันทึกต้องเห็นยอดคงเหลือหรือใบเสร็จ ดูหน้า 18–21'),
('เปิดรับลูกค้ารอบใหม่','บิลเดิมปิดแล้ว และทำความสะอาดโต๊ะจริงแล้ว','โต๊ะและออเดอร์ > ทำความสะอาดแล้ว พร้อมใช้งาน โต๊ะจึงกลับเป็นว่าง ดูหน้า 14 และ 20')],[78,148,242])
p('กรณีทำรายการแล้วไม่แน่ใจ',bold=True,before=5)
p('อ่านผลที่แสดงและตรวจประวัติก่อนกดซ้ำ โดยเฉพาะการส่งออเดอร์และรับชำระ หากระบบแจ้งยอดเปลี่ยนให้ตรวจข้อมูลใหม่ ถ้ายังติดปัญหาให้ดูหน้า 34–35 หรือแจ้งผู้จัดการพร้อมเลขบิลและข้อความที่พบ')

heading(4,titles[3])
p('สถานะบอกทั้งสิ่งที่เกิดขึ้นแล้วและงานถัดไป อ่านข้อความร่วมกับสี เพราะสีเดียวกันอาจมีความหมายต่างกันในแต่ละหน้า')
p('สถานะโต๊ะและบิล',bold=True,after=5)
table(['สถานะ','ความหมายและสิ่งที่ต้องทำต่อ'],[
('ว่าง พร้อมรับลูกค้า','โต๊ะพร้อมใช้งาน พนักงานตรวจจำนวนคนและการจองก่อนเปิดโต๊ะ'),
('กำลังใช้งาน','มีบิลเปิดอยู่ เพิ่มอาหารหรือดูแลรายการผ่านบิลเดิม ไม่เปิดบิลซ้ำ'),
('กำลังชำระเงิน','มีการยืนยันยอดแล้ว ตรวจยอดและรับชำระต่อ การแก้รายการหรือย้ายโต๊ะมีข้อจำกัด'),
('รอทำความสะอาด','จบการใช้งานบิลแล้ว แต่ยังไม่พร้อมรับลูกค้าใหม่ ทำความสะอาดจริงและกดยืนยันพร้อมใช้งาน')],[126,342])
p('สถานะการเตรียมและเสิร์ฟอาหาร',bold=True,before=5,after=5)
table(['สถานะ','ผู้ทำงานและขั้นตอนถัดไป'],[
('รับออเดอร์แล้ว','ครัวหรือบาร์ตรวจรายการ แล้วกดเริ่มทำเมื่อลงมือจริง'),
('กำลังเตรียม','ครัวหรือบาร์กำลังทำ เมื่อเสร็จให้เปลี่ยนเป็นพร้อมเสิร์ฟ'),
('พร้อมเสิร์ฟ','พนักงานหน้าร้านรับอาหารไปส่ง เมื่อส่งถึงลูกค้าจึงยืนยันเสิร์ฟแล้ว'),
('เสิร์ฟแล้ว','รายการส่งถึงลูกค้าแล้ว ตรวจรายการอื่นให้ครบก่อนรับชำระ')],[126,342])
p('คำขอเช็กบิล',bold=True,before=5)
p('ลูกค้าส่งคำขอให้ร้านตรวจบิล ยังไม่ถือว่ารับชำระ พนักงานต้องเปิดบิล ตรวจรายการ และให้ผู้มีสิทธิ์บันทึกรับเงินตามจริง')

doc.add_page_break()
p('5.4  ความหมายสถานะและสิ่งที่ต้องทำต่อ ( ต่อ )',style='Heading 2',after=12)
p('สถานะการจอง',bold=True,after=5)
table(['สถานะ','ความหมายและงานต่อไป'],[
('จองแล้ว','มีรายการจอง แต่ถ้ากำหนดมัดจำต้องดูสถานะมัดจำด้วย ยังไม่ใช่การเปิดโต๊ะ'),
('มาแล้ว','พนักงานรับลูกค้าและเชื่อมบิลแล้ว ให้ QR ของบิลนั้นเพื่อสั่งอาหาร'),
('ยกเลิกแล้ว','การจองไม่ใช้ต่อ ตรวจเรื่องมัดจำแยกต่างหาก เพราะยกเลิกการจองไม่ได้แปลว่าคืนเงินจริงแล้ว')],[126,342])
p('สถานะมัดจำ',bold=True,before=5,after=5)
table(['สถานะ','ความหมายและงานต่อไป'],[
('รอแจ้งโอน','ลูกค้าตรวจชื่อผู้รับ โอนตามยอด และส่งหลักฐานภายในเวลาที่กำหนด'),
('รอตรวจสอบยอดโอน','ลูกค้าส่งสลิปหรือเลขอ้างอิงแล้ว ผู้จัดการต้องตรวจเงินเข้าจริง ไม่ต้องให้ลูกค้าโอนซ้ำ'),
('ยืนยันมัดจำแล้ว','ผู้จัดการตรวจรับยอดแล้ว จึงรับลูกค้าเข้าที่นั่งและนำมัดจำไปหักบิลได้'),
('หักบิลแล้ว','นำมัดจำมาเป็นยอดรับชำระของบิลแล้ว ไม่หักซ้ำอีกครั้ง'),
('รอคืนเงิน / คืนเงินแล้ว','รอคืนเงินยังไม่ใช่คืนสำเร็จ ต้องคืนเงินจริงและบันทึกผลพร้อมหลักฐานก่อน'),
('หมดเวลาชำระ / ยกเลิกก่อนชำระ','รายการไม่อยู่ในช่วงรับชำระแล้ว ลูกค้าต้องติดต่อร้านก่อนโอน'),
('ไม่คืนตามเงื่อนไข','ผู้จัดการพิจารณาตามเงื่อนไขที่การจองนั้นยอมรับ และบันทึกเหตุผลตรวจสอบย้อนหลัง')],[126,342])
p('ระบบนี้ให้ผู้จัดการตรวจเงินเอง ไม่มีการยืนยันยอดกับธนาคารอัตโนมัติ เงื่อนไขการคืนเงินของการจองเดิมอาจต่างจากค่าที่ร้านตั้งใหม่ ให้เปิดตรวจรายละเอียดของรายการนั้น',before=4)

heading(5,titles[4])
p('ตัวอย่างสมมุติเพื่ออธิบายวิธีคิด ไม่ใช่อัตราบังคับของร้าน กำหนดค่าอาหาร 1,000 บาท ส่วนลด 100 บาท ค่าบริการ 10% ภาษี 7% และมัดจำที่ผู้จัดการยืนยันแล้ว 300 บาท')
table(['รายการคำนวณ','วิธีคิด','จำนวนเงิน ( บาท )'],[
('รวมอาหารและเครื่องดื่ม','รวมรายการก่อนส่วนลด','1,000.00'),
('ส่วนลด','ผู้จัดการอนุมัติ','100.00'),
('ยอดหลังส่วนลด','1,000.00 − 100.00','900.00'),
('ค่าบริการ 10%','900.00 × 10 ÷ 100','90.00'),
('ภาษี 7%','(900.00 + 90.00) × 7 ÷ 100','69.30'),
('ยอดสุทธิของบิล','900.00 + 90.00 + 69.30','1,059.30'),
('มัดจำที่นำมาหักบิล','รับไว้ก่อนแล้ว ไม่ใช่ส่วนลด','300.00'),
('ยอดที่ต้องรับเพิ่ม','1,059.30 − 300.00','759.30'),
('เงินสดรับเพิ่มจากลูกค้า','ลูกค้ายื่นเงินสด','800.00'),
('เงินทอน','800.00 − 759.30','40.70')],[155,195,118])
p('ทำรายการในหน้ารับชำระ',bold=True,before=5)
p('เปิดบิล > ตรวจรายการที่เสิร์ฟแล้ว > ให้ผู้จัดการกรอกส่วนลด > ยืนยันยอด > ยืนยันหักมัดจำของการจองที่ถูกต้อง > ตรวจยอดคงเหลือ 759.30 > เลือกเงินสด > กรอกรับเงิน 800.00 > ตรวจเงินทอน 40.70 > บันทึกรับชำระ > เปิดใบเสร็จ')
p('ตรวจใบเสร็จก่อนส่งลูกค้า',bold=True,before=4)
p('ชื่อโต๊ะและเลขบิลต้องตรง รายการและจำนวนถูกต้อง ยอดสุทธิ 1,059.30 บาท ประวัติชำระรวมมัดจำ 300.00 บาทกับยอดรับเพิ่ม 759.30 บาท เงินทอน 40.70 บาท และไม่มีหนี้คงเหลือ')
p('โปรแกรมปัดค่าบริการและภาษีแยกเป็นหน่วยสตางค์ก่อนรวมยอด ถ้าชำระด้วยการโอน ยอดรับต้องตรงยอดชำระและไม่มีเงินทอน มัดจำเกินบิลต้องตรวจขั้นตอนคืนส่วนเกิน ไม่บันทึกเป็นส่วนลด',before=4)

settings=doc.settings.element
up=settings.find(qn('w:updateFields'))
if up is None:up=OxmlElement('w:updateFields');settings.append(up)
up.set(qn('w:val'),'true')
doc.core_properties.subject='คู่มือฉบับเพิ่มคำแนะนำสำหรับผู้เริ่มต้น 29 ตุลาคม 2569'
doc.save(OUT)
print('Saved',OUT)
