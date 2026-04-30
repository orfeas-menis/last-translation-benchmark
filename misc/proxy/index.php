<?php

// transparent proxy from last-translation-benchmark.vilda.net
$target_base = 'https://quest.ms.mff.cuni.cz/ltb/';

$request_uri = $_SERVER['REQUEST_URI'];
$path = ltrim($request_uri, '/');
$target_url = $target_base . $path;

$ch = curl_init($target_url);

curl_setopt($ch, CURLOPT_CUSTOMREQUEST, $_SERVER['REQUEST_METHOD']);

$headers = [];
if (function_exists('getallheaders')) {
    foreach (getallheaders() as $name => $value) {
        if (strtolower($name) === 'host')
            continue;
        $headers[] = "$name: $value";
    }
}
curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);

$body = file_get_contents('php://input');
if (!empty($body)) {
    curl_setopt($ch, CURLOPT_POSTFIELDS, $body);
}

curl_setopt($ch, CURLOPT_FOLLOWLOCATION, false);

// 1. Intercept and stream headers
curl_setopt($ch, CURLOPT_HEADERFUNCTION, function ($curl, $header) {
    $len = strlen($header);
    $header_trim = trim($header);

    if (empty($header_trim))
        return $len;

    // Capture and forward the HTTP status line (e.g., "HTTP/1.1 200 OK")
    if (preg_match('#^HTTP/(1\.0|1\.1|2|3)\s+\d{3}#i', $header_trim)) {
        header($header_trim);
        return $len;
    }

    // Strip Transfer-Encoding; PHP/Apache manages the downstream stream encoding
    if (stripos($header_trim, 'Transfer-Encoding:') === 0)
        return $len;

    header($header_trim, false);
    return $len;
});

// 2. Intercept and stream body chunks
curl_setopt($ch, CURLOPT_WRITEFUNCTION, function ($curl, $data) {
    echo $data;
    flush(); // Force transmission of the chunk to the client
    return strlen($data);
});

// Execute request; blocks until the stream completes
$success = curl_exec($ch);

if ($success === false) {
    // If execution fails before headers are sent, output a 502
    if (!headers_sent()) {
        http_response_code(502);
        echo 'Bad Gateway';
    }
}

?>