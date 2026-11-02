"""Small browser enhancement for the Python-rendered queue and customer status."""
import json

def controls(staff=False):
    sound='<button type=button class=secondary id=live-sound>เปิดเสียงแจ้งเตือน</button>' if staff else ''
    return '<section class="panel noprint"><div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap"><span class=badge id=live-status role=status>อัปเดตอัตโนมัติทุก 5 วินาที</span>'+sound+'<button type=button class=secondary id=live-refresh>อัปเดตตอนนี้</button></div><small id=live-detail>เปิดหน้านี้ไว้เพื่อรับข้อมูลใหม่ ระบบจะเก็บข้อความที่กำลังกรอกไว้</small></section>'

def script(endpoint,initial_ids=None,staff=False):
    config=json.dumps({'endpoint':endpoint,'ids':initial_ids or [],'staff':staff})
    return '<script>const liveConfig='+config+''';
(()=>{
 const target=document.getElementById('live-content'), status=document.getElementById('live-status'), detail=document.getElementById('live-detail');
 if(!target)return;
 let audio=null, sound=false, busy=false, failures=0, pending=null, lastHtml=target.innerHTML;
 const seen=new Set(liveConfig.ids), drafts=new Map();
 const soundButton=document.getElementById('live-sound');
 const key=form=>form.getAttribute('action')+':'+(form.querySelector('[name=id]')?.value||'default');
 target.addEventListener('input',event=>{const form=event.target.closest('form');if(form)form.dataset.edited='1';});
 target.addEventListener('change',event=>{const form=event.target.closest('form');if(form)form.dataset.edited='1';});
 function beep(){if(!sound||!audio)return;try{audio.resume();const oscillator=audio.createOscillator(),gain=audio.createGain();oscillator.connect(gain);gain.connect(audio.destination);oscillator.frequency.value=880;gain.gain.setValueAtTime(.055,audio.currentTime);gain.gain.exponentialRampToValueAtTime(.001,audio.currentTime+.4);oscillator.start();oscillator.stop(audio.currentTime+.4);}catch(error){detail.textContent='เบราว์เซอร์หยุดเสียง กรุณากดเปิดเสียงอีกครั้ง';}}
 if(soundButton)soundButton.addEventListener('click',async()=>{if(!audio){const Audio=window.AudioContext||window.webkitAudioContext;if(!Audio){detail.textContent='เบราว์เซอร์นี้ไม่รองรับเสียงแจ้งเตือน';return;}audio=new Audio();}await audio.resume();sound=!sound;soundButton.textContent=sound?'ปิดเสียงแจ้งเตือน':'เปิดเสียงแจ้งเตือน';soundButton.setAttribute('aria-pressed',String(sound));if(sound)beep();});
 function apply(html){
  if(target.contains(document.activeElement)&&document.activeElement.closest('form')){pending=html;detail.textContent='มีข้อมูลใหม่ รอให้กรอกแบบฟอร์มเสร็จก่อนอัปเดต';return;}
  if(html===lastHtml)return;
  target.querySelectorAll('form[data-edited="1"]').forEach(form=>{const values={};form.querySelectorAll('input:not([type=hidden]),select,textarea').forEach(input=>{if(input.name)values[input.name]=input.value;});drafts.set(key(form),values);});
  target.innerHTML=html;lastHtml=html;pending=null;
  target.querySelectorAll('form').forEach(form=>{const values=drafts.get(key(form));if(!values)return;form.querySelectorAll('input:not([type=hidden]),select,textarea').forEach(input=>{if(Object.hasOwn(values,input.name)&&(input.tagName!=='SELECT'||[...input.options].some(option=>option.value===values[input.name])))input.value=values[input.name];});form.dataset.edited='1';});
 }
 target.addEventListener('focusout',()=>{setTimeout(()=>{if(pending)apply(pending);},150);});
 async function update(){
  if(busy)return;busy=true;
  try{
   const response=await fetch(liveConfig.endpoint,{credentials:'same-origin',cache:'no-store'});
   if(!response.ok||!response.headers.get('content-type')?.includes('application/json')){status.textContent='เซสชันอาจหมดอายุ';detail.textContent='กรุณารีเฟรชหน้าและเข้าสู่ระบบอีกครั้ง';return;}
   const data=await response.json();let fresh=false;(data.ids||[]).forEach(id=>{if(!seen.has(id)){seen.add(id);fresh=true;}});if(fresh&&liveConfig.staff)beep();
   apply(data.html);failures=0;status.textContent='เชื่อมต่อแล้ว · อัปเดตอัตโนมัติ';if(!pending)detail.textContent=(fresh?'มีรายการใหม่ · ':'')+'อัปเดตล่าสุด '+new Date().toLocaleTimeString('th-TH');
  }catch(error){failures++;status.textContent='เชื่อมต่อขัดข้อง · กำลังลองใหม่';detail.textContent='รายการเดิมยังอยู่ กรุณาตรวจเครือข่าย';}
  finally{busy=false;}
 }
 document.getElementById('live-refresh')?.addEventListener('click',update);
 target.addEventListener('submit',async event=>{
  const form=event.target,action=form.getAttribute('action');
  if(!['/queue-status','/service-done','/customer/service','/production-status'].includes(action))return;
  event.preventDefault();const button=form.querySelector('button');if(button)button.disabled=true;
  try{
   const response=await fetch(action,{method:'POST',body:new URLSearchParams(new FormData(form)),credentials:'same-origin'});
   if(!response.ok)throw new Error('ส่งข้อมูลไม่สำเร็จ กรุณาลองใหม่หรือรีเฟรชหน้า');
   const destination=new URL(response.url);
   if(action==='/service-done'&&destination.origin===location.origin&&['/checkout','/receipt'].includes(destination.pathname)){location.assign(destination.href);return;}
   const message=new URL(response.url).searchParams.get('message');
   if(message!=='บันทึกเรียบร้อยแล้ว')throw new Error(message||'เซสชันอาจหมดอายุ กรุณารีเฟรชหน้า');
   delete form.dataset.edited;drafts.delete(key(form));
   if(form.contains(document.activeElement))document.activeElement.blur();
   await update();detail.textContent='บันทึกแล้ว · อัปเดตอัตโนมัติต่อเนื่อง';
  }catch(error){detail.textContent=error.message;status.textContent='กรุณาตรวจสอบรายการ';}
  finally{if(button&&button.isConnected)button.disabled=false;}
 });
 async function poll(){await update();setTimeout(poll,Math.min(30000,5000*(failures+1)));}setTimeout(poll,5000);
})();</script>'''
