"""Install missing menu photos without changing products or existing presentations."""
from pathlib import Path
import json, shutil, sqlite3, sys
from datetime import datetime
from PIL import Image, ImageDraw
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import app

def main():
    assets=ROOT/'assets'
    manifest=json.loads((assets/'remaining-image-prompts.json').read_text(encoding='utf-8'))
    names={'lager':'เบียร์ Lager 330 ml','craft-ipa':'เบียร์ Craft IPA','whisky':'Whisky ขวด 700 ml','drinking-water':'น้ำดื่ม','soda-water':'โซดา','ice-bucket':'น้ำแข็งถัง'}
    sheet=Image.new('RGB',(900,640),'#102019'); draw=ImageDraw.Draw(sheet)
    for i,item in enumerate(manifest['assets']):
        original=assets/'originals'/(item['name']+'.png')
        if not original.exists(): shutil.copy2(item['source'],original)
        output=assets/(item['name']+'.webp')
        if not output.exists():
            with Image.open(original) as image:
                image=image.convert('RGB');image.thumbnail((960,960));image.save(output,'WEBP',quality=85,method=6)
        with Image.open(output) as image:
            image=image.resize((300,300));sheet.paste(image,((i%3)*300,(i//3)*320));draw.text(((i%3)*300+8,(i//3)*320+303),item['name'],fill='white')
    sheet.save(ROOT/'remaining-menu-preview.jpg',quality=90)
    if '--install' not in sys.argv: return
    with app.connect() as db:
        backup=ROOT/'data'/('before-remaining-photos-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.sqlite3')
        with sqlite3.connect(backup) as dest: db.backup(dest)
        db.execute('BEGIN IMMEDIATE')
        before=[tuple(r) for r in db.execute('SELECT * FROM products ORDER BY id')]
        for item in manifest['assets']:
            product=db.execute('SELECT id FROM products WHERE name=?',(names[item['name']],)).fetchone()
            if not product: raise ValueError('Menu name not found: '+names[item['name']])
            current=db.execute('SELECT image FROM product_presentation WHERE product_id=?',(product[0],)).fetchone()
            if current and current[0] and (assets/current[0]).is_file(): continue
            db.execute('INSERT INTO product_presentation(product_id,image,description,featured) VALUES (?,?,?,0) ON CONFLICT(product_id) DO UPDATE SET image=excluded.image',(product[0],item['name']+'.webp',''))
        assert before==[tuple(r) for r in db.execute('SELECT * FROM products ORDER BY id')]
        missing=[r['name'] for r in db.execute('SELECT p.name,v.image FROM products p LEFT JOIN product_presentation v ON v.product_id=p.id WHERE p.active=1') if not r['image'] or not (assets/r['image']).is_file()]
        if missing: raise ValueError('Missing images: '+repr(missing))
        print('All 18 active menu items have photos. Product prices and stock unchanged.')

if __name__=='__main__':main()
