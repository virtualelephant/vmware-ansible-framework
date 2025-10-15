# ESXi NTP Audit (Read-Only)

This playbook reads NTP **service status** and configured **NTP servers** for a list of ESXi hosts using the **vSphere API** (no SSH).

## Setup

1. Install required Ansible collections and Python libs on the control node:
   ```bash
   ansible-galaxy collection install -r ansible/collections/requirements.yml
   pip install -r ansible/requirements.txt
   ```

2. Put your vCenter hostname/credentials and ESXi host list in `ansible/group_vars/all/global.yml`. Store the `vcenter_password` in **Ansible Vault**:
   ```bash
   ansible-vault create ansible/group_vars/all/vault.yml
   # add: vault_vcenter_password: "YOUR_PASSWORD"
   ```
   Then reference it in `global.yml` as already shown.

## Run

```bash
cd ansible/playbooks/compliance
ansible-playbook read_ntp.yml -e "@../../group_vars/all/vault.yml"
```

Artifacts are written to `artifacts/ntp_audit_<timestamp>.yml` with both raw module output and a compact summary.

## Notes

- Custom module: `ansible/library/vmware_esxi_ntp_info.py`
- Uses `pyvmomi` to query:
  - `HostDateTimeSystem` -> `dateTimeInfo.ntpConfig.server`
  - `HostServiceSystem` -> `serviceInfo.service` (`ntpd`) for running/policy
- Strictly read-only (`changed: false`). Perfect as a building block for config-drift reports.
