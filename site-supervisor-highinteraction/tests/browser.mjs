// Requires a local Chrome debugging endpoint. Always use a disposable application copy.
import assert from 'node:assert/strict';
const base=process.argv[2]||'http://127.0.0.1:18010';
const debug=process.argv[3]||'http://127.0.0.1:9225';
const target=await fetch(debug+'/json/new?'+encodeURIComponent('about:blank'),{method:'PUT'}).then(r=>r.json());
const ws=new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject});
let sequence=0;const pending=new Map(),errors=[];
ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.id){const entry=pending.get(m.id);pending.delete(m.id);if(m.error)entry.reject(Error(JSON.stringify(m.error)));else entry.resolve(m.result)}else if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails.text)};
function send(method,params={}){return new Promise((resolve,reject)=>{const id=++sequence;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}))})}
async function evaluate(expression){const r=await send('Runtime.evaluate',{expression:'(()=>eval('+JSON.stringify(expression)+'))()',awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value}
const delay=ms=>new Promise(r=>setTimeout(r,ms));
async function until(expression,timeout=10000){const end=Date.now()+timeout;while(Date.now()<end){if(await evaluate(expression))return;await delay(150)}throw Error('Timed out: '+expression)}
try{
 await send('Runtime.enable');await send('Page.enable');await send('Page.navigate',{url:base+'/#/alarms'});
 await until("document.querySelector('.em-region .em-admin-controls')");
 await evaluate(`window.testRPC=async(method,params={})=>{const r=await fetch('/cgi-bin/mgw.cgi',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({method,params,id:1})});return r.json()}`);
 // Start as an anonymous reader, even if the browser has an earlier session.
 await evaluate("testRPC('Logout')");await send('Page.reload');await until("document.querySelector('.em-region .em-admin-controls')");
 await evaluate(`window.testRPC=async(method,params={})=>(await fetch('/cgi-bin/mgw.cgi',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({method,params,id:1})})).json()`);
 assert.equal(await evaluate("document.querySelector('button.em-btn').matches(':disabled')"),false);
 assert.equal(await evaluate("[...document.querySelectorAll('button')].find(b=>b.textContent==='Suppress').matches(':disabled')"),true);
 assert.equal(await evaluate("getComputedStyle(document.querySelector('.em-admin-controls')).opacity"),'0.48');
 // The gear must open a visible drawer at both desktop and mobile widths.
 await evaluate("document.querySelector('.ss-main-header-main-menu').click()");await delay(250);
 assert.equal(await evaluate("document.querySelector('.ss-main-header-main-menu').getAttribute('aria-expanded')"),'true');
 assert.equal(await evaluate("document.querySelector('.ss-main-body-menu').getBoundingClientRect().left>=0"),true);
 assert.equal(await evaluate("Boolean(document.elementFromPoint(100,150)?.closest('.ss-main-body-menu'))"),true,'Drawer must receive pointer events above its backdrop');
 await evaluate("document.querySelector('.em-menu-backdrop').click()");
 assert.equal(await evaluate("document.querySelector('.ss-main-body-menu').inert"),true);
 await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
 await evaluate("document.querySelector('.ss-main-header-main-menu').click()");await delay(250);
 assert.equal(await evaluate("document.querySelector('.ss-main-body-menu').getBoundingClientRect().right<=390"),true);
 await evaluate("[...document.querySelectorAll('.em-menu-items a')].find(a=>a.textContent==='General System Settings').click()");
 await until("document.querySelector('[aria-label=\"Site Name\"]')");
 assert.equal(await evaluate("document.querySelector('[aria-label=\"Site Name\"]').matches(':disabled')"),true);
 assert.equal(await evaluate("document.querySelector('.ss-main-header-main-menu').getAttribute('aria-expanded')"),'false');
 await send('Emulation.clearDeviceMetricsOverride');
 await evaluate("location.hash='#/profile'");await until("document.querySelector('[aria-label=\"User View Level\"]')");
 assert.equal(await evaluate("document.querySelector('[aria-label=\"User View Level\"]').matches(':disabled')"),false);
 await evaluate("document.querySelector('[aria-label=\"Time Format\"]').value='24-hour';document.querySelector('.em-settings-form').requestSubmit()");
 await until("document.querySelector('.em-settings-form').textContent.includes('Settings saved')");
 assert.equal((await evaluate("testRPC('GetProfile')")).result.profile.timeFormat,'24-hour');
 await evaluate("location.hash='#/alarms'");await until("[...document.querySelectorAll('button')].some(b=>b.textContent==='Suppress')");
 const denied=await evaluate("testRPC('SuppressAlarms',{minutes:1})");assert.equal(denied.error.code,-32001);
 await evaluate("document.querySelector('.ss-main-header-login').click();document.querySelector('.em-modal [aria-label=Username]').value='admin';document.querySelector('.em-modal [aria-label=Password]').value='admin';document.querySelector('.em-modal').requestSubmit()");
 await until("document.querySelector('.ss-main-header-login-text').textContent==='admin' && !document.querySelector('.em-overlay')");
 assert.equal(await evaluate("[...document.querySelectorAll('button')].find(b=>b.textContent==='Suppress').matches(':disabled')"),false);
 // Admin settings save through real forms; Viewer access stays read-only.
 await evaluate("location.hash='#/generalsystem'");await until("document.querySelector('[aria-label=\"Site Name\"]')");
 assert.equal(await evaluate("document.querySelector('[aria-label=\"Site Name\"]').matches(':disabled')"),false);
 await evaluate("document.querySelector('[aria-label=\"Site Name\"]').value='Validation Store';document.querySelector('.em-settings-form').requestSubmit()");
 await until("document.querySelector('.em-settings-form').textContent.includes('Settings saved')");
 assert.equal((await evaluate("testRPC('GetSystemSettings')")).result.settings.system.siteName,'Validation Store');
 await evaluate("location.hash='#/users'");await until("document.querySelector('.em-user-editor')");
 await evaluate("document.querySelector('#user-username').value='viewer';document.querySelector('#user-password').value='view123';document.querySelector('[aria-label=\"User Role\"]').value='Viewer';document.querySelector('.em-user-editor').requestSubmit()");
 await until("[...document.querySelectorAll('.em-table td')].some(n=>n.textContent==='viewer')");
 await evaluate("document.querySelector('.ss-main-header-login').click();[...document.querySelectorAll('.em-modal button')].find(b=>b.textContent==='Logout').click()");
 await until("document.querySelector('.ss-main-header-login-text').textContent==='Login'");
 await evaluate("document.querySelector('.ss-main-header-login').click();document.querySelector('.em-modal [aria-label=Username]').value='viewer';document.querySelector('.em-modal [aria-label=Password]').value='view123';document.querySelector('.em-modal').requestSubmit()");
 await until("document.querySelector('.ss-main-header-login-text').textContent==='viewer'");
 await evaluate("location.hash='#/generalsystem/network'");await until("document.querySelector('[aria-label=\"ETH 0 IP Address\"]')");
 assert.equal(await evaluate("document.querySelector('[aria-label=\"ETH 0 IP Address\"]').matches(':disabled')"),true);
 assert.equal((await evaluate("testRPC('SaveSystemSettings',{section:'system',values:{siteName:'Forbidden'}})")).error.code,-32001);
 assert.equal((await evaluate("testRPC('SetTemperature',{deviceId:'487988082',value:60})")).error.code,-32001);
 await evaluate("location.hash='#/profile'");await until("document.querySelector('[aria-label=\"User View Level\"]')");
 await evaluate("document.querySelector('[aria-label=\"User View Level\"]').value='Advanced';document.querySelector('.em-settings-form').requestSubmit()");
 await until("document.querySelector('.em-settings-form').textContent.includes('Settings saved')");
 assert.equal((await evaluate("testRPC('GetSessionID')")).result.isAdministrator,false);
 await evaluate("document.querySelector('.ss-main-header-login').click();[...document.querySelectorAll('.em-modal button')].find(b=>b.textContent==='Logout').click()");
 await until("document.querySelector('.ss-main-header-login-text').textContent==='Login'");
 await evaluate("document.querySelector('.ss-main-header-login').click();document.querySelector('.em-modal [aria-label=Username]').value='admin';document.querySelector('.em-modal [aria-label=Password]').value='admin';document.querySelector('.em-modal').requestSubmit()");
 await until("document.querySelector('.ss-main-header-login-text').textContent==='admin' && !document.querySelector('.em-overlay')");
 console.log('Settings checks passed: desktop/mobile drawer, guest profile, admin configuration, Viewer login and server permissions.');
 const deviceId=await evaluate(`(async()=>{const catalog=await fetch('/catalog.php').then(r=>r.json());for(const d of catalog.devices){const r=await testRPC('GetDeviceState',{deviceId:d.id});if(r.result.state.unit==='°F')return d.id}})()`);
 await evaluate(`location.hash='#/device/${deviceId}'`);await until("[...document.querySelectorAll('button')].some(b=>b.textContent==='Controls')");
 await evaluate("[...document.querySelectorAll('button')].find(b=>b.textContent==='Controls').click()");
 assert.equal(await evaluate("document.querySelector('[aria-label=\"Temperature value (°F)\"]').matches(':disabled')"),false);
 await evaluate("const input=document.querySelector('[aria-label=\"High temperature limit (°F)\"]');input.value='45';input.closest('.em-setting-row').querySelector('button').click()");await delay(300);
 await evaluate("const input=document.querySelector('[aria-label=\"Temperature value (°F)\"]');input.value='60';input.closest('.em-setting-row').querySelector('button').click()");await delay(400);
 // Check logout and login preserve the Controls tab and immediately update disabled state.
 await evaluate("document.querySelector('.ss-main-header-login').click();[...document.querySelectorAll('.em-modal button')].find(b=>b.textContent==='Logout').click()");
 await until("document.querySelector('[aria-label=\"Temperature value (°F)\"]')?.matches(':disabled')");
 await evaluate("document.querySelector('.ss-main-header-login').click();document.querySelector('.em-modal [aria-label=Username]').value='admin';document.querySelector('.em-modal [aria-label=Password]').value='admin';document.querySelector('.em-modal').requestSubmit()");
 await until("document.querySelector('[aria-label=\"Temperature value (°F)\"]') && !document.querySelector('[aria-label=\"Temperature value (°F)\"]').matches(':disabled')");
 // Choose the real 1-minute option in the UI and verify expiry without changing the clock/state.
 await evaluate("const select=document.querySelector('[aria-label=\"Suppression duration\"]');select.value='1';[...select.closest('.em-setting-row').querySelectorAll('button')].find(b=>b.textContent==='Suppress').click()");
 await delay(400);
 let alarm=await evaluate(`testRPC('GetAlarms').then(r=>r.result.alarms.find(a=>a.iid==='${deviceId}'&&a.messagekey==='High temperature'&&a.resolution==='ACTIVE'))`);
 assert.equal(alarm.suppressed,true);assert.ok(alarm.suppressedUntil-Math.floor(Date.now()/1000)<=60);
 await evaluate("[...document.querySelectorAll('.em-tabs button')].find(b=>b.textContent==='Alarms').click()");
 assert.equal(await evaluate("document.querySelector('.em-tabbody').textContent.includes('High temperature')"),false);
 console.log('Browser checks passed: anonymous controls disabled, API rejects writes, admin unlocks controls, logout re-locks controls.'+(process.argv.includes('--quick')?' Checking manual restore.':' Waiting for selected one-minute suppression to expire.'));
 if(process.argv.includes('--quick')){await evaluate("testRPC('RestoreAlarms')");await evaluate("document.querySelector('.ss-main-header-refresh').click()");}
 else{const remaining=Math.max(0,alarm.suppressedUntil*1000-Date.now());await delay(remaining+11000);}
 await until("document.querySelector('.em-tabbody').textContent.includes('High temperature')",15000);
 alarm=await evaluate(`testRPC('GetAlarms').then(r=>r.result.alarms.find(a=>a.uid==='${alarm.uid}'))`);
 assert.equal(alarm.suppressed,false);assert.equal(alarm.resolution,'ACTIVE');
 await evaluate("location.hash='#/controlactivity'");await until("document.querySelector('.em-table')");
 assert.equal(await evaluate("document.querySelector('.em-region').textContent.includes('SuppressAlarms')"),true);
 await evaluate("location.hash='#/help'");await until("document.querySelector('[aria-label=\"Operator feedback\"]')");
 await evaluate(`document.querySelector('[aria-label="Operator feedback"]').value='<img src=x onerror="window.injected=true">; $(id)';[...document.querySelectorAll('button')].find(b=>b.textContent==='Submit feedback').click()`);
 await until("document.querySelector('.em-region').textContent.includes('<img src=x')");
 assert.equal(await evaluate("window.injected===true"),false);
 for(const path of ['/private/state.json','/unit1/private/state.json','/%70rivate/state.json','/unit1/README.md','/unit1/api.php','/tests/browser.mjs']){const status=await evaluate(`fetch(${JSON.stringify(path)}).then(r=>r.status)`);assert.equal(status,404,'Private route: '+path);}
 assert.deepEqual(errors,[]);
 console.log('Browser checks passed: alarm returned after '+(process.argv.includes('--quick')?'manual restore':'automatic expiry')+', admin activity rendered, feedback payload displayed literally, private routes blocked, no JavaScript exceptions.');
}finally{ws.close();await fetch(debug+'/json/close/'+target.id)}
