#!/usr/bin/env bash
set -euo pipefail

# Ensure .mjs is mapped as JavaScript (PDF.js worker dynamic import)
if grep -Eq 'application/javascript[[:space:]]+js;' /etc/nginx/mime.types; then
  sed -i 's|application/javascript[[:space:]]\{1,\}js;|application/javascript                js mjs;|' /etc/nginx/mime.types
fi
echo "mime.types:"
grep 'application/javascript' /etc/nginx/mime.types

SITE=/etc/nginx/sites-available/papermate
if [[ ! -f "$SITE" ]]; then
  echo "missing $SITE" >&2
  exit 1
fi

if ! grep -q 'location ~\* \\.mjs\$' "$SITE"; then
  python3 - "$SITE" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
marker = "client_max_body_size 32m;"
block = """client_max_body_size 32m;

    # PDF.js worker (.mjs) must be served as JavaScript for dynamic import()
    location ~* \\.mjs$ {
        default_type application/javascript;
        types { application/javascript mjs; }
        try_files $uri =404;
        add_header Cache-Control "public, max-age=31536000, immutable";
    }
"""
if marker not in text:
    raise SystemExit("marker missing in nginx site")
path.write_text(text.replace(marker, block, 1), encoding="utf-8")
print("inserted .mjs location")
PY
else
  echo ".mjs location already present"
fi

nginx -t
systemctl reload nginx

echo "=== headers ==="
curl -sI "http://127.0.0.1/assets/pdf.worker.min-yatZIOMy.mjs" | head -15
