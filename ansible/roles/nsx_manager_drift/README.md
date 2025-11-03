---
title: NSX Manager Drift Role (NSX 4.2.x)
summary: Audit & remediate NTP, DNS, and SYSLOG drift on NSX Managers using the Manager REST APIs. Idempotent and --check friendly.
owners: platform-networking, sres
tags: nsx, manager, drift, remediation, ansible-role
---

## What it does
- **NTP:** Enforces `ntp.servers` via the **Central Node Config Profile** (“All NSX nodes”).
- **DNS:** Ensures Manager node `name-servers` and `search-domains` match desired values.
- **SYSLOG:** Enforces `syslog.exporters` on the **Central Node Config Profile**.

## Requirements
- Ansible 2.15+.
- `nsx_manager_url`, `nsx_username`, `nsx_password` (vault recommended).
- Network reachability from runner to the NSX Manager VIP/API.
- Optionally set `nsx_validate_certs: true` once trusted certs are in place.

## Variables
See `defaults/main.yml`. Common vars:

```yaml
nsx_manager_url: "https://nsx-mgr.home.virtualelephant.com"
nsx_validate_certs: false

nsx_ntp_servers: ["10.1.10.11","10.1.10.12"]

nsx_dns_nameservers: ["10.1.10.11","10.1.10.12"]
nsx_dns_search_domains: ["home.virtualelephant.com","cilium.virtualelephant.com"]

nsx_syslog_exporters:
  - name: "primary"
    server: "10.1.10.30"
    port: 514
    protocol: "UDP"   # UDP|TCP|LI
    max_log_level: "INFO"
    facility: "LOCAL0"
