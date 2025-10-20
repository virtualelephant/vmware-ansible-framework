# Mass vMotion + Storage vMotion (Throttled) — Ansible Playbook

This playbook performs **mass vMotions** (with optional **Storage vMotion**) across clusters in vCenter with **throttled parallelism**.  
It supports **per‑VM source and destination clusters**, validates that required **distributed portgroups (DVPGs)** exist, picks a destination host, and moves both **compute and storage**.

If a VM is not eligible (e.g., DVPG missing, no dest host, no target datastore), it is **skipped** and the play continues with the rest.

---

## Files & Paths

```
ansible/
└── playbooks/
    └── operations/
        └── vmotion_migrations.yml
ansible/group_vars/
└── vmotion.yml        # per-run variables (vCenter + list of VMs to move)
```

---

## Prerequisites

- Ansible 2.13+
- Python packages on the control host: `pyvmomi>=8.0.2.0`, `requests`
- Ansible Collection: `community.vmware`
  ```bash
  ansible-galaxy collection install community.vmware
  ```
- vCenter user with privileges to: read inventory, query clusters/hosts/datastores/DVPGs, **vMotion/Storage vMotion** VMs.
- The destination clusters must have at least one ESXi host in a connected state.
- Target DVPG names must already exist in the datacenter (or a VM will be skipped).

> **TLS**: If your vCenter uses a self-signed certificate, set `vcenter_validate_certs: false` in your vars file or add your CA to the control host trust store.

---

## Variables File (example)

**`ansible/group_vars/vmotion.yml`**
```yaml
# vCenter connection (store password with Ansible Vault in real use)
vcenter_server: "vcenter.home.virtualelephant.com"
vcenter_username: "administrator@vsphere.local"
vcenter_password: "!vault | your_encrypted_password_here"
vcenter_validate_certs: false
vcenter_datacenter: "HomeLab-DC"

# Optional run controls (can also be passed via -e at runtime)
# vmotion_parallel: 10          # number of VMs to move in parallel (default 5)
# vmotion_timeout: 7200         # seconds to wait for each VM task

# Workload: one entry per VM
# Required: name, src_cluster, dest_cluster
# Optional: dest_datastore, networks_to_check, priority (high|default|low)
vms:
  - name: "gitlab"
    src_cluster: "Compute-Cluster-A"
    dest_cluster: "Compute-Cluster-B"
    # networks_to_check: ["dvpg-servers"]  # defaults to VM's current networks
    # priority: high

  - name: "harbor"
    src_cluster: "Compute-Cluster-A"
    dest_cluster: "Compute-Cluster-C"
    dest_datastore: "vsanDatastore"
    networks_to_check: ["dvpg-servers"]
    priority: default

  - name: "runner-01"
    src_cluster: "Edge-Cluster-1"
    dest_cluster: "Compute-Cluster-B"

  - name: "analytics-01"
    src_cluster: "Analytics-Cluster"
    dest_cluster: "Compute-Cluster-B"
    dest_datastore: "nvme-ds1"
    networks_to_check:
      - "dvpg-frontend"
      - "dvpg-backend"
      - "dvpg-monitoring"
    priority: high
```

### Datastore selection logic
For each VM, the play picks the **destination datastore** as follows:
1. If `dest_datastore` is provided for that VM → **use it**.
2. Else, try the VM’s **current datastore name** on the destination side → **use it if present**.
3. Else, the VM is **skipped** (reported in the summary).

### DVPG validation & skip behavior
- If any DVPG listed in `networks_to_check` is missing, the VM is **skipped**.  
- If `networks_to_check` is omitted, the play validates the VM’s **current** DVPG names.

---

## How It Works (Logic)

1. **Load config**: vCenter details and `vms:` list from `vmotion.yml`.
2. **Discover**: Build destination cluster → host map; gather datastore info; read VM inventory.
3. **Throttle**: Split VMs into **batches** of size `vmotion_parallel`; process batches sequentially.
4. **Prechecks per VM**: 
   - VM exists?
   - Destination cluster has hosts?
   - Destination datastore resolvable?
   - Required DVPGs exist?
   - If any precheck fails → **skip VM**.
5. **Move**: Launch **asynchronous** vMotion (compute + storage) per eligible VM; wait for batch completion.
6. **Report**: Summarize **moved**, **skipped (precheck)**, and **not found**.

---

## Run Examples

### Basic run (defaults to 5 concurrent moves)
```bash
ansible-playbook ansible/playbooks/operations/vmotion_migrations.yml \
  -e vmotion_config_file=ansible/vars/vmotion.yml
```

### Increase parallelism to 10
```bash
ansible-playbook ansible/playbooks/operations/vmotion_migrations.yml \
  -e vmotion_config_file=ansible/group_vars/vmotion.yml \
  -e vmotion_parallel=10
```

### Extend timeout for very large VMs (3 hours)
```bash
ansible-playbook ansible/playbooks/operations/vmotion_migrations.yml \
  -e vmotion_config_file=ansible/group_vars/vmotion.yml \
  -e vmotion_timeout=10800
```

### Combine with Ansible Vault password prompt
```bash
ansible-playbook ansible/playbooks/operations/vmotion_migrations.yml \
  -e vmotion_config_file=ansible/group_vars/vmotion.yml --ask-vault-pass
```

> **Note:** VMware modules may not fully support `--check`, so treat dry runs with caution.

---

## Output & Summary

At the end of the run you’ll see a summary list of:
- **Moved successfully** — VMs for which vMotion/Storage vMotion finished.
- **Skipped (DVPG/datastore/host precheck)** — VMs not processed due to precheck issues.
- **Skipped (VM not found)** — Names not found in inventory.

Use this to identify prep work required on destination clusters (create DVPGs, ensure datastore visibility, etc.).

---

## Tips & Safeguards

- Ensure **DRS** is enabled if you plan to let vCenter balance placements post-move.
- Consider performing large moves **off-hours** and with **lower parallelism** to reduce contention.
- Verify there are **no snapshots** or **ISO mounts** blocking migration for critical VMs.
- If you prefer DRS placement instead of selecting a specific host, the play can be adapted to target a **resource pool** instead of a fixed host.
- If you need **per-VM host pinning** or **round-robin** host selection within a cluster, we can extend the play easily.

---

## Makefile (optional convenience)

```makefile
.PHONY: vmotion
vmotion:
\tansible-playbook ansible/playbooks/operations/vmotion_migrations.yml \\\
\t  -e vmotion_config_file=ansible/group_vars/vmotion.yml \\\
\t  -e vmotion_parallel=$${PARALLEL:-5} \\\
\t  -e vmotion_timeout=$${TIMEOUT:-7200}
```

Run with:
```bash
make vmotion PARALLEL=10 TIMEOUT=10800
```

---

## Troubleshooting

- **Missing DVPGs**: Create the portgroups on the destination (matching names) or narrow `networks_to_check` to what actually matters.
- **No destination host**: Ensure the destination cluster has at least one connected host and the user has rights to it.
- **Datastore not resolvable**: Provide `dest_datastore` explicitly or create a datastore with the same name on the destination side.
- **Permission errors**: Confirm the vCenter user has migrate/relocate privileges for source/destination clusters and datastores.

---

## Security

- Store secrets with **Ansible Vault**; don’t commit passwords to git.
- Use a **least‑privilege** service account scoped to the necessary datacenter/clusters.
- Mask sensitive variables in CI logs.
