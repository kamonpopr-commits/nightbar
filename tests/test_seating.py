import unittest
import tempfile
from pathlib import Path
from datetime import datetime,timedelta
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app
import table_management
import floor_plan

class Seating(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.old=app.DB;app.DB=Path(self.tmp.name)/'db.sqlite3';app.initialize()
        self.h=object.__new__(app.Handler);self.h.s={'username':'tester','role':'manager','csrf':'test'}
        self.act('/open',table_id=1,guests=3)
    def tearDown(self):
        app.DB=self.old;self.tmp.cleanup()
    def act(self,path,**data):
        with app.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if 'order_id' in data and 'revision' not in data:data['revision']=db.execute('SELECT table_revision FROM orders WHERE id=?',(data['order_id'],)).fetchone()[0]
            return self.h.mutate(db,path,{k:str(v) for k,v in data.items()})
    def test_move_preserves_bill_and_invalidates_scan_but_existing_session_follows(self):
        self.act('/add',order_id=1,product_id=1,qty=2)
        with app.connect() as db:
            old=db.execute('SELECT token FROM visits WHERE order_id=1').fetchone()[0];before=tuple(db.execute('SELECT * FROM items').fetchone())
        self.act('/table-move',order_id=1,target=2,reason='new seats')
        with app.connect() as db:
            self.assertEqual(tuple(db.execute('SELECT * FROM items').fetchone()),before)
            self.assertEqual(db.execute('SELECT table_id FROM orders WHERE id=1').fetchone()[0],2)
            self.assertIsNone(db.execute('SELECT 1 FROM visits WHERE token=?',(old,)).fetchone())
            self.h.c={'visit':old};self.assertEqual(self.h.active_visit(db)['name'],'T02')
            self.assertFalse(table_management.free(db,1))
        self.act('/table-ready',table_id=1)
        with app.connect() as db:self.assertTrue(table_management.free(db,1))
    def test_join_single_bill_blocks_open_and_booking_and_capacity(self):
        self.act('/table-join',order_id=1,target=2,billing='single',reason='party')
        self.act('/table-guests',order_id=1,guests=8)
        with self.assertRaises(ValueError):self.act('/open',table_id=2)
        with self.assertRaises(ValueError):self.act('/table-guests',order_id=1,guests=9)
        with self.assertRaises(ValueError):self.act('/table-release',order_id=1,target=2,reason='release')
        with app.connect() as db:
            t=db.execute('SELECT * FROM tables WHERE id=2').fetchone();self.assertEqual(floor_plan.state(db,t,datetime.now()+timedelta(minutes=30),2)[0],'occupied')
        self.act('/table-guests',order_id=1,guests=4)
        self.act('/table-release',order_id=1,target=2,reason='release')
    def test_separate_group_and_merge_no_stock_deduction(self):
        self.act('/table-join',order_id=1,target=2,billing='separate',reason='friends')
        self.act('/table-guests',order_id=2,guests=4)
        self.act('/add',order_id=1,product_id=1,qty=1);self.act('/add',order_id=2,product_id=1,qty=2)
        with app.connect() as db:revision=db.execute('SELECT table_revision FROM orders WHERE id=2').fetchone()[0]
        self.act('/table-merge',order_id=1,source=2,source_revision=revision,reason='one bill')
        with app.connect() as db:
            self.assertEqual(db.execute('SELECT stock FROM products WHERE id=1').fetchone()[0],69)
            self.assertEqual(db.execute('SELECT SUM(qty) FROM items WHERE order_id=1').fetchone()[0],3)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM table_usage WHERE order_id=1').fetchone()[0],2)
            self.assertEqual(db.execute('SELECT status FROM orders WHERE id=2').fetchone()[0],'void')
    def test_stale_revision_booking_and_occupied_destination_reject(self):
        self.act('/add',order_id=1,product_id=1,qty=1)
        with self.assertRaises(ValueError):self.act('/table-move',order_id=1,revision=0,target=2,reason='stale')
        self.act('/open',table_id=2)
        with self.assertRaises(ValueError):self.act('/table-move',order_id=1,target=2,reason='busy')
        with app.connect() as db:db.execute('INSERT INTO reservations(name,phone,table_id,time,guests) VALUES (?,?,?,?,?)',('booking','123',3,(datetime.now()+timedelta(minutes=30)).isoformat(),2))
        with self.assertRaises(ValueError):self.act('/table-join',order_id=1,target=3,reason='reserved')
    def test_empty_cancel_staff_and_cleaning_after_payment(self):
        self.h.s['role']='staff';self.act('/table-cancel',order_id=1,reason='mistake')
        self.act('/open',table_id=1,guests=2)
        self.act('/add',order_id=2,product_id=1,qty=1)
        with self.assertRaises(ValueError):self.act('/table-cancel',order_id=2,reason='mistake')
        self.h.s['role']='manager';self.act('/shift-open',opening=1000);self.act('/pay',order_id=2,discount=0,method='เงินสด',received=100)
        with self.assertRaises(ValueError):self.act('/open',table_id=1)
        self.act('/table-ready',table_id=1);self.act('/open',table_id=1)
    def test_partial_cancel_waste_cost_and_double_cancel(self):
        self.act('/add',order_id=1,product_id=1,qty=2)
        self.act('/item-cancel',order_id=1,item_id=1,disposition='waste',reason='cooked')
        with app.connect() as db:
            self.assertEqual(db.execute('SELECT stock FROM products WHERE id=1').fetchone()[0],70)
            self.assertEqual(db.execute('SELECT SUM(qty*cost) FROM item_cancellations').fetchone()[0],9600)
        with self.assertRaises(ValueError):self.act('/item-cancel',order_id=1,item_id=1,disposition='return',reason='again')
    def test_restricted_merge_and_locked_move(self):
        self.act('/open',table_id=2);self.h.s['role']='staff'
        with self.assertRaises(ValueError):self.act('/table-merge',order_id=1,source=2,source_revision=0,reason='not allowed')
        self.h.s['role']='manager';self.act('/add',order_id=1,product_id=1,qty=1);self.act('/checkout-freeze',order_id=1,discount=0)
        with self.assertRaises(ValueError):self.act('/table-move',order_id=1,target=3,reason='locked')

    def test_merge_redirects_customers_and_keeps_historical_seating_after_close(self):
        self.act('/open',table_id=2,guests=2)
        with app.connect() as db:
            token=db.execute('SELECT token FROM visits WHERE order_id=2').fetchone()[0]
            db.execute('INSERT INTO customer_sessions(token,csrf,expires,visit) VALUES (?,?,?,?)',('customer','csrf',(datetime.now()+timedelta(days=1)).isoformat(),token))
            revision=db.execute('SELECT table_revision FROM orders WHERE id=2').fetchone()[0]
        self.act('/table-merge',order_id=1,source=2,source_revision=revision,reason='together')
        with app.connect() as db:
            self.h.c={'visit':token};visit=self.h.active_visit(db);self.assertEqual((visit['id'],visit['name']),(1,'T01 + T02'))
            self.assertNotEqual(db.execute("SELECT visit FROM customer_sessions WHERE token='customer'").fetchone()[0],token)
        self.act('/add',order_id=1,product_id=1,qty=1);self.act('/shift-open',opening=1000);self.act('/pay',order_id=1,discount=0,method='เงินสด',received=100)
        with app.connect() as db:
            self.assertEqual(db.execute('SELECT name FROM order_labels WHERE id=1').fetchone()[0],'T01 + T02')
            self.assertEqual(db.execute('SELECT COUNT(*) FROM table_state WHERE cleaning=1').fetchone()[0],2)
            self.assertIsNone(self.h.active_visit(db))

    def test_preparing_cancellation_is_waste_and_partial_history_survives(self):
        self.act('/add',order_id=1,product_id=1,qty=1)
        with app.connect() as db:
            db.execute('INSERT INTO customer_sessions(token,csrf,expires) VALUES (?,?,?)',('customer','csrf',(datetime.now()+timedelta(days=1)).isoformat()))
            db.execute("INSERT INTO customer_requests(session_token,order_id,created,status,note,request_key) VALUES ('customer',1,?,'preparing','','request-1')",(app.now(),))
            db.execute("INSERT INTO customer_lines(request_id,item_id,name,qty,price) VALUES (1,1,'Beer',1,9500)")
        with self.assertRaises(ValueError):self.act('/item-cancel',order_id=1,item_id=1,disposition='return',reason='prepared')
        self.act('/queue-status',id=1,status='cancelled',reason='prepared')
        with app.connect() as db:
            self.assertEqual(db.execute('SELECT stock FROM products WHERE id=1').fetchone()[0],71)
            self.assertEqual(db.execute('SELECT disposition FROM item_cancellations').fetchone()[0],'waste')
            self.assertEqual(db.execute('SELECT status FROM customer_requests').fetchone()[0],'cancelled')
        with self.assertRaises(ValueError):self.act('/queue-status',id=1,status='cancelled',reason='again')

    def test_link_existing_tables_keeps_separate_bills_and_can_ungroup(self):
        self.act('/open',table_id=2,guests=2)
        self.act('/add',order_id=1,product_id=1,qty=1);self.act('/add',order_id=2,product_id=1,qty=1)
        with app.connect() as db:revision=db.execute('SELECT table_revision FROM orders WHERE id=2').fetchone()[0]
        self.act('/table-link',order_id=1,source=2,source_revision=revision,reason='friends')
        with app.connect() as db:
            rows=db.execute('SELECT status,party FROM orders').fetchall()
            self.assertEqual([r['status'] for r in rows],['open','open']);self.assertEqual(rows[0]['party'],rows[1]['party'])
            self.assertEqual(db.execute('SELECT COUNT(DISTINCT order_id) FROM items').fetchone()[0],2)
            self.assertEqual(db.execute('SELECT stock FROM products WHERE id=1').fetchone()[0],70)
        with self.assertRaises(ValueError):self.act('/table-guests',order_id=1,guests=5)
        self.act('/table-ungroup',order_id=2,reason='leaving')
        with app.connect() as db:self.assertEqual([r[0] for r in db.execute('SELECT party FROM orders')],[None,None])

    def test_cancelled_food_history_cannot_use_empty_table_shortcut(self):
        self.act('/add',order_id=1,product_id=1,qty=1)
        self.act('/item-cancel',order_id=1,item_id=1,disposition='waste',reason='used')
        self.h.s['role']='staff'
        with self.assertRaises(ValueError):self.act('/table-cancel',order_id=1,reason='not empty')

if __name__=='__main__':unittest.main()
