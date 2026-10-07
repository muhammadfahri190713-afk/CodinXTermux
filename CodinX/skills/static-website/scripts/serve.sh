#!/usr/bin/env bash
# Layani folder saat ini di background. Pakai: serve.sh [port=8080]. Hentikan: kill $(cat "$TMP/codinx-serve.pid")
port="${1:-8080}"
TMP="${TMPDIR:-/tmp}"
nohup python3 -m http.server "$port" --bind 127.0.0.1 >"$TMP/codinx-serve.log" 2>&1 &
echo $! > "$TMP/codinx-serve.pid"
sleep 1
echo "melayani http://127.0.0.1:$port (PID $(cat "$TMP/codinx-serve.pid"), log $TMP/codinx-serve.log)"
