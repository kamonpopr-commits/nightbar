"""Create a dedicated test table and local QR images; no sale is created."""
import sys, json, struct, zlib
from pathlib import Path
from urllib.parse import urlencode
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'vendor'))
import app, customer, qrcode
from qrcode.image.svg import SvgPathFillImage

def png(matrix,path,scale=8):
    size=len(matrix)*scale
    rows=[]
    for row in matrix:
        line=b'\0'+b''.join((b'\0' if bit else b'\xff')*scale for bit in row)
        rows.extend([line]*scale)
    def chunk(tag,data):
        return struct.pack('!I',len(data))+tag+data+struct.pack('!I',zlib.crc32(tag+data)&0xffffffff)
    path.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!IIBBBBB',size,size,8,0,0,0,0))+chunk(b'IDAT',zlib.compress(b''.join(rows)))+chunk(b'IEND',b''))

if __name__=='__main__':
    base=sys.argv[1].rstrip('/')
    app.initialize()
    with app.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute("INSERT OR IGNORE INTO tables(name,seats) VALUES ('DEMO',4)")
        tid=db.execute("SELECT id FROM tables WHERE name='DEMO'").fetchone()[0]
        order=db.execute("SELECT id FROM orders WHERE table_id=? AND status='open'",(tid,)).fetchone()
        oid=order[0] if order else db.execute('INSERT INTO orders(table_id,opened,note) VALUES (?,?,?)',(tid,app.now(),'โต๊ะสำหรับทดลอง QR')).lastrowid
        token=customer.ensure_visit(db,oid)
        db.execute("UPDATE settings SET value=? WHERE key='customer_url'",(base,))
    out=ROOT/'qr-demo'; out.mkdir(exist_ok=True)
    for name,url in [('menu',base+'/menu'),('table-demo',base+'/menu?'+urlencode({'visit':token}))]:
        qr=qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M,border=4)
        qr.add_data(url); qr.make(fit=True)
        png(qr.get_matrix(),out/(name+'.png'))
        qr.make_image(image_factory=SvgPathFillImage).save(out/(name+'.svg'))
    (out/'info.json').write_text(json.dumps({'table':'DEMO','order_id':oid,'url':base+'/menu?'+urlencode({'visit':token})},ensure_ascii=False,indent=2),encoding='utf8')
    print(f'QR ready: table DEMO, bill #{oid}; menu URL: {base}/menu')
