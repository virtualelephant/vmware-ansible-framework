# Linux OS Audit & Remediation Playbook

This Ansible playbook (`linux_os_audit.yml`) audits and automatically remediates critical Linux system configurations — **DNS**, **NTP (chrony)**, **liagentd**, and **SSHD** — across Ubuntu and Red Hat-based hosts.

The playbook ensures compliance with your defined global settings and reports the results for each host.

---

## 📋 Overview

### Functions Performed
| Component | Checks | Auto-Fixes | Validation |
|------------|---------|-------------|-------------|
| **DNS** | Verifies resolver configuration | Updates `/etc/resolv.conf` or `systemd-resolved` drop-in | Confirms desired DNS and search domains |
| **NTP (Chrony)** | Verifies `chrony` service and configuration | Installs/configures `chrony.conf` | Ensures service is enabled and running |
| **liagentd** | Validates checksum of `/etc/liagentd.ini` | Replaces from master copy if mismatched | Restarts service and checks status |
| **SSHD** | Validates checksum of `/etc/ssh/sshd_config` | Replaces from master copy if mismatched | Reloads SSHD and ensures service is enabled |

---

## 🧩 Repository Structure

```
ansible/
├── playbooks/
│   └── linux_os_audit.yml
├── group_vars/
│   └── all.yml
├── templates/
│   ├── chrony.conf.j2
│   ├── resolv.conf.j2
│   └── systemd-resolved-override.conf.j2
└── files/
    ├── liagentd.ini
    └── sshd_config
```

---

## ⚙️ Global Variables

Defined in **`group_vars/all.yml`**:

```yaml
# DNS settings
dns_nameservers:
  - 1.1.1.1
  - 8.8.8.8
dns_search_domains:
  - home.virtualelephant.com

# NTP servers
ntp_servers:
  - 0.pool.ntp.org
  - 1.pool.ntp.org
  - 2.pool.ntp.org
```

---

## 🚀 Usage

Run the playbook using `ansible-playbook` with your inventory file.

### 1️⃣ Audit Only (Dry Run)
Check what would change without applying modifications:

```bash
ansible-playbook playbooks/linux_os_audit.yml -i inventories/lab/inventory.ini --check --diff
```

### 2️⃣ Enforce and Remediate
Apply the changes automatically:

```bash
ansible-playbook playbooks/linux_os_audit.yml -i inventories/lab/inventory.ini
```

### 3️⃣ Target Specific Host or Group
```bash
ansible-playbook playbooks/linux_os_audit.yml -i inventories/prod/inventory.ini -l webservers
```

---

## 📊 Example Output

```yaml
TASK [Show per-host summary] *************************************************
ok: [ubuntu01] => {
    "msg": [
        "DNS: configured via systemd-resolved drop-in",
        "NTP: chrony installed, configured, and running",
        "liagentd: config OK & service running",
        "SSHD: config replaced & service reloaded"
    ]
}
```

---

## 🛠️ Notes

- Automatically detects whether `/etc/resolv.conf` is managed by **systemd-resolved**.
- Handles both **Debian/Ubuntu** and **RHEL/CentOS** naming conventions for services (`ssh` vs `sshd`, `chrony` vs `chronyd`).
- `liagentd.ini` and `sshd_config` are validated by checksum — if mismatched, they’re replaced and the service is restarted or reloaded.
- All changes are **idempotent** — safe to re-run repeatedly.

---

## 🧾 Example CI Integration (Optional)

You can lint and validate this playbook automatically in CI/CD:

```yaml
# .gitlab-ci.yml
stages:
  - lint
  - validate

ansible-lint:
  stage: lint
  image: cytopia/ansible-lint
  script:
    - ansible-lint playbooks/linux_os_audit.yml

syntax-check:
  stage: validate
  image: alpine/ansible:latest
  script:
    - ansible-playbook playbooks/linux_os_audit.yml --syntax-check
```

---

## 📘 License

Licensed under the MIT License © 2025 Virtual Elephant Consulting, LLC.

---

## 👤 Author

**Chris Mutchler**  
*Principal Enterprise Architect*  
Virtual Elephant Consulting, LLC  
[https://virtualelephant.com](https://virtualelephant.com)
