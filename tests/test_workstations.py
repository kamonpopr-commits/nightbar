import unittest,tempfile,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app,menu_options,workstations
from datetime import datetime,timedelta

class OptionsAndStations(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.old=app.DB;app.DB=Path(self.tmp.name)/'db.sqlite3';app.initialize()
        self.h=object.__new__(app.Handler);self.h.s={'role':'manager','username':'qa','csrf':'test'}
        self.act('/open',table_id=1)
        with app.connect() as db:
            self.rice=db.execute("INSERT INTO products(name,category,price,cost,stock,minimum) VALUES ('Rice','ข้าวจานเดียว',7900,3000,5,1)").lastrowid
            db.execute("UPDATE products SET name='ข้าวผัด' WHERE id=?",(self.rice,));menu_options.seed(db,db.execute('SELECT * FROM products WHERE id=?',(self.rice,)).fetchone())
            self.egg=db.execute("SELECT id FROM menu_options WHERE product_id=? AND price=1500",(self.rice,)).fetchone()[0]
            token=db.execute('SELECT token FROM visits WHERE order_id=1').fetchone()[0]
            db.execute('INSERT INTO customer_sessions(token,csrf,expires,visit) VALUES (?,?,?,?)',('customer','test',(datetime.now()+timedelta(days=1)).isoformat(),token))
    def tearDown(self):app.DB=self.old;self.tmp.cleanup()
    def act(self,path,**data):
        with app.connect() as db:
            db.execute('BEGIN IMMEDIATE');return self.h.mutate(db,path,{k:str(v) for k,v in data.items()})
    def customer(self,path,**data):
        with app.connect() as db:
            db.execute('BEGIN IMMEDIATE');self.h.c=dict(db.execute("SELECT * FROM customer_sessions WHERE token='customer'").fetchone())
            return self.h.customer_mutate(db,path,{k:str(v) for k,v in data.items()})
    def checkout(self):
        with app.connect() as db:
            cart=json.loads(db.execute("SELECT cart FROM customer_sessions WHERE token='customer'").fetchone()[0]);quote=self.h.quote(db,cart)
        self.customer('/customer/checkout',request_key='test-variant-order-key-001',confirmed=1,quote=quote)
    def test_variants_snapshot_price_cost_and_shared_stock(self):
        self.customer('/customer/cart',product_id=self.rice,qty=1)
        self.customer('/customer/cart',product_id=self.rice,qty=2,option_0=self.egg)
        self.checkout()
        with app.connect() as db:
            rows=db.execute('SELECT * FROM items ORDER BY id').fetchall();self.assertEqual([(r['price'],r['cost'],r['qty']) for r in rows],[(7900,3000,1),(9400,3600,2)])
            self.assertIn('เพิ่มไข่ดาว',rows[1]['name']);self.assertEqual(db.execute('SELECT stock FROM products WHERE id=?',(self.rice,)).fetchone()[0],2)
            self.assertEqual([r['station'] for r in rows],['kitchen','kitchen'])
    def test_forged_options_and_aggregate_stock(self):
        self.customer('/customer/cart',product_id=self.rice,qty=4)
        with self.assertRaises(ValueError):self.customer('/customer/cart',product_id=self.rice,qty=2,option_0=self.egg)
        with self.assertRaises(ValueError):self.customer('/customer/cart',product_id=1,qty=1,option_0=self.egg)
        with app.connect() as db:
            ids=[r[0] for r in db.execute("SELECT id FROM menu_options WHERE product_id=? AND group_name='ความเผ็ด'",(self.rice,))]
        with self.assertRaises(ValueError):self.customer('/customer/cart',product_id=self.rice,qty=1,option_0=ids[0],option_1=ids[1])
    def test_disabled_option_blocks_checkout_but_can_remove(self):
        self.customer('/customer/cart',product_id=self.rice,qty=1,option_0=self.egg)
        self.act('/option-toggle',id=self.egg,active=0)
        with self.assertRaises(ValueError):self.checkout()
        self.customer('/customer/cart',product_id=f'{self.rice}:{self.egg}',replace=1,qty=0)
        with app.connect() as db:self.assertEqual(db.execute("SELECT cart FROM customer_sessions WHERE token='customer'").fetchone()[0],'{}')
    def test_item_stations_permissions_aggregate_status_and_payment_guard(self):
        self.customer('/customer/cart',product_id=self.rice,qty=1);self.customer('/customer/cart',product_id=4,qty=1);self.checkout()
        self.h.s.update(role='staff',station='kitchen')
        with self.assertRaises(ValueError):self.act('/production-status',item_id=2,expected='received',status='preparing')
        with self.assertRaises(ValueError):self.act('/pay',order_id=1,method='เงินสด',discount=0,received=1000)
        self.act('/production-status',item_id=1,expected='received',status='preparing');self.act('/production-status',item_id=1,expected='preparing',status='ready')
        with self.assertRaises(ValueError):self.act('/production-status',item_id=1,expected='ready',status='served')
        with app.connect() as db:self.assertEqual(db.execute('SELECT status FROM customer_requests').fetchone()[0],'received')
        self.h.s['station']='bar';self.act('/production-status',item_id=2,expected='received',status='preparing');self.act('/production-status',item_id=2,expected='preparing',status='ready')
        self.h.s.update(role='manager');self.act('/shift-open',opening=1000)
        with self.assertRaises(ValueError):self.act('/checkout-freeze',order_id=1,discount=0)
        self.h.s.update(role='staff',station='floor');self.act('/production-status',item_id=1,expected='ready',status='served');self.act('/production-status',item_id=2,expected='ready',status='served')
        with app.connect() as db:self.assertEqual(db.execute('SELECT status FROM customer_requests').fetchone()[0],'served')
        self.h.s.update(station='cashier');self.act('/checkout-freeze',order_id=1,discount=0)
    def test_manual_ui_orders_enter_queue_and_duplicate_status_rejected(self):
        self.act('/add',order_id=1,product_id=1,qty=1,prep_required=1)
        with app.connect() as db:self.assertEqual(db.execute('SELECT prep_status FROM items').fetchone()[0],'received')
        self.act('/production-status',item_id=1,expected='received',status='preparing')
        with self.assertRaises(ValueError):self.act('/production-status',item_id=1,expected='received',status='preparing')
    def test_department_query_cannot_read_other_station_or_accounts(self):
        self.customer('/customer/cart',product_id=self.rice,qty=1);self.customer('/customer/cart',product_id=4,qty=1);self.checkout()
        self.h.s.update(role='staff',station='kitchen');self.h.query={'station':['bar']}
        with app.connect() as db:html,ids=workstations.board(self.h,db)
        self.assertEqual(ids,[1]);self.assertNotIn('Gin Tonic',html);self.assertFalse(workstations.allowed(self.h,'/reports'));self.assertFalse(workstations.allowed(self.h,'/queue-status',True))
    def test_routing_override_and_option_price_change_preserve_old_order(self):
        self.customer('/customer/cart',product_id=self.rice,qty=1,option_0=self.egg);self.checkout()
        self.act('/option-edit',id=self.egg,price=20,cost=8)
        self.act('/product-station',product_id=self.rice,station='bar')
        with app.connect() as db:
            old=db.execute('SELECT * FROM items').fetchone();self.assertEqual((old['price'],old['cost'],old['station']),(9400,3600,'kitchen'))
            p=menu_options.product(db,f'{self.rice}:{self.egg}');self.assertEqual((p['price'],p['cost']),(9900,3800));self.assertEqual(workstations.for_product(db,p),'bar')
    def test_tracked_manual_food_cannot_return_after_preparation(self):
        self.act('/add',order_id=1,product_id=9,qty=1,prep_required=1)
        self.act('/production-status',item_id=1,expected='received',status='preparing')
        with app.connect() as db:revision=db.execute('SELECT table_revision FROM orders WHERE id=1').fetchone()[0]
        with self.assertRaises(ValueError):self.act('/item-cancel',order_id=1,revision=revision,item_id=1,disposition='return',reason='prepared')
    def test_unified_menu_save_is_atomic_and_preserves_old_order(self):
        self.customer('/customer/cart',product_id=self.rice,qty=1,option_0=self.egg);self.checkout()
        data=dict(product_id=self.rice,name='Edited rice',category='Food',price=99,cost=31,minimum=2,active=1,description='New description',featured=1,image='',station='bar')
        self.act('/product-save',**data)
        with app.connect() as db:
            p=db.execute('SELECT * FROM products WHERE id=?',(self.rice,)).fetchone();self.assertEqual((p['name'],p['price'],p['cost'],p['stock']),('Edited rice',9900,3100,4))
            self.assertEqual(db.execute('SELECT description FROM product_presentation WHERE product_id=?',(self.rice,)).fetchone()[0],'New description')
            i=db.execute('SELECT * FROM items').fetchone();self.assertEqual((i['price'],i['cost']),(9400,3600))
        with self.assertRaises(ValueError):self.act('/product-save',**(data|{'name':'Wrong','price':200,'station':'invalid'}))
        with app.connect() as db:self.assertEqual(db.execute('SELECT name FROM products WHERE id=?',(self.rice,)).fetchone()[0],'Edited rice')
        self.h.s['role']='staff'
        with self.assertRaises(ValueError):self.act('/product-save',**data)
    def test_unified_editor_scopes_options_to_selected_product(self):
        import workspace
        self.h.query={'product_id':[str(self.rice)]}
        with app.connect() as db:body=workspace.editor(self.h,db)
        self.assertIn('action="/product-save"',body);self.assertIn('เพิ่มไข่ดาว',body)
        self.assertNotIn('action="/product-edit"',body);self.assertNotIn('action="/product-presentation"',body)

if __name__=='__main__':unittest.main()
