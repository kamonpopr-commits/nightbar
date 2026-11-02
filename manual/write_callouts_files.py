"""File-only native Word/PDF annotations; no bitmap editing or application launch."""
from pathlib import Path
from io import BytesIO
from zipfile import ZipFile,ZIP_DEFLATED
import json,math,uuid
from lxml import etree
import pdfplumber
from pypdf import PdfReader,PdfWriter
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from figure_callouts import CALLOUTS

ROOT=Path(__file__).resolve().parents[1]
DOC=ROOT/'output/docx/JUPITER_User_Manual.docx'
PDF=ROOT/'output/pdf/JUPITER_User_Manual.pdf'
MANIFEST=json.loads((ROOT/'tmp/manual/callouts.json').read_text(encoding='utf-8'))
NS={'v':'urn:schemas-microsoft-com:vml','w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','o':'urn:schemas-microsoft-com:office:office','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
RED='#ce2323'
pdfmetrics.registerFont(TTFont('Sarabun',str(ROOT/'manual/fonts/THSarabunPSK-Regular.ttf')))
pdfmetrics.registerFont(TTFont('SarabunBold',str(ROOT/'manual/fonts/THSarabunPSK-Bold.ttf')))

def v(tag,**attrs):
    return etree.Element('{'+NS['v']+'}'+tag,attrib={k:str(val) for k,val in attrs.items()},nsmap=NS)

def style(x,y,w,h,extra=''):
    return f'position:absolute;margin-left:{x:.3f}pt;margin-top:{y:.3f}pt;width:{max(w,.1):.3f}pt;height:{max(h,.1):.3f}pt;z-index:251659000;mso-position-horizontal-relative:page;mso-position-vertical-relative:page;{extra}'

def textbox(text,size=14,bold=False,center=False):
    box=v('textbox',inset='0,0,0,0')
    content=OxmlElement('w:txbxContent')
    for line in text.split('\n'):
        p=OxmlElement('w:p');pr=OxmlElement('w:pPr')
        jc=OxmlElement('w:jc');jc.set(qn('w:val'),'center' if center else 'left');pr.append(jc)
        spacing=OxmlElement('w:spacing')
        for k,value in [('before','0'),('after','0'),('line',str(240 if center else 340)),('lineRule','exact')]:spacing.set(qn('w:'+k),value)
        pr.append(spacing);p.append(pr)
        r=OxmlElement('w:r');rp=OxmlElement('w:rPr');fonts=OxmlElement('w:rFonts')
        for k in ['ascii','hAnsi','eastAsia','cs']:fonts.set(qn('w:'+k),'TH Sarabun PSK')
        rp.append(fonts)
        for tag,value in [('sz',str(size*2)),('szCs',str(size*2)),('color','CE2323' if center else '000000')]:
            el=OxmlElement('w:'+tag);el.set(qn('w:val'),value);rp.append(el)
        if bold:
            rp.append(OxmlElement('w:b'));rp.append(OxmlElement('w:bCs'))
        r.append(rp);t=OxmlElement('w:t');t.text=line;r.append(t);p.append(r);content.append(p)
    box.append(content);return box

def insert_shape(p,shape):
    r=p.add_run();pic=OxmlElement('w:pict');pic.append(shape);r._r.append(pic)

def legend_lines(points,width,column=False):
    lines=['จุดในภาพ']
    for n,p in enumerate(points,1):
        text=str(n)+' '+p[0]
        if column or len(lines)==1 or pdfmetrics.stringWidth(lines[-1]+'   /   '+text,'Sarabun',14)>width:
            lines.append(text)
        else:lines[-1]+='   /   '+text
    return lines

def add_fonts(path):
    with ZipFile(path) as z:data={n:z.read(n) for n in z.namelist()}
    root=etree.fromstring(data['word/fontTable.xml'])
    family=etree.SubElement(root,qn('w:font'));family.set(qn('w:name'),'TH Sarabun PSK')
    relns='http://schemas.openxmlformats.org/package/2006/relationships'
    relname='word/_rels/fontTable.xml.rels'
    rels=etree.fromstring(data[relname]) if relname in data else etree.Element('{'+relns+'}Relationships',nsmap={None:relns})
    for ident,filename,tag in [('Regular','THSarabunPSK-Regular.ttf','embedRegular'),('Bold','THSarabunPSK-Bold.ttf','embedBold')]:
        guid=uuid.uuid4();key=guid.bytes[::-1];raw=bytearray((ROOT/'manual/fonts'/filename).read_bytes())
        original=bytes(raw[:32])
        for i in range(32):raw[i]^=key[i%16]
        assert bytes(raw[i]^key[i%16] for i in range(32))==original
        target='fonts/Jupiter'+ident+'.odttf';data['word/'+target]=bytes(raw)
        rid='rIdJupiter'+ident
        e=etree.SubElement(family,qn('w:'+tag));e.set(qn('r:id'),rid);e.set(qn('w:fontKey'),'{'+str(guid).upper()+'}')
        etree.SubElement(rels,'{'+relns+'}Relationship',Id=rid,Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/font',Target=target)
    data['word/fontTable.xml']=etree.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True)
    data[relname]=etree.tostring(rels,xml_declaration=True,encoding='UTF-8',standalone=True)
    ct=etree.fromstring(data['[Content_Types].xml']);ctns='http://schemas.openxmlformats.org/package/2006/content-types'
    if not any(e.get('Extension')=='odttf' for e in ct):etree.SubElement(ct,'{'+ctns+'}Default',Extension='odttf',ContentType='application/vnd.openxmlformats-officedocument.obfuscatedFont')
    data['[Content_Types].xml']=etree.tostring(ct,xml_declaration=True,encoding='UTF-8',standalone=True)
    settings=etree.fromstring(data['word/settings.xml'])
    for tag in ['embedTrueTypeFonts','saveSubsetFonts']:
        el=settings.find(qn('w:'+tag))
        if el is None:el=etree.SubElement(settings,qn('w:'+tag))
        el.set(qn('w:val'),'1' if tag=='embedTrueTypeFonts' else '0')
    data['word/settings.xml']=etree.tostring(settings,xml_declaration=True,encoding='UTF-8',standalone=True)
    with ZipFile(path,'w',ZIP_DEFLATED) as z:
        for name,value in data.items():z.writestr(name,value)

def build():
    doc=Document(DOC)
    paragraphs={}
    for p in doc.paragraphs:
        for drawing in p._p.findall('.//'+qn('wp:docPr')):
            descr=drawing.get('descr','')
            if descr.startswith('ภาพหน้าจอระบบสาธิต '):paragraphs[descr.split(' ')[-1]]=p
    overlays={};num=0
    with pdfplumber.open(ROOT/'tmp/manual/callout-base.pdf') as ref:
        for m in MANIFEST:
            m['points']=CALLOUTS[m['screen']]
            page=ref.pages[m['page']-1]
            p=paragraphs[m['screen']]
            # A clearer booking form replaces only the old illustration, using
            # the same paragraph footprint; all body paragraphs stay in place.
            if m['screen']=='booking':
                from PIL import Image
                im=Image.open(ROOT/'manual/screens-current/booking.png')
                m['original_height']=m['height'];m['height']=m['width']*im.height/im.width
            column=m['width']<270
            if column:
                lx=72;ly=m['y']+15;lw=max(100,m['x']-82)
            else:
                lx=108;ly=max(c['bottom'] for c in page.chars if c['text'].strip())+12;lw=396
            lines=legend_lines(m['points'],lw,column)
            lh=17*len(lines)+4
            assert ly+lh<782,(m['screen'],ly,lh)
            m['legend']={'x':lx,'y':ly,'width':lw,'height':lh,'lines':lines}
            buf=BytesIO();c=canvas.Canvas(buf,pagesize=(612,792))
            if m['screen']=='booking':
                c.setFillColorRGB(1,1,1);c.rect(m['x'],792-m['y']-m['original_height'],m['width'],m['original_height'],fill=1,stroke=0)
                c.drawImage(ImageReader(str(ROOT/'manual/screens-current/booking.png')),m['x'],792-m['y']-m['height'],width=m['width'],height=m['height'])
            c.setStrokeColorRGB(.81,.14,.14);c.setLineWidth(1.4)
            for i,point in enumerate(m['points'],1):
                _,tx,ty,cx,cy=point
                tx=m['x']+tx*m['width'];ty=m['y']+ty*m['height'];cx=m['x']+cx*m['width'];cy=m['y']+cy*m['height']
                dx=tx-cx;dy=ty-cy;length=math.hypot(dx,dy);sx=cx+7*dx/length;sy=cy+7*dy/length
                c.line(sx,792-sy,tx,792-ty)
                ux=dx/length;uy=dy/length;bx=tx-5*ux;by=ty-5*uy
                path=c.beginPath();path.moveTo(tx,792-ty);path.lineTo(bx-2.5*uy,792-(by+2.5*ux));path.lineTo(bx+2.5*uy,792-(by-2.5*ux));path.close()
                c.setFillColorRGB(.81,.14,.14);c.drawPath(path,fill=1,stroke=0)
                c.setFillColorRGB(1,1,1);c.circle(cx,792-cy,7,fill=1,stroke=1)
                c.setFillColorRGB(.81,.14,.14);c.setFont('SarabunBold',14);c.drawCentredString(cx,792-cy-4,str(i))
                ax=0 if sx<=tx else 21600;ay=0 if sy<=ty else 21600
                arrow=v('shape',id=f'JupiterArrow{num}',style=style(min(sx,tx),min(sy,ty),abs(tx-sx),abs(ty-sy)),coordsize='21600,21600',path=f'm {ax},{ay} l {21600-ax},{21600-ay} e',filled='f',strokecolor=RED,strokeweight='1.4pt')
                arrow.append(v('stroke',endarrow='block',endarrowlength='short',endarrowwidth='narrow'));insert_shape(p,arrow)
                circle=v('oval',id=f'JupiterNumber{num}',style=style(cx-7,cy-7,14,14,'v-text-anchor:middle;'),fillcolor='white',strokecolor=RED,strokeweight='1.3pt')
                circle.append(textbox(str(i),14,True,True));insert_shape(p,circle);num+=1
            c.setFillColorRGB(0,0,0);c.setFont('Sarabun',14)
            for i,line in enumerate(lines):c.drawString(lx,792-ly-13-17*i,line)
            legend=v('rect',id='JupiterLegend'+m['screen'],style=style(lx,ly,lw,lh),filled='f',stroked='f')
            legend.append(textbox('\n'.join(lines),14));insert_shape(p,legend)
            c.save();buf.seek(0);overlays[m['page']-1]=PdfReader(buf)
    doc.save(DOC);add_fonts(DOC)
    reader=PdfReader(ROOT/'tmp/manual/callout-base.pdf');writer=PdfWriter();writer.clone_document_from_reader(reader)
    for i,page in enumerate(writer.pages):
        if i in overlays:page.merge_page(overlays[i].pages[0])
    with PDF.open('wb') as f:writer.write(f)
    (ROOT/'tmp/manual/callouts-final.json').write_text(json.dumps(MANIFEST,ensure_ascii=False),encoding='utf-8')
    print('Annotated',len(MANIFEST),'figures with',num,'editable callouts; pages',len(writer.pages))

if __name__=='__main__':build()
