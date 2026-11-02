"""Private payment evidence stored transactionally with the booking."""
from datetime import datetime
import deposit_qr

def initialize(db):
    db.execute('''CREATE TABLE IF NOT EXISTS deposit_slips(id INTEGER PRIMARY KEY,reservation_id INTEGER NOT NULL REFERENCES reservations(id),mime TEXT NOT NULL,image BLOB NOT NULL,created TEXT NOT NULL)''')

def save(h,db,rid,raw):
    ext=deposit_qr.validate(raw)
    if db.execute('SELECT 1 FROM deposit_slips WHERE reservation_id=? AND image=?',(rid,raw)).fetchone():return
    if db.execute('SELECT COUNT(*) FROM deposit_slips WHERE reservation_id=?',(rid,)).fetchone()[0]>=10:raise ValueError('แนบสลิปครบ 10 รูปแล้ว กรุณาติดต่อร้าน')
    mime={'.jpg':'image/jpeg','.png':'image/png','.webp':'image/webp'}[ext]
    db.execute('INSERT INTO deposit_slips(reservation_id,mime,image,created) VALUES (?,?,?,?)',(rid,mime,raw,datetime.now().isoformat(timespec='seconds')))

def links(h,db,rid):
    out=''
    for row in db.execute('SELECT id,created FROM deposit_slips WHERE reservation_id=? ORDER BY id DESC',(rid,)):
        out+=f'<p><a class="button secondary" href="/deposit-slip?id={row["id"]}" target=_blank rel=noopener>ดูสลิป · {h.api.esc(row["created"].replace("T"," "))}</a></p>'
    return out

def serve(h,db,path):
    if path!='/deposit-slip':return False
    try:ident=h.api.integer(h.query.get('id',['0'])[0])
    except ValueError:ident=0
    manager=bool(h.s and h.s.get('role')=='manager')
    if not manager:h.customer_session(db)
    row=db.execute('SELECT s.*,b.session_token FROM deposit_slips s JOIN customer_bookings b ON b.reservation_id=s.reservation_id WHERE s.id=?',(ident,)).fetchone()
    headers=[('Cache-Control','no-store, private'),('X-Content-Type-Options','nosniff'),('Referrer-Policy','no-referrer')]
    if not row or not manager and row['session_token']!=h.c['token']:
        h.respond('Not found',404,headers=headers);return True
    h.respond(row['image'],content=row['mime'],headers=headers);return True
