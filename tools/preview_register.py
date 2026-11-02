"""Disposable local QA server. All accounts and transactions here are test data."""
from pathlib import Path
import sys,secrets
from datetime import datetime,timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app

if __name__=='__main__':
    folder=app.ROOT/'.qa'; folder.mkdir(exist_ok=True)
    app.DB=folder/(secrets.token_hex(8)+'.sqlite3')
    app.initialize()
    with app.connect() as db:
        from tools.install_visuals import seed
        seed(db)
        import menu_options
        menu_options.initialize(db)
        db.execute('INSERT INTO users(username,password,role) VALUES (?,?,?)',('qa',app.password('demo-workflow-only'),'manager'))
        db.execute("UPDATE settings SET value='JUPITER · ทดสอบ' WHERE key='shop'")
        h=object.__new__(app.Handler); h.s={'username':'qa','role':'manager'}
        h.mutate(db,'/shift-open',{'opening':'1000'})
        h.mutate(db,'/open',{'table_id':'1'})
        h.mutate(db,'/add',{'order_id':'1','product_id':'1','qty':'2'})
        h.mutate(db,'/add',{'order_id':'1','product_id':'9','qty':'1'})
        if '--booking' in sys.argv:
            db.execute('INSERT INTO reservations(name,phone,table_id,time,guests) VALUES (?,?,?,?,?)',('ตัวอย่างการจอง','0812345678',2,(datetime.now()+timedelta(minutes=45)).isoformat(timespec='minutes'),2))
        if '--queue' in sys.argv or '--stations' in sys.argv:
            visit=db.execute('SELECT token FROM visits WHERE order_id=1').fetchone()[0]
            db.execute('INSERT INTO customer_sessions(token,csrf,expires,visit,cart) VALUES (?,?,?,?,?)',('qa-customer','qa-csrf',(datetime.now()+timedelta(hours=1)).isoformat(),visit,'{"4":1}'))
            h.c=dict(db.execute("SELECT * FROM customer_sessions WHERE token='qa-customer'").fetchone())
            h.customer_mutate(db,'/customer/checkout',{'request_key':'queue-preview-order-001','confirmed':'1','quote':h.quote(db,{'4':1}),'note':'ทดสอบคิวสด'})
            if '--stations' in sys.argv:
                for station in ['kitchen','bar','floor','cashier']:
                    db.execute('INSERT INTO users(username,password,role,station) VALUES (?,?,?,?)',('qa-'+station,app.password('demo-workflow-only'),'staff',station))
                h.c=dict(db.execute("SELECT * FROM customer_sessions WHERE token='qa-customer'").fetchone())
                rice=db.execute("SELECT id FROM products WHERE name='ข้าวผัดไก่'").fetchone()[0]
                egg=db.execute('SELECT id FROM menu_options WHERE product_id=? AND price=1500',(rice,)).fetchone()[0]
                h.customer_mutate(db,'/customer/cart',{'product_id':str(rice),'qty':'1','option_0':str(egg)})
                h.c=dict(db.execute("SELECT * FROM customer_sessions WHERE token='qa-customer'").fetchone())
                import json
                h.customer_mutate(db,'/customer/checkout',{'request_key':'queue-preview-rice-order-002','confirmed':'1','quote':h.quote(db,json.loads(h.c['cart'])),'note':'ทดสอบเมนูเพิ่มไข่'})
            if '--services' in sys.argv:
                h.customer_mutate(db,'/customer/service',{'kind':'bill'})
                h.customer_mutate(db,'/customer/service',{'kind':'staff'})
    port=int(sys.argv[1]) if len(sys.argv)>1 and sys.argv[1].isdigit() else 8877
    print(f'QA server: http://127.0.0.1:{port} — qa / demo-workflow-only',flush=True)
    app.ThreadingHTTPServer(('127.0.0.1',port),app.Handler).serve_forever()
