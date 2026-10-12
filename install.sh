#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run with sudo'; exit 1; }
. /etc/os-release
case "$ID:$VERSION_ID" in ubuntu:22.04|ubuntu:24.04|debian:12|debian:13) ;; *) echo "Unsupported: $PRETTY_NAME"; exit 1;; esac
[[ -f proxy.py && -f nexa && -f systemd/nexa-ssh.service ]] || { echo 'Run from extracted repository directory'; exit 1; }
command -v ss >/dev/null && ss -Hltpn '( sport = :443 )' | grep -q LISTEN && { echo 'Port 443 already in use. Stop conflicting service first.'; exit 1; }
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y python3 openssh-server openssl iproute2 ca-certificates
install -d -m 700 /etc/nexa-ssh
install -d -m 755 /opt/nexa-ssh
install -m 755 proxy.py /opt/nexa-ssh/proxy.py
install -m 755 nexa /usr/local/sbin/nexa
install -m 644 systemd/nexa-ssh.service /etc/systemd/system/nexa-ssh.service
read -rp 'TLS domain (DNS A record must point to VPS): ' domain
[[ "$domain" =~ ^[a-zA-Z0-9.-]+$ && "$domain" == *.* ]] || { echo 'Invalid domain'; exit 1; }
read -rp 'Fullchain certificate file path: ' cert
read -rp 'Private key file path: ' key
[[ -f "$cert" && -f "$key" ]] || { echo 'Certificate/key missing'; exit 1; }
install -m 600 "$cert" /etc/nexa-ssh/fullchain.pem
install -m 600 "$key" /etc/nexa-ssh/privkey.pem
if ! openssl x509 -in /etc/nexa-ssh/fullchain.pem -noout -checkend 86400; then echo 'Certificate expired or expires within 24 hours'; exit 1; fi
if ! openssl x509 -in /etc/nexa-ssh/fullchain.pem -noout -checkhost "$domain" | grep -q 'does match'; then echo 'Certificate does not match domain'; exit 1; fi
read -rp 'HTTP CONNECT proxy username: ' proxyuser
[[ "$proxyuser" =~ ^[a-zA-Z0-9_-]{3,32}$ ]] || { echo 'Invalid username'; exit 1; }
read -rsp 'HTTP CONNECT proxy password: ' proxypass; echo
[[ ${#proxypass} -ge 12 && "$proxypass" != *$'\n'* ]] || { echo 'Password must be at least 12 characters and one line'; exit 1; }
export NEXA_SETUP_USER="$proxyuser" NEXA_SETUP_PASS="$proxypass"
python3 - <<'PYENV'
import os,shlex
with open('/etc/nexa-ssh/proxy.env','w') as f:
 f.write('NEXA_PROXY_USER='+shlex.quote(os.environ['NEXA_SETUP_USER'])+'\n')
 f.write('NEXA_PROXY_PASSWORD='+shlex.quote(os.environ['NEXA_SETUP_PASS'])+'\n')
PYENV
unset NEXA_SETUP_USER NEXA_SETUP_PASS proxypass
chmod 600 /etc/nexa-ssh/proxy.env
systemctl enable --now ssh
systemctl daemon-reload
systemctl enable --now nexa-ssh
printf '\nInstalled. Run: sudo nexa\nTLS domain: %s\n' "$domain"
