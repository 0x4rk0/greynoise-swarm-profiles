/* Site Supervisor browser interface. Device operations use JSON-RPC /cgi-bin/mgw.cgi. */
(() => {
  'use strict';
  const $ = (s,root=document) => root.querySelector(s);
  const $$ = (s,root=document) => Array.from(root.querySelectorAll(s));
  const make = (tag,cls,text) => {const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=String(text);return n;};
  const icon = (name) => make('span','material-icons em-icon',name);
  const groups=['Refrigeration','HVAC','Other','System'];
  const routes = [
    ['Summaries & Dashboards',[['Network','networksummary'],['Case Defrost Schedule','casedefrostsummary'],['System Tile','systemsummary'],['Active Alarm','alarms']]],
    ['Layouts',[['Layout Manager','layoutmanager'],['BX','bx'],['CX','cx'],['RX','rx']]],
    ['Analysis',[['System Logs & Statistics','logs'],['Control Activity','controlactivity']]],
    ['System',[['General System Settings','generalsystem'],['My Profile','profile'],['File Management & Licensing','filemanagement'],['Alarm Communications','alarmhandling'],['Logging Groups','loggroup'],['Users & Roles','users'],['Info','info'],['Protocol Mapping','protocolMapping'],['Certificate Management','certificate-management']]],
  ];
  const pageNames=Object.fromEntries(routes.flatMap(g=>g[1].map(v=>[v[1],v[0]])));
  let devices=[],alarms=[],dash={},devicesById=new Map(), current='systemsummary', opened=new Set(), searchTerm='', initDone=false;
  const deviceTabs=new Map();
  const ackKey='e3-alarm-ack'; const notesKey='e3-operator-notes';
  function persisted(key){try{return JSON.parse(localStorage.getItem(key)||'{}')}catch{return {}}}
  let ack=persisted(ackKey),notes=persisted(notesKey);
  function persist(key, obj){try{localStorage.setItem(key,JSON.stringify(obj))}catch{}}
  const niceDate=v=>{
    if(!v)return '—';const date=new Date(Number(v)*1000);
    const parts=Object.fromEntries(new Intl.DateTimeFormat(profile.locale,{year:'numeric',month:'2-digit',day:'2-digit',timeZone:systemSettings.localization?.timeZone}).formatToParts(date).map(p=>[p.type,p.value]));
    const formatted=profile.dateFormat.replace('yyyy',parts.year).replace('MM',parts.month).replace('dd',parts.day);
    return formatted+' '+date.toLocaleTimeString(profile.locale,{hour12:profile.timeFormat==='12-hour',timeZone:systemSettings.localization?.timeZone});
  };
  let session={},systemSettings={},profile={homeScreen:'systemsummary',viewLevel:'Basic',locale:'en-US',dateFormat:'MM/dd/yyyy',timeFormat:'12-hour'};
  const unitName=()=>systemSettings.system?.unitName||'E3 Unit01';
  const siteName=()=>systemSettings.system?.siteName||'maplewood';
  const isAdmin=()=>session.isAdministrator===true;
  const alarmActive=a=>a.resolution==='ACTIVE'&&!a.suppressed;
  const getHash=()=>decodeURIComponent(location.hash.replace(/^#\/?/,'')||'');
  function routePath(){let h=getHash().replace(/^\//,'');return h==='activealarm'?'alarms':h==='network'?'networksummary':h||profile.homeScreen;}
  function link(path){return '#/'+path;}
  function go(path){if(path==='systemsummary'&&location.hash==='#/')return render();location.hash=link(path);if(!location.hash)render();}
  function button(label,onClick,kind='primary'){const b=make('button','em-btn '+kind,label);b.type='button';b.addEventListener('click',onClick);return b;}
  function countNote(label,count){const x=make('span','em-count',count);x.title=label;return x}
  function alertBanner(text,kind='info'){const n=make('div','em-alert '+kind,text);return n;}
  function safeText(v){return String(v??'');}
  async function rpc(method, params={}) {
    const r={jsonrpc:'2.0',method,id:'1',params};
    const response=await fetch('/cgi-bin/mgw.cgi',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(r),cache:'no-store'});
    if(!response.ok)throw Error('API '+response.status);
    const d=await response.json();if(d.error)throw Error(d.error.message||'RPC error');return d.result||{};
  }
  function setMenu(open){
    document.body.classList.toggle('sim-menu-open',open);
    const gear=$('.ss-main-header-main-menu');if(gear)gear.setAttribute('aria-expanded',String(open));
    const menu=$('.ss-main-body-menu');if(menu){menu.inert=!open;menu.setAttribute('aria-hidden',String(!open));}
    const backdrop=$('.em-menu-backdrop');if(backdrop)backdrop.hidden=!open;
  }
  async function loadSettings(){
    const [settings,prefs]=await Promise.all([rpc('GetSystemSettings'),rpc('GetProfile')]);
    systemSettings=settings.settings||{};profile={...profile,...prefs.profile};
    const build=$('.ss-main-footer-build');if(build)build.textContent='E3 '+siteName()+' · '+unitName()+' 2.30F01';
  }
  function settingsForm(root,values,fields,onSave,restricted=true){
    const form=make('form','em-settings-form'),controls=restricted?adminControls(form):form;
    const inputs=new Map();
    for(const [key,label,type='text',options] of fields){
      const row=make('div','em-setting-row'),id='setting-'+key;
      const name=make('label',null,label);name.htmlFor=id;
      const input=make(type==='select'?'select':'input','em-input');input.id=id;input.name=key;input.setAttribute('aria-label',label);
      if(type==='select'){for(const option of options){const [value,text]=Array.isArray(option)?option:[option,option];const item=make('option',null,text);item.value=String(value);input.append(item)}}
      else input.type=type;
      if(type==='checkbox')input.checked=Boolean(values[key]);else input.value=String(values[key]??'');
      if(type==='number'){input.min='1';input.max=key==='unitNumber'?'255':'65535';input.step='1'}
      if(type==='text')input.maxLength=80;
      row.append(name,input);controls.append(row);inputs.set(key,{input,type});
    }
    const message=make('p','em-muted'),save=button('Save',()=>{});save.type='submit';controls.append(save);form.append(message);
    form.onsubmit=async e=>{e.preventDefault();if(restricted&&!isAdmin())return;const data={};for(const [key,{input,type}] of inputs)data[key]=type==='checkbox'?input.checked:type==='number'||/Baud$/.test(key)?Number(input.value):input.value;
      save.disabled=true;try{const result=await onSave(data);if(result.success){message.textContent='Settings saved';notice('Settings saved')}else message.textContent=result.message||'Unable to save settings'}catch(err){message.textContent=err.message}finally{save.disabled=false}};
    root.append(form);return form;
  }
  function generalSettings(root){
    const tabs=make('div','em-tabs'),pane=make('div');root.append(tabs,pane);
    const sections={
      system:['System Values',[
        ['siteName','Site Name'],['unitName','Unit Name'],['unitNumber','Unit Number','number'],['groupName','Group Name'],['webPort','Web Port','number']]],
      network:['Network Settings',[
        ['dhcp','Use DHCP','checkbox'],['ipAddress','ETH 0 IP Address'],['subnetMask','Subnet Mask'],['gateway','Default Gateway'],['dns','DNS Server'],['monitoringPort','Monitoring Port','number'],['legacyClientPort','Legacy Client Port','number']]],
      com:['COM Ports',[
        ['com1Protocol','COM 1 Protocol','select',['Disabled','Modbus','BACnet']],['com1Baud','COM 1 Baud Rate','select',[9600,19200,38400,57600,115200]],
        ['com2Protocol','COM 2 Protocol','select',['Disabled','Modbus','BACnet']],['com2Baud','COM 2 Baud Rate','select',[9600,19200,38400,57600,115200]]]],
      localization:['Localization',[
        ['locale','Language','select',[['en-US','English (United States)'],['en-GB','English (United Kingdom)']]],
        ['timeZone','Time Zone','select',['America/Los_Angeles','America/Denver','America/Chicago','America/New_York','Europe/London','Etc/UTC']],
        ['dateFormat','Date Format','select',['MM/dd/yyyy','dd/MM/yyyy','yyyy-MM-dd']],['timeFormat','Time Format','select',['12-hour','24-hour']]]]
    };
    let advanced=profile.viewLevel==='Advanced';
    const show=key=>{tabs.replaceChildren();pane.replaceChildren();for(const [section,[name]] of Object.entries(sections))tabs.append(button(name,()=>{history.replaceState(null,'','#/generalsystem/'+section);show(section)},'tab'+(key===section?' selected':'')));
      heading(pane,sections[key][0]);if(profile.viewLevel==='Basic')pane.append(button(advanced?'Basic':'Advanced',()=>{advanced=!advanced;show(key)},'secondary'));const fields=sections[key][1].filter(([field])=>advanced||!['webPort','monitoringPort','legacyClientPort'].includes(field));settingsForm(pane,systemSettings[key]||{},fields,async values=>{const result=await rpc('SaveSystemSettings',{section:key,values});if(result.success){await loadSettings()}return result});};
    const section=routePath().split('/')[1];show(sections[section]?section:'system');
  }
  function profileSettings(root){
    textCard(root,'My Profile',session.username?'Preferences for '+session.username:'Preferences for this browser session');
    settingsForm(root,profile,[
      ['homeScreen','Home Screen','select',[['systemsummary','System Tile'],['networksummary','Network'],['alarms','Active Alarm'],['inventory','Control Inventory']]],
      ['viewLevel','User View Level','select',['Basic','Advanced']],
      ['locale','Language','select',[['en-US','English (United States)'],['en-GB','English (United Kingdom)']]],
      ['dateFormat','Date Format','select',['MM/dd/yyyy','dd/MM/yyyy','yyyy-MM-dd']],['timeFormat','Time Format','select',['12-hour','24-hour']]
    ],async values=>{const result=await rpc('SaveProfile',{profile:values});if(result.success){profile=result.profile;document.body.dataset.viewLevel=profile.viewLevel;const clock=$('.ss-main-footer-time .ivu-tooltip-rel div');if(clock)clock.textContent=niceDate(Date.now()/1000)}return result},false);
  }
  async function userSettings(root){
    try{
      const [users,roles]=await Promise.all([rpc('GetUsers'),rpc('GetRoles')]);if(!root.isConnected)return;
      textCard(root,'Current access',session.username?session.username+' · '+(session.role||'Viewer'):'Read only');
      root.append(button(session.username?'Manage session':'Login',loginDialog));
      table(root,['Role','View','Control','Configure','Administer','Suppress alarms'],roles.roles.map(r=>[r.name,...['view','control','configure','administer','muteAlarms'].map(k=>r[k]?'Yes':'No')]));
      const controls=adminControls(root),editor=make('form','em-user-editor');controls.append(editor);
      const fields={};for(const [key,label,type] of [['username','Username','text'],['password','Password','password'],['email','Email','email']]){const row=make('div','em-setting-row'),input=make('input','em-input');input.type=type;input.name=key;input.id='user-'+key;input.setAttribute('aria-label',label);input.maxLength=key==='password'?128:80;const name=make('label',null,label);name.htmlFor=input.id;row.append(name,input);editor.append(row);fields[key]=input;}
      const role=make('select','em-input');role.setAttribute('aria-label','User Role');for(const item of roles.roles){const option=make('option',null,item.name);role.append(option)}const row=make('div','em-setting-row');row.append(make('label',null,'User Role'),role);editor.append(row);
      const message=make('p','em-muted','For an existing user, leave Password blank to retain it.');editor.append(message);
      const save=button('Save user',()=>{});save.type='submit';editor.append(save);
      editor.onsubmit=async e=>{e.preventDefault();if(!isAdmin())return;try{const result=await rpc('SaveUser',{username:fields.username.value,password:fields.password.value,email:fields.email.value,role:role.value});if(result.success){notice('User saved');render()}else message.textContent=result.message}catch(err){message.textContent=err.message}};
      const rows=users.users.map(user=>{const actions=make('div','em-toolbar');const edit=button('Edit',()=>{fields.username.value=user.username;fields.email.value=user.email;fields.password.value='';role.value=user.role;fields.username.focus()},'secondary');const remove=button('Remove',async()=>{try{const result=await rpc('DeleteUser',{username:user.username});if(result.success){notice('User removed');render()}else notice(result.message)}catch(e){notice(e.message)}},'secondary');edit.disabled=remove.disabled=!isAdmin()||user.username==='admin';actions.append(edit,remove);return [user.username,user.role,user.email||'—',actions]});
      table(root,['Username','Role','Email','Actions'],rows);
    }catch(e){notice(e.message)}
  }
  function adminControls(root){
    const wrapper=make('fieldset','em-admin-controls');wrapper.disabled=!isAdmin();
    wrapper.append(make('legend',null,isAdmin()?'Administrator controls':'Administrator login required'));
    root.append(wrapper);return wrapper;
  }
  async function poll(){
    try{
      const previous=isAdmin();
      const identity=await rpc('GetSessionID');session=identity;updateSession();
      if(previous!==isAdmin()){await loadSettings();document.querySelectorAll('.em-overlay').forEach(el=>el.remove());render();}
      const r=await rpc('GetAlarms');alarms=r.alarms||[];updateAlarmCounts();
      const page=$('.em-region');if(page)page.dispatchEvent(new Event('alarm-update'));
    }catch{}
  }
  function updateSession(){
    const loginText=$('.ss-main-header-login-text');if(loginText)loginText.textContent=session.username||'Login';
    const el=$('.ss-main-footer-user-sessions');if(el)el.textContent=session.username?session.username+' · '+(isAdmin()?'Administrator':'Read only'):'0 users logged into system';
    const count=$('.ss-main-footer-user-sessions-count');if(count)count.textContent=session.username?' (1) ':' (0) ';
  }
  function loginDialog(){
    const overlay=make('div','em-overlay'),box=make('form','em-modal');
    box.append(make('h3',null,'User Login'));
    const user=make('input','em-input'),pass=make('input','em-input'),message=make('p','em-muted');
    user.placeholder='Username';user.autocomplete='username';user.setAttribute('aria-label','Username');
    pass.type='password';pass.placeholder='Password';pass.autocomplete='current-password';pass.setAttribute('aria-label','Password');
    const submit=button('Login',()=>{});submit.type='submit';
    box.append(user,pass,message,submit,button('Close',()=>overlay.remove(),'secondary'));
    if(session.username)box.append(button('My Profile',()=>{overlay.remove();go('profile')},'secondary'),button('Logout',async()=>{try{await rpc('Logout');session={};await loadSettings();updateSession();document.querySelectorAll('.em-overlay').forEach(el=>el.remove());render()}catch(e){message.textContent=e.message}},'secondary'));
    box.onsubmit=async e=>{e.preventDefault();try{const r=await rpc('Login',{username:user.value,password:pass.value});if(!r.success){message.textContent=r.message;return}session=r;await loadSettings();updateSession();document.querySelectorAll('.em-overlay').forEach(el=>el.remove());notice('Logged in as '+r.username);render()}catch(err){message.textContent=err.message}};
    overlay.append(box);document.body.append(overlay);user.focus();
  }
  function suppressionControls(root,params={}){
    const controls=adminControls(root);
    const row=make('div','em-setting-row'),duration=make('select','em-input');duration.setAttribute('aria-label','Suppression duration');
    for(const minutes of [1,15,60,240,1440]){const option=make('option',null,minutes<60?minutes+' minutes':minutes/60+' hours');option.value=minutes;duration.append(option)}
    const apply=async method=>{try{const r=await rpc(method,{...params,minutes:Number(duration.value)});if(!r.success){notice(r.message||'Update rejected');return}notice(method==='RestoreAlarms'?'Alarm reporting restored':'Alarms suppressed');const overlay=root.closest('.em-overlay');if(overlay)overlay.remove();await refresh()}catch(e){notice(e.message)}};
    row.append(make('label',null,'Alarm reporting'),duration,button('Suppress',()=>apply('SuppressAlarms'),'secondary'),button('Restore',()=>apply('RestoreAlarms'),'secondary'));controls.append(row);
    const status=make('p','em-muted em-suppression-status');root.append(status);
    const paint=()=>{const list=alarms.filter(a=>params.uid?a.uid===params.uid:params.deviceId?a.iid===String(params.deviceId):true);const active=list.filter(a=>a.suppressed);const until=Math.max(0,...active.map(a=>a.suppressedUntil));status.textContent=active.length?active.length+' alarms suppressed; latest expiry '+niceDate(until):'Alarm reporting enabled';};status.update=paint;paint();root.addEventListener('alarm-update',paint);
  }
  async function feedbackPanel(root,deviceId=''){
    const card=textCard(root,'Operator feedback',''),input=make('textarea','em-input em-textarea');input.placeholder='Enter an observation or maintenance comment';input.setAttribute('aria-label','Operator feedback');input.maxLength=4000;
    const history=make('div');
    const load=async()=>{const r=await rpc('GetFeedback',{deviceId});history.replaceChildren();for(const entry of (r.feedback||[]).slice(-10).reverse()){const line=make('div','em-detail-row');line.append(make('small',null,niceDate(entry.timestamp)+' · '+entry.username),make('span',null,entry.message));history.append(line)}};
    const controls=adminControls(card);
    controls.append(input,button('Submit feedback',async()=>{try{const r=await rpc('SubmitFeedback',{deviceId,message:input.value});if(!r.success){notice(r.message);return}input.value='';notice('Feedback saved');await load()}catch(e){notice(e.message)}},'secondary'));card.append(history);
    try{await load()}catch(e){notice(e.message)}
  }
  function updateAlarmCounts(){
    $$('.em-suppression-status').forEach(status=>status.update?.());
    for(const d of devices){d.activeCount=filteredAlarms(d.id).filter(alarmActive).length;d.alarmCount=filteredAlarms(d.id).length;}
    const total=alarms.filter(alarmActive).length;const counter=$('.ss-main-header-alarm-counter');if(counter)counter.textContent=' ('+total+') ';
    const bell=$('.ss-main-header-alarm .ss-main-header-icon');if(bell)bell.classList.toggle('ss-main-header-alarm-on',total>0);
    for(const group of groups){const category=document.getElementById(group);if(category){const alarm=$('.ss-ss-category-header-icon-alarm',category);if(alarm)alarm.classList.toggle('ss-invisible',!groupDevices(group).some(d=>d.activeCount>0));}}
    const header=$('.ss-main-header-alarm');if(header){header.title=alarms.filter(alarmActive).length+' active alarms';header.classList.toggle('em-alarm-active',alarms.some(alarmActive));}
  }
  function content(){return $('.ss-page-content')||$('#app')}
  function notice(text){const old=$('.em-toast');if(old)old.remove();const n=make('div','em-toast',text);document.body.append(n);setTimeout(()=>n.remove(),3600)}
  function dialog(title,items){const overlay=make('div','em-overlay');const box=make('div','em-modal');const header=make('div','em-modal-head');header.append(make('h3',null,title),button('×',()=>overlay.remove(),'subtle'));box.append(header);
    if(Array.isArray(items)){items.forEach(([k,v])=>{const line=make('div','em-detail-row');line.append(make('strong',null,k),make('span',null,v));box.append(line)})}else box.append(make('p',null,items));
    box.append(button('Close',()=>overlay.remove(),'secondary'));overlay.append(box);overlay.onclick=e=>{if(e.target===overlay)overlay.remove()};document.body.append(overlay);
  }
  function setTitle(t){const el=$('.ss-page-header-title');if(el)el.textContent=t;document.title=t+' | Site Supervisor'}
  function actions(items){const parent=$('.ss-page-header-actions.ss-mobile-hide');if(!parent)return;parent.replaceChildren();for(const [txt,fn,style] of items)parent.append(button(txt,fn,style||'primary'))}
  function clearPage(){const prior=$('.em-region');if(prior)prior.remove();const home=$('.ss-ss-content');if(home)home.classList.add('em-hidden')}
  function region(){clearPage();actions([['Back',()=>history.length>1?history.back():go('systemsummary')],['Refresh',refresh],['Device index',()=>go('inventory')]]);const root=make('section','em-region');content().append(root);return root}
  function heading(root,title,sub){const row=make('div','em-heading');row.append(make('h2',null,title));if(sub)row.append(make('p','em-muted',sub));root.append(row);return row}
  function infoGrid(root,data){const wrap=make('div','em-stats');for(const [name,value,route] of data){const card=make('div','em-stat');card.append(make('span','em-stat-label',name),make('strong','em-stat-value',value));if(route){card.classList.add('em-click');card.tabIndex=0;card.addEventListener('click',()=>go(route));card.onkeydown=e=>{if(e.key==='Enter')go(route)}}wrap.append(card)}root.append(wrap);return wrap}
  function textCard(root,title,body){const card=make('article','em-section-card');card.append(make('h3',null,title));if(typeof body==='string')card.append(make('p',null,body));else if(body)card.append(body);root.append(card);return card}
  function table(root,headers,rows,callback){const box=make('div','em-tablewrap');const t=make('table','em-table');const h=make('thead'),tr=make('tr');for(const name of headers)tr.append(make('th',null,name));h.append(tr);t.append(h);const tb=make('tbody');for(const [i,values] of rows.entries()){const row=make('tr',callback?'em-click':'');for(const value of values){const td=make('td');if(value instanceof Node)td.append(value);else td.textContent=safeText(value);row.append(td)}if(callback){row.tabIndex=0;row.onclick=()=>callback(i);row.onkeydown=e=>{if(e.key==='Enter')callback(i)}}tb.append(row)}t.append(tb);box.append(t);root.append(box);return box}
  function groupDevices(group){return devices.filter(d=>d.category===group)}
  function currentDevice(){const path=routePath();return /^device\/(\d+)$/.test(path)?devicesById.get(path.split('/')[1]):null}
  function deviceAnchor(dev){const a=make('a','em-device-link',dev.name);a.href=link('device/'+dev.id);a.onclick=e=>{e.stopPropagation()};return a}
  function deviceCard(d){const card=make('a','em-device-card');card.href=link('device/'+d.id);card.append(make('strong','em-device-name',d.name));card.append(make('span','em-device-sub',d.type));const foot=make('div','em-device-foot');foot.append(make('span',null,'ID '+d.id));const alarm=make('span','em-chip '+(d.activeCount?'warning':''),d.activeCount?d.activeCount+' active':'No active alarm');foot.append(alarm);card.append(foot);return card}
  function groupToggle(group,force){const header=document.getElementById(group);if(!header)return;const parent=header.closest('.ss-ss-category');if(!parent)return;const panel=$('.em-devices-panel',parent);if(panel){if(force===true)return;panel.remove();opened.delete(group);header.classList.remove('em-expanded');header.setAttribute('aria-expanded','false');return}
    if(force===false)return;
    opened.add(group);header.classList.add('em-expanded');header.setAttribute('aria-expanded','true');const wrap=make('div','em-devices-panel');const matches=groupDevices(group);const top=make('div','em-group-top');top.append(make('span',null,`${matches.length} applications`));const search=make('input','em-input');search.placeholder='Filter '+group.toLowerCase()+' devices';search.setAttribute('aria-label','Filter '+group+' devices');top.append(search);wrap.append(top);
    const grid=make('div','em-device-grid');wrap.append(grid);const paint=()=>{grid.replaceChildren();const q=search.value.toLowerCase();const filtered=matches.filter(x=>[x.name,x.type,x.id].join(' ').toLowerCase().includes(q));filtered.forEach(d=>grid.append(deviceCard(d)));if(!filtered.length)grid.append(make('p','em-muted',matches.length?'No matching devices.':'No applications in this category.'))};search.oninput=paint;paint();parent.append(wrap);
  }
  function home(){current='systemsummary';clearPage();const home=$('.ss-ss-content');if(home)home.classList.remove('em-hidden');setTitle('System Tile');actions([['Collapse all',()=>groups.forEach(g=>groupToggle(g,false))],['Expand all',()=>groups.forEach(g=>groupToggle(g,true))],['Refresh',refresh],['Device index',()=>go('inventory')]]);
    $$('.ss-ss-category-header').forEach(header=>{const g=header.id;header.tabIndex=0;header.setAttribute('role','button');header.setAttribute('aria-expanded',String(opened.has(g)));const note=$('.category-header-app-count',header);const count=dash.originalCategoryCounts?.[g];const observed=groupDevices(g).length;if(note)note.textContent=count!==undefined?`(${count})`:`(${observed})`;});
    for(const g of opened){if(!$('.em-devices-panel',document.getElementById(g)?.closest('.ss-ss-category')))groupToggle(g,true)}
  }
  function filteredAlarms(devId){return devId?alarms.filter(a=>a.iid===String(devId)):alarms}
  function alarmView(devId){const list=filteredAlarms(devId);const page=region();const subtitle=devId?(devicesById.get(String(devId))?.name||devId):unitName();setTitle(devId?'Device Alarms':'Active Alarm');heading(page,devId?'Alarm History — '+subtitle:'Active Alarm',`${list.length} alarm events from ${unitName()}`);
    const toolbar=make('div','em-toolbar'),q=make('input','em-input'),select=make('select','em-input');q.placeholder='Search message or source';for(const [v,label] of [['active','Active'],['all','All history'],['suppressed','Suppressed'],['critical','Critical'],['unack','Unacknowledged']]){const opt=make('option',null,label);opt.value=v;select.append(opt)}toolbar.append(q,select,button('Refresh',refresh,'secondary'));const match=make('span','em-muted');toolbar.append(match);page.append(toolbar);
    suppressionControls(page,devId?{deviceId:devId}:{});
    const place=make('div');page.append(place);
    function paint(){place.replaceChildren();const query=q.value.toLowerCase();const filtered=filteredAlarms(devId).filter(a=>{
      const accepted=select.value==='all'||select.value==='active'&&alarmActive(a)||select.value==='suppressed'&&a.suppressed||select.value==='critical'&&a.category==='Critical'||select.value==='unack'&&a.ack==='UNACK'&&!ack[a.uid];return accepted&&[a.messagekey,a.originator,a.category,a.uid].some(t=>String(t||'').toLowerCase().includes(query))});match.textContent=filtered.length+' events';
      const show=filtered.slice(0,300);table(place,['Time','Device','Message','Severity','State','ACK'],show.map(a=>[niceDate(a.timestamp),a.originator,a.messagekey,a.category,a.suppressed?'Suppressed until '+niceDate(a.suppressedUntil):a.resolution,ack[a.uid]?'ACK':a.ack]),i=>alarmDetail(show[i]));if(filtered.length>300)place.append(make('p','em-muted','Showing first 300. Narrow with filters to view more.'));
    }q.oninput=paint;select.onchange=paint;page.addEventListener('alarm-update',paint);paint();
  }
  function alarmDetail(a){const ov=make('div','em-overlay'),box=make('div','em-modal');const head=make('div','em-modal-head');head.append(make('h3',null,'Alarm '+a.uid),button('×',()=>ov.remove(),'subtle'));box.append(head);for(const [key,val] of Object.entries({'Device':a.originator,'Message':a.messagekey,'Category':a.category,'Resolution':a.resolution,'Timestamp':niceDate(a.timestamp),'Reported value':a.reportvalue||'—','Limit':a.limitvalue||'—','Type':a.apptype,'Device ID':a.iid}))box.append((()=>{const row=make('div','em-detail-row');row.append(make('strong',null,key),make('span',null,val));return row})());
    const actions=make('div','em-toolbar');const ackB=button((ack[a.uid]||a.ack==='ACK')?'Acknowledged':'Acknowledge',async()=>{try{await rpc('AcknowledgeAlarm',{uid:a.uid});ack[a.uid]=true;a.ack='ACK';ackB.textContent='Acknowledged';notice('Alarm acknowledged')}catch(e){notice(e.message)}});const ackControls=adminControls(box);ackControls.append(ackB);actions.append(button('Open device',()=>{ov.remove();go('device/'+a.iid)},'secondary'));box.append(actions);suppressionControls(box,{uid:a.uid});if(a.suppressed)box.append(make('p','em-muted','Suppressed until '+niceDate(a.suppressedUntil)));ov.append(box);ov.onclick=e=>{if(e.target===ov)ov.remove()};document.body.append(ov);
  }
  async function deviceView(id){const d=devicesById.get(String(id));if(!d){const root=region();setTitle('Device');heading(root,'Device '+id);root.append(alertBanner('Application not found.'));root.append(button('Device index',()=>go('inventory')));return}
    current='device/'+id;setTitle(d.name);const root=region();
    let live=null;try{const x=await rpc('GetDeviceState',{deviceId:id});live=x.state||null;}catch(e){console.warn('Status unavailable',e)}
    if(routePath().split('/')[1]!==String(id))return;
    const crumb=make('div','em-crumb');const back=make('a',null,'System Tile');back.href=link('systemsummary');crumb.append(back,make('span',null,' › '),make('span',null,d.category),make('span',null,' › '),make('strong',null,d.name));root.append(crumb);const headingRow=make('div','em-device-heading');const title=make('div');title.append(make('h2',null,d.name),make('p','em-muted',`${d.type} · Device ID ${d.id} · ${siteName()}`));headingRow.append(title);headingRow.append(button('Back to devices',()=>go('inventory'),'secondary'),button('Refresh',refresh));root.append(headingRow);
    const active=filteredAlarms(id).filter(alarmActive);infoGrid(root,[['Application',d.type],['Unit',d.unit],['Active alarms',String(active.length),'alarms'],['Alarm history',String(d.alarmCount)],['Current value',live?(live.value+' '+live.unit):'N/A'],['Setpoint',live?(live.setpoint+' '+live.unit):'N/A']]);
    const nav=make('div','em-tabs');const pane=make('div','em-tabbody');root.append(nav,pane);const tabs=['Overview','Points','Controls','Alarms','History','Configuration'];let selected='Overview';
    function show(tab){selected=tab;deviceTabs.set(String(id),tab);nav.replaceChildren();for(const t of tabs){const x=button(t,()=>show(t),'tab'+(t===tab?' selected':''));nav.append(x)}pane.replaceChildren();if(tab==='Overview'){
      const details=make('div','em-two-col');const inf=make('article','em-section-card');inf.append(make('h3',null,'Application information'));for(const [k,v] of Object.entries({'Name':d.name,'Application type':d.type,'ID':d.id,'Unit':d.unit,'Site':siteName(),'Status':'Online'})){const line=make('div','em-detail-row');line.append(make('strong',null,k),make('span',null,v));inf.append(line)}details.append(inf);
      const liveCard=make('article','em-section-card');liveCard.append(make('h3',null,'Current operating conditions'));
      if(live){for(const [k,v] of [['Measured value',live.value+' '+live.unit],['Control setpoint',live.setpoint+' '+live.unit],['Output mode',live.output],['Operating status',live.enabled?'Enabled':'Disabled']]){const ln=make('div','em-detail-row');ln.append(make('strong',null,k),make('span',null,v));liveCard.append(ln)}}
      details.append(liveCard);pane.append(details);
      const rec=make('article','em-section-card');rec.append(make('h3',null,'Most recent events'));for(const a of filteredAlarms(id).slice(0,8)){const l=make('a','em-event');l.href=link('device/'+d.id+'/alarms');l.append(make('span',null,a.messagekey),make('small',null,niceDate(a.timestamp)));l.onclick=e=>{e.preventDefault();show('Alarms')};rec.append(l)}details.append(rec);pane.append(details);
    }else if(tab==='Points'){
      if(live){table(pane,['Point','Value','Unit','Status'],[['Measured value',String(live.value),live.unit,live.value>live.highLimit?'High temperature':'Normal'],['Control setpoint',String(live.setpoint),live.unit,'Active'],['Control output',live.output,'','Active']]);}
      pane.append(make('h3',null,'Additional application points'));
      table(pane,['Point','Database key','Reported value','Limit','Last event'],d.points.map(p=>[p.name,p.key,p.value||'—',p.limit||'—',niceDate(p.lastSeen)]));
    }else if(tab==='Controls'){
      const card=make('article','em-section-card');card.append(make('h3',null,'Application control'));pane.append(card);const panel=adminControls(card);
      if(!live){panel.append(make('p',null,'Current status unavailable.'));return}
      const setRow=make('div','em-setting-row');
      const inp=make('input','em-input');inp.type='number';inp.step=live.unit==='Pa'?'100':'0.5';inp.min=String(live.min);inp.max=String(live.max);inp.value=String(live.setpoint);
      const val=make('label',null,'Control setpoint ('+live.unit+')');setRow.append(val,inp,
        button('Apply',async()=>{try{const result=await rpc('SetPointValues',{deviceId:id,setpoint:Number(inp.value)});if(result.success){live.setpoint=result.applied;notice('Setpoint updated');show('Controls')}else notice('Value outside permitted range')}catch(e){notice(e.message)}}));panel.append(setRow);
      const enabledRow=make('div','em-setting-row'),enabled=make('select','em-input');enabled.setAttribute('aria-label','Application status');for(const [value,label] of [['true','Enabled'],['false','Disabled']]){const option=make('option',null,label);option.value=value;option.selected=String(live.enabled)===value;enabled.append(option)}enabledRow.append(make('label',null,'Application status'),enabled,button('Apply',async()=>{try{const r=await rpc('SetDeviceEnabled',{deviceId:id,enabled:enabled.value==='true'});if(r.success){live=r.state;notice('Application status updated')}else notice(r.message)}catch(e){notice(e.message)}}));panel.append(enabledRow);
      const outputRow=make('div','em-setting-row');const mode=make('select','em-input');for(const k of ['AUTO','ON','OFF']){const option=make('option',null,k);option.value=k;if(live.output===k)option.selected=true;mode.append(option)}outputRow.append(make('label',null,'Control output mode'),mode,
        button('Apply',async()=>{try{const r=await rpc('SetDeviceOutput',{deviceId:id,output:mode.value});if(r.success){live.output=r.output;notice('Output mode updated')}else notice('Update rejected')}catch(e){notice(e.message)}}));panel.append(outputRow);
      if(d.type==='StdCircuit'){
        const def=make('div','em-setting-row');def.append(make('label',null,'Defrost cycle'),button('Start defrost',async()=>{const ans=await rpc('StartDefrost',{deviceId:id});if(ans.success){live.defrostUntil=Math.floor(Date.now()/1000)+900;notice('Defrost started')}else notice('Unable to start defrost')},'secondary'));panel.append(def);
      }
      if(live.unit==='°F'){
        for(const [label,field,method] of [['Temperature value','value','SetTemperature'],['High temperature limit','highLimit','SetHighTemperatureLimit']]){
          const row=make('div','em-setting-row'),input=make('input','em-input');input.type='number';input.step='0.1';input.min='-100';input.max='250';input.value=live[field];input.setAttribute('aria-label',label+' (°F)');
          row.append(make('label',null,label+' (°F)'),input,button('Apply',async()=>{if(input.value===''||!input.checkValidity()){notice('Enter a temperature between -100 and 250 °F');return}try{const r=await rpc(method,{deviceId:id,value:Number(input.value)});if(!r.success){notice(r.message);return}live=r.state;const a=await rpc('GetAlarms');alarms=a.alarms;updateAlarmCounts();notice('Temperature settings updated');show('Controls')}catch(e){notice(e.message)}}));panel.append(row);
        }
        panel.append(make('p','em-muted',live.override?'Temperature input override is active.':'Temperature input is automatic.'));
        if(live.override)panel.append(button('Resume automatic input',async()=>{try{const r=await rpc('ResumeTemperatureAuto',{deviceId:id});if(r.success){live=r.state;notice('Automatic input restored');show('Controls')}}catch(e){notice(e.message)}},'secondary'));
      }
      suppressionControls(panel,{deviceId:id});
      const status=make('p','em-muted','Last reading: '+live.value+' '+live.unit);panel.append(status);
    }else if(tab==='Alarms'||tab==='History'){
      const data=filteredAlarms(id).filter(a=>tab==='History'||alarmActive(a)).slice(0,150);table(pane,['Time','Message','Priority','State','ACK'],data.map(a=>[niceDate(a.timestamp),a.messagekey,a.category,a.suppressed?'Suppressed until '+niceDate(a.suppressedUntil):a.resolution,ack[a.uid]?'ACK':a.ack]),i=>alarmDetail(data[i]));if(!data.length)pane.append(make('p','em-muted','No events matched this view.'));
    }else {
      const form=make('div','em-two-col');const conf=make('article','em-section-card');conf.append(make('h3',null,'Application properties'));for(const [key,value] of Object.entries({'Application':d.type,'Unit Number':d.unitNumber,'Attributes':d.attributes.join(', ')||'—','Alarm points':d.points.length,'Alarm events':d.alarmCount})){const line=make('div','em-detail-row');line.append(make('strong',null,key),make('span',null,String(value)));conf.append(line)}form.append(conf);
      const memo=make('article','em-section-card');memo.append(make('h3',null,'Operator notes'));const input=make('textarea','em-input em-textarea');input.placeholder='Application notes';input.value=notes[id]||'';memo.append(input,button('Save notes',()=>{notes[id]=input.value;persist(notesKey,notes);notice('Notes saved')},'secondary'));form.append(memo);pane.append(form);feedbackPanel(pane,id);
    }}show(location.hash.endsWith('/alarms')?'Alarms':deviceTabs.get(String(id))||'Overview');root.addEventListener('alarm-update',()=>{if(selected==='Alarms'||selected==='History')show(selected);});
  }
  function inventory(){setTitle('Control Inventory');const root=region();heading(root,'Control Inventory',`${devices.length} applications`);const bar=make('div','em-toolbar'),q=make('input','em-input');q.placeholder='Find device name, type or ID';const category=make('select','em-input');for(const x of ['All',...groups]){const o=make('option',null,x);o.value=x;category.append(o)}bar.append(q,category,button('System Tile',()=>go('systemsummary'),'secondary'));root.append(bar);const container=make('div');root.append(container);function paint(){container.replaceChildren();const rows=devices.filter(d=>(category.value==='All'||d.category===category.value)&&[d.name,d.type,d.id].join(' ').toLowerCase().includes(q.value.toLowerCase()));table(container,['Application','Type','Group','ID','Active Alarms'],rows.map(d=>[deviceAnchor(d),d.type,d.category,d.id,String(d.activeCount)]),i=>go('device/'+rows[i].id));}q.oninput=paint;category.onchange=paint;paint();}
  function network(){setTitle('Network');const root=region();heading(root,'Network Summary',unitName()+' · Online');infoGrid(root,[['System',unitName()],['Site',siteName()],['Version','2.30F01'],['Identified devices',devices.length,'inventory'],['Alarm history',alarms.length,'alarms']]);textCard(root,'Applications by category',(()=>{const wrap=make('div','em-cat-list');for(const g of groups){const r=make('a','em-cat-row');r.href=link('inventory');r.append(make('strong',null,g),make('span',null,groupDevices(g).length+' applications'));wrap.append(r)}return wrap})());}
  function schedule(){setTitle('Case Defrost Schedule');const root=region();heading(root,'Case Defrost Schedule','E3 Unit01');const fridge=groupDevices('Refrigeration').filter(d=>d.type==='StdCircuit');textCard(root,'Refrigeration circuits',`${fridge.length} configured circuits. Select an application to view its status and controls.`);table(root,['Circuit','Application ID','Last reported event'],fridge.map(d=>[deviceAnchor(d),d.id,niceDate(d.lastSeen)]),i=>go('device/'+fridge[i].id));}
  function info(){setTitle('Info');const root=region();heading(root,'System Information',unitName());infoGrid(root,[['Controller','E3'],['Unit',unitName()],['Site',siteName()],['Firmware','2.30F01'],['Configured applications',devices.length],['Alarm history',alarms.length]]);textCard(root,'About this environment','Copeland E3 supervisory controller. Monitor configured applications, alarms and refrigeration status.');}
  function generic(path){const root=region();const title=pageNames[path.split('/')[0]]||path.replace(/[-_]/g,' ');setTitle(title);heading(root,title,unitName());
    if(path==='floorplan'){textCard(root,'Floorplan','No floorplan has been assigned to this unit.');}
    else if(path==='physicalio'){const io=devices.filter(d=>/Input|Output|Sensor/.test(d.type));textCard(root,'Physical I/O','Physical input and output applications registered on this unit.');table(root,['Point / Device','Type','ID'],io.map(d=>[deviceAnchor(d),d.type,d.id]),i=>go('device/'+io[i].id));return;}
    else if(path==='controlactivity'){if(!isAdmin()){textCard(root,'Control Activity','Administrator login required.');root.append(button('Login',loginDialog));return;}rpc('GetControlEvents').then(r=>{if(!root.isConnected)return;table(root,['Time','User','Device','Action','Value'],(r.events||[]).slice(0,200).map(e=>[niceDate(e.timestamp),e.username||'—',e.deviceId||'System',e.action,typeof e.value==='object'?JSON.stringify(e.value):String(e.value)]));}).catch(e=>notice(e.message));return;}
    else if(path==='logs'){table(root,['Timestamp','Origin','Event','Severity'],alarms.slice(0,200).map(a=>[niceDate(a.timestamp),a.originator,a.messagekey,a.category]),i=>alarmDetail(alarms[i]));return;}
    else if(path==='generalsystem'||path.startsWith('generalsystem/')){generalSettings(root);return;}
    else if(path==='profile'){profileSettings(root);return;}
    else if(path==='users'){userSettings(root);return;}
    else if(path==='alarmhandling'){heading(root,'Alarm reporting');suppressionControls(root);return;}
    else if(path==='help'){feedbackPanel(root);textCard(root,'Navigation','Use System Tile to expand equipment categories, Control Inventory to find a device, and Active Alarm to view controller events.');return;}
    else if(path==='filemanagement'){textCard(root,'System files',`System contains ${devices.length} configured applications and ${alarms.length} alarm records. File operations are not available in this session.`);return;}
    else if(path==='layoutmanager'||['bx','cx','rx'].includes(path)){textCard(root,'Available devices','Select an application from the inventory to inspect its status.');return;}
    else{textCard(root,'Configuration unavailable','No changes are pending for this unit.');}
    root.append(button('Browse devices',()=>go('inventory'),'secondary'));
  }
  async function refresh(){try{const r=await rpc('GetAlarms');if(Array.isArray(r.alarms))alarms=r.alarms;updateAlarmCounts();notice('Updated');render()}catch(e){notice('API unavailable: '+e.message)}}
  function render(){let path=routePath();current=path;$$('.ss-main-menu .ivu-menu-item').forEach(n=>n.classList.toggle('ivu-menu-item-selected',((n.textContent||'').trim().toLowerCase())===(pageNames[path]||'').toLowerCase()));
    if(path==='systemsummary'||path==='/'){home();return}
    if(path.startsWith('device/')){deviceView(path.split('/')[1]);return}
    if(path==='alarms'){alarmView();return}
    if(path==='inventory'){inventory();return}
    if(path==='networksummary'){network();return}
    if(path==='casedefrostsummary'){schedule();return}
    if(path==='info'){info();return}
    generic(path);
  }
  function replaceSideMenu(){const menu=$('.ss-main-menu-container');if(!menu)return;menu.replaceChildren();for(const [group,links] of routes){const li=make('li','ivu-menu-submenu ss-main-menu-submenu em-menu-group');const title=make('div','ivu-menu-submenu-title em-menu-title',group+' ▾');li.append(title);const list=make('ul','ivu-menu em-menu-items');for(const [name,path] of links){const item=make('li','ivu-menu-item ss-main-menu-item');const a=make('a',null,name);a.href=link(path);a.onclick=()=>setMenu(false);item.append(a);list.append(item)}li.append(list);title.onclick=()=>list.classList.toggle('em-hidden');menu.append(li)}}
  function wire(){replaceSideMenu();const backdrop=make('div','em-menu-backdrop');backdrop.hidden=true;backdrop.onclick=()=>setMenu(false);document.body.append(backdrop);const gear=$('.ss-main-header-main-menu');if(gear){gear.setAttribute('role','button');gear.setAttribute('aria-label','Main Menu');gear.setAttribute('aria-controls','controller-main-menu')}const menu=$('.ss-main-body-menu');if(menu){menu.id='controller-main-menu';menu.setAttribute('aria-label','Main Menu')}setMenu(false);document.addEventListener('keydown',e=>{if(e.key==='Escape'){setMenu(false);gear?.focus()}});$$('.ss-ss-category-header').forEach(header=>{header.onclick=()=>groupToggle(header.id);header.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();groupToggle(header.id)}}});
    const clicks=[['.ss-main-header-back',()=>history.length>1?history.back():go('systemsummary')],['.ss-main-header-main-menu',()=>setMenu(!document.body.classList.contains('sim-menu-open'))],['.ss-main-header-home',()=>go(profile.homeScreen)],['.ss-main-header-refresh',refresh],['.ss-main-header-inventory',()=>go('inventory')],['.ss-main-header-schedule',()=>go('casedefrostsummary')],['.ss-main-header-floorplan',()=>go('floorplan')],['.ss-main-header-physical-io',()=>go('physicalio')],['.ss-main-header-add-app',()=>go('inventory')],['.ss-main-header-help',()=>go('help')],['.ss-main-header-alarm',()=>go('alarms')],['.ss-main-header-login',loginDialog]];
    for(const [selector,handler] of clicks){const el=$(selector);if(el){el.classList.remove('ss-main-header-item-disabled');el.style.cursor='pointer';el.onclick=handler;el.tabIndex=0;el.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();handler()}}}}
    window.addEventListener('hashchange',render);
  }
  async function init(){if(initDone)return;initDone=true;try{
      const login=await rpc('GetSessionID');
      const [d,a]=await Promise.all([fetch('/catalog.php').then(r=>r.json()),rpc('GetAlarms')]);
      devices=Array.isArray(d.devices)?d.devices:[];dash=d.dashboard||{};devicesById=new Map(devices.map(x=>[x.id,x]));alarms=a.alarms||[];session=login;updateSession();updateAlarmCounts();if(!login.sid)console.warn('Session not returned');
    }catch(e){console.error('Data loading error',e);notice('Controller not responding: '+e.message)}
    try{await loadSettings()}catch(e){notice(e.message)}
    wire();render();
    setInterval(poll,10000);
    let name=$('.ss-main-footer-build');if(name)name.title='Site Supervisor build information';
    const clock=$('.ss-main-footer-time .ivu-tooltip-rel div');
    if(clock){const tick=()=>{clock.textContent=niceDate(Date.now()/1000)};tick();setInterval(tick,30000)}
    $$('.ss-themes-theme').forEach((swatch,i)=>swatch.addEventListener('click',()=>{
      $$('.ss-themes-theme').forEach(x=>x.classList.remove('ss-themes-theme-selected'));
      swatch.classList.add('ss-themes-theme-selected');
      document.body.classList.remove('em-light-theme','em-dark-theme');
      if(i===1)document.body.classList.add('em-light-theme');
      if(i===2)document.body.classList.add('em-dark-theme');
    }));
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
