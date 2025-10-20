# ESXi DNS Audit & Enforce

This folder contains two tools to **audit** and **enforce** DNS settings on ESXi hosts via vCenter:

1) **Ansible playbook:** `ansible/playbooks/31_esxi_audit_dns.yml`  
   - Runs in **audit** (default) or **enforce** mode.  
   - Uses the desired values from `ansible/group_vars/all/globals.yml`.

2) **Python audit script:** `library/vmware_esxi_dns_audit.py`  
   - Read‑only checker that compares the **current** ESXi DNS configuration to your **desired** settings and prints a host-by-host diff.

> Designed to mirror the prior NTP audit/enforce workflow in this repository: audit first, then optionally enforce. The playbook is **idempotent** and **does not reboot** any host.


---

## Repository Layout

```
ansible/
  group_vars/
    all/
      globals.yml                 # Desired DNS + vCenter connection
  inventories/
    lab/
      inventory.ini               # Example inventory group [esxi]
  playbooks/
        31_esxi_audit_dns.yml        # <-- This playbook
library/
  vmware_esxi_dns_audit.py               # <-- Python audit script
```

---

## Prerequisites

### Common
- vCenter credentials with permission to read/update host network settings.
- ESXi hosts are managed by the vCenter defined in `globals.yml`.

### Ansible
- Python 3.8+ on the control node
- Ansible 2.15+
- `community.vmware` collection

Install the collection:
```bash
ansible-galaxy collection install community.vmware
```

### Python audit script
- `pyvmomi` and `PyYAML`

Install:
```bash
pip install pyvmomi pyyaml
```

---

## Variables

Define the desired DNS servers and search domains (and vCenter connection) in `ansible/group_vars/all/globals.yml`:

```yaml
# vCenter connectivity
vcenter_hostname: "vcenter.home.virtualelephant.com"
vcenter_username: "administrator@vsphere.local"
vcenter_password: "{{ vault_vcenter_password }}"   # or plain env var, see below
vcenter_validate_certs: false

# Desired DNS for ESXi
dns_nameservers:
  - 10.1.10.11
  - 10.1.10.12

dns_search_domains:
  - home.virtualelephant.com
  - cilium.virtualelephant.com
```

> Tip: Store the password in Ansible Vault or inject as a CI/CD variable.

### Inventory

Example: `ansible/inventories/lab/inventory.ini`
```ini
[esxi]
esxi-01.home.virtualelephant.com
esxi-02.home.virtualelephant.com
esxi-03.home.virtualelephant.com
```

---

## 1) Ansible Playbook — `31_esxi_audit_dns.yml`

### What it does
- **Audit mode (default):** dry-run against each ESXi host to determine whether DNS settings differ from the desired values. No changes are made.
- **Enforce mode:** sets `dns_nameservers` and `dns_search_domains` on each host that differs. No changes are made if hosts already match.

Under the hood, the playbook uses `community.vmware.vmware_host_dns`, which is idempotent and vCenter‑aware.

### Usage

**Audit (no changes):**
```bash
ansible-playbook ansible/playbooks/31_esxi_audit_dns.yml \
  -i ansible/inventories/inventory.ini \
  -e mode=audit
```

**Enforce (apply changes):**
```bash
ansible-playbook ansible/playbooks/31_esxi_audit_dns.yml \
  -i ansible/inventories/inventory.ini \
  -e mode=enforce
```

You can also set the mode via environment variable:
```bash
MODE=audit ansible-playbook ansible/playbooks/31_esxi_audit_dns.yml -i ansible/inventories/inventory.ini
```

### Expected Output

**Audit mode:** prints a list of hosts that *would* change, e.g.
```
TASK [Audit summary (mode=audit)] *****************************************
ok: [esxi-01.home.virtualelephant.com] => {
  "msg": [
    {"host": "esxi-02.home.virtualelephant.com", "would_change": true},
    {"host": "esxi-03.home.virtualelephant.com", "would_change": true}
  ]
}
```

**Enforce mode:** shows standard Ansible changed/ok status per host:
```
TASK [(ENFORCE) Apply DNS settings (idempotent)] ***************************
changed: [esxi-02.home.virtualelephant.com]
ok:      [esxi-03.home.virtualelephant.com]
```

### Notes
- The playbook **does not reboot** hosts.
- If hosts are governed by **Host Profiles**, ensure the profile is aligned with these desired DNS values to avoid drift/remediation loops.
- To scope to a subset of hosts, use an inventory limit:
  ```bash
  ansible-playbook ... --limit esxi-02.home.virtualelephant.com
  ```

---

## 2) Python Audit Script — `tools/esxi_dns_audit.py`

A lightweight, read‑only checker that lists for each ESXi host:
- Current DNS servers
- Current search domains
- Desired DNS servers / search domains
- Status: `MATCH` or `DIFF`

### Environment Variables
Set these before running:
```bash
export VCENTER_HOSTNAME=vcenter.home.virtualelephant.com
export VCENTER_USERNAME=administrator@vsphere.local
export VCENTER_PASSWORD='********'
```

### Run

Audit a specific inventory (recommended):
```bash
python3 library/vmware_esxi_dns_audit.py --inventory ansible/inventories/lab/inventory.ini
```

Audit *all* HostSystems in vCenter (omit `--inventory`):
```bash
python3 library/vmware_esxi_dns_audit.py
```

Use a different globals file:
```bash
python3 library/vmware_esxi_dns_audit.py --globals ansible/group_vars/all/globals.yml
```

### Example Output
```
HOST                               | STATUS | CURRENT DNS                  | CURRENT SEARCH                | DESIRED DNS                  | DESIRED SEARCH
----------------------------------------------------------------------------------------------------------------------------
esxi-01.home.virtualelephant.com   | MATCH  | 10.1.10.11,10.1.10.12       | home.virtualelephant.com      | 10.1.10.11,10.1.10.12       | home.virtualelephant.com
esxi-02.home.virtualelephant.com   | DIFF   | 8.8.8.8                     | localdomain                   | 10.1.10.11,10.1.10.12       | home.virtualelephant.com
```

---

## Troubleshooting

- **`ModuleNotFoundError: No module named 'pyVmomi'`**  
  Install: `pip install pyvmomi`

- **`community.vmware` collection missing**  
  Install: `ansible-galaxy collection install community.vmware`

- **TLS/Certificate issues with vCenter**  
  Set `vcenter_validate_certs: false` in `globals.yml` (or fix your trust chain).

- **Permission denied when enforcing**  
  Ensure the vCenter account has privileges to modify host network settings.

- **Host Profiles reverting changes**  
  Update and remediate the profile to include the desired DNS settings.

---

## CI/CD Tips (Optional)

- Add a CI job that runs the Python audit script daily and attaches the diff to your pipeline artifact.
- Use `mode=audit` in a scheduled Ansible job to track configuration drift without making changes.
- Commit `globals.yml` changes via pull request to maintain change history and reviews.

---

## Safety & Idempotency

- **No reboots** are performed.
- The Ansible module only changes hosts when the current values differ from desired.
- The Python script is read‑only and never performs writes.

---

## Maintainers

- Virtual Elephant Consulting, LLC — Platform/VMware Automation
- Chris Mutchler (@virtualelephant)

