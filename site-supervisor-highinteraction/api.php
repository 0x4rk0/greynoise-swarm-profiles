<?php
/** Site Supervisor E3 JSON-RPC service. */
declare(strict_types=1);
ini_set('display_errors','0');
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');
header('X-Content-Type-Options: nosniff');
header('Access-Control-Allow-Origin: same-origin');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');
if (($_SERVER['REQUEST_METHOD'] ?? '') === 'OPTIONS') { http_response_code(204); exit; }

session_set_cookie_params(['httponly'=>true,'samesite'=>'Lax']);
session_start();
if (!isset($_SESSION['sid'])) $_SESSION['sid'] = makeUuid();

function makeUuid(): string {
  $b=random_bytes(16);$b[6]=chr((ord($b[6])&15)|64);$b[8]=chr((ord($b[8])&63)|128);
  $h=bin2hex($b);return substr($h,0,8).'-'.substr($h,8,4).'-'.substr($h,12,4).'-'.substr($h,16,4).'-'.substr($h,20);
}
function asset(string $name): array {
  $path=__DIR__.'/data/'.$name;
  if (!is_file($path)) return [];
  $v=json_decode((string)file_get_contents($path),true);
  return is_array($v)?$v:[];
}
function getDeviceId($params): string {
  if (!is_array($params)) return '';
  foreach (['deviceId','deviceid','appId','appid','iid','applicationId','id','device','app'] as $key) {
    if (isset($params[$key]) && (is_scalar($params[$key]))) {
      $x=(string)$params[$key];if (preg_match('/^\d{6,12}$/',$x))return $x;
    }
  }
  foreach ($params as $v) if(is_array($v)) { $id=getDeviceId($v);if($id!=='')return $id; }
  return '';
}
function getValue($params, array $keys, $default=null) {
  if (!is_array($params)) return $default;
  foreach($keys as $k) if(array_key_exists($k,$params) && is_scalar($params[$k])) return $params[$k];
  foreach($params as $v)if(is_array($v)){ $r=getValue($v,$keys,null);if($r!==null)return $r; }
  return $default;
}
function initialSetpoint(array $d): array {
  $type=strtolower((string)($d['type']??''));$name=strtolower((string)($d['name']??''));
  if(str_contains($type,'suction'))return ['unit'=>'Pa','target'=>413685.0,'value'=>442100.0,'min'=>100000,'max'=>800000,'rate'=>420.0];
  if(str_contains($type,'digital')||str_contains($type,'relay')||str_contains($type,'system')||str_contains($type,'network'))return ['unit'=>'ON/OFF','target'=>1,'value'=>1,'min'=>0,'max'=>1,'rate'=>0];
  if(str_contains($name,'frz')||str_contains($name,'freez'))return ['unit'=>'°F','target'=>-5.0,'value'=>-2.8,'min'=>-25,'max'=>30,'rate'=>0.12];
  if(str_contains($type,'analog')||str_contains($type,'sensor'))return ['unit'=>'°F','target'=>38.0,'value'=>39.1,'min'=>-25,'max'=>100,'rate'=>0.06];
  return ['unit'=>'°F','target'=>36.0,'value'=>39.2,'min'=>-25,'max'=>100,'rate'=>0.09];
}
function initializeState(array $devices): array {
  $states=[];$now=time();
  foreach ($devices as $d) {
    $p=initialSetpoint($d);$id=(string)$d['id'];
    $states[$id]=['id'=>$id,'setpoint'=>$p['target'],'value'=>$p['value'],'unit'=>$p['unit'],'min'=>$p['min'],'max'=>$p['max'],'rate'=>$p['rate'],
      'output'=>'AUTO','enabled'=>true,'defrostUntil'=>0,'lastTick'=>$now,'updated'=>$now,
      'history'=>[['timestamp'=>$now,'value'=>$p['value'],'setpoint'=>$p['target']]]];
  }
  return ['created'=>$now,'devices'=>$states,'acks'=>[],'events'=>[],'sequence'=>0];
}
function advanceState(array &$state): void {
  $now=time();
  foreach($state['devices'] as &$d){
    $dt=min(7200,max(0,$now-(int)$d['lastTick']));if(!$dt)continue;
    $d['lastTick']=$now;
    if($d['unit']==='ON/OFF' || !empty($d['override']))continue;
    $target=(float)$d['setpoint'];$current=(float)$d['value'];
    $minutes=$dt/60.0;$dir=$current>$target?-1:1;
    $desired=$target+($d['unit']==='Pa'?2400.0:($d['enabled']?0.7:7.5));
    if((int)$d['defrostUntil']>$now)$desired=$d['unit']==='Pa'?$target+8000:$target+12.0;
    if(!$d['enabled'])$desired=$d['unit']==='Pa'?$target+12000:$target+9;
    if($d['output']==='OFF')$desired=$d['unit']==='Pa'?$target+16000:$target+8;
    if($d['output']==='ON')$desired=$target-($d['unit']==='Pa'?2500:1.5);
    $diff=$desired-$current;$speed=(float)$d['rate']*$minutes;
    $current += max(-$speed,min($speed,$diff));
    $d['value']=round($current,$d['unit']==='Pa'?1:2);
    if(($now-(int)$d['updated'])>=30){
      $d['history'][]=['timestamp'=>$now,'value'=>$d['value'],'setpoint'=>$d['setpoint']];
      if(count($d['history'])>200)$d['history']=array_slice($d['history'],-200);
      $d['updated']=$now;
    }
  }
  unset($d);
}
function recordChange(array &$state,string $device,string $action,$value): void {
  $state['sequence']=(int)($state['sequence']??0)+1;
  $state['events'][]=['seq'=>$state['sequence'],'timestamp'=>time(),'deviceId'=>$device,'action'=>$action,'value'=>$value,'username'=>$_SESSION['user']??''];
  if(count($state['events'])>1000)$state['events']=array_slice($state['events'],-1000);
}
function evaluateTemperatureAlarms(array &$state, array $devices): void {
  foreach($devices as $device){
    $id=(string)$device['id'];$d=&$state['devices'][$id];
    if($d['unit']!=='°F')continue;
    $d['highLimit']=$d['highLimit']??($d['max']<=30?10.0:45.0);
    $uid=$d['temperatureAlarm']??null;
    $active=$uid && ($state['temperatureAlarms'][$uid]['resolution']??'')==='ACTIVE';
    if(!$active && $d['value']>$d['highLimit']){
      $uid=makeUuid();$d['temperatureAlarm']=$uid;
      $state['temperatureAlarms'][$uid]=['uid'=>$uid,'iid'=>$id,'apptype'=>$device['type'],'ack'=>'UNACK','category'=>'Critical',
        'resolution'=>'ACTIVE','timestamp'=>(string)time(),'priority'=>'1','unitnum'=>'1','sitename'=>'E3 Unit01',
        'messagekey'=>'High temperature','originator'=>$device['name'],'reportvalue'=>$d['value'],'limitvalue'=>$d['highLimit']];
    }elseif($active){
      $state['temperatureAlarms'][$uid]['reportvalue']=$d['value'];
      $state['temperatureAlarms'][$uid]['limitvalue']=$d['highLimit'];
      if($d['value']<=$d['highLimit']-2){
        $state['temperatureAlarms'][$uid]['resolution']='RETURNED';
        $state['temperatureAlarms'][$uid]['clearedAt']=time();
      }
    }
    unset($d);
  }
}
function controllerSettings(array $state): array {
  $defaults=[
    'system'=>['siteName'=>'maplewood','unitName'=>'E3 Unit01','unitNumber'=>1,'groupName'=>'maplewood','webPort'=>80],
    'network'=>['dhcp'=>false,'ipAddress'=>'192.168.1.250','subnetMask'=>'255.255.255.0','gateway'=>'192.168.1.1','dns'=>'192.168.1.1','monitoringPort'=>3001,'legacyClientPort'=>1025],
    'com'=>['com1Protocol'=>'Modbus','com1Baud'=>9600,'com2Protocol'=>'Disabled','com2Baud'=>19200],
    'localization'=>['locale'=>'en-US','timeZone'=>'America/Los_Angeles','dateFormat'=>'MM/dd/yyyy','timeFormat'=>'12-hour']
  ];
  foreach($defaults as $section=>&$values)$values=array_replace($values,$state['settings'][$section]??[]);
  unset($values);return $defaults;
}
function defaultProfile(): array {
  return ['homeScreen'=>'systemsummary','viewLevel'=>'Basic','locale'=>'en-US','dateFormat'=>'MM/dd/yyyy','timeFormat'=>'12-hour'];
}
function activeProfile(array $state): array {
  $defaults=array_replace(defaultProfile(),array_intersect_key(controllerSettings($state)['localization'],defaultProfile()));
  return array_replace($defaults,isset($_SESSION['user'])?($state['profiles'][$_SESSION['user']]??[]):($_SESSION['profile']??[]));
}
function validateSetting(string $key,$value): bool {
  $choices=['com1Protocol'=>['Disabled','Modbus','BACnet'],'com2Protocol'=>['Disabled','Modbus','BACnet'],
    'com1Baud'=>[9600,19200,38400,57600,115200],'com2Baud'=>[9600,19200,38400,57600,115200],
    'locale'=>['en-US','en-GB'],'dateFormat'=>['MM/dd/yyyy','dd/MM/yyyy','yyyy-MM-dd'],'timeFormat'=>['12-hour','24-hour'],
    'homeScreen'=>['systemsummary','networksummary','alarms','inventory'],'viewLevel'=>['Basic','Advanced']];
  if(isset($choices[$key]))return in_array($value,$choices[$key],true);
  if(in_array($key,['siteName','unitName','groupName'],true))return is_string($value)&&strlen(trim($value))>0&&strlen($value)<=80;
  if(in_array($key,['ipAddress','subnetMask','gateway','dns'],true))return is_string($value)&&filter_var($value,FILTER_VALIDATE_IP,FILTER_FLAG_IPV4)!==false;
  if(in_array($key,['webPort','monitoringPort','legacyClientPort','unitNumber'],true))return is_int($value)&&$value>=1&&$value<=($key==='unitNumber'?255:65535);
  if($key==='dhcp')return is_bool($value);
  if($key==='timeZone')return is_string($value)&&in_array($value,DateTimeZone::listIdentifiers(),true);
  return false;
}
function sessionInfo(): array {
  return ['username'=>$_SESSION['user']??'', 'role'=>$_SESSION['role']??(($_SESSION['user']??'')==='admin'?'System Admin':'Viewer'), 'isAdministrator'=>isset($_SESSION['user'])&&($_SESSION['role']??($_SESSION['user']==='admin'?'System Admin':'Viewer'))==='System Admin'];
}
function alarmsFor(array $state, ?int $now=null): array {
  $now=$now??time();
  $all=array_merge(array_values($state['temperatureAlarms']??[]),asset('alarms.json'));
  foreach($all as &$a)if(!empty($state['acks'][(string)($a['uid']??'')])){$a['ack']='ACK';$a['ackuser']='OPERATOR';}
  unset($a);
  // Add generated alarm events for synthetic device operations. These use the same field family as captured records.
  foreach(array_reverse($state['events']??[]) as $ev){
    if(($ev['action']??'')!=='defrost')continue;
    $all[]=['uid'=>'9'.$ev['seq'],'iid'=>$ev['deviceId'],'apptype'=>'StdCircuit','ack'=>'UNACK','ackuser'=>'','category'=>'Notice',
      'resolution'=>'ACTIVE','timestamp'=>(string)$ev['timestamp'],'priority'=>'50','unitnum'=>'1','sitename'=>'E3 Unit01',
      'messagekey'=>'Manual defrost initiated','originator'=>(string)$ev['deviceId'],'reportvalue'=>'','limitvalue'=>''];
  }
  foreach($all as &$alarm){
    $uid=(string)$alarm['uid'];$device=(string)$alarm['iid'];
    if(!empty($state['acks'][$uid])){$alarm['ack']='ACK';$alarm['ackuser']='admin';}
    $alarm['suppressedUntil']=max((int)($state['suppression']['all']??0),(int)($state['suppression']['device:'.$device]??0),(int)($state['suppression']['alarm:'.$uid]??0));
    $alarm['suppressed']=$alarm['suppressedUntil']>$now;
  }
  unset($alarm);
  return $all;
}
function processRPC(array $rpc,array &$state,array $devices): array {
  $id=$rpc['id']??null;$method=(string)($rpc['method']??'');$params=$rpc['params']??[];
  if(!is_array($params))$params=[];
  if($method==='')return ['jsonrpc'=>'2.0','error'=>['code'=>-32600,'message'=>'Invalid request'],'id'=>$id];
  $index=[];foreach($devices as $d)$index[(string)$d['id']]=$d;
  $deviceId=getDeviceId($params);$dev=$index[$deviceId]??null;
  $single=$state['devices'][$deviceId]??null;
  $result=[];
  if(isset($_SESSION['user']) && $_SESSION['user']!=='admin'){
    if(isset($state['users'][$_SESSION['user']]))$_SESSION['role']=$state['users'][$_SESSION['user']]['role'];
    else unset($_SESSION['user'],$_SESSION['role']);
  }
  $writes=['SetPointValues','SetDeviceSetpoint','SetDeviceOutput','StartDefrost','AcknowledgeAlarm','ResetAlarm','MuteAlarm','SuppressAlarms','RestoreAlarms','SetTemperature','ResumeTemperatureAuto','SetHighTemperatureLimit','SubmitFeedback','SetDeviceEnabled','GetControlEvents','SaveSystemSettings','SaveUser','DeleteUser'];
  if(in_array($method,$writes,true) && !sessionInfo()['isAdministrator'])return ['jsonrpc'=>'2.0','error'=>['code'=>-32001,'message'=>'Administrator access required'],'id'=>$id];
  switch($method){
    case 'GetSessionID':$result=array_merge(['sid'=>$_SESSION['sid']],sessionInfo());break;
    case 'TouchSession':$result=['status'=>'ok'];break;
    case 'GetSystemInformation':$settings=controllerSettings($state);$system=$settings['system'];$result=[
      'unitnum'=>'1','unitnumber'=>1,'unitNumber'=>1,'unitname'=>$system['unitName'],'site'=>$system['siteName'],'sitename'=>$system['siteName'],
      'name'=>'E3 Unit01','username'=>$_SESSION['user']??'system.default','productname'=>'E3','product'=>'E3','model'=>'E3',
      'displayname'=>'E3 Unit01','systemname'=>'E3 Unit01','version'=>'2.30F01','unitversion'=>'2.30F01',
      'softwareVersion'=>'2.30F01','firmwareversion'=>'2.30F01','platform'=>'E3','localunitnum'=>1,
      'time'=>time(),'timestamp'=>time(),'timezone'=>'America/Los_Angeles','connected'=>true,'online'=>true,'isOnline'=>true,
      'network'=>[],'units'=>[['unitnum'=>(string)$system['unitNumber'],'name'=>$system['unitName']]]
    ];
      foreach(['unitnum','unitnumber','unitNumber','localunitnum'] as $key)$result[$key]=$system['unitNumber'];
      foreach(['name','displayname','systemname'] as $key)$result[$key]=$system['unitName'];
      $result['timezone']=$settings['localization']['timeZone'];break;
    case 'GetHomeScreenState':$home=activeProfile($state)['homeScreen'];$result=['homescreen'=>$home,'page'=>$home,'state'=>$home];break;
    case 'GetSetupWizardStatus':$result=['completed'=>true,'isFinished'=>true,'status'=>'finished'];break;
    case 'Login':
      $user=(string)getValue($params,['username','user'],'');
      $password=(string)getValue($params,['password','passwd'],'');
      $account=$state['users'][$user]??null;
      if(($user==='admin' && $password==='admin') || ($account && password_verify($password,$account['passwordHash']))){
        session_regenerate_id(true);$_SESSION['user']=$user;$_SESSION['role']=$user==='admin'?'System Admin':$account['role'];$_SESSION['sid']=makeUuid();
        $result=array_merge(['success'=>true,'newsid'=>$_SESSION['sid']],sessionInfo());
      }else $result=['success'=>false,'message'=>'Invalid username or password'];break;
    case 'Logout':unset($_SESSION['user'],$_SESSION['role']);session_regenerate_id(true);$result=['success'=>true];break;
    case 'GetProfile':$result=['profile'=>activeProfile($state)];break;
    case 'SaveProfile':
      $profile=$params['profile']??[];$valid=is_array($profile)&&count($profile)>0;
      foreach($profile as $key=>$value)if(!array_key_exists($key,defaultProfile())||!validateSetting($key,$value))$valid=false;
      if(!$valid){$result=['success'=>false,'message'=>'Invalid profile settings'];break;}
      $profile=array_replace(activeProfile($state),$profile);
      if(isset($_SESSION['user']))$state['profiles'][$_SESSION['user']]=$profile;else $_SESSION['profile']=$profile;
      $result=['success'=>true,'profile'=>$profile];break;
    case 'GetSystemSettings':$result=['settings'=>controllerSettings($state)];break;
    case 'SaveSystemSettings':
      $section=$params['section']??'';$values=$params['values']??[];$settings=controllerSettings($state);
      $valid=is_string($section)&&isset($settings[$section])&&is_array($values)&&count($values)>0;
      if($valid)foreach($values as $key=>$value)if(!array_key_exists($key,$settings[$section])||!validateSetting($key,$value))$valid=false;
      if(!$valid){$result=['success'=>false,'message'=>'Invalid settings. Check the field values.'];break;}
      $state['settings'][$section]=array_replace($settings[$section],$values);recordChange($state,'','settings:'.$section,$values);
      $result=['success'=>true,'settings'=>controllerSettings($state)];break;
    case 'GetSessions':$result=['report'=>isset($_SESSION['user'])?[sessionInfo()]:[]];break;
    case 'GetUsers':
      $users=[['username'=>'admin','role'=>'System Admin','email'=>'']];
      foreach($state['users']??[] as $username=>$account)$users[]=['username'=>$username,'role'=>$account['role'],'email'=>$account['email']??''];
      $result=['users'=>$users];break;
    case 'GetRoles':$result=['roles'=>[
      ['name'=>'Viewer','view'=>true,'control'=>false,'configure'=>false,'administer'=>false,'muteAlarms'=>false],
      ['name'=>'System Admin','view'=>true,'control'=>true,'configure'=>true,'administer'=>true,'muteAlarms'=>true]
    ]];break;
    case 'SaveUser':
      $username=$params['username']??'';$password=$params['password']??'';$role=$params['role']??'Viewer';$email=$params['email']??'';
      if(!is_string($username)||!preg_match('/^[a-zA-Z0-9_.-]{1,40}$/',$username)||$username==='admin'||!in_array($role,['Viewer','System Admin'],true)||!is_string($password)||strlen($password)>128||(!isset($state['users'][$username])&&strlen($password)<4)||($password!==''&&strlen($password)<4)||!is_string($email)||($email!==''&&!filter_var($email,FILTER_VALIDATE_EMAIL))){$result=['success'=>false,'message'=>'Use a unique username, valid role, optional email, and a password of 4–128 characters.'];break;}
      $hash=$password!==''?password_hash($password,PASSWORD_DEFAULT):$state['users'][$username]['passwordHash'];
      $state['users'][$username]=['role'=>$role,'email'=>$email,'passwordHash'=>$hash];recordChange($state,'','user:save',['username'=>$username,'role'=>$role]);
      $result=['success'=>true];break;
    case 'DeleteUser':
      $username=$params['username']??'';
      if(!is_string($username)||$username==='admin'||!isset($state['users'][$username])){$result=['success'=>false,'message'=>'User cannot be removed'];break;}
      unset($state['users'][$username],$state['profiles'][$username]);recordChange($state,'','user:delete',$username);$result=['success'=>true];break;
    case 'GetLicenses':$result=['licenses'=>[]];break;
    case 'GetNetworkSummary':$result=['units'=>[['unitnum'=>'1','name'=>'E3 Unit01','status'=>'Online']],'network'=>[],'devices'=>$devices];break;
    case 'GetSystemInventory':$result=['devices'=>$devices,'apps'=>$devices,'applications'=>$devices,'inventory'=>$devices,'units'=>[['unitnum'=>'1','name'=>'E3 Unit01']]];break;
    case 'GetAppTypes':$result=['apptypes'=>array_values(array_unique(array_column($devices,'type'))),'appTypes'=>array_values(array_unique(array_column($devices,'type'))),'apps'=>[]];break;
    case 'GetDashboardSummaryProps':
      $result=['groups'=>[['name'=>'Refrigeration','count'=>36],['name'=>'HVAC','count'=>2],['name'=>'Other','count'=>36],['name'=>'System','count'=>27]],
      'categories'=>['Refrigeration'=>36,'HVAC'=>2,'Other'=>36,'System'=>27], 'tiles'=>$devices,'apps'=>$devices,'applications'=>$devices];break;
    case 'GetDevices':$result=['devices'=>$devices,'count'=>count($devices)];break;
    case 'GetDeviceState':
      $result=$single!==null?['device'=>$dev,'state'=>$single,'success'=>true]:['success'=>false,'message'=>'Application not found'];break;
    case 'GetControlEvents':$result=['events'=>array_reverse($state['events']??[])];break;
    case 'SetDeviceEnabled':
      $enabled=$params['enabled']??null;
      if($single && is_bool($enabled)){
        $state['devices'][$deviceId]['enabled']=$enabled;recordChange($state,$deviceId,'enabled',$enabled);
        $result=['success'=>true,'state'=>$state['devices'][$deviceId]];
      }else $result=['success'=>false,'message'=>'Select enabled or disabled'];break;
    case 'GetDeviceHistory':$result=['history'=>$single['history']??[]];break;
    case 'GetUserSelectedTilePoints':$result=['points'=>[],'tiles'=>[]];break;
    case 'GetPointsDescription':
      $rows=[];if($dev)foreach($dev['points'] as $p)$rows[]=['name'=>$p['name'],'key'=>$p['key'],'datatype'=>$p['datatype']??'float','value'=>$p['value']??null];
      $result=['points'=>$rows,'descriptions'=>$rows];break;
    case 'GetPointValues':
      $rows=[];
      if($single){$rows=[['name'=>$single['unit']==='Pa'?'SUCTION PRES':'CASE TEMP','key'=>'TEMP','value'=>(string)$single['value'],'unit'=>$single['unit']],
        ['name'=>'CONTROL SETPOINT','key'=>'SETPOINT','value'=>(string)$single['setpoint'],'unit'=>$single['unit']],
        ['name'=>'CONTROL OUTPUT','key'=>'OUTPUT','value'=>$single['output'],'unit'=>'']];}
      $result=['points'=>$rows,'values'=>$rows,'deviceId'=>$deviceId];break;
    case 'SetPointValues':
    case 'SetDeviceSetpoint':
      $raw=getValue($params,['setpoint','value','val','target'],null);
      if($single && is_numeric($raw)){
        $num=(float)$raw;
        if($num>=$single['min'] && $num<=$single['max']){
          $state['devices'][$deviceId]['setpoint']=$num;recordChange($state,$deviceId,'setpoint',$num);
          $result=['success'=>true,'status'=>'OK','applied'=>$num];
        }else $result=['success'=>false,'status'=>'OUT_OF_RANGE'];
      }else $result=['success'=>false,'status'=>'BAD_PARAMETERS'];
      break;
    case 'SetDeviceOutput':
      $v=strtoupper((string)getValue($params,['output','value','state'],'AUTO'));
      if($single && in_array($v,['AUTO','ON','OFF'],true)){
        $state['devices'][$deviceId]['output']=$v;recordChange($state,$deviceId,'output',$v);
        $result=['success'=>true,'status'=>'OK','output'=>$v];
      }else $result=['success'=>false,'status'=>'BAD_PARAMETERS'];break;
    case 'StartDefrost':
      if($single && ($dev['type']??'')==='StdCircuit'){$state['devices'][$deviceId]['defrostUntil']=time()+15*60;recordChange($state,$deviceId,'defrost','START');$result=['success'=>true,'status'=>'OK'];}
      else $result=['success'=>false,'status'=>'NOT_FOUND'];break;
    case 'GetAlarms':$result=['alarms'=>alarmsFor($state)];break;
    case 'GetAlarmStatus':$a=alarmsFor($state);$result=['alarms'=>$a,'count'=>count($a)];break;
    case 'AcknowledgeAlarm':
      $uid=(string)getValue($params,['uid','alarmId','alarmid'],'');
      if($uid!==''){$state['acks'][$uid]=true;recordChange($state,'','ack',$uid);}
      $result=['success'=>$uid!=='','status'=>$uid!==''?'OK':'BAD_PARAMETERS'];break;
    case 'ResumeTemperatureAuto':
      if($single){$state['devices'][$deviceId]['override']=false;recordChange($state,$deviceId,'temperatureInput','AUTO');$result=['success'=>true,'state'=>$state['devices'][$deviceId]];}else $result=['success'=>false];break;
    case 'SetTemperature':
    case 'SetHighTemperatureLimit':
      $raw=getValue($params,['temperature','highLimit','value'],null);
      if($single && $single['unit']==='°F' && is_numeric($raw) && is_finite((float)$raw) && (float)$raw>=-100 && (float)$raw<=250){
        $field=$method==='SetTemperature'?'value':'highLimit';
        $state['devices'][$deviceId][$field]=(float)$raw;
        if($field==='value'){
          $state['devices'][$deviceId]['override']=true;
          $state['devices'][$deviceId]['history'][]=['timestamp'=>time(),'value'=>(float)$raw,'setpoint'=>$single['setpoint']];
          $state['devices'][$deviceId]['history']=array_slice($state['devices'][$deviceId]['history'],-200);
        }
        recordChange($state,$deviceId,$field,(float)$raw);evaluateTemperatureAlarms($state,$devices);
        $result=['success'=>true,'state'=>$state['devices'][$deviceId]];
      }else $result=['success'=>false,'message'=>'Enter a temperature between -100 and 250 °F'];break;
    case 'ResetAlarm':case 'MuteAlarm':case 'SuppressAlarms':case 'RestoreAlarms':
      $uid=(string)getValue($params,['uid','alarmId'],'');
      $key=$uid!==''?'alarm:'.$uid:($deviceId!==''?'device:'.$deviceId:'all');
      $minutes=getValue($params,['minutes'],60);
      if(!is_numeric($minutes) || $minutes<1 || $minutes>1440){$result=['success'=>false,'message'=>'Duration must be 1–1440 minutes'];break;}
      $until=in_array($method,['RestoreAlarms','ResetAlarm'],true)?0:time()+(int)$minutes*60;
      if($until===0){
        if($key==='all')$state['suppression']=[];
        elseif($deviceId!=='' && $uid==='')foreach(alarmsFor($state) as $alarm)if((string)$alarm['iid']===$deviceId)unset($state['suppression']['alarm:'.$alarm['uid']]);
      }
      $state['suppression'][$key]=$until;recordChange($state,$deviceId,$method,['scope'=>$key,'until'=>$until]);
      $result=['success'=>true,'suppressedUntil'=>$until];break;
    case 'GetAlarmSuppression':$result=['suppression'=>$state['suppression']??[]];break;
    case 'SubmitFeedback':
      $message=trim((string)getValue($params,['message','feedback'],''));
      if($message==='' || strlen($message)>4000){$result=['success'=>false,'message'=>'Enter feedback up to 4000 characters'];break;}
      $entry=['id'=>makeUuid(),'timestamp'=>time(),'deviceId'=>$deviceId,'username'=>$_SESSION['user'],'message'=>$message];
      $state['feedback'][]=$entry;$state['feedback']=array_slice($state['feedback'],-500);
      recordChange($state,$deviceId,'feedback',$entry['id']);$result=['success'=>true,'feedback'=>$entry];break;
    case 'GetFeedback':$result=['feedback'=>array_values(array_filter($state['feedback']??[],fn($f)=>$deviceId===''||$f['deviceId']===$deviceId))];break;
    case 'GetReportTypes':$result=['reports'=>[]];break;
    case 'GetReport':$result=['report'=>[]];break;
    case 'GetStorageStatus':$result=['storages'=>[],'storage'=>[]];break;
    case 'GetFloorPlanTemplate':$result=['templates'=>[],'floorplans'=>[]];break;
    case 'GetAggregationSubCategoriesApps':$result=['categories'=>[],'apps'=>[]];break;
    case 'GetRuntimeStatus':$result=['status'=>'RUN','running'=>true];break;
    case 'GetSystemResetStatus':$result=['status'=>'READY'];break;
    case 'SetUserSelectedTilePoints':$result=['success'=>true,'status'=>'OK'];break;
    default:
      $result=[];break; // unknown method is logged, no real operations performed
  }
  return ['jsonrpc'=>'2.0','result'=>$result,'id'=>$id];
}
function safeLoggingParams($payload){
  if(!is_array($payload))return $payload;
  $out=[];
  foreach($payload as $k=>$v){
    if(is_string($k)&&preg_match('/password|passwd|token|secret|authorization|cookie|keyfile/i',$k))$out[$k]='[REDACTED]';
    else $out[$k]=is_array($v)?safeLoggingParams($v):$v;
  }
  return $out;
}
function logActivity($rpc): void {
  $entry=['time'=>gmdate('c'),'source'=>$_SERVER['REMOTE_ADDR']??'', 'method'=>$_SERVER['REQUEST_METHOD']??'',
    'path'=>parse_url($_SERVER['REQUEST_URI']??'',PHP_URL_PATH), 'user_agent'=>substr($_SERVER['HTTP_USER_AGENT']??'',0,450),
    'rpc'=>safeLoggingParams($rpc)];
  $line=json_encode($entry,JSON_INVALID_UTF8_SUBSTITUTE|JSON_UNESCAPED_SLASHES);
  @file_put_contents(__DIR__.'/private/events.jsonl',substr($line?:'{}',0,24000)."\n",FILE_APPEND|LOCK_EX);
}

$raw=$_GET['m']??$_POST['m']??null;
if($raw===null){
  $body=file_get_contents('php://input',false,null,0,131072)?:'';
  $form=[];parse_str($body,$form);$raw=$form['m']??$body;
}
$rpc=json_decode((string)$raw,true);
if(!is_array($rpc)){
  logActivity(['error'=>'invalid JSON-RPC']);
  echo json_encode(['jsonrpc'=>'2.0','error'=>['code'=>-32700,'message'=>'Parse error'],'id'=>null]);exit;
}
logActivity($rpc);
$devices=asset('devices.json');
$fp=@fopen(__DIR__.'/private/state.json','c+');
if(!$fp||!flock($fp,LOCK_EX)){
  http_response_code(500);echo json_encode(['jsonrpc'=>'2.0','error'=>['code'=>-32603,'message'=>'Storage unavailable'],'id'=>null]);exit;
}
$existing=stream_get_contents($fp);
$state=json_decode($existing?:'',true);
if(!is_array($state)||!isset($state['devices']))$state=initializeState($devices);
// Smoothly add newly configured applications without losing old runtime state.
foreach($devices as $d)if(!isset($state['devices'][(string)$d['id']])){
  $new=initializeState([$d]);$state['devices'][(string)$d['id']]=$new['devices'][(string)$d['id']];
}
advanceState($state);
evaluateTemperatureAlarms($state,$devices);
$batch=array_is_list($rpc)&&isset($rpc[0])&&is_array($rpc[0]);
try {
  if($batch){$result=[];foreach($rpc as $item)$result[]=processRPC(is_array($item)?$item:[],$state,$devices);}
  else $result=processRPC($rpc,$state,$devices);
  $text=json_encode($state,JSON_UNESCAPED_SLASHES|JSON_INVALID_UTF8_SUBSTITUTE);
  rewind($fp);ftruncate($fp,0);fwrite($fp,$text?:'{}');fflush($fp);
  echo json_encode($result,JSON_UNESCAPED_SLASHES|JSON_INVALID_UTF8_SUBSTITUTE);
} catch(Throwable $e) {
  echo json_encode(['jsonrpc'=>'2.0','error'=>['code'=>-32603,'message'=>'Internal error'],'id'=>$rpc['id']??null]);
}
flock($fp,LOCK_UN);fclose($fp);
