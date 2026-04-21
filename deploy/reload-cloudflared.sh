#!/bin/bash
# Non-interactively kickstart the cloudflared system service using the keychain password file.
set -euo pipefail
PW_FILE="$HOME/.keychain_pw"
if [ ! -f "$PW_FILE" ]; then
  echo "ERROR: $PW_FILE missing" >&2
  exit 1
fi
sudo -S -p '' launchctl kickstart -k system/com.cloudflare.cloudflared < "$PW_FILE"
echo "cloudflared kickstart complete"
