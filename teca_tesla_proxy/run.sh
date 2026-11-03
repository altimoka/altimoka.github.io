#!/bin/sh
set -e

DATA=/data
KEY_FILE=/config/tesla_smart_routes/private.pem

if [ ! -f "$KEY_FILE" ]; then
    echo "[tesla-proxy] ERROR: $KEY_FILE not found."
    echo "[tesla-proxy] Copy your Tesla EC private key to P:\\tesla_smart_routes\\private.pem (HAOS config share)"
    exit 1
fi

# Generate TLS cert on first run
if [ ! -f "$DATA/tls-cert.pem" ]; then
    echo "[tesla-proxy] Generating self-signed TLS cert..."
    openssl req -x509 -nodes -newkey ec \
        -pkeyopt ec_paramgen_curve:secp384r1 \
        -pkeyopt ec_param_enc:named_curve \
        -subj "/CN=tesla-proxy" \
        -keyout "$DATA/tls-key.pem" \
        -out "$DATA/tls-cert.pem" \
        -sha256 -days 3650 \
        -addext "subjectAltName=IP:127.0.0.1,DNS:localhost" \
        -addext "extendedKeyUsage=serverAuth" \
        -addext "keyUsage=digitalSignature,keyCertSign,keyAgreement"
    echo "[tesla-proxy] TLS cert generated."
fi

echo "[tesla-proxy] TLS certificate SHA256 (public identifier):"
openssl x509 -in "$DATA/tls-cert.pem" -noout -fingerprint -sha256

echo "[tesla-proxy] Starting proxy on port 4443..."
exec tesla-http-proxy \
    -tls-key "$DATA/tls-key.pem" \
    -cert "$DATA/tls-cert.pem" \
    -key-file "$KEY_FILE" \
    -host 0.0.0.0 \
    -port 4443
