from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import app
app.DB=ROOT/'tmp/manual/jupiter_manual_demo.sqlite3'
app.initialize()
with app.connect() as db:
    if not db.execute('SELECT 1 FROM orders').fetchone():
        db.execute("INSERT INTO orders(id,table_id,opened,guests,note) VALUES (1001,1,'2026-10-30T18:00:00+07:00',2,'ข้อมูลสาธิตสำหรับคู่มือ')")
        db.execute('INSERT INTO table_assignments VALUES (1,1001)')
        for pid,qty in [(1,2),(6,1)]:
            p=db.execute('SELECT * FROM products WHERE id=?',(pid,)).fetchone()
            db.execute('INSERT INTO items(order_id,product_id,name,price,cost,qty) VALUES (?,?,?,?,?,?)',(1001,pid,p['name'],p['price'],p['cost'],qty))
    schema={r['name']:{'columns':[dict(x) for x in db.execute('PRAGMA table_info("'+r['name']+'")')], 'foreign_keys':[dict(x) for x in db.execute('PRAGMA foreign_key_list("'+r['name']+'")')]} for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    (ROOT/'tmp/manual/system-schema.json').write_text(json.dumps(schema,ensure_ascii=False,indent=2),encoding='utf-8')
    assert not db.execute('PRAGMA foreign_key_check').fetchall()
print(app.DB)
