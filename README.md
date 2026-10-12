# Nexa SSH Tunnel — initial prototype

Ubuntu 22.04/24.04 and Debian 12/13. TLS on port 443, authenticated HTTP CONNECT to the **local SSH server only**, SSH account management through a terminal menu.

## Installation

Clone this repository, inspect the source, and run:

```bash
sudo bash install.sh
sudo nexa
```

Prerequisites: a DNS name pointing to the VPS, an existing valid TLS fullchain and private key, TCP 443 available, and SSH service. Open 443 in cloud firewall. The installer will ask for certificate paths and a separate proxy username/password. Do not publish these secrets. The installer does not automatically issue or renew certificates. Re-copy renewed certificates and restart the service.

## HTTP CONNECT

Use a client supporting TLS to your domain:443, a valid SNI matching the certificate, HTTP CONNECT with Basic proxy authentication, target `ssh.internal:22`, and then SSH authentication. For example the request shape is:

```http
CONNECT ssh.internal:22 HTTP/1.1
Host: ssh.internal:22
Proxy-Authorization: Basic <base64(username:password)>

```

Do not put credentials in public payload files. This prototype does not support arbitrary CONNECT destinations, WebSocket Upgrade, arbitrary Host/SNI spoofing, HTTP GET tunneling, or an admin web GUI. It does not guarantee compatibility with HTTP Injector's payload modes.

## Security and operations

- Run on a fresh test VPS first. Back up SSH access and use a separate administrative account.
- The proxy binds TCP 443 and forwards only to 127.0.0.1:22. It does not expose an open general-purpose proxy.
- SSH accounts are real OS users. Restrict their permissions separately for production and enforce quotas/expiry before offering commercial service.
- The terminal menu's SSH process counts are estimates, not unique people.
- TLS private keys are root-readable; systemd currently runs the proxy as root. Consider a dedicated service user for production.
- Test client compatibility and security before deploying publicly.
