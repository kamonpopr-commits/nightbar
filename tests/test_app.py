import unittest
import tempfile
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app

class Workflow(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.original=app.DB
        app.DB=Path(self.tmp.name)/'store.sqlite3'
        app.initialize()
        self.h=object.__new__(app.Handler)
        self.h.s={'username':'test','role':'manager'}
        with app.connect() as db: self.h.mutate(db,'/shift-open',{'opening':'1000'})
    def tearDown(self):
        app.DB=self.original
        self.tmp.cleanup()
    def run_action(self,path,**data):
        with app.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            return self.h.mutate(db,path,{k:str(v) for k,v in data.items()})
    def open_add(self,qty=2):
        self.run_action('/open',table_id=1)
        self.run_action('/add',order_id=1,product_id=1,qty=qty)
    def test_batch_stock_multiple_items_reasons_and_deduplication(self):
        data={'request_key':'stock-batch-test-key-001','common_reason':'รับสินค้า','qty_1':'10','qty_2':'-2','qty_3':'0','qty_4':'','reason_2':'ตรวจนับ'}
        self.run_action('/stock-batch',**data);self.run_action('/stock-batch',**data)
        with app.connect() as db:
            self.assertEqual(db.execute('SELECT stock FROM products WHERE id=1').fetchone()[0],82)
            self.assertEqual(db.execute('SELECT stock FROM products WHERE id=2').fetchone()[0],34)
            self.assertEqual([tuple(r) for r in db.execute('SELECT product_id,qty,reason FROM movements')],[(1,10,'รับสินค้า'),(2,-2,'ตรวจนับ')])
        with self.assertRaises(ValueError):self.run_action('/stock-batch',**(data|{'qty_1':'20'}))
    def test_batch_stock_all_or_nothing_and_missing_reason(self):
        data={'request_key':'stock-batch-test-key-002','common_reason':'ตรวจนับ','qty_1':'10','qty_2':'-100'}
        with self.assertRaises(ValueError):self.run_action('/stock-batch',**data)
        with app.connect() as db:
            self.assertEqual(db.execute('SELECT stock FROM products WHERE id=1').fetchone()[0],72)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM movements').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM stock_batches').fetchone()[0],0)
        with self.assertRaises(ValueError):self.run_action('/stock-batch',**(data|{'qty_2':'-1','common_reason':''}))
        with self.assertRaises(ValueError):self.run_action('/stock-batch',**(data|{'qty_1':'0','qty_2':'0'}))
    def test_batch_stock_single_row_and_manager_permission(self):
        data={'request_key':'stock-batch-test-key-003','common_reason':'เติม','qty_1':'3','qty_2':'10','only_product':'1'}
        self.run_action('/stock-batch',**data)
        with app.connect() as db:
            self.assertEqual(db.execute('SELECT stock FROM products WHERE id=1').fetchone()[0],75)
            self.assertEqual(db.execute('SELECT stock FROM products WHERE id=2').fetchone()[0],36)
        self.h.s['role']='staff'
        with self.assertRaises(ValueError):self.run_action('/stock-batch',**(data|{'request_key':'stock-batch-test-key-004'}))
    def test_payment_snapshot_and_stock(self):
        self.open_add()
        self.run_action('/product-edit',product_id=1,price=150,active=1)
        self.run_action('/pay',order_id=1,discount=0,method='เงินสด',received=200)
        with app.connect() as db:
            o=db.execute('SELECT * FROM orders').fetchone()
            self.assertEqual(o['total'],19000)
            self.assertEqual(o['received']-o['total'],1000)
            self.assertEqual(db.execute('SELECT stock FROM products WHERE id=1').fetchone()[0],70)
        with self.assertRaises(ValueError): self.run_action('/pay',order_id=1,discount=0,method='เงินสด',received=200)

    def test_complete_menu_edit_preserves_bill_and_stock(self):
        self.open_add()
        with app.connect() as db:
            before=dict(db.execute('SELECT * FROM items WHERE order_id=1').fetchone())
        self.run_action('/product-edit',product_id=1,name='New menu',category='Food',cost=25,minimum=7,price=150,active=1)
        with app.connect() as db:
            product=db.execute('SELECT * FROM products WHERE id=1').fetchone()
            self.assertEqual((product['name'],product['category'],product['cost'],product['minimum'],product['stock']),('New menu','Food',2500,7,70))
            self.assertEqual(dict(db.execute('SELECT * FROM items WHERE order_id=1').fetchone()),before)
        with self.assertRaises(ValueError):self.run_action('/product-edit',product_id=1,name='',price=150,active=1)
        self.h.s['role']='staff'
        with self.assertRaises(ValueError):self.run_action('/product-edit',product_id=1,price=150,active=1)
    def test_void_restores_stock_once(self):
        self.open_add()
        self.run_action('/void',order_id=1,reason='ลูกค้ายกเลิก',disposition='return')
        with app.connect() as db: self.assertEqual(db.execute('SELECT stock FROM products WHERE id=1').fetchone()[0],72)
        with self.assertRaises(ValueError): self.run_action('/void',order_id=1,reason='ซ้ำ')
    def test_insufficient_stock_rolls_back(self):
        self.run_action('/open',table_id=1)
        with self.assertRaises(ValueError): self.run_action('/add',order_id=1,product_id=1,qty=1000)
        with app.connect() as db:
            self.assertEqual(db.execute('SELECT stock FROM products WHERE id=1').fetchone()[0],72)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM items').fetchone()[0],0)
    def test_discount_tax_rounding(self):
        self.open_add(1)
        self.run_action('/settings',shop='Test',address='',service=10,tax=7)
        self.run_action('/pay',order_id=1,discount=5,method='โอนเงิน',received='')
        with app.connect() as db:
            o=db.execute('SELECT * FROM orders').fetchone()
            self.assertEqual((o['service'],o['tax'],o['total']),(900,693,10593))
    def test_staff_discount_rejected(self):
        self.open_add(); self.h.s['role']='staff'
        with self.assertRaises(ValueError): self.run_action('/pay',order_id=1,discount=1,method='เงินสด',received='')
    def test_remove_returns_stock(self):
        self.open_add()
        with app.connect() as db:revision=db.execute('SELECT table_revision FROM orders WHERE id=1').fetchone()[0]
        self.run_action('/item-cancel',order_id=1,revision=revision,item_id=1,reason='ยังไม่ทำ',disposition='return')
        with app.connect() as db: self.assertEqual(db.execute('SELECT stock FROM products WHERE id=1').fetchone()[0],72)
    def test_password_hash(self):
        saved=app.password('long-password')
        self.assertTrue(app.verify('long-password',saved))
        self.assertFalse(app.verify('wrong',saved))
    def test_unique_open_table(self):
        import sqlite3
        self.run_action('/open',table_id=1)
        with self.assertRaises(ValueError): self.run_action('/open',table_id=1)
    def test_all_pages_and_exports_render(self):
        self.open_add()
        self.h.s['csrf']='test-token'
        outputs=[]
        self.h.respond=lambda body,*args,**kwargs: outputs.append(body)
        for path in ['/','/tables','/products','/reservations','/reports','/expenses','/settings','/order','/export','/backup']:
            self.h.path=path; self.h.query={'id':['1']}
            with app.connect() as db: self.h.render(db,path)
            self.assertTrue(outputs[-1],path)
        self.run_action('/pay',order_id=1,discount=0,method='เงินสด',received='')
        self.h.path='/receipt'
        with app.connect() as db: self.h.render(db,'/receipt')
        self.assertIn('190.00',outputs[-1])
    def test_browser_setup_multiple_tabs_and_favicon(self):
        import threading, urllib.request, urllib.parse, http.cookiejar, re
        server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        client=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        base=f'http://127.0.0.1:{server.server_port}'
        try:
            first=client.open(base,timeout=5).read().decode()
            csrf=re.search(r'name=csrf value="([^"]+)"',first).group(1)
            self.assertEqual(client.open(base+'/favicon.ico',timeout=5).status,204)
            second=client.open(base,timeout=5).read().decode()
            self.assertIn(csrf,second)
            data=urllib.parse.urlencode({'csrf':csrf,'username':'owner','password':'test-password-123'}).encode()
            response=client.open(base+'/setup',data,timeout=5)
            self.assertEqual(response.status,200)
            self.assertIn('OPERATIONS / JUPITER',response.read().decode())
        finally:
            server.shutdown(); server.server_close(); thread.join()

if __name__=='__main__': unittest.main()
