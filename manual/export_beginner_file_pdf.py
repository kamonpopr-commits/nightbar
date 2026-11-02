"""Render the added chapter directly; preserve the verified original PDF pages."""
from pathlib import Path
from io import BytesIO
import json,subprocess
from docx import Document
from docx.text.paragraph import Paragraph
from docx.table import Table
from docx.oxml.ns import qn
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pypdf import PdfReader,PdfWriter
from lxml import etree
from zipfile import ZipFile,ZIP_DEFLATED

ROOT=Path(__file__).resolve().parents[1]
DOC=ROOT/'output/docx/JUPITER_User_Manual.docx'
PDF=ROOT/'output/pdf/JUPITER_User_Manual.pdf'
TMP=ROOT/'tmp/manual'
doc=Document(DOC)
pages=[[]];active=False;texts=[]
for e in doc.element.body:
    if e.tag==qn('w:p'):
        p=Paragraph(e,doc)
        if p.text.startswith('5.1  เริ่มอ่าน') and p.style.name=='Heading 2':active=True
        if not active:continue
        if e.xpath('.//w:br[@w:type="page"]'):
            if pages[-1]:pages.append([])
            continue
        if not p.text:continue
        size=18 if p.style.name=='Heading 2' else 16
        b={'kind':'p','text':p.text,'bold':size==18 or any(r.bold for r in p.runs),'size':size,
           'before':p.paragraph_format.space_before.pt if p.paragraph_format.space_before else 0,
           'after':p.paragraph_format.space_after.pt if p.paragraph_format.space_after else 0,
           'indent':p.paragraph_format.left_indent.pt if p.paragraph_format.left_indent else 0}
        pages[-1].append(b);texts.append(p.text)
    elif active and e.tag==qn('w:tbl'):
        t=Table(e,doc);rows=[[c.text for c in row.cells] for row in t.rows]
        b={'kind':'table','rows':rows,'widths':[c.width.pt for c in t.rows[0].cells]};pages[-1].append(b)
        texts.extend(x for row in rows for x in row)
assert len(pages)==6,len(pages)
segment_input=TMP/'beginner-strings.json';segment_input.write_text(json.dumps(texts,ensure_ascii=False),encoding='utf-8')
node=Path(r'C:\Users\TUF GAMING\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe')
js=r"const fs=require('fs');const a=JSON.parse(fs.readFileSync(process.argv[1],'utf8'));const s=new Intl.Segmenter('th',{granularity:'word'});function seg(t){const out=[];let p=0;for(const m of t.matchAll(/py -3 --version|py -3 -m pip install -r requirements\.txt|http:\/\/[^\s]+/g)){out.push(...[...s.segment(t.slice(p,m.index))].map(x=>x.segment),m[0]);p=m.index+m[0].length}out.push(...[...s.segment(t.slice(p))].map(x=>x.segment));return out}fs.writeFileSync(process.argv[2],JSON.stringify(Object.fromEntries(a.map(t=>[t,seg(t)]))));"
segout=TMP/'beginner-segments.json'
subprocess.run([str(node),'-e',js,str(segment_input),str(segout)],check=True)
tokens=json.loads(segout.read_text(encoding='utf-8'))
for face,f in [('Sarabun','THSarabunPSK-Regular.ttf'),('SarabunBold','THSarabunPSK-Bold.ttf')]:
    pdfmetrics.registerFont(TTFont(face,str(ROOT/'manual/fonts'/f)))

def wrap(text,font,size,width):
    lines=[];line=''
    for tok in tokens.get(text,[text]):
        tok=tok.replace('\t','   ')
        if line and pdfmetrics.stringWidth(line+tok,font,size)>width:
            lines.append(line.rstrip());line=tok.lstrip()
        else:line+=tok
    if line:lines.append(line.rstrip())
    return lines or ['']

def textlines(c,lines,x,y,font,size,leading=19.5):
    c.setFont(font,size);c.setFillColorRGB(0,0,0)
    for line in lines:c.drawString(x,y-size*.78,line);y-=leading
    return y

stream=BytesIO();c=canvas.Canvas(stream,pagesize=(612,792));bottoms=[]
for idx,blocks in enumerate(pages):
    c.setFont('Sarabun',16);c.drawRightString(540,739,str(37+idx));y=720
    for b in blocks:
        if b['kind']=='p':
            font='SarabunBold' if b['bold'] else 'Sarabun';y-=b['before']
            # Match numbered paragraphs with a hanging number and readable wrap.
            text=b['text'];indent=b['indent']
            lines=wrap(text,font,b['size'],468-indent)
            y=textlines(c,lines,72+indent,y,font,b['size']);y-=b['after']
        else:
            widths=b['widths']
            for ri,row in enumerate(b['rows']):
                font='SarabunBold' if ri==0 else 'Sarabun'
                wrapped=[wrap(t,font,16,w-9) for t,w in zip(row,widths)]
                height=max(len(lines) for lines in wrapped)*19.5+7
                x=72
                for j,(w,lines) in enumerate(zip(widths,wrapped)):
                    c.setFillColorRGB(*((.906,.902,.902) if ri==0 else (1,1,1)))
                    c.setStrokeColorRGB(.85,.85,.85);c.setLineWidth(.5);c.rect(x,y-height,w,height,stroke=1,fill=1)
                    yy=y-(height-len(lines)*19.5)/2
                    textlines(c,lines,x+4.5,yy,font,16);x+=w
                y-=height
    bottoms.append(y);c.showPage()
c.save()
assert min(bottoms)>=54,('Content exceeds page area',bottoms)
(TMP/'beginner-added.pdf').write_bytes(stream.getvalue())

# Render the third contents page with the same font, top margin, and page labels.
toc=BytesIO();c=canvas.Canvas(toc,pagesize=(612,792));c.setFont('Sarabun',16);c.drawRightString(504,739,'ค')
c.setFont('SarabunBold',22);c.drawCentredString(306,663,'สารบัญ ( ต่อ )')
c.setFont('SarabunBold',18);c.drawString(108,616,'คำแนะนำเพิ่มเติมสำหรับผู้เริ่มใช้งาน')
titles=['เริ่มอ่านตามหน้าที่ของผู้ใช้งาน','ติดตั้งและเปิดระบบครั้งแรก','เงื่อนไขและเส้นทางก่อนทำรายการ','ความหมายสถานะและสิ่งที่ต้องทำต่อ','ตัวอย่างคำนวณเงินและตรวจใบเสร็จ']
c.setFont('Sarabun',16)
for i,(title,num) in enumerate(zip(titles,[37,38,39,40,42]),1):
    yy=589-(i-1)*24.5;c.drawString(120,yy,f'5.{i}  {title}');c.drawRightString(504,yy,str(num))
c.save()
w=PdfWriter();original=PdfReader(TMP/'before_beginner_extension.pdf')
for pg in original.pages[:5]:w.add_page(pg)
w.add_page(PdfReader(toc).pages[0])
for pg in original.pages[5:]:w.add_page(pg)
for pg in PdfReader(stream).pages:w.add_page(pg)
w.add_metadata({'/Title':'คู่มือการใช้งานเว็บ JUPITER','/Author':'นายกลภพ ราศรีนวล','/Subject':'ฉบับเพิ่มคำแนะนำสำหรับผู้เริ่มต้น'})
# Restore a usable outline for the consolidated file.
w.add_outline_item('สารบัญ',3)
for label,phys in [('การเตรียมใช้งาน',6),('สำหรับลูกค้า',10),('สำหรับพนักงานและผู้จัดการ',18),('ฐานข้อมูลและการดูแลระบบ',35),('คำแนะนำสำหรับผู้เริ่มต้น',42)]:w.add_outline_item(label,phys)
with PDF.open('wb') as f:w.write(f)

# Cache page references for readers that do not auto-update Word fields.
with ZipFile(DOC) as z:parts={n:z.read(n) for n in z.namelist()}
r=etree.fromstring(parts['word/document.xml']);ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
starts={1:0,2:4,3:12,4:29};extra=[37,38,39,40,42]
for fld in r.findall('.//w:fldSimple',ns):
    ins=fld.get(qn('w:instr'),'')
    if 'PAGEREF topic_' not in ins:continue
    key=ins.split('topic_')[1].split()[0];ch,n=map(int,key.split('_'))
    value=extra[n-1] if ch==5 else starts[ch]+n
    for child in list(fld):fld.remove(child)
    rr=etree.SubElement(fld,qn('w:r'));tt=etree.SubElement(rr,qn('w:t'));tt.text=str(value)
parts['word/document.xml']=etree.tostring(r,xml_declaration=True,encoding='UTF-8',standalone=True)
with ZipFile(DOC,'w',ZIP_DEFLATED) as z:
    for name,data in parts.items():z.writestr(name,data)
print('Pages',len(w.pages),'new-page bottom positions',bottoms)
