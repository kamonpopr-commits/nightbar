import unittest,tempfile,sys
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime,timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app,streamline,operations

class Shortcuts(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.old=app.DB;app.DB=Path(self.tmp.name)/'test.sqlite3';app.initialize()
        self.h=object.__new__(app.Handler);self.h.s={'role':'manager','username':'test','csrf':'test'};self.h.query={};self.h.server=SimpleNamespace(server_port=8765)
        self.act('/open',table_id=1);self.act('/add',order_id=1,product_id=1,qty=2);self.act('/shift-open',opening=1000)
    def tearDown(self):app.DB=self.old;self.tmp.cleanup()
    def act(self,path,**d):
        with app.connect() as db:
            db.execute('BEGIN IMMEDIATE');return self.h.mutate(db,path,{k:str(v) for k,v in d.items()})
    def payload(self):
        with app.connect() as db:q,token=streamline.quote(db,app,1)
        return dict(order_id=1,quote=token,method='เงินสด',received=200,request_key='simple-checkout-request-001')
    def test_simple_checkout_one_transaction_duplicate_safe(self):
        d=self.payload();self.assertEqual(self.act('/checkout-simple',**d),'/receipt?id=1');self.act('/checkout-simple',**d)
        with app.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM payments').fetchone()[0],1)
            row=db.execute('SELECT * FROM orders').fetchone();self.assertEqual((row['status'],row['total'],row['received']),('paid',19000,20000))
            self.assertEqual(db.execute('SELECT change FROM payments').fetchone()[0],1000)
    def test_stale_quote_and_underpayment_roll_back(self):
        d=self.payload();d['received']=100
        with self.assertRaises(ValueError):self.act('/checkout-simple',**d)
        with app.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM checkout_totals').fetchone()[0],0)
        d=self.payload();self.act('/add',order_id=1,product_id=1,qty=1)
        with self.assertRaises(ValueError):self.act('/checkout-simple',**d)
        with app.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM payments').fetchone()[0],0)
    def test_cashier_allowed_floor_denied(self):
        self.h.s.update(role='staff',station='floor')
        with self.assertRaises(ValueError):self.act('/checkout-simple',**self.payload())
        self.h.s['station']='cashier';self.act('/checkout-simple',**self.payload())
    def test_verified_deposit_combines_freeze_and_credit(self):
        with app.connect() as db:
            rid=db.execute('INSERT INTO reservations(name,phone,table_id,time,guests,status) VALUES (?,?,?,?,?,?)',('Guest','0812345678',1,datetime.now().isoformat(),2,'arrived')).lastrowid
            db.execute('INSERT INTO reservation_orders VALUES (?,?,?,?)',(rid,1,datetime.now().isoformat(),'test'))
            db.execute('INSERT INTO booking_deposits(reservation_id,amount,state,deadline,instructions,cancel_hours) VALUES (?,?,?,?,?,?)',(rid,7000,'confirmed',(datetime.now()+timedelta(days=1)).isoformat(),'test',24))
        d=self.payload()
        with self.assertRaises(ValueError):self.act('/checkout-simple',**d)
        self.assertEqual(self.act('/checkout-deposit',order_id=1,id=rid,quote=d['quote']),'/checkout?id=1')
        self.act('/checkout-deposit',order_id=1,id=rid,quote=d['quote'])
        with app.connect() as db:
            self.assertEqual(operations.paid(db,1),7000);self.assertEqual(db.execute('SELECT COUNT(*) FROM payments').fetchone()[0],1)
            part=db.execute('SELECT id FROM bill_parts').fetchone()[0]
        self.act('/payment-add',order_id=1,part_id=part,amount=120,received=200,method='เงินสด',request_key='cash-after-deposit-test-001')
        with app.connect() as db:self.assertEqual(db.execute('SELECT status FROM orders').fetchone()[0],'paid')
    def test_menu_toggle_preserves_stock_and_permissions(self):
        self.act('/product-availability',product_id=1,expected=1)
        with app.connect() as db:self.assertEqual(tuple(db.execute('SELECT active,stock FROM products WHERE id=1').fetchone()),(0,70))
        with self.assertRaises(ValueError):self.act('/product-availability',product_id=1,expected=1)
        self.act('/product-availability',product_id=1,expected=0)
        self.h.s['role']='staff'
        with self.assertRaises(ValueError):self.act('/product-availability',product_id=1,expected=1)
    def test_order_hub_only_contains_own_bill_and_returns_after_action(self):
        self.act('/add',order_id=1,product_id=4,qty=1,prep_required=1)
        self.act('/open',table_id=2);self.act('/add',order_id=2,product_id=9,qty=1,prep_required=1)
        with app.connect() as db:
            html,ids=streamline.board(self.h,db,1)
            item=db.execute("SELECT id FROM items WHERE order_id=1 AND prep_status='received'").fetchone()[0]
            other=db.execute('SELECT id FROM items WHERE order_id=2').fetchone()[0]
            self.assertIn(item,ids);self.assertNotIn(other,ids)
        self.assertEqual(self.act('/production-status',item_id=item,expected='received',status='preparing',return_order=1),'/order?id=1')

if __name__=='__main__':unittest.main()
