# VMware Ansible Playbooks — VM Lifecycle

This repo contains three Ansible playbooks that manage the end‑to‑end lifecycle of VMs in vCenter:

1. **Clone missing VMs from a template** — `ansible/playbooks/vmware/clone_vm.yml`
2. **Provision brand‑new empty VMs (no template)** — `ansible/playbooks/vmware/provision_vm.yml`
3. **Delete a set of VMs** — `ansible/playbooks/vmware/delete_vm.yml`

Each playbook is **idempotent**: it queries vCenter first, skips work for VMs that already match the requested state (or are missing in the case of delete), and continues processing the rest.

---

## Prerequisites

- **Ansible** 2.13+ recommended
- **Python packages** on the control machine:
  - `pyvmomi` (>= 8.0.2.0)
  - `requests`
- **Ansible Collection**: `community.vmware`
  ```bash
  ansible-galaxy collection install -r ansible/collections/requirements.yml
  ```
  Example `ansible/collections/requirements.yml`:
  ```yaml
  ---
  collections:
    - name: community.vmware
  ```
- **vCenter credentials** (recommend using **Ansible Vault** for the password)  
- Network objects (distributed portgroups) and clusters/datastores referenced in your vars must already exist.

> **TLS note:** If your vCenter uses a self‑signed cert, set `vcenter_validate_certs: false` in your vars file or add your CA to the control host’s trust store.

---

## Folder Structure

```
ansible/
├── collections/
│   └── requirements.yml
├── playbooks/
│   └── vmware/
│       ├── clone_vms.yml
│       ├── provision_empty_vms.yml
│       └── delete_vms.yml
└── vars/
    ├── vms.yml                 # example for clone_vms.yml
    ├── empty_vms.yml           # example for provision_empty_vms.yml
    └── vms_delete.yml          # example for delete_vms.yml
```

---

## Shared Variables (all playbooks)

Every vars file includes the vCenter connection block and a list of VMs:

```yaml
vcenter_server: "vcenter.home.virtualelephant.com"
vcenter_username: "administrator@vsphere.local"
vcenter_password: "!vault | your_encrypted_password_here"
vcenter_validate_certs: false
vcenter_datacenter: "HomeLab-DC"
```

> Store `vcenter_password` in Vault in real use:  
> `ansible-vault create ansible/vars/.vault.yml` then reference it with `!vault` or use `lookup('env','VMWARE_PASSWORD')` if you prefer environment variables.

---

## 1) Clone Only Missing VMs from a Template

**Playbook:** `ansible/playbooks/vmware/clone_vm.yml`

**Vars example:** `ansible/group_vars/vms_clone.yml`
```yaml
default_template: "ubuntu-25.10-template"

vms:
  - name: "gitlab"
    vcpu: 4
    memory_gb: 16
    network: "dvpg-servers"      # distributed portgroup
    cluster: "Compute-Cluster"
    datastore: "vsanDatastore"

  - name: "harbor"
    vcpu: 4
    memory_gb: 8
    network: "dvpg-servers"
    cluster: "Compute-Cluster"
    datastore: "vsanDatastore"

  - name: "runner-01"
    vcpu: 2
    memory_mb: 4096
    network: "dvpg-servers"
    cluster: "Compute-Cluster"
    datastore: "vsanDatastore"
    template: "ubuntu-22.04-template"   # overrides default_template
```

### How it works (Logic)
1. **Discover** — For each requested `name`, the play runs `vmware_guest_info`. Missing VMs return no instance.
2. **Decide** — Build a map of `{ vm_name: exists? }`.
3. **Act** — For VMs that **don’t exist**, run `vmware_guest state=present` with `template`, target `cluster`, `datastore`, hardware, and **distributed portgroup**.  
   Existing VMs are **skipped** (so they are not modified).

### Run
```bash
ansible-playbook ansible/playbooks/vmware/clone_vm.yml \
  -e vms_config_file=ansible/group_vars/vms_clone.yml
```

---

## 2) Provision Empty VMs (No Template)

**Playbook:** `ansible/playbooks/vmware/provision_vm.yml`

Use this when you need *brand‑new* VMs (no template) that you’ll install an OS on manually (optionally mount an ISO).

**Vars example:** `ansible/group_vars/vms_create.yml`
```yaml
vms:
  - name: "win-build-01"
    vcpu: 4
    memory_gb: 16
    disk_gb: 200
    disk_type: thin
    guest_id: "windows2019srv_64Guest"
    network: "dvpg-servers"
    cluster: "Compute-Cluster"
    datastore: "vsanDatastore"
    firmware: "efi"
    scsi_type: "paravirtual"
    iso_path: "[vsanDatastore] iso/en_windows_server_2019.iso"  # optional
    power_on: false

  - name: "linux-bare-01"
    vcpu: 2
    memory_mb: 4096
    disk_gb: 60
    guest_id: "ubuntu64Guest"
    network: "dvpg-servers"
    cluster: "Compute-Cluster"
    datastore: "vsanDatastore"
    firmware: "efi"
    power_on: false
```

### How it works (Logic)
1. **Discover** — `vmware_guest_info` checks if each VM name already exists.
2. **Decide** — Build `{ vm_name: exists? }`.
3. **Act** — For **missing** VMs, `vmware_guest state=present` creates a **new empty VM** with:
   - `guest_id` (Guest OS type), CPU, memory, disk size/type
   - SCSI controller (optional), firmware (`efi`/`bios`)
   - Distributed portgroup network
   - Optional **ISO** attached to virtual CDROM for manual install  
   Default behavior leaves VMs **powered off** so you can adjust boot order or start installs later.

> Tip: `guest_id` must match a valid vSphere Guest OS identifier (e.g., `ubuntu64Guest`, `rhel9_64Guest`, `windows2019srv_64Guest`).

### Run
```bash
ansible-playbook ansible/playbooks/vmware/provision_vm.yml \
  -e vms_config_file=ansible/group_vars/vm_create.yml
```

---

## 3) Delete VMs

**Playbook:** `ansible/playbooks/vmware/delete_vm.yml`

**Vars example:** `ansible/group_vars/vms_delete.yml`
```yaml
delete_from_disk: true   # if false: remove from inventory only

# names as strings:
# vms:
#   - "gitlab"
#   - "harbor"
#   - "runner-01"

# or objects (future extensibility):
vms:
  - name: "gitlab"
  - name: "harbor"
  - name: "runner-01"
```

### How it works (Logic)
1. **Discover** — Get `vmware_guest_info` for each requested name to determine existence and power state.
2. **Safeguard** — For existing VMs that are **powered on**, the play first **powers them off** using `vmware_guest_powerstate`.
3. **Remove** — Run `vmware_guest state=absent` with `delete_from_disk` (default `true`).  
   Missing VMs are **skipped**; the play continues with the rest.

### Run
```bash
ansible-playbook ansible/playbooks/vmware/delete_vms.yml \
  -e vms_config_file=ansible/group_vars/vms_delete.yml
```

---

## Makefile (Optional Convenience)

```makefile
.PHONY: deps clone empty delete

deps:
\tansible-galaxy collection install -r ansible/collections/requirements.yml

clone:
\tansible-playbook ansible/playbooks/vmware/clone_vm.yml -e vms_config_file=ansible/group_vars/vms_clone.yml

empty:
\tansible-playbook ansible/playbooks/vmware/provision_vm.yml -e vms_config_file=ansible/vars/vms_create.yml

delete:
\tansible-playbook ansible/playbooks/vmware/delete_vm.yml -e vms_config_file=ansible/vars/vms_delete.yml
```

---

## Troubleshooting

- **Self‑signed vCenter certs:** set `vcenter_validate_certs: false` or install your CA on the control host.
- **Guest IDs:** If creation fails, double‑check `guest_id` strings against vSphere’s supported list.
- **Distributed Portgroups:** Ensure the `network` exists and is a **DVPG** when `type: distributed` is used.
- **Permissions:** The vCenter user must have privileges to read inventory, create, power control, and delete VMs in the target DC/cluster/folder/datastore.
- **Check mode:** Some VMware modules only partially support `--check`. Prefer running on a test project first.

---

## Security

- Store secrets with **Ansible Vault** and avoid committing them to git.
- Consider scoping credentials to a service account with least‑privilege in vCenter.
- If you log CI output, mask or avoid printing sensitive variables.

---
