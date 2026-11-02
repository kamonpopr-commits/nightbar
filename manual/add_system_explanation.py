"""Append verified JUPITER system diagrams and screen-reference explanations."""
from pathlib import Path
from io import BytesIO
from copy import deepcopy
import json,subprocess,shutil,math,sqlite3
from docx import Document
from docx.shared import Pt
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.parts.hdrftr import HeaderPart
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.enum.text import WD_ALIGN_PARAGRAPH,WD_TAB_ALIGNMENT
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
from pypdf import PdfReader,PdfWriter
from PIL import Image

ROOT=Path(__file__).resolve().parents[1];TMP=ROOT/'tmp/manual/system';TMP.mkdir(exist_ok=True)
DOC=ROOT/'output/docx/JUPITER_User_Manual.docx';PDF=ROOT/'output/pdf/JUPITER_User_Manual.pdf'
BD=TMP/'before-system.docx';BP=TMP/'before-system.pdf'
if not BD.exists():shutil.copy2(DOC,BD);shutil.copy2(PDF,BP)
NODE=Path(r'C:\Users\TUF GAMING\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe')
POP=Path(r'C:\Users\TUF GAMING\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin\pdftoppm.exe')
for n,f in [('S','THSarabunPSK-Regular.ttf'),('B','THSarabunPSK-Bold.ttf')]:pdfmetrics.registerFont(TTFont(n,str(ROOT/'manual/fonts'/f)))
PAGES=[]
def page(title,intro,blocks):PAGES.append({'title':title,'intro':intro,'blocks':blocks})
def text(s,bold=False):return {'type':'text','text':s,'bold':bold}
def tab(head,rows,widths):return {'type':'table','head':head,'rows':rows,'widths':widths}
def box(id,x,y,w,h,label,kind='process'):return dict(id=id,x=x,y=y,w=w,h=h,label=label,kind=kind)
def edge(points,label='',at=None):return dict(points=points,label=label,at=at)
def diag(nodes,edges,height=350):return dict(type='diagram',nodes=nodes,edges=edges,height=height)

STORES=[
['D1','บัญชีพนักงาน','users และข้อมูลตำแหน่งงาน'],
['D2','เมนูและสต็อก','products, product_presentation, menu_options, movements'],
['D3','การจองและมัดจำ','reservations, customer_bookings, booking_deposits, deposit_slips, reservation_orders, deposit_events'],
['D4','โต๊ะและออเดอร์','tables, orders, items, table_assignments, table_state, customer_requests, customer_lines, service_requests, visits, customer_sessions'],
['D5','ยอดบิลและรับชำระ','checkout_totals, bill_parts, payments, receipt_rates'],
['D6','กะและรายจ่าย','shifts, cash_events, expenses'],
['D7','ค่าตั้งและประวัติ','settings, audit, table_events, item_cancellations']]
page('6.1  วิธีอ่านแผนภาพและแหล่งเก็บข้อมูล','บทนี้อธิบายข้อมูลของ JUPITER ตามโครงสร้างโปรแกรมที่ตรวจสอบวันที่ 30 ตุลาคม 2569 ใช้ประกอบคู่มือการกดใช้งานในบทก่อนหน้า',[
text('สัญลักษณ์ใน DFD',True),text('กรอบสี่เหลี่ยมคือผู้ใช้นอกระบบ กรอบมุมมนพร้อมเลขคือกระบวนการ กรอบมีแถบด้านซ้ายรหัส D คือแหล่งเก็บข้อมูล ลูกศรระบุทิศทางพร้อมชื่อข้อมูล ไม่ใช่ลำดับการกดปุ่ม'),
tab(['รหัส','กลุ่มข้อมูล','ตารางที่ใช้จริง'],STORES,[35,112,321]),
text('รหัส D เป็นการจัดกลุ่มเพื่อให้อ่านแผนภาพง่าย ไม่ใช่ชื่อตารางใหม่ กระบวนการเดียวกันอาจอ่านและบันทึกหลายตาราง ส่วนกรอบชื่อเดิมที่ปรากฏหลายหน้าอ้างถึงกลุ่มเดียวกัน'),
text('Context Diagram แสดงทั้งระบบเป็นกระบวนการ 0; Diagram 0 แยกเป็นกระบวนการ 1.0–6.0; Child Diagram ขยายงาน 3.0, 4.0 และ 5.0 โดยคงข้อมูลเข้าและออกที่เกี่ยวข้อง')])

nodes=[box('sys',177,110,127,110,'0\nระบบจัดการร้าน\nJUPITER'),box('c',0,0,120,48,'ลูกค้า','entity'),box('f',0,140,120,48,'พนักงานหน้าร้าน','entity'),box('k',0,280,120,48,'ครัวและบาร์','entity'),box('cash',348,0,120,48,'แคชเชียร์','entity'),box('m',348,280,120,48,'ผู้จัดการ','entity')]
edges=[edge([(120,15),(150,15),(150,125),(177,125)],'คำขอจอง / อาหาร / สลิป',(83,62)),edge([(177,150),(137,150),(137,42),(120,42)],'เมนู / รหัสจอง / สถานะ',(80,100)),edge([(120,153),(177,173)],'ข้อมูลโต๊ะ / ผลเสิร์ฟ',(70,207)),edge([(177,190),(152,190),(152,180),(120,180)],'บิลโต๊ะ / งานบริการ',(67,238)),edge([(120,294),(160,294),(160,208),(177,208)],'ผลเตรียมอาหาร',(73,275)),edge([(177,218),(171,218),(171,322),(120,322)],'คิวอาหาร / เครื่องดื่ม',(180,345)),edge([(348,15),(324,15),(324,125),(304,125)],'ยอดรับ / ผลตรวจเงิน',(368,68)),edge([(304,150),(338,150),(338,43),(348,43)],'ยอดค้าง / ใบเสร็จ / กะ',(367,103)),edge([(348,294),(327,294),(327,185),(304,185)],'เมนู / ค่าตั้ง / ผลตรวจมัดจำ',(373,238)),edge([(304,210),(315,210),(315,322),(348,322)],'รายงาน / รายการรอตรวจ',(369,273))]
for n in nodes:
    if n['id'] in ['k','m']:n['y']=300
edges[4]['points'][0]=(120,314)
edges[4]['points'][1]=(160,314)
edges[8]['points'][0]=(348,314)
edges[8]['points'][1]=(327,314)
page('6.2  แผนภาพภาพรวมระบบ Context Diagram','ผู้ใช้ภายนอกระบบแบ่งตามหน้าที่ บัญชีผู้จัดการอาจทำงานแคชเชียร์ได้เมื่อได้รับสิทธิ์และเปิดกะแล้ว แต่ในแผนภาพแยกบทบาทเพื่อให้เห็นความรับผิดชอบ',[
diag(nodes,edges,370),text('ลูกค้าไม่ต้องสมัครสมาชิกเพื่อดูเมนูหรือจอง ส่วนพนักงานทุกตำแหน่งต้องส่งชื่อผู้ใช้และรหัสผ่าน และได้รับผลเข้าสู่ระบบตามสิทธิ์'),text('ระบบไม่มีการตรวจเงินเข้ากับธนาคารอัตโนมัติ ภาพ QR เป็นข้อมูลรับโอน หลักฐานและผลตรวจมัดจำจึงแลกเปลี่ยนกับลูกค้าและผู้จัดการ ไม่วาดธนาคารเป็นบริการที่เชื่อมต่ออยู่')])

def level0(a,b):
    nodes=[];edges=[]
    for idx,(num,title,actor,store,inp,out,read,write) in enumerate([a,b]):
        y=30+idx*180
        nodes += [box(f'e{idx}',0,y,115,65,actor,'entity'),box(f'p{idx}',164,y,135,65,f'{num}.0\n{title}'),box(f'd{idx}',354,y,114,65,store,'store')]
        edges += [edge([(115,y+17),(164,y+17)],inp,(137,y-16)),edge([(164,y+49),(115,y+49)],out,(135,y+86)),edge([(299,y+17),(354,y+17)],write,(328,y-16)),edge([(354,y+49),(299,y+49)],read,(330,y+86))]
    return diag(nodes,edges,355)

page('6.3  แผนภาพการไหลข้อมูล Diagram 0','แผนภาพระดับ 0 แบ่งเป็นสามหน้าให้อ่านชื่อข้อมูลได้ชัด หน้านี้แสดงกระบวนการ 1.0 และ 2.0 ซึ่งใช้ร่วมกับงานขายและการจอง',[
level0((1,'ตรวจบัญชีและสิทธิ์','พนักงานทุกตำแหน่ง','D1\nบัญชีพนักงาน','ข้อมูลเข้าสู่ระบบ','ผลตรวจและสิทธิ์','บัญชีและตำแหน่ง','ข้อมูลบัญชีที่แก้ไข'),(2,'ดูแลเมนูและสต็อก','ผู้จัดการ','D2\nเมนูและสต็อก','เมนู / รูป / จำนวน','ผลบันทึก / คงเหลือ','เมนูและตัวเลือก','เมนูและการเคลื่อนไหว')),
text('1.0 ใช้ D7 สำหรับประวัติบางการดำเนินการ และส่งสิทธิ์ที่ตรวจแล้วให้กระบวนการ 2.0–6.0 ก่อนอนุญาตทำรายการ'),text('2.0 ให้ข้อมูลเมนู ราคา และสต็อกแก่ 4.0 ส่วนลูกค้าได้รับเมนูผ่านการเลือกอาหารใน 4.0 การปรับสต็อกต้องเก็บจำนวนและเหตุผลใน movements')])
page('6.3  แผนภาพการไหลข้อมูล Diagram 0 ( ต่อ )','หน้านี้แสดง 3.0 การจองและมัดจำ กับ 4.0 การเปิดโต๊ะ สั่ง และดูแลงานอาหาร โดยใช้ข้อมูลเมนูจาก 2.0 และส่งยอดรายการต่อไปยัง 5.0',[
level0((3,'จองโต๊ะและมัดจำ','ลูกค้า / ผู้จัดการ','D3\nการจองและมัดจำ','คำขอจอง / หลักฐาน','รหัสจอง / ผลตรวจ','การจอง / เงื่อนไข','การจอง / สลิป / ผลตรวจ'),(4,'โต๊ะและงานอาหาร','ลูกค้า / หน้าร้าน\nครัวและบาร์','D4\nโต๊ะและออเดอร์','QR / อาหาร / สถานะ','บิล / คิว / ผลส่ง','โต๊ะ / บิล / รายการ','ออเดอร์ / ผลเตรียม')),
text('3.0 อ่านโต๊ะและการใช้งานจาก D4 กับนโยบายจาก D7 แล้วส่งการจองที่รับลูกค้าแล้วไปเชื่อมบิลใน 4.0 ผู้จัดการเป็นผู้ให้ผลตรวจมัดจำ'),text('4.0 อ่านเมนูจาก D2 และตัดสต็อกเมื่อยืนยันส่งออเดอร์ การคืนสต็อกต้องผ่านการยกเลิกที่ตรวจสิทธิ์และบันทึกเหตุผล คิวอาหารส่งให้ครัวและบาร์ งานเสิร์ฟส่งให้หน้าร้าน')])
page('6.3  แผนภาพการไหลข้อมูล Diagram 0 ( ต่อ )','หน้านี้แสดง 5.0 รับชำระ และ 6.0 รายงานกับการดูแลร้าน กลุ่มผู้ใช้ในกรอบหมายถึงบทบาทที่ส่งข้อมูลให้กระบวนการนั้น ไม่ใช่บัญชีที่ใช้ร่วมกัน',[
level0((5,'รับชำระและใบเสร็จ','แคชเชียร์ / ผู้จัดการ','D5 / D6\nยอดชำระและกะ','ส่วนลด / ยอดรับ / วิธีจ่าย','ยอดค้าง / ใบเสร็จ','ยอดบิล / กะปัจจุบัน','รายการชำระ / ยอดยืนยัน'),(6,'รายงานและดูแลร้าน','ผู้จัดการ','D2–D7\nข้อมูลดำเนินงาน','ช่วงวันที่ / ค่าตั้ง','รายงาน / ผลบันทึก','ยอดขาย / สต็อก / กะ','ค่าตั้ง / รายจ่าย / ประวัติ')),
text('5.0 อ่านบิลและงานค้างจาก D4 มัดจำที่ยืนยันจาก D3 และอัตราบริการกับภาษีจาก D7 แล้วส่งสถานะปิดบิลกลับ D4 เพื่อปล่อยที่นั่งเป็นรอทำความสะอาด'),text('6.0 สรุปข้อมูลตามช่วงที่ผู้จัดการเลือก การสำรองข้อมูลเป็นการอ่านชุดข้อมูลเพื่อส่งไฟล์สำรองให้ผู้จัดการ ไม่ใช่การส่งข้อมูลจริงออกสาธารณะ')])

def child(prefix,titles,actor,store,inputs,notes=None):
    nodes=[box('actor',0,20,112,65,actor,'entity'),box('store',354,125,114,100,store,'store')]
    for i,title in enumerate(titles):nodes.append(box(str(i),163,15+i*87,136,51,f'{prefix}.{i+1}\n{title}'))
    edges=[edge([(112,40),(163,40)],inputs,(135,5))]
    for i,label in enumerate(['ข้อมูลผ่านตรวจ','รายการพร้อมบันทึก','ผลบันทึก']):edges.append(edge([(231,66+i*87),(231,102+i*87)],label,(174,85+i*87)))
    edges += [edge([(299,127),(328,127),(328,150),(354,150)],'ข้อมูลบันทึก',(330,95)),edge([(354,195),(319,195),(319,214),(299,214)],'ข้อมูลตรวจสอบ',(360,253)),edge([(163,301),(145,301),(145,90),(100,90),(100,85)],'ผลและสถานะ',(65,110))]
    if prefix==3:
        nodes.append(box('manager',0,270,112,65,'ผู้จัดการ','entity'))
        edges += [edge([(112,70),(128,70),(128,214),(163,214)],'สลิป / เลขอ้างอิง',(67,175)),edge([(112,301),(163,301)],'ผลตรวจเงินจริง',(128,250)),edge([(299,301),(340,301),(340,215),(354,215)],'สถานะมัดจำ',(361,289)),edge([(163,128),(120,128),(120,85)],'รหัสจอง / ยอด',(62,140))]
    elif prefix==4:
        edges[4]['points']=[(299,200),(328,200),(328,150),(354,150)]
        nodes.append(box('team',0,270,112,65,'ครัว / บาร์\nหน้าร้าน','entity'))
        nodes.append(box('menu',354,10,114,65,'D2\nเมนู / สต็อก','store'))
        edges += [edge([(354,57),(314,57),(314,126),(299,126)],'ราคา / ตัวเลือก',(371,83)),edge([(299,206),(345,206),(345,35),(354,35)],'จำนวนตัดสต็อก',(380,112)),edge([(163,285),(112,285)],'คิวจัดเตรียม',(125,251)),edge([(112,318),(163,318)],'ผลทำ / ผลเสิร์ฟ',(125,337))]
    else:
        nodes.append(box('manager',0,270,112,65,'ผู้จัดการ','entity'))
        nodes.append(box('deposit',354,10,114,65,'D3\nมัดจำยืนยันแล้ว','store'))
        edges += [edge([(112,289),(130,289),(130,127),(163,127)],'ส่วนลดอนุมัติ',(67,200)),edge([(354,55),(309,55),(309,208),(299,208)],'มัดจำคงเหลือ',(370,85)),edge([(299,300),(344,300),(344,215),(354,215)],'ผลรับชำระ',(370,289))]
    return diag(nodes,edges,350)

page('6.4  แผนภาพย่อยการจองและมัดจำ','Child Diagram ของกระบวนการ 3.0 แยกการส่งหลักฐานของลูกค้าออกจากการยืนยันเงินของผู้จัดการ ข้อมูลการจองและมัดจำอยู่ใน D3',[
child(3,['ตรวจวันเวลาและโต๊ะ','บันทึกจองและเงื่อนไข','รับสลิปหรือเลขอ้างอิง','บันทึกผลตรวจมัดจำ'],'ลูกค้า','D3\nการจอง / มัดจำ\nสลิป / ประวัติ','วันเวลา / คน / โต๊ะ'),
text('ข้อมูลเพิ่มเติมของ 3.1 คือโต๊ะจาก D4 และนโยบายจาก D7; 3.2 คืนรหัสจองและยอดมัดจำให้ลูกค้า; 3.3 คืนสถานะรอตรวจสอบยอดโอน'),text('ผู้จัดการส่งผลตรวจเงินจริงและหมายเหตุเข้า 3.4 ระบบจึงเปลี่ยนเป็นยืนยันมัดจำแล้ว หรือให้ส่งหลักฐานใหม่ หากรับลูกค้าเข้าที่นั่งจะส่งการจองที่ตรวจแล้วไปยัง 4.0 ไม่สร้างบิลตั้งแต่ลูกค้าเพียงส่งคำขอจอง')])
page('6.4  แผนภาพย่อยการสั่งอาหารผ่าน QR ( ต่อ )','Child Diagram ของ 4.0 แสดงการรับรายการจากลูกค้าและการส่งงานต่อครัว บาร์ และหน้าร้าน ตะกร้าก่อนยืนยันยังไม่ใช่ออเดอร์ที่เข้าบิล',[
child(4,['ตรวจ QR และบิลเปิด','ตรวจราคาและจำนวน','บันทึกรายการและสต็อก','ส่งคิวและบันทึกสถานะ'],'ลูกค้า','D4\nบิล / รายการ\nคิว / บริการ','QR / ตะกร้า / หมายเหตุ'),
text('4.1 อ่าน visits และบิลใน D4; 4.2 อ่านเมนูกับตัวเลือกจาก D2 และตรวจยอดล่าสุด; 4.3 บันทึกรายการลงบิลและตัดสต็อก D2 ในธุรกรรมเดียวกัน พร้อมคืนเลขออเดอร์'),text('4.4 ส่งคิวให้ครัวหรือบาร์ รับผลกำลังจัดเตรียมหรือพร้อมเสิร์ฟ แล้วรับผลเสิร์ฟจากหน้าร้าน ส่งสถานะกลับลูกค้าและข้อมูลบิลให้ 5.0 การขอเช็กบิลเป็นคำขอบริการ ไม่ใช่ผลรับชำระ')])
page('6.4  แผนภาพย่อยรับชำระและหักมัดจำ ( ต่อ )','Child Diagram ของ 5.0 ใช้ยอดรายการจาก 4.0 และมัดจำที่ยืนยันแล้วจาก 3.0 ผู้มีสิทธิ์ต้องเปิดกะและตรวจเงินจริงก่อนบันทึก',[
child(5,['ตรวจบิลและกะ','ยืนยันยอดและส่วนลด','บันทึกมัดจำและรับเงิน','ออกใบเสร็จและปิดบิล'],'แคชเชียร์\nหรือผู้จัดการ','D5 / D6\nยอดบิล / รับชำระ\nกะ / เงินสด','บิล / ยอดรับ / ช่องทาง'),
text('5.1 อ่านงานค้าง D4 และกะ D6; 5.2 รับส่วนลดจากผู้จัดการ อ่านอัตราจาก D7 แล้วบันทึกยอดยืนยันใน D5; 5.3 อ่านมัดจำ D3 และบันทึกยอดใช้เพื่อป้องกันหักซ้ำ'),text('5.4 เกิดเมื่อรับชำระครบยอด ส่งใบเสร็จและเงินทอนให้ผู้รับชำระ ส่งสถานะบิลปิดให้ D4 ระบบปล่อยที่นั่งเป็นรอทำความสะอาด และเก็บข้อมูลให้ 6.0 นำไปออกรายงาน')])

def er(nodes,links):
    edges=[]
    for n in nodes:n['y']+=25
    for a,b,label,path in links:
        shifted=[(x,y+25) for x,y in path]
        at=None
        if len(path)==2 and path[0][1]==path[1][1]:
            at=((path[0][0]+path[1][0])/2,10 if path[0][1]<150 else 242)
        edges.append(edge(shifted,label,at))
    return diag(nodes,edges,365)

ersale=[box('p',0,10,140,92,'products\nPK id\nname / price / stock','er'),box('i',164,10,140,92,'items\nPK id\nFK product_id\nFK order_id','er'),box('o',328,10,140,92,'orders\nPK id\nFK table_id\nstatus / total','er'),box('s',0,235,140,92,'shifts\nPK id\nopened / closed','er'),box('pay',164,235,140,92,'payments\nPK id\nFK order_id / part_id\nFK shift_id','er'),box('part',328,235,140,92,'bill_parts\nPK id\nFK order_id\namount','er')]
erl=[('p','i','1 : 0..N',[(140,55),(164,55)]),('o','i','1 : 0..N',[(328,70),(304,70)]),('o','part','1 : 0..N',[(398,102),(398,235)]),('o','pay','1 : 0..N',[(360,102),(360,165),(234,165),(234,235)]),('s','pay','0..1 : 0..N',[(140,281),(164,281)]),('part','pay','0..1 : 0..N',[(328,302),(304,302)])]
page('6.5  ความสัมพันธ์ข้อมูลการขาย ER Diagram','PK คือรหัสหลักของตาราง FK คือรหัสที่อ้างไปยังตารางอื่น 1 หมายถึงหนึ่งรายการ 0..1 คืออาจไม่มีหรือมีหนึ่ง และ 0..N คืออาจไม่มีหรือมีได้หลายรายการ',[
er(ersale,erl),text('products หนึ่งเมนูอยู่ใน items ได้หลายรายการ และ orders หนึ่งบิลมี items กับ bill_parts ได้หลายรายการ payments แต่ละรายการผูกกับ orders เสมอ ส่วน part_id และ shift_id อนุญาตให้ว่างได้ตามโครงสร้าง'),text('มัดจำที่นำมาหักบิลบันทึกเป็น payments เช่นกัน แต่ไม่มี shift_id เพื่อไม่ให้นับเป็นเงินสดรับใหม่ของกะ ชื่อและราคาที่ items เก็บเป็นค่าขณะสั่ง จึงไม่เปลี่ยนย้อนหลังเมื่อแก้เมนู'),text('กรอบและเส้นนี้สรุปเฉพาะความสัมพันธ์หลัก ไม่ใช่ทุกคอลัมน์ทั้งหมด ตาราง checkout_totals และ receipt_rates ใช้ order_id เป็น PK และ FK เพื่อเก็บยอดยืนยันกับอัตราของบิล')])

erseat=[box('t',0,10,140,92,'tables\nPK id\nname / seats','er'),box('r',164,10,140,92,'reservations\nPK id\nFK table_id\ntime / status','er'),box('d',328,10,140,92,'booking_deposits\nPK/FK reservation_id\nFK order_id\nstate / applied','er'),box('a',0,235,140,92,'table_assignments\nPK/FK table_id\nFK order_id','er'),box('o',164,235,140,92,'orders\nPK id\nFK table_id','er'),box('ro',328,235,140,92,'reservation_orders\nPK/FK reservation_id\nFK order_id','er')]
erl2=[('t','r','1 : 0..N',[(140,40),(164,40)]),('r','d','1 : 0..1',[(304,55),(328,55)]),('t','a','1 : 0..1',[(70,102),(70,235)]),('o','a','1 : 0..N',[(164,281),(140,281)]),('r','ro','1 : 0..1',[(270,102),(270,164),(398,164),(398,235)]),('o','ro','1 : 0..N',[(304,302),(328,302)])]
page('6.5  ความสัมพันธ์ข้อมูลโต๊ะและการจอง ( ต่อ )','โต๊ะเดิมมีการจองได้หลายเวลา แต่การจองหนึ่งรายการมีโต๊ะที่เลือกหนึ่งโต๊ะ ระบบใช้ table_assignments เก็บโต๊ะที่กำลังใช้งานจริงแยกจากโต๊ะหลักของบิล',[
er(erseat,erl2),text('หนึ่งบิลมี table_assignments หลายแถวได้ จึงเพิ่มโต๊ะร่วมได้ ขณะที่ table_id เป็น PK ทำให้โต๊ะหนึ่งมีการจัดที่นั่งปัจจุบันได้ไม่เกินหนึ่งแถว เมื่อปิดบิลระบบลบการจัดที่นั่งและตั้งรอทำความสะอาด'),text('reservations หนึ่งรายการมี booking_deposits ได้ไม่เกินหนึ่งแถว และมี reservation_orders ได้ไม่เกินหนึ่งแถวเพื่อเชื่อมบิลหลังรับลูกค้า ส่วน deposit_slips ผูก reservation_id แบบหนึ่งการจองต่อหลายภาพ'),text('เส้นที่ไม่ได้วาดเพื่อให้ภาพอ่านง่าย: orders.table_id อ้าง tables.id; booking_deposits.order_id อ้าง orders.id; customer_bookings.reservation_id อ้าง reservations.id และเก็บ session_token กับรหัสจองให้ลูกค้าตรวจรายการของตน')])

demo=ROOT/'tmp/manual/jupiter_manual_demo.sqlite3'
db=sqlite3.connect(f'file:{demo.as_posix()}?mode=ro',uri=True)
result=db.execute('SELECT o.id,t.name,i.name,i.qty,i.price, i.qty*i.price FROM orders o JOIN tables t ON t.id=o.table_id JOIN items i ON i.order_id=o.id WHERE o.id=1001').fetchall();db.close()
page('6.6  เปิดดู SQLite ด้วย DB Browser','ใช้ฐานข้อมูลสาธิตหรือสำเนาที่สำรองไว้เท่านั้น เพื่อเรียนรู้โดยไม่เปลี่ยนข้อมูลร้าน ฐานข้อมูลสาธิตในตัวอย่างชื่อ jupiter_manual_demo.sqlite3',[
text('วิธีเปิดและตำแหน่งที่ใช้',True),
text('1. เปิด DB Browser for SQLite เลือก File แล้วเลือก Open Database Read Only จากนั้นเลือกไฟล์สำเนา ไม่เลือกฐานข้อมูลร้านที่กำลังให้บริการ'),
text('2. ใช้แท็บ Database Structure ดูชื่อตารางและคอลัมน์ จากนั้นเลือกแท็บ Browse Data เพื่อดูข้อมูลจริง'),
text('3. ในช่อง Table เลือก products เพื่อดูชื่อเมนู price และ stock หรือเลือก orders เพื่อดูบิล และ items เพื่อดูอาหารที่ผูกกับบิล'),
text('4. ใช้แท็บ Execute SQL เมื่อต้องตรวจข้อมูลข้ามตารางตามตัวอย่างหน้าถัดไป อ่านผลจากตารางด้านล่าง ไม่กด Write Changes เพื่อแก้ข้อมูลข้ามขั้นตอนเว็บ'),
{'type':'dbshot'},
text('ข้อควรทราบ',True),text('DB Browser เป็นเครื่องมือเปิดไฟล์ SQLite ไม่ใช่ตัวเปิดเว็บ ราคาหลักเก็บเป็นสตางค์ เช่น price = 9500 คือ 95.00 บาท ไม่ใช่ 9,500 บาท ภาพและข้อมูลในส่วนนี้เป็นข้อมูลสาธิต')])

page('6.6  ตรวจความเชื่อมโยงข้อมูลจากเลขบิล ( ต่อ )','ตัวอย่างนี้อ่านข้อมูลจาก SQLite สาธิตจริงด้วยคำสั่ง SELECT เท่านั้น เลขบิล 1001 เชื่อมโต๊ะ T01 กับรายการอาหารสองรายการ ไม่ใช่ข้อมูลการขายของลูกค้าจริง',[
text('คำสั่งตัวอย่างในแท็บ Execute SQL',True),
text('SELECT o.id, t.name, i.name, i.qty, i.price, i.qty*i.price\nFROM orders o\nJOIN tables t ON t.id=o.table_id\nJOIN items i ON i.order_id=o.id\nWHERE o.id=1001;'),
tab(['บิล','โต๊ะ','รายการ','จำนวน','ราคา','รวม'],[[str(x) for x in row] for row in result],[42,42,165,57,78,84]),
text('อ่านผลอย่างไร',True),text('orders.id = 1001 เป็นรหัสบิล และ items.order_id = 1001 ทำให้ทราบว่าอาหารอยู่ในบิลใด ส่วน orders.table_id เชื่อม tables.id เพื่อแสดงชื่อโต๊ะ T01'),
text('ราคาและผลรวมในตารางยังเป็นสตางค์ แถวแรก 9500 × 2 = 19000 คือ 190.00 บาท แถวที่สอง 3000 × 1 = 3000 คือ 30.00 บาท รวมรายการ 220.00 บาทก่อนส่วนลด ค่าบริการ และภาษี'),
text('หากต้องดูโต๊ะร่วม ให้เชื่อม table_assignments กับ orders เพิ่มเติม เพราะ orders.table_id คือโต๊ะหลักและไม่แทนรายชื่อทุกโต๊ะที่ใช้ร่วมกัน การดู orders.total ของบิลเปิดยังไม่ใช่ยอดที่ยืนยันรับชำระแล้ว')])

page('6.7  รายละเอียดหน้าจองโต๊ะสำหรับผู้เริ่มต้น','อ่านประกอบภาพในหน้า 9–10 เส้นทางคือ หน้าลูกค้า > จองโต๊ะ > เลือกวันเวลาและคน > ดูโต๊ะว่าง > เลือกโต๊ะ > กรอกข้อมูลและยืนยัน',[
tab(['ช่องหรือปุ่ม','กรอกหรือใช้อย่างไร','สิ่งที่ควรเห็น'],[
['วันและเวลาที่จะมา','เลือกเวลามาร้านล่วงหน้าอย่างน้อย 15 นาทีและไม่เกิน 90 วัน','ระบบค้นช่วงจองครั้งละ 2 ชั่วโมงตามเวลาร้าน'],
['จำนวนคน','กรอกจำนวนเต็มตามที่จะมา หากที่นั่งไม่พอ ให้เลือกโต๊ะอื่นหรือสอบถามร้าน','โต๊ะที่รองรับไม่พอจะเลือกไม่ได้'],
['ดูโต๊ะว่าง','กดหลังเลือกวันเวลาและจำนวนคน หากเปลี่ยนข้อมูลให้ค้นใหม่','แสดงผังหรือรายการโต๊ะพร้อมคำอธิบายสถานะ'],
['โต๊ะที่ต้องการ','แตะโต๊ะที่แสดงว่าจองได้ แล้วอ่านชื่อโต๊ะที่เลือก','แสดงชื่อโต๊ะที่เลือกถูกต้อง'],
['ชื่อและเบอร์โทร','กรอกชื่อสำหรับแจ้งร้านกับเบอร์ที่ติดต่อได้จริง หมายเหตุใช้แจ้งคำขอเพิ่มเติม','กรอกช่องที่จำเป็นครบก่อนส่ง'],
['เงื่อนไขและยืนยัน','อ่านเงื่อนไขมัดจำและความยินยอม แล้วกดยืนยันหนึ่งครั้ง','เห็นรหัสจองและขั้นตอนชำระมัดจำถ้ามี']],[98,230,140]),
text('ผลหลังบันทึก',True),text('มีรหัสจองใช้ติดต่อร้าน แต่ยังไม่เปิดโต๊ะหรือสร้างบิลอาหาร หากมัดจำรอแจ้งโอน ให้ส่งหลักฐานต่อในหน้า 11 และเก็บรหัสไว้ เปิดด้วยเบราว์เซอร์เดิมเพื่อติดตามหน้า 12'),
text('กรณีไม่สำเร็จ',True),text('ถ้าโต๊ะถูกจองก่อนหรือข้อมูลเก่า ให้ค้นโต๊ะว่างใหม่ ไม่กดส่งซ้ำโดยไม่ตรวจรหัสจองหรือข้อความสำเร็จ')])
page('6.7  รายละเอียดการแนบสลิปมัดจำ ( ต่อ )','อ่านประกอบภาพหน้า 11 และตารางสถานะหน้า 41 เส้นทางคือ จองโต๊ะ > เปิดรายละเอียดการจอง > ตรวจยอดและข้อมูลผู้รับ > ส่งสลิปหรือเลขอ้างอิง',[
tab(['ช่องหรือปุ่ม','กรอกหรือใช้อย่างไร','สิ่งที่ควรเห็น'],[
['ยอด / ผู้รับโอน','อ่านยอด วันหมดเวลา ชื่อผู้รับ และเงื่อนไขของการจองนั้นก่อนโอน','ยอดตรงกับการจอง ไม่ใช้ยอดในภาพตัวอย่าง'],
['แนบสลิปโอนมัดจำ','เลือกภาพ JPG, PNG หรือ WebP ไม่เกิน 5 MB ที่เห็นรายละเอียดชัด','ชื่อไฟล์ที่เลือกหรือหลักฐานที่ส่งแล้ว'],
['เลขอ้างอิง / เวลาโอน','กรอกเลขอ้างอิงหรือข้อมูลรายการโอน ถ้ากรอกต้องยาว 6–160 ตัวอักษร','ใช้ช่วยผู้จัดการเทียบกับเงินเข้า'],
['ส่งสลิป / แจ้งโอน','ต้องแนบรูปหรือกรอกเลขอ้างอิงอย่างน้อยหนึ่งอย่าง ไม่จำเป็นต้องส่งซ้ำเมื่อสำเร็จ','ขึ้นสถานะรอตรวจยอดโอน'],
['ผลตรวจจากร้าน','กลับดูสถานะเดิม เมื่อผู้จัดการตรวจเงินแล้วจึงยืนยัน','ยืนยันมัดจำแล้ว หรือคำแนะนำให้ส่งใหม่']],[98,230,140]),
text('ฝั่งผู้จัดการทำอะไรต่อ',True),text('เปิดการจองโต๊ะ > ตรวจมัดจำ > เลือกรายการ > เปิดสลิป > ตรวจยอดเงินจริงและข้อมูลอ้างอิง > บันทึกผลตรวจ เมื่อรับลูกค้าให้ใช้ รับลูกค้า / เปิดโต๊ะ ไม่เปิดโต๊ะใหม่ซ้ำ'),
text('หากหมดเวลา ให้ติดต่อร้านก่อนโอน หากหลักฐานยังรอตรวจ การส่งสลิปไม่ถือว่าเงินเข้าหรือได้รับการยืนยัน และระบบนี้ไม่ตรวจสลิปกับธนาคารอัตโนมัติ')])
page('6.7  รายละเอียดหน้ารับชำระและใบเสร็จ ( ต่อ )','อ่านประกอบภาพหน้า 18–20 และตัวอย่างคำนวณหน้า 42 ผู้รับชำระต้องมีสิทธิ์ เปิดกะ และตรวจว่ารายการอาหารเสิร์ฟครบก่อนเริ่ม',[
tab(['ช่องหรือปุ่ม','กรอกหรือใช้อย่างไร','ผลที่ต้องตรวจ'],[
['ยอดบิล / คงเหลือ','อ่านยอดล่าสุด ตรวจส่วนลด ค่าบริการ ภาษี และมัดจำก่อนรับเงิน','ใช้ยอดคงเหลือเป็นยอดรับเพิ่ม ไม่หักมัดจำซ้ำ'],
['ยอดที่จ่ายครั้งนี้','กรอกยอดที่จะชำระในครั้งนั้น ไม่เกินยอดค้างของส่วนบิล','ใช้แบ่งรับชำระได้เมื่อบิลอยู่ในขั้นตอนที่รองรับ'],
['ช่องทาง','เลือกเงินสด โอน หรือช่องทางที่ร้านเปิดไว้ให้ตรงเงินจริง','เงินโอนต้องตรวจเงินเข้าและรับเท่ากับยอดชำระ'],
['รับเงิน','เงินสดกรอกตามที่ลูกค้ายื่น ใช้ปุ่ม +จำนวนเพื่อบวกเพิ่ม พอดีเพื่อเท่ายอด หรือ ล้างยอด เพื่อเริ่มใหม่','ตรวจเงินทอนก่อนกดบันทึก'],
['บันทึกรับชำระ','กดเมื่อรับเงินจริงแล้ว ตรวจประวัติก่อนทำซ้ำหากไม่แน่ใจ','ยอดค้างลดลงหรือเปิดใบเสร็จเมื่อครบยอด'],
['พิมพ์ใบเสร็จ','เลือก A4 หรือ 80 มม. ตรวจขนาดกระดาษและความชัด','เลขบิล รายการ ยอดสุทธิ ยอดรับ และเงินทอนตรง']],[98,230,140]),
text('ผลหลังชำระครบ',True),text('บิลเปลี่ยนเป็นชำระแล้ว โต๊ะรอทำความสะอาด พนักงานต้องทำความสะอาดจริงและกดยืนยันพร้อมใช้งานก่อนรับลูกค้ารอบใหม่ หากจ่ายไปบางส่วนให้ติดตามยอดค้าง ไม่ออกความเข้าใจว่าปิดบิลแล้ว'),
text('ต้องการเปลี่ยนรายการหลังยืนยันยอด ให้ตรวจข้อจำกัดในหน้าบิลก่อน หากรับเงินแล้วไม่แก้ยอดข้ามระบบหรือแก้ฐานข้อมูลเอง ให้ผู้จัดการตรวจประวัติและดำเนินการตามสิทธิ์')])

# All wrapping uses the platform's Thai dictionary rather than splitting marks.
strings=[]
def collect(o):
    if isinstance(o,str):strings.append(o)
    elif isinstance(o,list):
        for v in o:collect(v)
    elif isinstance(o,dict):
        for v in o.values():collect(v)
collect(PAGES)
(TMP/'strings.json').write_text(json.dumps(strings,ensure_ascii=False),encoding='utf-8')
js="const fs=require('fs');const a=JSON.parse(fs.readFileSync(process.argv[1],'utf8'));const s=new Intl.Segmenter('th',{granularity:'word'});fs.writeFileSync(process.argv[2],JSON.stringify(Object.fromEntries(a.map(t=>[t,[...s.segment(t)].map(x=>x.segment)]))));"
subprocess.run([str(NODE),'-e',js,str(TMP/'strings.json'),str(TMP/'segments.json')],check=True)
segments=json.loads((TMP/'segments.json').read_text(encoding='utf-8'))
def wrap(s,font,size,width):
    lines=[]
    for part in s.split('\n'):
        line=''
        toks=segments.get(part)
        if toks is None:
            # Reuse original segmentation then force explicit newlines.
            toks=part.split(' ');toks=[t+' ' for t in toks]
        for tok in toks:
            if line and pdfmetrics.stringWidth(line+tok,font,size)>width:lines.append(line.rstrip());line=tok.lstrip()
            else:line+=tok
        lines.append(line.rstrip())
    return lines
def lines(c,ss,x,y,font='S',size=16,leading=19.5,center=False):
    c.setFont(font,size);c.setFillColorRGB(0,0,0)
    for s in ss:
        (c.drawCentredString if center else c.drawString)(x,y-size*.8,s);y-=leading
    return y
def drawdiagram(c,d):
    H=d['height']
    for e in d['edges']:
        pts=e['points'];c.setStrokeColorRGB(.18,.18,.18);c.setLineWidth(.8)
        path=c.beginPath();path.moveTo(pts[0][0],H-pts[0][1])
        for x,y in pts[1:]:path.lineTo(x,H-y)
        c.drawPath(path)
        (x1,y1),(x2,y2)=pts[-2:];ang=math.atan2(y2-y1,x2-x1)
        for diff in [-.48,.48]:c.line(x2,H-y2,x2-5*math.cos(ang+diff),H-(y2-5*math.sin(ang+diff)))
        if e['label']:
            if e['at']:x,y=e['at']
            else:
                x=(x1+x2)/2;y=(y1+y2)/2-13
            ss=wrap(e['label'],'S',13,123);w=max(pdfmetrics.stringWidth(s,'S',13) for s in ss)+5
            c.setFillColorRGB(1,1,1);c.rect(x-w/2,H-y-len(ss)*15,w,len(ss)*15,stroke=0,fill=1)
            lines(c,ss,x,H-y,'S',13,15,True)
    for b in d['nodes']:
        x,y,w,h=b['x'],b['y'],b['w'],b['h'];c.setFillColorRGB(1,1,1);c.setStrokeColorRGB(0,0,0);c.setLineWidth(.8)
        if b['kind']=='process':c.roundRect(x,H-y-h,w,h,6,stroke=1,fill=1)
        else:c.rect(x,H-y-h,w,h,stroke=1,fill=1)
        if b['kind']=='store':c.line(x+8,H-y,x+8,H-y-h)
        ss=wrap(b['label'],'B' if b['kind'] in ['entity','process'] else 'S',14,w-14)
        lines(c,ss,x+w/2,H-y-(h-len(ss)*17)/2,'B' if b['kind'] in ['entity','process'] else 'S',14,17,True)

def render_table(c,b,y):
    for ri,row in enumerate([b['head']]+b['rows']):
        font='B' if ri==0 else 'S';wrapped=[wrap(t,font,16,w-10) for t,w in zip(row,b['widths'])];height=max(len(ss) for ss in wrapped)*19.5+8;x=72
        for w,ss in zip(b['widths'],wrapped):
            c.setFillColorRGB(*((.91,.9,.9) if ri==0 else (1,1,1)));c.setStrokeColorRGB(.85,.85,.85);c.setLineWidth(.5);c.rect(x,y-height,w,height,stroke=1,fill=1)
            lines(c,ss,x+5,y-4,font,16);x+=w
        y-=height
    return y-8

# Generate diagram assets as code-native vector PDF plus high-resolution PNG.
for pi,pg in enumerate(PAGES):
    for bi,b in enumerate(pg['blocks']):
        if b['type']!='diagram':continue
        buf=BytesIO();cc=canvas.Canvas(buf,pagesize=(468,b['height']));drawdiagram(cc,b);cc.save()
        f=TMP/f'diagram-{pi+43}.pdf';f.write_bytes(buf.getvalue())
        subprocess.run([str(POP),'-singlefile','-r','180','-png',str(f),str(f.with_suffix(''))],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        b['image']=str(f.with_suffix('.png'))

# Source-safe SQLite results stand in for a UI image only if no real capture exists.
dbshot=ROOT/'manual/screens-current/sqlite-browser-demo.jpg'
if not dbshot.exists():
    for pg in PAGES:
        pg['blocks']=[text('ภาพหน้าจอ DB Browser ยังไม่ได้แนบในฉบับนี้ ตำแหน่งที่ต้องใช้คือ File > Open Database Read Only, Browse Data > Table และ Execute SQL ให้ดูผลจากฐานข้อมูลสาธิตจริงในหน้าถัดไป') if b['type']=='dbshot' else b for b in pg['blocks']]
else:
    # Compose a document figure with vector callouts over the untouched capture.
    with Image.open(dbshot) as im:sw,sh=im.size
    shotbuf=BytesIO();sc=canvas.Canvas(shotbuf,pagesize=(sw,sh));sc.drawImage(str(dbshot),0,0,width=sw,height=sh)
    for i,(tx,ty,cx,cy) in enumerate([(166,92,275,54),(120,117,240,180),(282,191,410,240),(372,191,492,307),(946,650,813,586)],1):
        sc.setStrokeColorRGB(.81,.14,.14);sc.setFillColorRGB(1,1,1);sc.setLineWidth(3)
        dx,dy=tx-cx,ty-cy;l=math.hypot(dx,dy);sc.line(cx+18*dx/l,sh-(cy+18*dy/l),tx,sh-ty)
        for a in [-.45,.45]:
            ang=math.atan2(dy,dx)+a;sc.line(tx,sh-ty,tx-10*math.cos(ang),sh-(ty-10*math.sin(ang)))
        sc.circle(cx,sh-cy,18,fill=1,stroke=1);sc.setFillColorRGB(.81,.14,.14);sc.setFont('B',29);sc.drawCentredString(cx,sh-cy-8,str(i))
    sc.save();ann=TMP/'sqlite-callouts.pdf';ann.write_bytes(shotbuf.getvalue())
    subprocess.run([str(POP),'-singlefile','-r','130','-png',str(ann),str(ann.with_suffix(''))],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    for pg in PAGES:
        revised=[]
        for b in pg['blocks']:
            if b['type']=='dbshot':
                b.update(type='image',image=str(ann.with_suffix('.png')),height=230)
                revised += [b,text('จุดในภาพ 1 Browse Data   2 เลือก Table   3 ราคา ( สตางค์ )   4 สต็อกคงเหลือ   5 เปิดแบบ Read only')]
            else:revised.append(b)
        pg['blocks']=revised

buf=BytesIO();cc=canvas.Canvas(buf,pagesize=(612,792));bottoms=[]
for idx,pg in enumerate(PAGES):
    cc.setFont('S',16);cc.drawRightString(540,739,str(43+idx));y=720
    y=lines(cc,wrap(pg['title'],'B',18,468),72,y,'B',18)-12
    y=lines(cc,wrap(pg['intro'],'S',16,468),72,y)-10
    for b in pg['blocks']:
        if b['type']=='text':y=lines(cc,wrap(b['text'],'B' if b['bold'] else 'S',16,468),72,y,'B' if b['bold'] else 'S',16)-8
        elif b['type']=='table':y=render_table(cc,b,y)
        elif b['type']=='diagram':
            cc.saveState();cc.translate(72,y-b['height']);drawdiagram(cc,b);cc.restoreState();y-=b['height']+10
        elif b['type']=='image':
            with Image.open(b['image']) as im:iw,ih=im.size
            h=min(b['height'],468*ih/iw);w=h*iw/ih;cc.drawImage(b['image'],72+(468-w)/2,y-h,width=w,height=h);y-=h+10
    bottoms.append(round(y,1));cc.showPage()
cc.save();(TMP/'technical-pages.pdf').write_bytes(buf.getvalue())
print('New pages',len(PAGES),'bottoms',bottoms)
assert min(bottoms)>=54,('Page overflow',[(i+43,y) for i,y in enumerate(bottoms) if y<54])

# Append editable text and tables; diagrams remain embedded high-resolution images.
doc=Document(BD)
for idx,pg in enumerate(PAGES):
    br=doc.add_page_break();br.paragraph_format.line_spacing=Pt(1);br.paragraph_format.space_after=Pt(0);br.paragraph_format.space_before=Pt(0)
    for r in br.runs:r.font.size=Pt(1)
    pp=doc.add_paragraph(pg['title'],'Heading 2');pp.paragraph_format.space_after=Pt(12)
    bm=OxmlElement('w:bookmarkStart');bm.set(qn('w:id'),str(700+idx));bm.set(qn('w:name'),f'system_{idx}')
    en=OxmlElement('w:bookmarkEnd');en.set(qn('w:id'),str(700+idx));pp._p.insert(0,bm);pp._p.append(en)
    def para(s,bold=False):
        pp=doc.add_paragraph();pp.add_run(s).bold=bold;pp.paragraph_format.space_after=Pt(8);pp.paragraph_format.line_spacing=Pt(19.5);return pp
    para(pg['intro'])
    for b in pg['blocks']:
        if b['type']=='text':para(b['text'],b['bold'])
        elif b['type'] in ['diagram','image']:
            pp=doc.add_paragraph();pp.paragraph_format.space_after=Pt(10);pp.paragraph_format.line_spacing=1
            if b['type']=='diagram':pp.add_run().add_picture(b['image'],width=Pt(468),height=Pt(b['height']))
            else:
                pp.alignment=WD_ALIGN_PARAGRAPH.CENTER
                with Image.open(b['image']) as im:iw,ih=im.size
                h=min(b['height'],468*ih/iw);pp.add_run().add_picture(b['image'],height=Pt(h))
        elif b['type']=='table':
            t=doc.add_table(rows=1,cols=len(b['head']));t.autofit=False
            for c,s in zip(t.rows[0].cells,b['head']):c.text=s
            for row in b['rows']:
                for c,s in zip(t.add_row().cells,row):c.text=s
            for ri,row in enumerate(t.rows):
                for c,w in zip(row.cells,b['widths']):
                    c.width=Pt(w);pr=c._tc.get_or_add_tcPr();bd=OxmlElement('w:tcBorders')
                    for ed in ['top','left','bottom','right']:
                        e=OxmlElement('w:'+ed);e.set(qn('w:val'),'single');e.set(qn('w:sz'),'4');e.set(qn('w:color'),'D9D9D9');bd.append(e)
                    pr.append(bd);sh=OxmlElement('w:shd');sh.set(qn('w:fill'),'E7E6E6' if ri==0 else 'FFFFFF');pr.append(sh)
                    for pp in c.paragraphs:
                        pp.paragraph_format.line_spacing=Pt(19.5);pp.paragraph_format.space_after=Pt(2)
                        for r in pp.runs:r.bold=ri==0
                rp=row._tr.get_or_add_trPr();rp.append(OxmlElement('w:cantSplit'))
                if ri==0:rp.append(OxmlElement('w:tblHeader'))
            para('')

# A fourth contents leaf follows the existing third contents page.
boundary=None
for pp in doc.paragraphs:
    sp=pp._p.xpath('./w:pPr/w:sectPr')
    if sp and pp._p.getprevious() is not None and '5.5' in ''.join(pp._p.getprevious().itertext()):boundary=pp;break
assert boundary is not None
anchor=boundary._p;tocnodes=[]
def tp(s,style=None):
    pp=doc.add_paragraph(s,style);tocnodes.append(pp._p);return pp
tochead=tp('สารบัญ ( ต่อ )','Heading 1');tochead.alignment=WD_ALIGN_PARAGRAPH.CENTER;tochead.paragraph_format.space_after=Pt(27.5)
tocsub=tp('แผนภาพระบบและคำอธิบายเพิ่มเติม','Cover Body');tocsub.paragraph_format.space_after=Pt(6)
for r in tocsub.runs:r.bold=True
entries=[(0,'6.1 วิธีอ่านแผนภาพและแหล่งเก็บข้อมูล'),(1,'6.2 แผนภาพภาพรวมระบบ Context Diagram'),(2,'6.3 แผนภาพการไหลข้อมูล Diagram 0'),(5,'6.4 แผนภาพย่อยงานสำคัญ Child Diagram'),(8,'6.5 ความสัมพันธ์ข้อมูล ER Diagram'),(10,'6.6 เปิดดู SQLite และตรวจเลขบิล'),(12,'6.7 รายละเอียดช่องกรอกและผลการทำงาน')]
for idx,label in entries:
    pp=tp(label+'\t');pp.paragraph_format.space_after=Pt(5);pp.paragraph_format.line_spacing=Pt(24.5)
    pp.paragraph_format.tab_stops.add_tab_stop(Pt(384),WD_TAB_ALIGNMENT.RIGHT)
    fld=OxmlElement('w:fldSimple');fld.set(qn('w:instr'),f'PAGEREF system_{idx} \\h')
    rr=OxmlElement('w:r');tt=OxmlElement('w:t');tt.text=str(43+idx);rr.append(tt);fld.append(rr);pp._p.append(fld)
end=tp('');sec=deepcopy(boundary._p.xpath('./w:pPr/w:sectPr')[0])
for old in list(sec.findall(qn('w:headerReference'))):sec.remove(old)
hp=HeaderPart.new(doc.part.package);rid=doc.part.relate_to(hp,RT.HEADER);ref=OxmlElement('w:headerReference');ref.set(qn('w:type'),'default');ref.set(qn('r:id'),rid);sec.insert(0,ref)
ha=hp.element.find(qn('w:p'));pr=ha.get_or_add_pPr();jc=OxmlElement('w:jc');jc.set(qn('w:val'),'right');pr.append(jc);rr=OxmlElement('w:r');tt=OxmlElement('w:t');tt.text='ง';rr.append(tt);ha.append(rr)
end._p.get_or_add_pPr().append(sec)
for el in tocnodes:el.getparent().remove(el);anchor.addnext(el);anchor=el
doc.core_properties.subject='คู่มือพร้อม DFD และ ER Diagram ตรวจโครงสร้าง 30 ตุลาคม 2569'
for sec in doc.sections:
    for hp2 in sec.header.paragraphs:
        if hp2.text.strip() in ['ก','ข','ค','ง']:hp2.alignment=WD_ALIGN_PARAGRAPH.RIGHT
doc.save(DOC)

tocbuf=BytesIO();tc=canvas.Canvas(tocbuf,pagesize=(612,792));tc.setFont('S',16);tc.drawRightString(504,739,'ง');tc.setFont('B',22);tc.drawCentredString(306,663,'สารบัญ ( ต่อ )');tc.setFont('B',18);tc.drawString(108,616,'แผนภาพระบบและคำอธิบายเพิ่มเติม');tc.setFont('S',16)
for i,(idx,label) in enumerate(entries):tc.drawString(120,589-i*27,label);tc.drawRightString(504,589-i*27,str(43+idx))
tc.save()
base=PdfReader(BP);w=PdfWriter()
for p in base.pages[:6]:w.add_page(p)
w.add_page(PdfReader(tocbuf).pages[0])
for p in base.pages[6:]:w.add_page(p)
for p in PdfReader(buf).pages:w.add_page(p)
w.add_metadata({'/Title':'คู่มือการใช้งานและแผนภาพระบบ JUPITER','/Author':'นายกลภพ ราศรีนวล'})
for i,(idx,label) in enumerate(entries):w.add_outline_item(label,49+idx)
with PDF.open('wb') as f:w.write(f)
(TMP/'pages.json').write_text(json.dumps(PAGES,ensure_ascii=False,indent=2),encoding='utf-8')
print('Final PDF pages',len(w.pages),'DB Browser capture',dbshot.exists())
