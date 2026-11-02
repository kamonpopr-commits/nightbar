import unittest,tempfile,sys,threading
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app,operations

class Register(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.old=app.DB; app.DB=Path(self.tmp.name)/'db.sqlite3'; app.initialize()
        self.h=object.__new__(app.Handler); self.h.s={'username':'owner','role':'manager','csrf':'demo'}; self.h.server=SimpleNamespace(server_port=8765)
        self.run_action('/open',table_id=1); self.run_action('/add',order_id=1,product_id=1,qty=2)
    def tearDown(self): app.DB=self.old; self.tmp.cleanup()
    def run_action(self,path,**data):
        with app.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            return self.h.mutate(db,path,{k:str(v) for k,v in data.items()})
    def freeze(self): self.run_action('/checkout-freeze',order_id=1,discount=0)
    def parts(self):
        with app.connect() as db: return db.execute('SELECT * FROM bill_parts ORDER BY id').fetchall()
    def payment(self,pid,value,method='เงินสด',received='',key='test-payment-key-0001'):
        return self.run_action('/payment-add',part_id=pid,amount=value,method=method,received=received,request_key=key)
    def test_shift_required_and_no_partial_write_on_failure(self):
        self.freeze(); pid=self.parts()[0]['id']
        with self.assertRaises(ValueError): self.payment(pid,190)
        with app.connect() as db:
            self.assertEqual(operations.paid(db,1),0)
            self.assertEqual(db.execute('SELECT status FROM orders').fetchone()[0],'open')
    def test_equal_split_rounding_exact(self):
        with app.connect() as db: db.execute('UPDATE items SET price=10001,qty=1 WHERE order_id=1')
        self.freeze(); self.run_action('/bill-split',order_id=1,mode='equal',count=3)
        self.assertEqual([p['amount'] for p in self.parts()],[3334,3334,3333])
    def test_custom_split_must_match_total(self):
        self.freeze()
        with self.assertRaises(ValueError): self.run_action('/bill-split',order_id=1,mode='custom',amounts='100,91')
        self.assertEqual(len(self.parts()),1)
        self.run_action('/bill-split',order_id=1,mode='custom',amounts='100,90')
        self.assertEqual([p['amount'] for p in self.parts()],[10000,9000])
    def test_mixed_payments_change_finalization_and_duplicate(self):
        self.run_action('/shift-open',opening=1000); self.freeze()
        self.run_action('/bill-split',order_id=1,mode='equal',count=2); parts=self.parts()
        self.payment(parts[0]['id'],50,received=100)
        self.payment(parts[0]['id'],50,received=100)
        with app.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM payments').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT status FROM orders').fetchone()[0],'open')
            self.assertEqual(operations.cash_summary(db,operations.active(db))['expected'],105000)
        self.payment(parts[0]['id'],45,'โอนเงิน',key='test-payment-key-0002')
        self.payment(parts[1]['id'],95,'บัตร',key='test-payment-key-0003')
        with app.connect() as db:
            o=db.execute('SELECT * FROM orders').fetchone()
            self.assertEqual((o['status'],o['total'],o['method']),('paid',19000,'หลายช่องทาง'))
            self.assertEqual(o['received']-o['total'],5000)
            self.assertEqual(db.execute('SELECT stock FROM products WHERE id=1').fetchone()[0],70)
    def test_cash_expenses_and_adjustments_reconcile(self):
        self.run_action('/shift-open',opening=1000)
        self.run_action('/expense',title='ซื้ออุปกรณ์',amount=100,method='เงินสด')
        self.run_action('/expense',title='ค่าน้ำ',amount=50,method='โอนเงิน')
        self.run_action('/cash-event',shift_id=1,kind='in',amount=200,reason='เติมเงินทอน',request_key='cash-adjustment-key-001')
        self.run_action('/cash-event',shift_id=1,kind='out',amount=300,reason='นำส่ง',request_key='cash-adjustment-key-002')
        with app.connect() as db: self.assertEqual(operations.cash_summary(db,operations.active(db))['expected'],80000)
        with self.assertRaises(ValueError): self.run_action('/shift-close',shift_id=1,counted=790,note='')
        self.run_action('/shift-close',shift_id=1,counted=790,note='เงินขาด 10 บาท ตรวจสอบแล้ว')
        with app.connect() as db:
            s=db.execute('SELECT * FROM shifts').fetchone()
            self.assertEqual((s['expected'],s['counted'],s['difference']),(80000,79000,-1000))
            self.assertIsNone(operations.active(db))
    def test_cannot_close_shift_with_incomplete_payment(self):
        self.run_action('/shift-open',opening=0); self.freeze(); self.payment(self.parts()[0]['id'],100)
        with self.assertRaises(ValueError): self.run_action('/shift-close',shift_id=1,counted=100,note='')
        with self.assertRaises(ValueError): self.run_action('/bill-split',order_id=1,mode='equal',count=2)
        with self.assertRaises(ValueError): self.run_action('/checkout-unlock',order_id=1)
        with self.assertRaises(ValueError): self.run_action('/void',order_id=1,reason='ลอง')
        self.payment(self.parts()[0]['id'],90,key='remaining-payment-0001')
        self.run_action('/shift-close',shift_id=1,counted=190,note='')
    def test_quote_stays_frozen_when_settings_change(self):
        self.freeze()
        with app.connect() as db: db.execute("UPDATE settings SET value='7' WHERE key='tax'")
        with self.assertRaises(ValueError): self.run_action('/add',order_id=1,product_id=1,qty=1)
        self.run_action('/shift-open',opening=0); self.payment(self.parts()[0]['id'],190)
        with app.connect() as db: self.assertEqual(db.execute('SELECT total FROM orders').fetchone()[0],19000)
    def test_parallel_payments_cannot_overpay(self):
        self.run_action('/shift-open',opening=0); self.freeze(); pid=self.parts()[0]['id']; results=[]; barrier=threading.Barrier(2)
        def submit(i):
            barrier.wait()
            try: self.payment(pid,190,key=f'concurrent-payment-{i:04}'); results.append('ok')
            except ValueError: results.append('rejected')
        threads=[threading.Thread(target=submit,args=(i,)) for i in range(2)]
        for t in threads:t.start()
        for t in threads:t.join()
        self.assertEqual(sorted(results),['ok','rejected'])
        with app.connect() as db:self.assertEqual(operations.paid(db,1),19000)
    def test_views_and_old_bill_migration(self):
        self.run_action('/shift-open',opening=1000); self.freeze(); output=[]
        self.h.respond=lambda body,*args,**kwargs:output.append(body)
        for path,query in [('/shifts',{}),('/checkout',{'id':['1']}),('/part-receipt',{'id':[str(self.parts()[0]['id'])]})]:
            self.h.path=path; self.h.query=query
            with app.connect() as db:self.h.render(db,path)
            self.assertTrue(output[-1])
        with app.connect() as db:
            db.execute("INSERT INTO orders(table_id,opened,closed,status,total,method,received) VALUES (2,?,?,'paid',10000,'เงินสด',12000)",(app.now(),app.now()))
            operations.initialize(db); operations.initialize(db)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM payments WHERE order_id=2').fetchone()[0],1)
            self.assertIsNone(db.execute('SELECT shift_id FROM payments WHERE order_id=2').fetchone()[0])
    def test_duplicate_cash_expense_not_deducted_twice(self):
        self.run_action('/shift-open',opening=1000)
        data={'title':'อุปกรณ์','amount':100,'method':'เงินสด','request_key':'expense-request-000001'}
        self.run_action('/expense',**data); self.run_action('/expense',**data)
        with app.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM expenses').fetchone()[0],1)
            self.assertEqual(operations.cash_summary(db,operations.active(db))['expected'],90000)

if __name__=='__main__':unittest.main()
