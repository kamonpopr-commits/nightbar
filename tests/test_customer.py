import unittest
import tempfile
import threading
import sys
import re
import json
import sqlite3
from pathlib import Path
from datetime import datetime,timedelta
from urllib.request import build_opener,HTTPCookieProcessor,ProxyHandler
from urllib.parse import urlencode
from http.cookiejar import CookieJar
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app

class CustomerFlow(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.old=app.DB; app.DB=Path(self.temp.name)/'db.sqlite3'
        app.initialize()
        self.h=object.__new__(app.Handler); self.h.s={'role':'manager','username':'owner','csrf':'staff'}
        self.h.server=SimpleNamespace(server_port=8765)
        with app.connect() as db:
            self.h.mutate(db,'/shift-open',{'opening':'1000'})
            db.execute("INSERT INTO users(username,password,role) VALUES ('owner',?,'manager')",(app.password('test-password'),))
            self.h.mutate(db,'/open',{'table_id':'1'})
            self.visit=db.execute('SELECT token FROM visits WHERE order_id=1').fetchone()[0]
        self.server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True); self.thread.start()
        self.base=f'http://127.0.0.1:{self.server.server_port}'
        self.clients=[]
    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(); app.DB=self.old; self.temp.cleanup()
    def client(self):
        jar=CookieJar(); client=build_opener(ProxyHandler({}),HTTPCookieProcessor(jar)); self.clients.append((client,jar)); return client
    def get(self,c,path): return c.open(self.base+path,timeout=5).read().decode()
    def post(self,c,path,data): return c.open(self.base+path,urlencode(data).encode(),timeout=5).read().decode()
    def csrf(self,body): return re.search(r'name="csrf" value="([^"]+)"',body).group(1)
    def join(self,c): return self.get(c,'/menu?'+urlencode({'visit':self.visit}))
    def cart(self,c,pid=1,qty=2):
        page=self.join(c)
        self.post(c,'/customer/cart',{'csrf':self.csrf(page),'product_id':pid,'qty':qty})
        return self.get(c,'/cart')
    def payload(self,page):
        return {name:re.search(r'name='+name+r' value="([^"]+)"',page).group(1) for name in ['request_key','quote']} | {'csrf':self.csrf(page),'confirmed':'1','note':'ไม่ใส่มะนาว'}
    def test_customer_seating_update_keeps_cart_and_old_qr_expires(self):
        c=self.client();self.cart(c)
        with app.connect() as db:
            revision=db.execute('SELECT table_revision FROM orders WHERE id=1').fetchone()[0]
            self.h.mutate(db,'/table-move',{'order_id':'1','revision':str(revision),'target':'2','reason':'test move'})
        status=json.loads(self.get(c,'/live/seating'))
        self.assertEqual(status,{'open':True,'name':'T02'})
        self.assertIn('T02',self.get(c,'/cart'))
        with app.connect() as db:self.assertEqual(json.loads(db.execute('SELECT cart FROM customer_sessions WHERE cart!=?',('{}',)).fetchone()[0]),{'1':2})
        fresh=self.client();self.assertIn('QR นี้ใช้สั่งไม่ได้แล้ว',self.join(fresh))
    def test_async_cart_totals_and_csrf(self):
        from urllib.request import Request
        from urllib.error import HTTPError
        c=self.client(); page=self.join(c)
        with app.connect() as db:
            db.execute("UPDATE settings SET value='10' WHERE key='service'")
            db.execute("UPDATE settings SET value='7' WHERE key='tax'")
            price=db.execute('SELECT price FROM products WHERE id=1').fetchone()[0]
            expected=self.h.estimate(db,price*2)[2]
        request=Request(self.base+'/customer/cart',urlencode({'csrf':self.csrf(page),'product_id':1,'qty':2}).encode(),headers={'Accept':'application/json'})
        with c.open(request) as response: data=json.load(response)
        self.assertEqual({k:data[k] for k in ['count','total']},{'count':2,'total':app.money(expected)})
        request=Request(self.base+'/customer/cart',urlencode({'csrf':'wrong','product_id':1,'qty':2}).encode(),headers={'Accept':'application/json'})
        with self.assertRaises(HTTPError) as raised: c.open(request)
        self.assertEqual(raised.exception.code,400); raised.exception.close()
        with app.connect() as db:
            self.assertEqual(json.loads(db.execute('SELECT cart FROM customer_sessions').fetchone()[0]),{'1':2})
            self.assertEqual(db.execute('SELECT COUNT(*) FROM items').fetchone()[0],0)
    def test_card_cart_update_returns_fresh_quote_before_checkout(self):
        from urllib.request import Request
        c=self.client();page=self.cart(c);data=self.payload(page)
        request=Request(self.base+'/customer/cart',urlencode({'csrf':data['csrf'],'product_id':1,'qty':3,'replace':1}).encode(),headers={'Accept':'application/json'})
        with c.open(request) as response:state=json.load(response)
        self.assertEqual(state['cart']['1']['qty'],3);self.assertEqual(state['cart']['1']['total'],'285.00')
        self.assertNotEqual(state['quote'],data['quote'])
        self.assertIn('ราคาเมนูหรือค่าบริการเปลี่ยน',self.post(c,'/customer/checkout',data))
        self.assertIn('ส่งออเดอร์สำเร็จ',self.post(c,'/customer/checkout',data|{'quote':state['quote']}))
        with app.connect() as db:self.assertEqual(db.execute('SELECT qty FROM items').fetchone()[0],3)
    def test_ready_order_stays_pending_until_served(self):
        c=self.client();data=self.payload(self.cart(c));self.post(c,'/customer/checkout',data)
        with app.connect() as db:
            self.h.mutate(db,'/queue-status',{'id':'1','status':'preparing'})
            self.h.mutate(db,'/queue-status',{'id':'1','status':'ready'})
            with self.assertRaises(ValueError):self.h.mutate(db,'/checkout-freeze',{'order_id':'1','discount':'0'})
            with self.assertRaises(ValueError):self.h.mutate(db,'/queue-status',{'id':'1','status':'preparing'})
        self.assertIn('พร้อมเสิร์ฟ',self.get(c,'/my-orders'))
        self.sign_in(c);page=self.get(c,'/customer-queue')
        self.assertIn('name=status value=served',page)
        self.post(c,'/queue-status',{'csrf':self.csrf(page),'id':'1','status':'served'})
        with app.connect() as db:
            self.h.mutate(db,'/checkout-freeze',{'order_id':'1','discount':'0'})
            self.assertIsNotNone(db.execute('SELECT * FROM checkout_totals WHERE order_id=1').fetchone())
    def test_hidden_product_can_be_removed_from_cart(self):
        c=self.client(); page=self.cart(c)
        with app.connect() as db: db.execute('UPDATE products SET active=0 WHERE id=1')
        result=self.post(c,'/customer/cart',{'csrf':self.csrf(page),'product_id':'1','qty':'0','replace':'1'})
        self.assertIn('เลือกเมนูที่คุณชอบก่อน',result)
        with app.connect() as db:self.assertEqual(db.execute('SELECT cart FROM customer_sessions').fetchone()[0],'{}')
    def test_success_confirmation_is_private_and_reflects_cancellation(self):
        c=self.client(); data=self.payload(self.cart(c))
        self.assertIn('ส่งออเดอร์สำเร็จ',self.post(c,'/customer/checkout',data))
        path='/my-orders?'+urlencode({'confirmed':data['request_key']})
        self.assertNotIn('ส่งออเดอร์สำเร็จ',self.get(self.client(),path))
        with app.connect() as db:self.h.mutate(db,'/queue-status',{'id':'1','status':'cancelled','reason':'ทดสอบ'})
        result=self.get(c,path)
        self.assertIn('ออเดอร์นี้ถูกยกเลิกแล้ว',result);self.assertNotIn('ส่งออเดอร์สำเร็จ',result)
        future=(datetime.now()+timedelta(days=2)).isoformat(timespec='minutes')
        page=self.get(c,'/booking?'+urlencode({'time':future,'guests':2})); key='confirmation-booking-001'
        result=self.post(c,'/customer/booking',{'csrf':self.csrf(page),'name':'ทดสอบ','phone':'0812345678','time':future,'guests':'2','consent':'1','table_id':'2','request_key':key})
        self.assertIn('จองโต๊ะสำเร็จ',result)
        self.assertNotIn('จองโต๊ะสำเร็จ',self.get(self.client(),'/booking?'+urlencode({'confirmed':key})))
    def test_stale_menu_cannot_add_cart_after_checkout_freeze(self):
        c=self.client(); page=self.join(c)
        with app.connect() as db:
            self.h.mutate(db,'/add',{'order_id':'1','product_id':'1','qty':'1'})
            self.h.mutate(db,'/checkout-freeze',{'order_id':'1','discount':'0'})
        result=self.post(c,'/customer/cart',{'csrf':self.csrf(page),'product_id':'1','qty':'1'})
        self.assertIn('กำลังชำระเงิน',result)
        with app.connect() as db:self.assertEqual(db.execute('SELECT cart FROM customer_sessions').fetchone()[0],'{}')
    def test_expired_bookings_do_not_use_active_booking_limit(self):
        c=self.client(); future=(datetime.now()+timedelta(days=2)).isoformat(timespec='minutes')
        page=self.get(c,'/booking?'+urlencode({'time':future,'guests':2}))
        with app.connect() as db:
            token=db.execute('SELECT token FROM customer_sessions').fetchone()[0]
            for i in range(3):
                rid=db.execute('INSERT INTO reservations(name,phone,table_id,time,guests) VALUES (?,?,?,?,2)',('เก่า','0812345678',2,(datetime.now()-timedelta(days=i+1)).isoformat(timespec='minutes'))).lastrowid
                db.execute('INSERT INTO customer_bookings VALUES (?,?,?,?)',(rid,token,f'PAST{i}',''))
        result=self.post(c,'/customer/booking',{'csrf':self.csrf(page),'name':'ใหม่','phone':'0812345678','time':future,'guests':'2','consent':'1','table_id':'2'})
        self.assertRegex(result,r'จองสำเร็จ</span> · โต๊ะ T02')
        with app.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM reservations').fetchone()[0],4)
    def test_customer_order_fulfillment_and_deduplication(self):
        c=self.client(); page=self.cart(c); data=self.payload(page)
        self.assertIn('ออเดอร์ #0001',self.post(c,'/customer/checkout',data))
        self.post(c,'/customer/checkout',data)
        with app.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM customer_requests').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT stock FROM products WHERE id=1').fetchone()[0],70)
            with self.assertRaises(ValueError): self.h.mutate(db,'/pay',{'order_id':'1','discount':'0','method':'เงินสด','received':''})
            self.h.mutate(db,'/queue-status',{'id':'1','status':'preparing'})
            self.h.mutate(db,'/queue-status',{'id':'1','status':'served'})
            self.h.mutate(db,'/pay',{'order_id':'1','discount':'0','method':'เงินสด','received':''})
        self.assertIn('QR นี้ใช้สั่งไม่ได้แล้ว',self.get(c,'/menu?'+urlencode({'visit':self.visit})))
        other=self.client(); self.assertNotIn('ออเดอร์ #0001',self.get(other,'/my-orders'))
    def test_cancel_restores_stock_once(self):
        c=self.client(); page=self.cart(c); self.post(c,'/customer/checkout',self.payload(page))
        with app.connect() as db:
            with self.assertRaises(ValueError): self.h.mutate(db,'/remove',{'item_id':'1'})
            self.h.mutate(db,'/queue-status',{'id':'1','status':'cancelled','reason':'ลูกค้าเปลี่ยนใจ'})
            with self.assertRaises(ValueError): self.h.mutate(db,'/queue-status',{'id':'1','status':'cancelled','reason':'ซ้ำ'})
            self.assertEqual(db.execute('SELECT stock FROM products WHERE id=1').fetchone()[0],72)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM items').fetchone()[0],0)
    def test_concurrent_last_item_cannot_oversell(self):
        with app.connect() as db: db.execute('UPDATE products SET stock=1 WHERE id=1')
        clients=[self.client(),self.client()]; payloads=[self.payload(self.cart(c,qty=1)) for c in clients]
        barrier=threading.Barrier(2); results=[]
        def submit(i):
            barrier.wait(); results.append(self.post(clients[i],'/customer/checkout',payloads[i]))
        threads=[threading.Thread(target=submit,args=(i,)) for i in range(2)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(len(results),2)
        with app.connect() as db:
            self.assertEqual(db.execute('SELECT stock FROM products WHERE id=1').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM customer_requests').fetchone()[0],1)
    def test_price_changes_require_reconfirmation(self):
        c=self.client(); data=self.payload(self.cart(c))
        with app.connect() as db: db.execute('UPDATE products SET price=12000 WHERE id=1')
        self.assertIn('ราคาเมนูหรือค่าบริการเปลี่ยน',self.post(c,'/customer/checkout',data))
        with app.connect() as db: self.assertEqual(db.execute('SELECT COUNT(*) FROM customer_requests').fetchone()[0],0)
    def test_booking_privacy_capacity_cancel_and_conflicts(self):
        c=self.client(); future=(datetime.now()+timedelta(days=1)).isoformat(timespec='minutes'); page=self.get(c,'/booking?'+urlencode({'time':future,'guests':4}))
        data={'csrf':self.csrf(page),'name':'ลูกค้าทดสอบ','phone':'0812345678','time':future,'guests':'4','consent':'1','note':'วันเกิด'}
        result=self.post(c,'/customer/booking',data); self.assertIn('จองสำเร็จ',result)
        other=self.client(); self.assertNotIn('0812345678',self.get(other,'/booking'))
        page=self.get(other,'/booking?'+urlencode({'time':future,'guests':4}))
        self.assertIn('ไม่สามารถยกเลิก',self.post(other,'/customer/booking-cancel',{'csrf':self.csrf(page),'id':1}))
        self.assertIn('ยกเลิกแล้ว',self.post(c,'/customer/booking-cancel',{'csrf':self.csrf(result),'id':1}))
        with app.connect() as db:
            for t in db.execute('SELECT id FROM tables').fetchall():
                db.execute('INSERT INTO reservations(name,phone,table_id,time,guests) VALUES (?,?,?,?,1)',('เต็ม','00000000',t[0],future))
        self.assertIn('ไม่มีโต๊ะว่าง',self.post(c,'/customer/booking',data))
    def test_floor_plan_selected_table_capacity_duplicate_and_privacy(self):
        c=self.client(); future=(datetime.now()+timedelta(days=2)).isoformat(timespec='minutes')
        page=self.get(c,'/booking?'+urlencode({'time':future,'guests':5}))
        self.assertIn('แผนผังจำลอง',page); self.assertIn('name=table_id value=9',page)
        data={'csrf':self.csrf(page),'name':'เลือกโต๊ะ','phone':'0812345678','time':future,'guests':'5','consent':'1','table_id':'1','request_key':'floor-plan-request-0001'}
        self.assertIn('ที่นั่งไม่พอ',self.post(c,'/customer/booking',data))
        data['table_id']='9'
        result=self.post(c,'/customer/booking',data);self.assertRegex(result,r'จองสำเร็จ</span> · โต๊ะ T09')
        self.post(c,'/customer/booking',data)
        with app.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM reservations').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT table_id FROM reservations').fetchone()[0],9)
        other=self.client(); page=self.get(other,'/booking?'+urlencode({'time':future,'guests':5}))
        self.assertIn('มีการจองแล้ว',page);self.assertNotIn('0812345678',page)
        data.update(csrf=self.csrf(page),request_key='floor-plan-request-0002')
        self.assertIn('โต๊ะที่เลือกไม่พร้อมจอง',self.post(other,'/customer/booking',data))
    def test_floor_plan_concurrent_same_table_only_one_succeeds(self):
        future=(datetime.now()+timedelta(days=3)).isoformat(timespec='minutes')
        clients=[self.client(),self.client()]; pages=[self.get(c,'/booking?'+urlencode({'time':future,'guests':2})) for c in clients]
        barrier=threading.Barrier(2);results=[]
        def book(i):
            data={'csrf':self.csrf(pages[i]),'name':'ลูกค้า','phone':'0812345678','time':future,'guests':'2','consent':'1','table_id':'2','request_key':f'concurrent-booking-000{i}'}
            barrier.wait();results.append(self.post(clients[i],'/customer/booking',data))
        threads=[threading.Thread(target=book,args=(i,)) for i in range(2)]
        for t in threads:t.start()
        for t in threads:t.join()
        with app.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM reservations WHERE table_id=2').fetchone()[0],1)
        self.assertEqual(sum('จองสำเร็จ</span> · โต๊ะ T02' in result for result in results),1)
    def test_floor_plan_two_hour_boundary_and_occupied_table(self):
        import floor_plan
        with app.connect() as db:
            table=db.execute('SELECT * FROM tables WHERE id=1').fetchone()
            near=datetime.now()+timedelta(minutes=40)
            self.assertEqual(floor_plan.state(db,table,near,2)[0],'occupied')
            future=datetime.now()+timedelta(days=4)
            db.execute('INSERT INTO reservations(name,phone,table_id,time,guests) VALUES (?,?,?,?,?)',('ลูกค้า','0812345678',1,future.isoformat(),2))
            self.assertEqual(floor_plan.state(db,table,future+timedelta(minutes=119),2)[0],'reserved')
            self.assertEqual(floor_plan.state(db,table,future+timedelta(hours=2),2)[0],'available')
            with self.assertRaises(ValueError):self.h.mutate(db,'/reserve',{'time':near.isoformat(timespec='minutes'),'table_id':'1','guests':'2','name':'พนักงานจอง','phone':'0812345678'})
    def test_public_cannot_access_staff_and_csrf_required(self):
        from urllib.error import HTTPError
        c=self.client(); self.assertIn('เมนู',self.get(c,'/menu'))
        self.assertIn('เข้าสู่ระบบ',self.get(c,'/customer-queue'))
        self.assertIn('แบบฟอร์มหมดอายุ',self.post(c,'/customer/booking',{'csrf':'bad'}))
        page=self.join(c)
        with self.assertRaises(HTTPError) as error: self.post(c,'/stock',{'csrf':self.csrf(page),'product_id':1,'qty':5,'reason':'hack'})
        self.assertEqual(error.exception.code,403)
    def test_staff_queue_and_real_qr_svg(self):
        c=self.client(); page=self.cart(c); self.post(c,'/customer/checkout',self.payload(page))
        output=[]; self.h.path='/qr'; self.h.query={}; self.h.respond=lambda body,*args,**kwargs: output.append(body)
        with app.connect() as db:
            self.h.render(db,'/qr'); db.commit()
        self.assertIn('/qr.svg?order_id=1',output[-1])
        self.assertIn('href="/menu?visit=',output[-1])
        self.h.query={'order_id':['1']}
        with app.connect() as db: self.h.render(db,'/qr.svg')
        self.assertIn(b'<svg',output[-1])
        self.assertIn(b'<path',output[-1])
        self.h.path='/production'; self.h.query={}
        with app.connect() as db: self.h.render(db,'/production')
        self.assertIn('ไม่ใส่มะนาว',output[-1])
    def test_staff_link_when_already_logged_in(self):
        c=self.client(); page=self.get(c,'/login')
        csrf=re.search(r'name=csrf value="([^"]+)"',page).group(1)
        self.post(c,'/login',{'csrf':csrf,'username':'owner','password':'test-password'})
        result=self.get(c,'/login')
        self.assertIn('OPERATIONS / JUPITER',result)
        self.assertNotIn('Not found',result)
    def test_visual_menu_seed_assets_and_permissions(self):
        from tools.install_visuals import seed
        with app.connect() as db:
            original=list(db.execute('SELECT id,price,stock FROM products').fetchall())
            seed(db); seed(db)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM products').fetchone()[0],18)
            self.assertEqual([tuple(r) for r in original],[tuple(r) for r in db.execute('SELECT id,price,stock FROM products WHERE id<=10')])
        c=self.client()
        page=self.get(c,'/menu?'+urlencode({'category':'ข้าวจานเดียว'}))
        self.assertIn('ข้าวกะเพราหมูสับไข่ดาว',page)
        self.assertIn('/assets/pad-krapao.webp',page)
        self.assertIn('jupiter-mark.svg',page)
        image=c.open(self.base+'/assets/pad-krapao.webp',timeout=5)
        self.assertEqual(image.headers['Content-Type'],'image/webp'); image.close()
        from urllib.error import HTTPError
        with self.assertRaises(HTTPError) as error: self.get(c,'/assets/%2e%2e/app.py')
        self.assertEqual(error.exception.code,404); error.exception.close()
        with app.connect() as db:
            self.h.s['role']='staff'
            with self.assertRaises(ValueError): self.h.mutate(db,'/product-presentation',{'product_id':'1','image':'','featured':'1'})
    def sign_in(self,c,name='owner',password='test-password'):
        page=self.get(c,'/login')
        csrf=re.search(r'name=csrf value="([^"]+)"',page).group(1)
        return self.post(c,'/login',{'csrf':csrf,'username':name,'password':password})
    def test_bill_service_opens_checkout_and_remains_until_paid(self):
        c=self.client();data=self.payload(self.cart(c));self.post(c,'/customer/checkout',data)
        self.post(c,'/customer/service',{'csrf':data['csrf'],'kind':'bill'})
        self.post(c,'/customer/service',{'csrf':data['csrf'],'kind':'staff'})
        self.sign_in(c);page=self.get(c,'/customer-queue');staff_csrf=self.csrf(page)
        self.assertIn('ไปชำระเงิน',page);self.assertIn('ดูแลแล้ว',page)
        result=self.post(c,'/service-bill',{'csrf':staff_csrf,'id':'1'})
        self.assertIn('กลับไปจัดการคิว',result)
        with app.connect() as db:
            self.assertEqual(db.execute('SELECT status FROM service_requests WHERE id=1').fetchone()[0],'handling')
            self.assertEqual(db.execute('SELECT status FROM orders WHERE id=1').fetchone()[0],'open')
            self.assertEqual(db.execute('SELECT COUNT(*) FROM payments').fetchone()[0],0)
        page=self.get(c,'/customer-queue');self.assertIn('ชำระต่อ',page)
        self.post(c,'/service-bill',{'csrf':staff_csrf,'id':'1'})
        self.assertIn('ส่งคำขอแล้ว',self.post(c,'/customer/service',{'csrf':data['csrf'],'kind':'bill'}))
        self.post(c,'/service-done',{'csrf':staff_csrf,'id':'2'})
        with app.connect() as db:
            self.assertEqual(db.execute('SELECT status FROM service_requests WHERE id=2').fetchone()[0],'done')
            self.assertEqual(db.execute('SELECT status FROM service_requests WHERE id=1').fetchone()[0],'handling')
            self.h.mutate(db,'/queue-status',{'id':'1','status':'served'})
            self.h.mutate(db,'/pay',{'order_id':'1','discount':'0','method':'เงินสด','received':''})
            self.assertEqual(db.execute('SELECT status FROM service_requests WHERE id=1').fetchone()[0],'done')
        self.assertNotIn('ชำระต่อ',self.get(c,'/customer-queue'))
    def test_old_bill_service_button_also_routes_to_checkout(self):
        c=self.client();page=self.join(c)
        self.post(c,'/customer/service',{'csrf':self.csrf(page),'kind':'bill'})
        self.sign_in(c);page=self.get(c,'/customer-queue')
        result=self.post(c,'/service-done',{'csrf':self.csrf(page),'id':'1'})
        self.assertIn('ตรวจยอดก่อนรับชำระ',result)
        with app.connect() as db:self.assertEqual(db.execute('SELECT status FROM service_requests WHERE id=1').fetchone()[0],'handling')
    def test_failed_batch_retains_draft_and_success_clears_it(self):
        c=self.client();self.sign_in(c);page=self.get(c,'/products')
        data={'csrf':self.csrf(page),'request_key':'draft-stock-batch-0001','common_reason':'ตรวจนับ','qty_1':'7','qty_2':'-999'}
        result=self.post(c,'/stock-batch',data)
        self.assertIn('name=qty_1 value="7"',result);self.assertIn('name=qty_2 value="-999"',result)
        with app.connect() as db:self.assertEqual(db.execute('SELECT stock FROM products WHERE id=1').fetchone()[0],72)
        other=self.client();self.sign_in(other);self.assertNotIn('name=qty_1 value="7"',self.get(other,'/products'))
        data.update(csrf=self.csrf(result),qty_2='-1')
        self.post(c,'/stock-batch',data)
        result=self.get(c,'/products');self.assertNotIn('name=qty_1 value="7"',result)
        with app.connect() as db:self.assertEqual(db.execute('SELECT stock FROM products WHERE id=1').fetchone()[0],79)
    def test_nearby_reservation_requires_acknowledgement_before_opening(self):
        future=(datetime.now()+timedelta(minutes=45)).isoformat(timespec='minutes')
        with app.connect() as db:
            rid=db.execute('INSERT INTO reservations(name,phone,table_id,time,guests) VALUES (?,?,?,?,2)',('ทดสอบ','0812345678',2,future)).lastrowid
            with self.assertRaises(ValueError):self.h.mutate(db,'/open',{'table_id':'2'})
            with self.assertRaises(ValueError):self.h.mutate(db,'/open',{'table_id':'2','reservation_ack':'999'})
            self.h.mutate(db,'/open',{'table_id':'2','reservation_ack':str(rid)})
            self.assertEqual(db.execute("SELECT COUNT(*) FROM orders WHERE table_id=2 AND status='open'").fetchone()[0],1)
    def test_qr_shortcut_shows_only_selected_order(self):
        with app.connect() as db:self.h.mutate(db,'/open',{'table_id':'2'})
        c=self.client();self.sign_in(c)
        result=self.get(c,'/qr?order_id=2')
        self.assertIn('QR โต๊ะ T02',result);self.assertNotIn('QR โต๊ะ T01',result)
    def upload_request(self,c,path,data,raw):
        from urllib.request import Request
        boundary='nightbar-upload-test-boundary';body=b''
        for k,v in data.items():body+=f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
        body+=f'--{boundary}\r\nContent-Disposition: form-data; name="photo"; filename="../../unsafe-name.png"\r\nContent-Type: image/png\r\n\r\n'.encode()+raw+f'\r\n--{boundary}--\r\n'.encode()
        return c.open(Request(self.base+path,body,headers={'Content-Type':'multipart/form-data; boundary='+boundary}),timeout=8).read().decode()
    def test_reading_tools_and_order_next_steps_follow_live_status(self):
        c=self.client();page=self.cart(c);data=self.payload(page)
        page=self.post(c,'/customer/checkout',data)
        self.assertIn('id=reading-tools',page);self.assertIn('ตัวอักษรใหญ่',page);self.assertIn('สีชัดขึ้น',page)
        self.assertIn('ทำต่ออย่างไร',page);self.assertIn('ไม่ต้องส่งรายการเดิมซ้ำ',page)
        with app.connect() as db:
            item=db.execute('SELECT item_id FROM customer_lines LIMIT 1').fetchone()[0]
            self.h.mutate(db,'/production-status',{'item_id':str(item),'expected':'received','status':'preparing'})
        live=json.loads(self.get(c,'/live/my-orders?'+urlencode({'confirmed':data['request_key']})))
        self.assertIn('ร้านกำลังจัดเตรียม',live['html']);self.assertNotIn('id=reading-tools',live['html'])
        self.assertIn('id=reading-tools',self.get(c,'/login'))

    def test_booking_confirmation_distinguishes_pending_review_confirmed(self):
        with app.connect() as db:self.h.mutate(db,'/deposit-settings',{'amount':'100','min_guests':'1','hold':'15','cancel_hours':'24','instructions':'Test account'})
        c=self.client();time=(datetime.now()+timedelta(days=3)).isoformat(timespec='minutes')
        page=self.get(c,'/booking?'+urlencode({'time':time,'guests':2}))
        key='booking-next-steps-test-001'
        page=self.post(c,'/customer/booking',{'csrf':self.csrf(page),'request_key':key,'name':'Test Guest','phone':'0812345678','time':time,'guests':'2','table_id':'2','consent':'1','deposit_consent':'1'})
        self.assertIn('ยังไม่ยืนยันการจอง',page);self.assertIn('ชำระมัดจำ / แนบสลิป',page)
        endpoint='/live/booking-confirmation?'+urlencode({'confirmed':key})
        with app.connect() as db:db.execute("UPDATE booking_deposits SET state='review'")
        self.assertIn('ส่งหลักฐานแล้ว',json.loads(self.get(c,endpoint))['html'])
        with app.connect() as db:db.execute("UPDATE booking_deposits SET state='confirmed'")
        self.assertIn('จองโต๊ะสำเร็จ',json.loads(self.get(c,endpoint))['html'])
        other=self.client();self.assertEqual(json.loads(self.get(other,endpoint))['html'],'')

    def test_short_checkout_http_and_cleanup_action(self):
        with app.connect() as db:self.h.mutate(db,'/add',{'order_id':'1','product_id':'1','qty':'2'})
        c=self.client();self.sign_in(c);page=self.get(c,'/checkout?id=1')
        self.assertIn('ยืนยันยอดและรับชำระ',page)
        quote=re.search(r'name=quote value=([0-9a-f]+)',page).group(1)
        key=re.search(r'name=request_key value="([^"]+)"',page).group(1)
        data={'csrf':self.csrf(page),'order_id':'1','quote':quote,'request_key':key,'method':'เงินสด','received':'200'}
        page=self.post(c,'/checkout-simple',data);self.assertIn('ทำความสะอาดเสร็จ / พร้อมรับลูกค้า',page)
        self.post(c,'/checkout-simple',data)
        with app.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM payments').fetchone()[0],1)

    def test_paid_order_uses_large_receipt_for_printing(self):
        with app.connect() as db:
            self.h.mutate(db,'/add',{'order_id':'1','product_id':'1','qty':'1'})
            self.h.mutate(db,'/pay',{'order_id':'1','discount':'0','method':'เงินสด','received':'100'})
        c=self.client();self.sign_in(c)
        for path in ['/order?id=1','/receipt?id=1']:
            html=self.get(c,path)
            self.assertIn('class=receipt-sheet',html);self.assertIn('font-size:16pt!important',html)
            self.assertIn('ยอดชำระสุทธิ',html);self.assertNotIn('<th>ผู้รับ</th>',html)

    def test_customer_deposit_slip_private_upload_and_validation(self):
        import io
        from PIL import Image
        from urllib.error import HTTPError
        with app.connect() as db:self.h.mutate(db,'/deposit-settings',{'amount':'100','min_guests':'1','hold':'15','cancel_hours':'24','instructions':'Test transfer only'})
        c=self.client();page=self.get(c,'/booking?'+urlencode({'time':(datetime.now()+timedelta(days=2)).isoformat(timespec='minutes'),'guests':2}));csrf=self.csrf(page)
        result=self.post(c,'/customer/booking',{'csrf':csrf,'request_key':'private-slip-booking-test-001','name':'Slip Guest','phone':'0812345678','time':(datetime.now()+timedelta(days=2)).isoformat(timespec='minutes'),'guests':'2','table_id':'2','consent':'1','deposit_consent':'1'})
        with app.connect() as db:rid=db.execute('SELECT MAX(id) FROM reservations').fetchone()[0]
        self.assertIn('แนบสลิปโอนมัดจำ',result)
        data={'csrf':csrf,'id':str(rid),'reference':''}
        self.upload_request(c,'/customer/deposit-reference',data,b'not an image')
        with app.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM deposit_slips').fetchone()[0],0)
        out=io.BytesIO();Image.new('RGB',(240,300),'white').save(out,'PNG');raw=out.getvalue()
        self.upload_request(c,'/customer/deposit-reference',data,raw)
        with app.connect() as db:
            slip=db.execute('SELECT id FROM deposit_slips').fetchone()[0]
            self.assertEqual(db.execute('SELECT state FROM booking_deposits').fetchone()[0],'review')
        url=self.base+'/deposit-slip?id='+str(slip)
        with c.open(url) as response:
            self.assertEqual(response.read(),raw);self.assertIn('no-store',response.headers.get('Cache-Control'))
        other=self.client()
        with self.assertRaises(HTTPError) as denied:other.open(url)
        self.assertEqual(denied.exception.code,404);denied.exception.close()
        badcsrf=dict(data,csrf='invalid')
        self.upload_request(c,'/customer/deposit-reference',badcsrf,raw)
        with app.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM deposit_slips').fetchone()[0],1)
        owner=self.client();self.sign_in(owner)
        self.assertIn('/deposit-slip?id='+str(slip),self.get(owner,'/reservations?view=deposits'))
        with owner.open(url) as response:self.assertEqual(response.read(),raw)
        with app.connect() as db:db.execute("INSERT INTO users(username,password,role) VALUES ('slip-staff',?,'staff')",(app.password('test-password'),))
        staff=self.client();self.sign_in(staff,'slip-staff')
        with self.assertRaises(HTTPError) as denied:staff.open(url)
        self.assertEqual(denied.exception.code,404);denied.exception.close()

    def test_reservation_arrival_http_opens_bill_and_repeat_reuses(self):
        with app.connect() as db:
            rid=db.execute('INSERT INTO reservations(name,phone,table_id,time,guests) VALUES (?,?,?,?,?)',('Arrival Guest','0812345678',2,(datetime.now()+timedelta(hours=1)).isoformat(),3)).lastrowid
        c=self.client();self.sign_in(c);page=self.get(c,'/reservations')
        self.assertIn('รับลูกค้า / เปิดโต๊ะ',page)
        data={'csrf':self.csrf(page),'id':str(rid),'status':'arrived','target':'2'}
        opened=self.post(c,'/reservation-status',data)
        self.assertIn('T02',opened);self.assertIn('QR',opened)
        self.post(c,'/reservation-status',data)
        with app.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM orders').fetchone()[0],2)
            self.assertEqual(db.execute('SELECT guests FROM orders WHERE id=2').fetchone()[0],3)
        self.assertIn('ดูบิล #2',self.get(c,'/reservations'))
        when=(datetime.now()+timedelta(minutes=40)).isoformat(timespec='minutes')
        payload=json.loads(self.get(c,'/live/booking?'+urlencode({'time':when,'guests':2})))
        self.assertEqual(next(r for r in payload['tables'] if r['id']=='2')['state'],'reserved')

    def test_bank_qr_multipart_original_asset_and_permissions(self):
        import io,visuals
        from PIL import Image
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as assets:
            with patch.object(visuals,'ASSETS',Path(assets)):
                c=self.client();self.sign_in(c);page=self.get(c,'/settings?tab=shop')
                self.assertIn('enctype="multipart/form-data"',page)
                out=io.BytesIO();Image.new('RGB',(240,240),'white').save(out,'PNG');raw=out.getvalue()
                self.upload_request(c,'/deposit-qr',{'csrf':self.csrf(page),'bank':'Test bank','payee':'Test owner'},raw)
                with app.connect() as db:name=db.execute("SELECT value FROM settings WHERE key='deposit_qr'").fetchone()[0]
                self.assertEqual(c.open(self.base+'/assets/'+name).read(),raw)
                self.upload_request(c,'/deposit-qr',{'csrf':self.csrf(page),'bank':'Invalid','payee':'Invalid'},b'bad image')
                with app.connect() as db:self.assertEqual(db.execute("SELECT value FROM settings WHERE key='deposit_bank'").fetchone()[0],'Test bank')
                self.assertEqual(len(list(Path(assets).glob('bank-qr-*'))),1)
                from urllib.error import HTTPError
                with self.assertRaises(HTTPError) as denied:self.upload_request(c,'/deposit-qr',{'csrf':'wrong','bank':'Invalid','payee':'Invalid'},raw)
                self.assertEqual(denied.exception.code,403);denied.exception.close()
                self.assertEqual(len(list(Path(assets).glob('bank-qr-*'))),1)

    def test_unified_menu_multipart_and_invalid_photo_rollback(self):
        import visuals,io
        from PIL import Image
        old=visuals.ASSETS
        with tempfile.TemporaryDirectory() as assets:
            visuals.ASSETS=Path(assets)
            try:
                c=self.client();self.sign_in(c);page=self.get(c,'/products?view=edit&product_id=1')
                data={'csrf':self.csrf(page),'product_id':'1','name':'Edited beer','category':'Beer','price':'125','cost':'50','minimum':'12','active':'1','description':'Photo and details','featured':'1','image':'','station':'bar'}
                photo=io.BytesIO();Image.new('RGB',(32,32),'green').save(photo,'PNG')
                self.upload_request(c,'/product-save',data,photo.getvalue())
                with app.connect() as db:
                    row=db.execute('SELECT * FROM products WHERE id=1').fetchone();self.assertEqual((row['name'],row['price'],row['stock']),('Edited beer',12500,72))
                    self.assertTrue(db.execute('SELECT image FROM product_presentation WHERE product_id=1').fetchone()[0].startswith('menu-upload-'))
                self.upload_request(c,'/product-save',data|{'name':'Wrong','price':'200'},b'not an image')
                with app.connect() as db:self.assertEqual(db.execute('SELECT price FROM products WHERE id=1').fetchone()[0],12500)
            finally:visuals.ASSETS=old
    def test_menu_upload_create_replace_and_remove_preserves_product(self):
        import visuals,io
        from PIL import Image
        old=visuals.ASSETS
        with tempfile.TemporaryDirectory() as assets:
            visuals.ASSETS=Path(assets)
            try:
                c=self.client(); self.sign_in(c);page=self.get(c,'/products');photo=io.BytesIO();Image.new('RGB',(1800,1200),'green').save(photo,'PNG')
                data={'csrf':self.csrf(page),'name':'รูปทดสอบ','category':'อาหาร','price':'79','cost':'30','stock':'20','minimum':'5','description':'ทดสอบภาพ','featured':'1'}
                self.upload_request(c,'/product',data,photo.getvalue())
                with app.connect() as db:
                    p=db.execute("SELECT * FROM products WHERE name='รูปทดสอบ'").fetchone(); before=tuple(p); pid=p['id'];image=db.execute('SELECT image FROM product_presentation WHERE product_id=?',(pid,)).fetchone()[0]
                self.assertTrue(image.startswith('menu-upload-'));self.assertNotIn('unsafe',image)
                with Image.open(visuals.ASSETS/image) as img:self.assertEqual(img.size,(960,640));self.assertEqual(img.format,'WEBP')
                self.assertEqual(c.open(self.base+'/assets/'+image).status,200)
                data={'csrf':self.csrf(page),'product_id':pid,'image':image,'description':'แก้ภาพ','featured':'0'}
                self.upload_request(c,'/product-presentation',data,photo.getvalue())
                with app.connect() as db:
                    self.assertEqual(tuple(db.execute('SELECT * FROM products WHERE id=?',(pid,)).fetchone()),before)
                    self.assertNotEqual(db.execute('SELECT image FROM product_presentation WHERE product_id=?',(pid,)).fetchone()[0],image)
                self.post(c,'/product-presentation',data|{'image':''})
                with app.connect() as db:self.assertEqual(db.execute('SELECT image FROM product_presentation WHERE product_id=?',(pid,)).fetchone()[0],'')
            finally:visuals.ASSETS=old
    def test_invalid_upload_rolls_back_product_and_rejects_wrong_csrf(self):
        from urllib.error import HTTPError
        c=self.client();self.sign_in(c);page=self.get(c,'/products')
        data={'csrf':self.csrf(page),'name':'ห้ามเพิ่ม','category':'อาหาร','price':'79','cost':'30','stock':'20','minimum':'5','featured':'0'}
        self.assertIn('อ่านรูปไม่ได้',self.upload_request(c,'/product',data,b'<svg onload="alert(1)"></svg>'))
        with app.connect() as db:self.assertIsNone(db.execute("SELECT id FROM products WHERE name='ห้ามเพิ่ม'").fetchone())
        with self.assertRaises(HTTPError) as error:self.upload_request(c,'/product',data|{'csrf':'wrong'},b'invalid')
        self.assertEqual(error.exception.code,403);error.exception.close()
        with app.connect() as db:db.execute("INSERT INTO users(username,password,role) VALUES ('uploader-staff',?,'staff')",(app.password('staff-password'),))
        staff=self.client();self.sign_in(staff,'uploader-staff','staff-password')
        with self.assertRaises(HTTPError) as error:self.upload_request(staff,'/product',data,b'invalid')
        self.assertEqual(error.exception.code,403);error.exception.close()
    def test_image_upload_limits_and_script_safe_json(self):
        import menu_uploads,io
        from PIL import Image
        with self.assertRaises(ValueError):menu_uploads.normalized(b'x'*(menu_uploads.MAX_FILE+1))
        image=io.BytesIO();Image.new('RGB',(10,10)).save(image,'GIF')
        with self.assertRaises(ValueError):menu_uploads.normalized(image.getvalue())
        with app.connect() as db:
            db.execute('INSERT INTO product_presentation VALUES (?,?,?,0)',(1,'','</script><script>bad</script>'))
            script=menu_uploads.script(db);text=re.search(r'id=menu-presentation-data>(.*?)</script>',script).group(1)
            self.assertNotIn('<',text);self.assertEqual(json.loads(text)['1']['description'],'</script><script>bad</script>')
    def test_password_recovery_one_time_and_session_revocation(self):
        import html
        manager=self.client(); self.sign_in(manager)
        page=self.get(manager,'/account-security')
        result=self.post(manager,'/issue-reset',{'csrf':self.csrf(page),'user_id':1,'manager_password':'test-password'})
        link=html.unescape(re.search(r'href="([^"]+/reset-password\?token=[^"]+)"',result).group(1))
        path=link.split(self.base)[1]; raw=path.split('token=')[1]
        other=self.client(); reset=self.get(other,path)
        csrf=re.search(r'name=csrf value="([^"]+)"',reset).group(1)
        invalid=self.post(other,'/reset-password',{'csrf':csrf,'token':raw,'new':'changed-password','confirm':'different'})
        self.assertIn('กรอกทั้งสองช่องให้ตรงกัน',invalid)
        csrf=re.search(r'name=csrf value="([^"]+)"',invalid).group(1)
        result=self.post(other,'/reset-password',{'csrf':csrf,'token':raw,'new':'changed-password','confirm':'changed-password'})
        self.assertIn('ตั้งรหัสผ่านใหม่แล้ว',result)
        self.assertIn('ยินดีต้อนรับกลับ',self.get(manager,'/'))
        self.assertIn('ลิงก์นี้ใช้ไม่ได้แล้ว',self.get(other,path))
        self.assertIn('OPERATIONS / JUPITER',self.sign_in(other,password='changed-password'))
        with app.connect() as db:
            self.assertNotEqual(db.execute('SELECT token_hash FROM password_resets').fetchone()[0],raw)
            audit=' '.join(r[0] for r in db.execute('SELECT action FROM audit'))
            self.assertNotIn('test-password',audit); self.assertNotIn('changed-password',audit); self.assertNotIn(raw,audit)
    def test_recovery_expiry_and_staff_permissions(self):
        import auth_ui
        with app.connect() as db:
            db.execute("INSERT INTO users(username,password,role) VALUES ('staff',?,'staff')",(app.password('staff-password'),))
            db.execute('INSERT INTO password_resets(user_id,token_hash,expires,issued_by,created) VALUES (1,?,?,?,?)',(auth_ui.digest('expired-token'),(datetime.now()-timedelta(minutes=1)).isoformat(),'owner',app.now()))
        c=self.client(); self.assertIn('ลิงก์นี้ใช้ไม่ได้แล้ว',self.get(c,'/reset-password?token=expired-token'))
        self.sign_in(c,'staff','staff-password')
        from urllib.error import HTTPError
        with self.assertRaises(HTTPError) as error: self.get(c,'/account-security')
        self.assertEqual(error.exception.code,403); error.exception.close()
    def test_login_failure_throttle_and_forgot_page(self):
        c=self.client()
        self.assertIn('ยังไม่ส่งลิงก์ผ่านอีเมล',self.get(c,'/forgot-password'))
        for i in range(8): self.sign_in(c,password='wrong-password')
        self.assertIn('กรุณารอ 10 นาที',self.sign_in(c,password='wrong-password'))
        with app.connect() as db: self.assertEqual(db.execute('SELECT COUNT(*) FROM login_failures').fetchone()[0],8)
    def test_password_change_invalidates_outstanding_reset(self):
        import auth_ui
        with app.connect() as db:
            db.execute('INSERT INTO password_resets(user_id,token_hash,expires,issued_by,created) VALUES (1,?,?,?,?)',(auth_ui.digest('outstanding'),(datetime.now()+timedelta(minutes=15)).isoformat(),'owner',app.now()))
            self.h.mutate(db,'/password',{'old':'test-password','new':'updated-password'})
            self.assertIsNotNone(db.execute('SELECT used FROM password_resets').fetchone()[0])
    def test_live_endpoints_keep_customer_data_private(self):
        c=self.client(); data=self.payload(self.cart(c)); self.post(c,'/customer/checkout',data)
        own=json.loads(self.get(c,'/live/my-orders'))
        self.assertIn('ออเดอร์ #0001',own['html'])
        other=self.client(); other_data=json.loads(self.get(other,'/live/my-orders'))
        self.assertNotIn('ออเดอร์ #0001',other_data['html'])
        self.assertIn('เข้าสู่ระบบ',self.get(other,'/live/queue'))
        self.sign_in(other)
        queue=json.loads(self.get(other,'/live/queue'))
        self.assertIn(1,queue['ids']); self.assertIn('ไม่ใส่มะนาว',queue['html'])
    def test_customer_cannot_order_into_checkout_locked_bill(self):
        c=self.client(); data=self.payload(self.cart(c))
        with app.connect() as db:
            self.h.mutate(db,'/add',{'order_id':'1','product_id':'2','qty':'1'})
            self.h.mutate(db,'/checkout-freeze',{'order_id':'1','discount':'0'})
        self.assertIn('กำลังชำระเงิน',self.post(c,'/customer/checkout',data))
        with app.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM customer_requests').fetchone()[0],0)
    def test_split_payment_http_receipts_and_shift_totals(self):
        with app.connect() as db:self.h.mutate(db,'/add',{'order_id':'1','product_id':'1','qty':'2'})
        c=self.client(); self.sign_in(c)
        page=self.get(c,'/checkout?id=1')
        page=self.post(c,'/checkout-freeze',{'csrf':self.csrf(page),'order_id':1,'discount':0})
        page=self.post(c,'/bill-split',{'csrf':self.csrf(page),'order_id':1,'mode':'equal','count':2})
        ids=re.findall(r'name=part_id value=(\d+)',page); self.assertEqual(len(ids),2)
        page=self.post(c,'/payment-add',{'csrf':self.csrf(page),'order_id':1,'part_id':ids[0],'amount':95,'received':100,'method':'เงินสด','request_key':'http-payment-first-001'})
        self.assertIn('คงเหลือ ฿95.00',page)
        self.assertIn('ใบรับเงินส่วนแบ่ง',self.get(c,'/part-receipt?id='+ids[0]))
        page=self.post(c,'/payment-add',{'csrf':self.csrf(page),'order_id':1,'part_id':ids[1],'amount':95,'received':'','method':'โอนเงิน','request_key':'http-payment-second-001'})
        self.assertIn('หลายช่องทาง',page)
        shift=self.get(c,'/shifts'); self.assertIn('1,095.00',shift)
        with app.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM payments').fetchone()[0],2)

    def test_focused_settings_and_reservation_workspaces(self):
        c=self.client(); self.sign_in(c)
        shop=self.get(c,'/settings?tab=shop')
        self.assertIn('action="/deposit-settings"',shop)
        self.assertIn('action="/deposit-qr"',shop)
        self.assertNotIn('action="/user"',shop)
        saved=self.post(c,'/deposit-settings',{'csrf':self.csrf(shop),'amount':'0','min_guests':'2','hold':'15','cancel_hours':'24','instructions':''})
        self.assertIn('บันทึกเรียบร้อยแล้ว',saved)
        self.assertIn('action="/deposit-settings"',saved)
        staff=self.get(c,'/settings?tab=staff')
        self.assertIn('action="/user"',staff)
        self.assertNotIn('action="/deposit-settings"',staff)
        self.assertIn('action="/password"',self.get(c,'/settings?tab=security'))
        self.assertIn('href=/backup',self.get(c,'/settings?tab=backup'))
        bookings=self.get(c,'/reservations')
        self.assertNotIn('action="/reserve"',bookings)
        self.assertNotIn('action="/deposit-settings"',bookings)
        self.assertIn('action="/reserve"',self.get(c,'/reservations?view=new'))
        self.assertIn('deposit-workspace',self.get(c,'/reservations?view=deposits'))
        order=self.get(c,'/order?id=1')
        self.assertEqual(order.count('href="/receipt?id=1"'),1)

    def test_latest_order_summary_is_session_scoped_and_updates(self):
        c=self.client(); page=self.cart(c)
        self.post(c,'/customer/checkout',self.payload(page))
        menu=self.get(c,'/menu')
        self.assertIn('id=latest-order',menu)
        self.assertIn('ร้านรับออเดอร์แล้ว',menu)
        self.assertIn('nav-cart-with-bottom',menu)
        other=self.client(); self.join(other)
        self.assertEqual(json.loads(self.get(other,'/live/order-summary'))['html'],'')
        with app.connect() as db:
            db.execute("UPDATE customer_requests SET status='preparing'")
        self.assertIn('กำลังจัดเตรียม',json.loads(self.get(c,'/live/order-summary'))['html'])
        with app.connect() as db:
            db.execute("UPDATE orders SET status='paid' WHERE id=1")
        self.assertEqual(json.loads(self.get(c,'/live/order-summary'))['html'],'')

if __name__=='__main__': unittest.main()
