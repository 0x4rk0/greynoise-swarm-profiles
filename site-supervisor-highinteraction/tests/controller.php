<?php
/** Runtime checks using an isolated state file. */
$root=dirname(__DIR__);
$fixture=sys_get_temp_dir().'/controller-check-'.bin2hex(random_bytes(6));
mkdir($fixture);mkdir($fixture.'/private');mkdir($fixture.'/data');
copy($root.'/api.php',$fixture.'/api.php');
foreach(['devices.json','alarms.json'] as $file)copy($root.'/data/'.$file,$fixture.'/data/'.$file);
// Loading one read request initializes the service without opening a port.
$_SERVER['REQUEST_METHOD']='POST';$_SERVER['REQUEST_URI']='/cgi-bin/mgw.cgi';
$_POST['m']=json_encode(['method'=>'GetSessionID','id'=>1]);
ob_start();require $fixture.'/api.php';ob_end_clean();
$devices=asset('devices.json');$state=initializeState($devices);
function check($value,$message){if(!$value)throw new RuntimeException($message);}
function callRPC($method,$params=[]){global $state,$devices;return processRPC(['method'=>$method,'params'=>$params,'id'=>1],$state,$devices);}
try{
  $id='';foreach($state['devices'] as $key=>$d)if($d['unit']==='°F'){$id=(string)$key;break;}
  check($id!=='','Temperature device required');
  check(isset(callRPC('SetTemperature',['deviceId'=>$id,'value'=>60])['error']),'Anonymous write rejected');
  $before=$state;
  $_SESSION['user']='operator';
  foreach(['SetTemperature','SetHighTemperatureLimit','ResumeTemperatureAuto','SetDeviceSetpoint','SetPointValues','SetDeviceOutput','SetDeviceEnabled','StartDefrost','SuppressAlarms','RestoreAlarms','MuteAlarm','ResetAlarm','AcknowledgeAlarm','GetControlEvents'] as $method){
    $reply=callRPC($method,['deviceId'=>$id,'value'=>60,'setpoint'=>40,'output'=>'OFF','enabled'=>false,'minutes'=>1,'uid'=>'test']);
    check(($reply['error']['code']??null)===-32001,'Non-admin rejected: '.$method);
    check($state===$before,'Non-admin must not mutate state: '.$method);
  }
  unset($_SESSION['user']);
  check(!callRPC('Login',['username'=>'admin','password'=>'wrong'])['result']['success'],'Wrong password rejected');
  check(callRPC('Login',['username'=>'admin','password'=>'admin'])['result']['isAdministrator'],'Admin login');
  check(callRPC('GetSessionID')['result']['username']==='admin','Session identity retained');
  $params=['deviceId'=>$id];
  check(callRPC('SetHighTemperatureLimit',$params+['value'=>45])['result']['success'],'Set limit');
  check(callRPC('SetTemperature',$params+['value'=>60])['result']['success'],'Set temperature');
  $uid=$state['devices'][$id]['temperatureAlarm'];
  check($state['temperatureAlarms'][$uid]['resolution']==='ACTIVE','High temperature raises alarm');
  evaluateTemperatureAlarms($state,$devices);check(count($state['temperatureAlarms'])===1,'No duplicate active alarms');
  callRPC('AcknowledgeAlarm',['uid'=>$uid]);
  callRPC('SuppressAlarms',['uid'=>$uid,'minutes'=>15]);
  $find=function()use(&$state,$uid){foreach(alarmsFor($state) as $a)if($a['uid']===$uid)return $a;throw new RuntimeException('Alarm missing');};
  check($find()['suppressed'] && $find()['ack']==='ACK','Alarm suppression and acknowledgement');
  $until=$find()['suppressedUntil'];
  foreach([$until-1=>true,$until=>false,$until+1=>false] as $clock=>$suppressed){
    $rows=alarmsFor(json_decode(json_encode($state),true),$clock);
    $alarm=array_values(array_filter($rows,fn($a)=>$a['uid']===$uid))[0];
    check($alarm['suppressed']===$suppressed,'Expiry boundary '.$clock);
    check($alarm['resolution']==='ACTIVE','Suppression expiry preserves active condition');
  }
  foreach([1,15,60,240,1440] as $minutes){
    $start=time();callRPC('SuppressAlarms',['uid'=>$uid,'minutes'=>$minutes]);
    $expiry=$find()['suppressedUntil'];check($expiry>=$start+$minutes*60 && $expiry<=time()+$minutes*60,'Selected duration '.$minutes);
    $alarms=alarmsFor($state,$expiry);$alarm=array_values(array_filter($alarms,fn($a)=>$a['uid']===$uid))[0];
    check(!$alarm['suppressed'] && $alarm['resolution']==='ACTIVE','Alarm returns after '.$minutes.' minutes');
  }
  callRPC('RestoreAlarms',['uid'=>$uid]);check(!$find()['suppressed'],'Restore alarm');
  callRPC('SuppressAlarms',$params+['minutes'=>15]);check($find()['suppressed'],'Device suppression');
  $state['suppression']['device:'.$id]=time()-1;check(!$find()['suppressed'],'Suppression expires');
  callRPC('SuppressAlarms',['minutes'=>60]);check($find()['suppressed'],'Global suppression');
  callRPC('SuppressAlarms',['uid'=>$uid,'minutes'=>15]);
  callRPC('RestoreAlarms');check(!$find()['suppressed'],'Global restore clears narrower scopes');
  callRPC('SetTemperature',$params+['value'=>44]);check($find()['resolution']==='ACTIVE','Hysteresis avoids chattering');
  callRPC('SetTemperature',$params+['value'=>43]);check($find()['resolution']==='RETURNED','Temperature recovery clears alarm');
  callRPC('SetTemperature',$params+['value'=>60]);check(count($state['temperatureAlarms'])===2,'New excursion raises new alarm');
  check(!callRPC('SetTemperature',$params+['value'=>999])['result']['success'],'Reject invalid temperature');
  check(!callRPC('SuppressAlarms',['minutes'=>0])['result']['success'],'Reject invalid suppression duration');
  callRPC('ResumeTemperatureAuto',$params);check(!$state['devices'][$id]['override'],'Resume automatic readings');
  callRPC('SetDeviceEnabled',$params+['enabled'=>false]);check(!$state['devices'][$id]['enabled'],'Disable application');
  callRPC('SetDeviceEnabled',$params+['enabled'=>true]);check($state['devices'][$id]['enabled'],'Enable application');
  check(count(callRPC('GetControlEvents')['result']['events'])>0,'Admin activity report');
  check(!callRPC('Login',['username'=>"admin' OR '1'='1",'password'=>'x'])['result']['success'],'SQL-like login does not bypass credentials');
  check(!callRPC('SetTemperature',$params+['value'=>'60; id'])['result']['success'],'Command-like temperature rejected');
  $payload="<script>window.injected=true</script>; ".'$(id)'."; ' OR 1=1 --";
  callRPC('SubmitFeedback',$params+['message'=>$payload]);
  check(callRPC('GetFeedback',$params)['result']['feedback'][0]['message']===$payload,'Injection strings stored literally');
  $state['feedback']=[];

  callRPC('SubmitFeedback',$params+['message'=>'Check evaporator <inspection>']);
  check(callRPC('GetFeedback',$params)['result']['feedback'][0]['message']==='Check evaporator <inspection>','Feedback stored');
  $state=json_decode(json_encode($state),true);
  check(count(callRPC('GetFeedback',$params)['result']['feedback'])===1,'Feedback survives serialization');
  check(count($state['temperatureAlarms'])===2,'Alarm history survives serialization');
  check(callRPC('SaveSystemSettings',['section'=>'system','values'=>['siteName'=>'North Store','unitName'=>'E3 Unit02','unitNumber'=>2]])['result']['success'],'Admin saves system values');
  check(callRPC('GetSystemInformation')['result']['unitname']==='E3 Unit02','System information reflects settings');
  $before=$state;
  check(!callRPC('SaveSystemSettings',['section'=>'network','values'=>['ipAddress'=>'bad-ip']])['result']['success'],'Invalid IP rejected');
  check($before===$state,'Invalid settings are atomic');
  check(callRPC('SaveUser',['username'=>'viewer','password'=>'view123','role'=>'Viewer'])['result']['success'],'Create viewer');
  check(!str_contains(json_encode(callRPC('GetUsers')),'passwordHash'),'User list never returns password hashes');
  check(!callRPC('DeleteUser',['username'=>'admin'])['result']['success'],'Default admin cannot be deleted');
  callRPC('Logout');
  check(callRPC('Login',['username'=>'viewer','password'=>'view123'])['result']['success'],'Viewer login');
  check(!callRPC('GetSessionID')['result']['isAdministrator'],'Viewer is not admin');
  foreach(['SaveSystemSettings','SaveUser','DeleteUser','SuppressAlarms','SetTemperature'] as $method)check(isset(callRPC($method,['section'=>'system','values'=>['siteName'=>'Unauthorized'],'username'=>'intruder','password'=>'test','role'=>'System Admin','deviceId'=>$id,'value'=>80])['error']),'Viewer forbidden: '.$method);
  check(callRPC('SaveProfile',['profile'=>['viewLevel'=>'Advanced','dateFormat'=>'dd/MM/yyyy']])['result']['success'],'Viewer can edit personal profile');
  check(!callRPC('GetSessionID')['result']['isAdministrator'],'Advanced view does not grant admin');
  callRPC('Logout');
  check(callRPC('SaveProfile',['profile'=>['timeFormat'=>'24-hour']])['result']['success'],'Guest can save browser preferences');
  callRPC('Login',['username'=>'viewer','password'=>'view123']);
  check(callRPC('GetProfile')['result']['profile']['dateFormat']==='dd/MM/yyyy','Named profile survives login');
  callRPC('Logout');callRPC('Login',['username'=>'admin','password'=>'admin']);
  check(callRPC('DeleteUser',['username'=>'viewer'])['result']['success'],'Admin removes created user');
  callRPC('Logout');check(isset(callRPC('SuppressAlarms')['error']),'Logout revokes write access');
  echo "Controller checks passed\n";
}finally{
  foreach(glob($fixture.'/private/*') as $file)unlink($file);
  foreach(glob($fixture.'/data/*') as $file)unlink($file);
  unlink($fixture.'/api.php');rmdir($fixture.'/private');rmdir($fixture.'/data');rmdir($fixture);
}
