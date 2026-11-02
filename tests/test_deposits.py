import unittest,tempfile,sys
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime,timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app,deposits,operations,readability
import deposit_qr,visuals,io
from unittest.mock import patch

class Deposits(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.old=app.DB;app.DB=Path(self.tmp.name)/'test.sqlite3';app.initialize()
        self.h=object.__new__(app.Handler);self.h.s={'username':'test','role':'manager','csrf':'test'};self.h.server=SimpleNamespace(server_port=8765)
        with app.connect() as db:
            db.execute("INSERT INTO customer_sessions(token,csrf,expires) VALUES ('test','test','2099-01-01')")
            self.h.c=dict(db.execute('SELECT * FROM customer_sessions').fetchone())
        self.act('/deposit-settings',amount='100',min_guests='2',hold='15',cancel_hours='24',instructions='Test account')
    def tearDown(self):app.DB=self.old;self.tmp.cleanup()
    def act(self,path,**d):
        with app.connect() as db:
            db.execute('BEGIN IMMEDIATE');return self.h.mutate(db,path,{k:str(v) for k,v in d.items()})
    def booking(self,amount=10000):
        with app.connect() as db:
            rid=db.execute('INSERT INTO reservations(name,phone,table_id,time,guests) VALUES (?,?,?,?,?)',('Guest','0812345678',1,(datetime.now()+timedelta(days=3)).isoformat(),2)).lastrowid
            db.execute("INSERT INTO customer_bookings VALUES (?,'test',?,'')",(rid,f'CODE{rid}'))
            deposits.create(self.h,db,rid,2,{'deposit_consent':'1'})
            db.execute('UPDATE booking_deposits SET amount=? WHERE reservation_id=?',(amount,rid))
        return rid
    def verify(self,rid):
        with app.connect() as db:deposits.customer_mutate(self.h,db,'/customer/deposit-reference',{'id':str(rid),'reference':'TRANSFER123 12:30'})
        self.act('/deposit-action',id=rid,expected='review',action='verify',note='checked bank')
    def test_consent_and_policy_snapshots(self):
        rid=self.booking()
        self.act('/deposit-settings',amount='200',min_guests=2,hold=20,cancel_hours=48,instructions='Changed')
        with app.connect() as db:
            row=db.execute('SELECT * FROM booking_deposits').fetchone();self.assertEqual((row['amount'],row['cancel_hours'],row['instructions']),(10000,24,'Test account'))
            with self.assertRaises(ValueError):deposits.create(self.h,db,rid+1,2,{})
    def test_customer_booking_creates_deposit_atomically(self):
        payload={'request_key':'booking-deposit-request-001','name':'Test Guest','phone':'0812345678','time':(datetime.now()+timedelta(days=4)).isoformat(timespec='minutes'),'guests':'2','table_id':'2','consent':'1','deposit_consent':'1'}
        with app.connect() as db:
            db.execute('BEGIN IMMEDIATE');self.h.customer_mutate(db,'/customer/booking',payload)
        with app.connect() as db:
            self.assertEqual(db.execute('SELECT state FROM booking_deposits').fetchone()[0],'pending')
            self.h.customer_mutate(db,'/customer/booking',payload)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM booking_deposits').fetchone()[0],1)
            self.assertIn('รอแจ้งโอน',deposits.customer_card(self.h,db,1))
    def test_expiry_releases_table_and_late_reference_denied(self):
        rid=self.booking()
        with app.connect() as db:
            db.execute("UPDATE booking_deposits SET deadline='2000-01-01'");deposits.expire(db)
            self.assertEqual(db.execute('SELECT status FROM reservations').fetchone()[0],'cancelled')
            with self.assertRaises(ValueError):deposits.customer_mutate(self.h,db,'/customer/deposit-reference',{'id':str(rid),'reference':'TOO LATE'})
    def test_ownership_and_manager_verification(self):
        rid=self.booking();self.h.c={'token':'other'}
        with app.connect() as db:
            with self.assertRaises(ValueError):deposits.customer_mutate(self.h,db,'/customer/deposit-reference',{'id':str(rid),'reference':'OTHER CLIENT'})
        self.h.s['role']='staff'
        with self.assertRaises(ValueError):self.act('/deposit-action',id=rid,expected='pending',action='verify',note='x')
        with self.assertRaises(ValueError):self.act('/reservation-status',id=rid,status='arrived')
    def test_cancel_refund_and_stale_double_refund(self):
        rid=self.booking();self.verify(rid)
        self.act('/reservation-status',id=rid,status='cancelled')
        self.act('/deposit-action',id=rid,expected='refund_due',action='refund',note='refund reference')
        with self.assertRaises(ValueError):self.act('/deposit-action',id=rid,expected='refund_due',action='refund',note='duplicate')
        with app.connect() as db:self.assertEqual(db.execute('SELECT refunded FROM booking_deposits').fetchone()[0],10000)
    def test_review_cannot_cancel_without_bank_check(self):
        rid=self.booking()
        with app.connect() as db:deposits.customer_mutate(self.h,db,'/customer/deposit-reference',{'id':str(rid),'reference':'TRANSFER123'})
        with self.assertRaises(ValueError):self.act('/reservation-status',id=rid,status='cancelled')
    def test_apply_split_once_preserves_sales_and_cash(self):
        rid=self.booking();self.verify(rid);self.act('/reservation-status',id=rid,status='arrived')
        self.act('/add',order_id=1,product_id=1,qty=2);self.act('/shift-open',opening=1000);self.act('/checkout-freeze',order_id=1,discount=0)
        self.act('/bill-split',order_id=1,mode='equal',count=2)
        self.act('/deposit-apply',id=rid,order_id=1)
        with self.assertRaises(ValueError):self.act('/deposit-apply',id=rid,order_id=1)
        with app.connect() as db:
            self.assertEqual(operations.paid(db,1),10000);self.assertEqual(operations.cash_summary(db,operations.active(db))['expected'],100000)
            parts=db.execute('SELECT * FROM bill_parts ORDER BY id').fetchall()
            self.assertEqual([operations.part_paid(db,p['id']) for p in parts],[9500,500])
            self.assertEqual(db.execute('SELECT SUM(amount) FROM payments WHERE shift_id IS NULL').fetchone()[0],10000)
        self.act('/payment-add',part_id=parts[1]['id'],amount=90,received=100,method='เงินสด',request_key='remaining-payment-test-001')
        with app.connect() as db:
            o=db.execute('SELECT o.*,t.name FROM orders o JOIN order_labels t ON t.id=o.id').fetchone()
            self.assertEqual((o['status'],o['total']),('paid',19000));html=readability.receipt(self.h,db,o);self.assertIn('90.00',html);self.assertIn('receipt-sheet',html)
    def test_excess_deposit_refunded_and_cannot_forge_payment(self):
        rid=self.booking(30000);self.verify(rid);self.act('/reservation-status',id=rid,status='arrived')
        self.act('/add',order_id=1,product_id=1,qty=2);self.act('/shift-open',opening=1000);self.act('/checkout-freeze',order_id=1,discount=0)
        with app.connect() as db:part=db.execute('SELECT id FROM bill_parts').fetchone()[0]
        with self.assertRaises(ValueError):self.act('/payment-add',part_id=part,amount=190,method='มัดจำ',received=190,request_key='forged-deposit-payment-01')
        self.act('/deposit-apply',id=rid,order_id=1)
        self.act('/deposit-action',id=rid,expected='refund_due',action='refund',note='return excess')
        with app.connect() as db:
            r=db.execute('SELECT * FROM booking_deposits').fetchone();self.assertEqual((r['applied'],r['refunded']),(19000,11000));self.assertEqual(db.execute('SELECT status FROM orders').fetchone()[0],'paid')
    def test_no_show_time_guard_and_late_cancel(self):
        rid=self.booking();self.verify(rid)
        with self.assertRaises(ValueError):self.act('/deposit-action',id=rid,expected='confirmed',action='no-show',note='too early')
        with app.connect() as db:db.execute('UPDATE reservations SET time=?',((datetime.now()-timedelta(minutes=20)).isoformat(),))
        self.act('/deposit-action',id=rid,expected='confirmed',action='no-show',note='called guest')
        with app.connect() as db:self.assertEqual(db.execute('SELECT state FROM booking_deposits').fetchone()[0],'forfeited')
    def test_open_bill_preview_is_not_a_paid_receipt(self):
        self.act('/open',table_id=1);self.act('/add',order_id=1,product_id=1,qty=2)
        with app.connect() as db:
            row=db.execute('SELECT o.*,t.name FROM orders o JOIN order_labels t ON t.id=o.id').fetchone()
            html=readability.receipt(self.h,db,row)
            self.assertIn('ยอดค้างชำระ',html);self.assertIn('190.00',html);self.assertNotIn('สถานะ: ชำระครบแล้ว',html)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM payments').fetchone()[0],0)
    def test_receipt_groups_identical_items_and_preserves_variants(self):
        self.act('/open',table_id=1)
        self.act('/add',order_id=1,product_id=1,qty=1);self.act('/add',order_id=1,product_id=1,qty=2)
        with app.connect() as db:
            item=db.execute('SELECT * FROM items LIMIT 1').fetchone()
            db.execute('INSERT INTO items(order_id,product_id,name,price,cost,qty) VALUES (?,?,?,?,?,?)',(1,1,item['name']+' extra',item['price'],item['cost'],1))
            row=db.execute('SELECT o.*,t.name FROM orders o JOIN order_labels t ON t.id=o.id').fetchone()
            html=readability.receipt(self.h,db,row)
            self.assertIn('จำนวน 3 ×',html);self.assertIn(' extra',html)
            self.assertEqual(html.count('<div class=receipt-line>'),2)
            self.assertIn('ใบเสร็จ 80 มม.',html)
    def test_receipt_rates_snapshotted_and_transfer_has_no_cash_change(self):
        self.act('/open',table_id=1);self.act('/add',order_id=1,product_id=1,qty=2);self.act('/shift-open',opening=1000)
        with app.connect() as db:
            db.execute("UPDATE settings SET value='10' WHERE key='service'");db.execute("UPDATE settings SET value='7' WHERE key='tax'")
        self.act('/pay',order_id=1,discount=0,method='โอนเงิน',received='')
        with app.connect() as db:
            db.execute("UPDATE settings SET value='20' WHERE key IN ('service','tax')")
            row=db.execute('SELECT o.*,t.name FROM orders o JOIN order_labels t ON t.id=o.id').fetchone();html=readability.receipt(self.h,db,row)
            self.assertIn('ค่าบริการ 10%',html);self.assertIn('ภาษี 7%',html)
            self.assertIn('โอนเงิน ·',html);self.assertNotIn('เงินทอน ',html);self.assertNotIn('รับเงินสด ',html)
    def test_qr_upload_preserves_bytes_and_booking_snapshot(self):
        from PIL import Image
        out=io.BytesIO();Image.new('RGB',(220,220),'white').save(out,'PNG');raw=out.getvalue()
        folder=Path(self.tmp.name)/'assets';folder.mkdir()
        with patch.object(visuals,'ASSETS',folder):
            self.h.uploads={'photo':raw};self.act('/deposit-qr',bank='PromptPay',payee='Test receiver')
            with app.connect() as db:name=db.execute("SELECT value FROM settings WHERE key='deposit_qr'").fetchone()[0]
            self.assertEqual((folder/name).read_bytes(),raw)
            rid=self.booking();self.h.uploads={};self.act('/deposit-qr',bank='Different bank',payee='Other receiver')
            with app.connect() as db:
                row=db.execute('SELECT * FROM booking_deposits').fetchone();self.assertEqual((row['payment_qr'],row['payment_payee']),(name,'Test receiver'))
                html=deposits.customer_card(self.h,db,rid);self.assertIn('Test receiver',html);self.assertIn('download=',html)
                db.execute("UPDATE booking_deposits SET state='expired'");self.assertNotIn('bank-qr-card',deposits.customer_card(self.h,db,rid))
            self.h.uploads={'photo':b'not an image'}
            with self.assertRaises(ValueError):self.act('/deposit-qr',bank='Bad',payee='Bad')
            self.h.s['role']='staff';self.h.uploads={'photo':raw}
            with self.assertRaises(ValueError):self.act('/deposit-qr',bank='Bad',payee='Bad')

    def test_arrival_opens_once_with_guests_qr_and_link(self):
        rid=self.booking();self.verify(rid)
        self.assertEqual(self.act('/reservation-status',id=rid,status='arrived'),'/order?id=1')
        self.assertEqual(self.act('/reservation-status',id=rid,status='arrived'),'/order?id=1')
        with app.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM orders').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT guests FROM orders').fetchone()[0],2)
            self.assertEqual(db.execute('SELECT status FROM reservations').fetchone()[0],'arrived')
            self.assertTrue(db.execute('SELECT token FROM visits WHERE order_id=1').fetchone()[0])
            self.assertEqual(db.execute('SELECT order_id FROM reservation_orders').fetchone()[0],1)

    def test_paid_and_cleaned_arrival_releases_booking_availability(self):
        import floor_plan
        rid=self.booking();self.verify(rid)
        when=datetime.now()+timedelta(minutes=35)
        with app.connect() as db:db.execute('UPDATE reservations SET time=? WHERE id=?',(when.isoformat(),rid))
        self.act('/reservation-status',id=rid,status='arrived')
        self.act('/add',order_id=1,product_id=1,qty=2);self.act('/shift-open',opening=1000)
        self.act('/pay',order_id=1,discount=0,method='เงินสด',received=200)
        with app.connect() as db:
            table=db.execute('SELECT * FROM tables WHERE id=1').fetchone()
            self.assertEqual(floor_plan.state(db,table,when,2)[0],'occupied')
        self.act('/table-ready',table_id=1)
        with app.connect() as db:
            self.assertEqual(floor_plan.state(db,table,when,2)[0],'available')
            self.assertEqual(db.execute('SELECT status FROM reservations WHERE id=?',(rid,)).fetchone()[0],'arrived')
        self.act('/reserve',name='Next guest',phone='0812345678',table_id=1,time=when.isoformat(),guests=2)
        with app.connect() as db:self.assertEqual(floor_plan.state(db,table,when,2)[0],'reserved')

    def test_arrival_busy_cleaning_and_alternative_table(self):
        rid=self.booking();self.verify(rid);self.act('/open',table_id=1)
        with self.assertRaises(ValueError):self.act('/reservation-status',id=rid,status='arrived')
        with app.connect() as db:
            self.assertEqual(db.execute('SELECT status FROM reservations').fetchone()[0],'booked')
            db.execute('INSERT OR REPLACE INTO table_state VALUES (2,1)')
        with self.assertRaises(ValueError):self.act('/reservation-status',id=rid,status='arrived',target=2)
        self.act('/table-ready',table_id=2)
        self.assertEqual(self.act('/reservation-status',id=rid,status='arrived',target=2),'/order?id=2')
        with app.connect() as db:self.assertEqual(db.execute('SELECT table_id FROM reservations').fetchone()[0],2)

    def test_arrival_capacity_and_other_reservation_guard(self):
        rid=self.booking();self.verify(rid)
        with app.connect() as db:db.execute('UPDATE tables SET seats=1 WHERE id=2')
        with self.assertRaises(ValueError):self.act('/reservation-status',id=rid,status='arrived',target=2)
        with app.connect() as db:
            db.execute('INSERT INTO reservations(name,phone,table_id,time,guests) VALUES (?,?,?,?,?)',('Other','0812345678',1,datetime.now().isoformat(),2))
        with self.assertRaises(ValueError):self.act('/reservation-status',id=rid,status='arrived')
        with app.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM orders').fetchone()[0],0)

    def test_deposit_link_survives_move_and_merge(self):
        rid=self.booking();self.verify(rid);self.act('/reservation-status',id=rid,status='arrived')
        self.act('/table-move',order_id=1,revision=0,target=2,reason='Guest move')
        with app.connect() as db:self.assertTrue(deposits.linked_to(db,rid,1,1))
        self.act('/open',table_id=3)
        with app.connect() as db:revision=db.execute('SELECT table_revision FROM orders WHERE id=1').fetchone()[0]
        self.act('/table-merge',order_id=2,revision=0,source=1,source_revision=revision,reason='Group')
        with app.connect() as db:
            self.assertTrue(deposits.linked_to(db,rid,2,1));self.assertFalse(deposits.linked_to(db,rid,1,1))
        self.assertEqual(self.act('/reservation-status',id=rid,status='arrived'),'/order?id=2')

if __name__=='__main__':unittest.main()
