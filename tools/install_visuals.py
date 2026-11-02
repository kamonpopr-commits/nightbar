"""Install generated menu photos and add sample dishes without changing existing stock."""
from pathlib import Path
import sys, json, shutil
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import app

NEW=[
 ('ข้าวกะเพราหมูสับไข่ดาว','ข้าวจานเดียว',7900,3500,'pad-krapao','กะเพราหมูสับหอมใบกะเพรา เสิร์ฟกับข้าวและไข่ดาว',1),
 ('ข้าวผัดไก่','ข้าวจานเดียว',7900,3200,'chicken-fried-rice','ข้าวผัดไก่และไข่ หอมกระทะ เสิร์ฟพร้อมมะนาว',1),
 ('ข้าวไก่กระเทียม','ข้าวจานเดียว',7900,3300,'garlic-chicken-rice','ไก่กระเทียมพริกไทย โรยกระเทียมเจียว พร้อมข้าวสวย',0),
 ('ข้าวไข่เจียวหมูสับ','ข้าวจานเดียว',6900,2600,'omelette-rice','ไข่เจียวหมูสับฟูนุ่ม ขอบกรอบ เสิร์ฟบนข้าวสวย',0),
 ('ชาไทยเย็น','เครื่องดื่มไม่มีแอลกอฮอล์',5500,1800,'thai-tea','ชาไทยนมเย็น หอมชา เข้มข้น กลมกล่อม',1),
 ('ลาเต้เย็น','เครื่องดื่มไม่มีแอลกอฮอล์',6500,2200,'iced-coffee','กาแฟผสมนมสด เสิร์ฟเย็น หอมละมุน',0),
 ('มะนาวโซดา','เครื่องดื่มไม่มีแอลกอฮอล์',4900,1500,'lime-soda','มะนาวและโซดา เปรี้ยวซ่า สดชื่น',0),
 ('โคล่าใส่น้ำแข็ง','เครื่องดื่มไม่มีแอลกอฮอล์',3500,1200,'cola','โคล่าเย็นซ่า เสิร์ฟพร้อมน้ำแข็ง',0),
]
EXISTING=[('Gin Tonic','gin-tonic','จินและโทนิก หอมมะนาวและสมุนไพร',0),('Mojito','mojito','โมฮิโต้มะนาวและมิ้นต์ สดชื่น กลิ่นหอม',1),('เฟรนช์ฟรายส์','fries','มันฝรั่งทอดสีทอง กรอบนอกนุ่มใน พร้อมซอสมะเขือเทศ',0),('ปีกไก่ทอด','wings','ปีกไก่ทอดกรอบ เสิร์ฟพร้อมน้ำจิ้ม',0)]

def seed(db):
    for name,category,price,cost,image,desc,featured in NEW:
        p=db.execute('SELECT id FROM products WHERE name=?',(name,)).fetchone()
        if p: pid=p[0]
        else:
            pid=db.execute('INSERT INTO products(name,category,price,cost,stock,minimum) VALUES (?,?,?,?,20,5)',(name,category,price,cost)).lastrowid
            db.execute('INSERT INTO movements(product_id,qty,reason,created) VALUES (?,20,?,?)',(pid,'จำนวนตัวอย่างสำหรับทดลองเมนูใหม่',app.now()))
        db.execute('INSERT INTO product_presentation VALUES (?,?,?,?) ON CONFLICT(product_id) DO UPDATE SET image=excluded.image,description=excluded.description,featured=excluded.featured',(pid,image+'.webp',desc,featured))
    for name,image,desc,featured in EXISTING:
        p=db.execute('SELECT id FROM products WHERE name=?',(name,)).fetchone()
        if p: db.execute('INSERT INTO product_presentation VALUES (?,?,?,?) ON CONFLICT(product_id) DO UPDATE SET image=excluded.image,description=excluded.description,featured=excluded.featured',(p[0],image+'.webp',desc,featured))

if __name__=='__main__':
    from PIL import Image
    assets=ROOT/'assets'; originals=assets/'originals'; originals.mkdir(exist_ok=True)
    manifest=json.loads((assets/'image-prompts.json').read_text(encoding='utf8'))
    for asset in manifest['assets']:
        source=Path(asset['source']); copy=originals/(asset['name']+'.png')
        if not copy.exists(): shutil.copy2(source,copy)
        with Image.open(copy) as image:
            image=image.convert('RGB'); image.thumbnail((960,960)); image.save(assets/(asset['name']+'.webp'),'WEBP',quality=85,method=6)
    app.initialize()
    stamp=__import__('datetime').datetime.now().strftime('%Y%m%d-%H%M%S')
    backup=app.connect(); dest=__import__('sqlite3').connect(ROOT/'data'/f'before-menu-styling-{stamp}.sqlite3'); backup.backup(dest); dest.close(); backup.close()
    with app.connect() as db: seed(db)
    print('Installed 12 menu photos, 8 sample menu items, logo and brand styling.')
