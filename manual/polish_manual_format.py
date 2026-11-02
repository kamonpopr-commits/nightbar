"""Normalize the existing manual while preserving screenshots and annotations."""
from pathlib import Path
from copy import deepcopy
import re,shutil
from docx import Document
from docx.shared import Pt,RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT,WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from figure_callouts import CALLOUTS

ROOT=Path(__file__).resolve().parents[1];TMP=ROOT/'tmp/manual/format';TMP.mkdir(exist_ok=True)
OUT=ROOT/'output/docx/JUPITER_User_Manual.docx';BASE=TMP/'before-format.docx'
if not BASE.exists():
    shutil.copy2(OUT,BASE);shutil.copy2(ROOT/'output/pdf/JUPITER_User_Manual.pdf',TMP/'before-format.pdf')
d=Document(BASE);FONT='TH Sarabun PSK';V='urn:schemas-microsoft-com:vml'
def fontstyle(st,size,bold=False):
    st.font.name=FONT;st.font.size=Pt(size);st.font.bold=bold;st.font.color.rgb=RGBColor(0,0,0)
    r=st.element.get_or_add_rPr();rf=r.find(qn('w:rFonts'))
    if rf is None:rf=OxmlElement('w:rFonts');r.insert(0,rf)
    rf.attrib.clear()
    for k in ['ascii','hAnsi','cs','eastAsia']:rf.set(qn('w:'+k),FONT)
    lang=r.find(qn('w:lang'))
    if lang is None:lang=OxmlElement('w:lang');r.append(lang)
    for k in ['val','eastAsia','bidi']:lang.set(qn('w:'+k),'th-TH')
    sz=r.find(qn('w:szCs'))
    if sz is None:sz=OxmlElement('w:szCs');r.append(sz)
    sz.set(qn('w:val'),str(size*2))
for name,size,bold in [('Normal',16,False),('Heading 1',22,True),('Heading 2',18,True)]:fontstyle(d.styles[name],size,bold)
for name,size,bold,lead in [('Manual Caption',16,False,19.5),('Manual Label',16,True,19.5)]:
    if name not in d.styles:d.styles.add_style(name,1)
    st=d.styles[name];fontstyle(st,size,bold);st.paragraph_format.line_spacing=Pt(lead);st.paragraph_format.left_indent=Pt(36)
    st.paragraph_format.space_before=Pt(6 if name=='Manual Label' else 4);st.paragraph_format.space_after=Pt(4 if name=='Manual Label' else 6)
    if name=='Manual Label':st.paragraph_format.keep_with_next=True

headings=[p for p in d.paragraphs if p.style.name=='Heading 2'];assert len(headings)==57
for i,p in enumerate(headings,1):
    bs=OxmlElement('w:bookmarkStart');bs.set(qn('w:id'),str(2000+i));bs.set(qn('w:name'),f'manual_page_{i}')
    be=OxmlElement('w:bookmarkEnd');be.set(qn('w:id'),str(2000+i));p._p.insert(0,bs);p._p.append(be)

# Replace floating legends with captions immediately below their screenshots.
for p in list(d.paragraphs):
    for el in list(p._p.iter()):
        if el.tag=='{'+V+'}rect' and 'JupiterLegend' in el.get('id',''):el.getparent().remove(el)
for p in list(d.paragraphs):
    pic=next((x for x in p._p.iter() if x.tag.endswith('}docPr') and (x.get('descr') or '').startswith('ภาพหน้าจอระบบสาธิต ')),None)
    if pic is None:continue
    screen=pic.get('descr').split()[-1]
    if screen not in CALLOUTS:continue
    cp=OxmlElement('w:p');p._p.addnext(cp)
    from docx.text.paragraph import Paragraph
    c=Paragraph(cp,d);c.style='Manual Caption'
    c.add_run('จุดในภาพ  ').bold=True
    c.add_run('   /   '.join(f'{i}\u00a0{point[0]}' for i,point in enumerate(CALLOUTS[screen],1)))
    # Keep the shorter booking replacement's actual image height; its old blank
    # footprint is no longer needed once captions participate in paragraph flow.
    p.paragraph_format.space_after=Pt(6)

body=False;had_method=False
for p in list(d.paragraphs):
    if p.style.name=='Heading 2':
        body=True;had_method=False;f=p.paragraph_format;f.left_indent=Pt(0);f.space_before=Pt(0);f.space_after=Pt(10);f.keep_with_next=True;f.line_spacing=Pt(19.5)
        for r in p.runs:r.bold=True;r.font.size=Pt(18);r.font.color.rgb=RGBColor(0,0,0)
        continue
    if not body:continue
    if p.style.name=='Heading 1':continue
    # Standalone page breaks should not acquire a normal-sized blank line.
    if p._p.xpath('.//w:br[@w:type="page"]') and not p.text.strip():
        f=p.paragraph_format;f.line_spacing=Pt(1);f.space_before=Pt(0);f.space_after=Pt(0)
        for r in p.runs:r.font.size=Pt(1)
        continue
    if p._p.xpath('.//w:drawing') or any(x.tag.startswith('{'+V+'}') for x in p._p.iter()):continue
    if p.style.name=='Manual Caption':continue
    if not p.text.strip():
        p.paragraph_format.line_spacing=Pt(1);p.paragraph_format.space_after=Pt(2);p.paragraph_format.space_before=Pt(0)
        continue
    f=p.paragraph_format;f.line_spacing=Pt(19.5);f.left_indent=Pt(36);f.right_indent=Pt(0);f.first_line_indent=Pt(0);f.space_after=Pt(3);f.space_before=Pt(0);f.widow_control=True
    s=p.text.strip()
    if 'อยู่ใกล้ ๆ' in s:
        for r in p.runs:r.text=r.text.replace('อยู่ใกล้ ๆ','อยู่ใกล้')
        s=p.text.strip()
    if re.match(r'^\d+\.[\t ]',s):
        if not had_method:
            hp=p.insert_paragraph_before('วิธีใช้งาน','Manual Label');had_method=True
        f.left_indent=Pt(54);f.first_line_indent=Pt(-18)
    if s.startswith('ผลการทำงาน : '):
        value=s.split(' : ',1)[1];p.clear();p.add_run('ผลการทำงาน  ').bold=True;p.add_run(value).bold=False;f.space_before=Pt(6)
    elif s.startswith('( ') and s.endswith(')'):
        value=s[2:-1].strip();p.clear();p.add_run('ข้อควรทราบ  ').bold=True;p.add_run(value).bold=False;f.space_before=Pt(6)
    elif all(r.bold for r in p.runs if r.text.strip()) and len(s)<95:
        if s=='ผลหลังบันทึก':s='ผลการทำงาน'
        elif s=='ผลหลังชำระครบ':s='ผลการทำงานหลังชำระครบ'
        elif s=='กรณีไม่สำเร็จ':s='ข้อควรทราบเมื่อทำรายการไม่สำเร็จ'
        p.text=s;p.style='Manual Label'
    for r in p.runs:r.font.name=FONT;r.font.size=Pt(16);r.font.color.rgb=RGBColor(0,0,0)

# Normalize tables using the intended cell widths, not an equal-width grid.
for t in d.tables:
    t.autofit=False;t.alignment=WD_TABLE_ALIGNMENT.CENTER
    widths=[c.width for c in t.rows[0].cells]
    for col,w in zip(t.columns,widths):
        if w:col.width=w
    for ri,row in enumerate(t.rows):
        tr=row._tr.get_or_add_trPr()
        if tr.find(qn('w:cantSplit')) is None:tr.append(OxmlElement('w:cantSplit'))
        for c,w in zip(row.cells,widths):
            if w:c.width=w
            c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            pr=c._tc.get_or_add_tcPr()
            for old in list(pr.findall(qn('w:tcMar'))):pr.remove(old)
            mar=OxmlElement('w:tcMar')
            for ed in ['top','bottom','left','right']:
                el=OxmlElement('w:'+ed);el.set(qn('w:w'),'60' if ed in ['top','bottom'] else '90');el.set(qn('w:type'),'dxa');mar.append(el)
            pr.append(mar)
            for p in c.paragraphs:
                f=p.paragraph_format;f.line_spacing=Pt(19.5);f.space_before=Pt(0);f.space_after=Pt(0);f.left_indent=Pt(0);f.right_indent=Pt(0);f.first_line_indent=Pt(0);f.widow_control=False
                for r in p.runs:r.font.name=FONT;r.font.size=Pt(16);r.bold=ri==0;r.font.color.rgb=RGBColor(0,0,0)

# Turn prose page references into native fields so repagination cannot make
# the quick-start guide and the new explanatory chapter point to stale pages.
pat=re.compile(r'หน้า\s+\d+(?:\s*[–-]\s*\d+)?(?:\s*(?:และ|,)\s*\d+(?:\s*[–-]\s*\d+)?)?')
allps=list(d.paragraphs)+[p for t in d.tables for row in t.rows for c in row.cells for p in c.paragraphs]
converted=0
for p in allps:
    s=p.text
    if not pat.search(s) or p.style.name in ['Title','Cover Body','Preface','Heading 1','Heading 2'] or p._p.xpath('.//w:drawing'):continue
    if p._p.xpath('.//w:instrText') or p._p.xpath('.//w:fldSimple'):continue
    matches=list(pat.finditer(s))
    if not all(1<=int(n)<=57 for m in matches for n in re.findall(r'\d+',m.group())):continue
    p.clear();pos=0
    for m in matches:
        p.add_run(s[pos:m.start()]);chunk=m.group();j=0
        for num in re.finditer(r'\d+',chunk):
            p.add_run(chunk[j:num.start()]);fld=OxmlElement('w:fldSimple');fld.set(qn('w:instr'),f'PAGEREF manual_page_{int(num.group())} \\h')
            rr=OxmlElement('w:r');tt=OxmlElement('w:t');tt.text=num.group();rr.append(tt);fld.append(rr);p._p.append(fld);j=num.end();converted+=1
        p.add_run(chunk[j:]);pos=m.end()
    p.add_run(s[pos:])
    if s.startswith('ข้อควรทราบ') or s.startswith('ผลการทำงาน'):
        # Rebuild only the short lead-in's emphasis without changing field runs.
        lead='ข้อควรทราบ' if s.startswith('ข้อควรทราบ') else 'ผลการทำงาน'
        first=p.runs[0]
        if first.text.startswith(lead):
            tail=first.text[len(lead):];first.text=lead;first.bold=True
            rr=deepcopy(first._r);rr.find(qn('w:t')).text=tail
            for bold in list(rr.findall('.//'+qn('w:b'))):bold.getparent().remove(bold)
            first._r.addnext(rr)

# Front matter retains the reference's typography and clean covers.
if not d.sections[0].header._element.xpath('.//w:drawing'):
    from build_reference_manual import floating_picture
    floating_picture(d.sections[0].header.paragraphs[0],ROOT/'tmp/manual/reference-assets/faculty-crest.png',245,108,122,122)
    for prop in d.sections[0].header._element.xpath('.//wp:docPr'):prop.set('id','9001')
for sec in d.sections:
    for p in sec.header.paragraphs:
        if p.text.strip() in ['ก','ข','ค','ง']:p.alignment=WD_ALIGN_PARAGRAPH.RIGHT
d.core_properties.subject='คู่มือฉบับเกลารูปแบบและการอ้างอิงหน้า 30 ตุลาคม 2569'
d.save(OUT)
print('Normalized 57 topic headings; moved 29 image legends; linked',converted,'page references')
