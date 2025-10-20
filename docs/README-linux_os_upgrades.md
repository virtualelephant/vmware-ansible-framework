# OS Upgrade (Skip Kubernetes) — Ansible Playbook

Safely upgrade OS packages on **Ubuntu/Debian** and **RHEL/CentOS/Alma/Rocky** hosts **without upgrading Kubernetes components** (`kubeadm`, `kubelet`, `kubectl`).  
This playbook also **does not reboot** hosts. Instead, it **detects** whether a reboot is required and produces a Markdown **report** on the control node.

---

## Playbook Location

```
ansible/playbooks/21_linux_os_upgrades.yml
```

---

## What This Playbook Does

- **Skips Kubernetes packages** on all hosts:
  - Ubuntu/Debian: uses `dpkg --set-selections` to **hold** `kubeadm`, `kubelet`, `kubectl`.
  - RHEL-family: uses `yum/dnf` `exclude` to skip `kubeadm*`, `kubelet*`, `kubectl*`.
- **Upgrades OS packages** (dist-upgrade on Debian; latest updates on RedHat).
- **No automatic reboot**.
- **Detects reboot requirement**:
  - Ubuntu/Debian: checks for `/var/run/reboot-required`.
  - RHEL-family: runs `needs-restarting -r`.
- **Generates a Markdown report** on the control node with:
  - Hostname
  - OS family
  - Whether anything was upgraded
  - Whether a reboot is required
- Builds a dynamic inventory group `needs_reboot` to target later.

---

## Supported Platforms

- Ubuntu / Debian (Ansible `ansible_os_family: Debian`)
- RHEL / CentOS / AlmaLinux / Rocky Linux (Ansible `ansible_os_family: RedHat`)

> If a host is not one of these OS families, the playbook asserts and fails early.

---

## Requirements

- **Ansible** 2.12+ recommended.
- Sudo privileges on target hosts.
- **RHEL-family only:** the `needs-restarting` command must be present:
  - On RHEL/CentOS 7/8: `yum install -y yum-utils`
  - On RHEL/CentOS 9 / Alma / Rocky: `dnf install -y dnf-utils` (or `yum-utils` if available)
- SSH connectivity to targets.
- Python available on targets (Ansible default).

---

## Inventory Example

`inventories/prod/inventory.ini`

```ini
[linux]
web01 ansible_host=10.0.0.11
api01 ansible_host=10.0.0.12
db01  ansible_host=10.0.0.13

[ubuntu]
web01
api01

[rhel]
db01
```

---

## Variables

These are defined inside the playbook but can be overridden via `-e` if needed.

| Variable        | Default    | Purpose |
|-----------------|------------|---------|
| `k8s_packages`  | `[kubeadm, kubelet, kubectl]` | Packages to hold/exclude during upgrade |
| `report_dir`    | `reports`  | Directory on the **control node** where the Markdown report is written |

### Override example

```bash
ansible-playbook ansible/playbooks/os_upgrade_skip_k8s.yml   -i inventories/prod/inventory.ini   -e report_dir=out/reports
```

---

## How It Skips Kubernetes Packages

- **Debian/Ubuntu:**  
  Uses `ansible.builtin.dpkg_selections` to set each package’s selection to `hold`. `apt dist-upgrade` will upgrade everything else and **skip** held packages.

- **RHEL-family:**  
  Uses `ansible.builtin.yum`/`dnf` with `exclude: ["kubeadm*", "kubelet*", "kubectl*"]` so those packages are **never** selected for upgrade.

---

## Running the Playbook

### Upgrade a group (no reboot) and produce a report
```bash
ansible-playbook ansible/playbooks/os_upgrade_skip_k8s.yml   -i inventories/prod/inventory.ini   -l linux
```

### Target a single host
```bash
ansible-playbook ansible/playbooks/os_upgrade_skip_k8s.yml   -i inventories/prod/inventory.ini   -l web01
```

### Dry run (preview changes)
```bash
ansible-playbook ansible/playbooks/os_upgrade_skip_k8s.yml   -i inventories/prod/inventory.ini   --check
```

> **Note:** `--check` will show what would be changed, but some facts (like reboot-required files) may not reflect post-upgrade reality in check mode.

---

## Report Output

After a successful run, a Markdown report is written to the control node:

```
reports/os_upgrade_report_<timestamp>.md
```

### Example report (excerpt)

```markdown
# OS Upgrade Report (no reboot)
Generated: 20250101-120102

| Host  | OS Family | Upgraded Anything | Reboot Required |
|------|-----------|-------------------|-----------------|
| web01 | Debian | True | True |
| api01 | Debian | False | False |
| db01  | RedHat | True | False |

## Notes
- Kubernetes packages (`kubeadm`, `kubelet`, `kubectl`) were held/excluded and **not** upgraded.
- No automatic reboot was performed.
```

---

## Follow‑up Actions

### Reboot only hosts that need it (later)
The play builds a dynamic inventory group `needs_reboot`. You can reboot just those hosts when ready:

```bash
ansible -i inventories/prod/inventory.ini needs_reboot -m reboot --become
```

Or via a playbook that targets `needs_reboot` with a maintenance window.

---

## Troubleshooting

- **`needs-restarting: command not found`** (RHEL-family):
  - Install utils: `sudo yum install -y yum-utils` (or `dnf install -y dnf-utils`).
  - Re-run the play.

- **APT “locked/held” messages**:
  - That’s expected for `kubeadm`, `kubelet`, `kubectl`. Those are intentionally held.

- **Permissions / sudo**:
  - Ensure your Ansible connection has `become: true` privileges for package actions.

- **Connectivity / Python**:
  - Confirm SSH works and Python is present on targets (`/usr/bin/python` or Python 3 variants).

- **Fact gathering issues**:
  - The play relies on `ansible_os_family`. If fact gathering is disabled, ensure that var is otherwise provided.

---

## Extending the Playbook

- Include kernel versions and changed packages in the report.
- Add a tag (e.g., `--tags report`) to run only the reporting tasks.
- Pin specific OS version levels (e.g., `dist` → `full-upgrade` behaviour) per your policy.
- Add Slack/Email notification when any host requires a reboot.

If you want any of the above, open an issue or request an enhanced version.

---

## Security Notes

- Package upgrades run with `become: true`. Limit inventory scope with `-l` to reduce blast radius.
- Review any OS-specific repo definitions and mirrors before executing in production.
- Ensure your CI/CD pipeline performs linting (`ansible-lint`) on the playbook before merge.

---

## Example CI Lint (optional)

`.gitlab-ci.yml` (excerpt)

```yaml
stages: [lint]
lint:
  image: cytopia/ansible-lint
  stage: lint
  script:
    - ansible-lint ansible/playbooks/os_upgrade_skip_k8s.yml || true
```

---

## License

MIT (or align with your repo’s license).

---

## Maintainer

Virtual Elephant Consulting, LLC — Operations & Platform Engineering
