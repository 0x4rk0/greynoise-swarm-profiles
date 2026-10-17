<?php
// For local testing only: php -S 127.0.0.1:8080 router.php
$path = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH) ?: '/';
if (!preg_match('~^/(unit[0-9]+/)?cgi-bin/mgw\.cgi$~', $path)) {
    $record = ['time'=>gmdate('c'),'ip'=>$_SERVER['REMOTE_ADDR']??'','method'=>$_SERVER['REQUEST_METHOD']??'',
        'path'=>$path,'ua'=>substr($_SERVER['HTTP_USER_AGENT']??'',0,250)];
    @file_put_contents(__DIR__.'/private/http-events.jsonl',json_encode($record,JSON_INVALID_UTF8_SUBSTITUTE)."\n",FILE_APPEND|LOCK_EX);
}

$path=rawurldecode($path);
if(str_contains($path,"\0") || preg_match('~(?:^|/)\.\.?(?:/|$)~',$path)) {http_response_code(404);return true;}
if (preg_match('~^/unit\d+/(.+)$~',$path,$m)) $path='/'.$m[1];
if (preg_match('~^/(unit\d+/)?cgi-bin/mgw\.cgi$~',$path)) { require __DIR__.'/api.php'; return true; }
if ($path==='/catalog.php') { require __DIR__.'/catalog.php'; return true; }
if (str_starts_with($path, '/data/') || str_starts_with($path, '/private/') || str_starts_with($path, '/tests/') || in_array($path,['/router.php','/api.php','/README.md','/.htaccess','/Dockerfile','/compose.yaml','/original-vue.html.bak'],true) || preg_match('~/(?:\.|[^/]+\.(?:log|sqlite|zip|php\.bak))~i',$path)) {
    http_response_code(404); return true;
}
if ($path==='/' || $path==='/index.html') {readfile(__DIR__.'/index.html');return true;}
$full=realpath(__DIR__.$path);
if ($full!==false && str_starts_with($full,realpath(__DIR__).DIRECTORY_SEPARATOR) && is_file($full)) {
    $ext=strtolower(pathinfo($full, PATHINFO_EXTENSION));
    $types=['js'=>'text/javascript','css'=>'text/css','html'=>'text/html','json'=>'application/json','png'=>'image/png','jpg'=>'image/jpeg','ico'=>'image/x-icon','woff2'=>'font/woff2','svg'=>'image/svg+xml'];
    if(!isset($types[$ext])){http_response_code(404);return true;}
    header('Content-Type: '.$types[$ext]);
    readfile($full);return true;
}
http_response_code(404); echo 'Not found'; return true;
