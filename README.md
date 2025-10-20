# VMware Cloud Foundation (VCF) Ansible Framework

This repository provides a **modular Ansible framework** for managing and automating **VMware Cloud Foundation (VCF)** environments.

It includes automation for:

- Detecting and remediating **configuration drift** across infrastructure components  
  *(vCenter, ESXi hosts, NSX-T Managers, etc.)*
- **Provisioning and configuring virtual machines (VMs)** within the VCF-managed environment
- Applying **OS-level configuration, compliance, and hardening policies**
- Integrating with **GitLab CI/CD pipelines** for linting, validation, and automated deployment

The structure follows **GitLab best practices** for CI/CD automation, code ownership, and Ansible project organization.

---

## 🧭 Repository Structure

```bash
vmware-ansible-vcf/
├── .gitlab/                          # GitLab templates for CI/CD, issues, and MRs
│   ├── ci/templates/
│   ├── issue_templates/
│   └── merge_request_templates/
├── ansible/
│   ├── ansible.cfg                   # Project-wide Ansible configuration
│   ├── collections/                  # Required Ansible collections (community.vmware, etc.)
│   │   └── requirements.yml
│   ├── group_vars/                   # Global variable definitions
│   │   └── all/
│   │   │   ├── global.yml
│   ├── vms_clone.yml
│   ├── vms_create.yml
│   ├── vms_delete.yml
│   ├── host_vars/                    # Host-specific variable files
│   ├── inventories/                  # Environment-specific inventories
│   │   ├── inventory.ini
│   ├── library
│   │   ├── vmware_esxi_ntp_info.py   # Python module for NTP on ESXi
│   │   ├── vmware_esxi_dns_audit.py  # Python module for DNS on ESXi
│   ├── playbooks/
│   │   ├── 20_linux_os_audit.yml     # Audit & remediate config drift on Linux OS hosts/vms
│   │   ├── 21_linux_os_upgrades.yml  # Perform host upgrades on Linux OS hosts/vms  
│   │   ├── 30_esxi_audit_ntp.yml      # Audit & remediate ESXi NTP settings
│   │   ├── 31_esxi_audit_dns.yml     # Audit & remediate ESXi DNS settings
│   │   ├── 80_clone_vm.yml           # Clone VM template in VCF environment 
│   │   ├── 81_delete_vm.yml          # Delete VMs in VCF environment
│   │   ├── 82_provision_vm.yml       # Provision new VMs in VCF environment
│   │   ├── 83_vmotion_migrations.yml # Mass migration of VMs using vMotion  
│   └── roles/                        # Modular roles for each function
│       ├── vcf_sddc_manager/
│       ├── vcenter_drift/
│       ├── esxi_drift/
│       ├── nsxt_drift/
│       ├── vsphere_vm/
│       └── linux_hardening/
├── ci/                               # CI/CD configuration for linting and validation
│   ├── ansible-lint.yml
│   └── yamllint.yml
├── docs/                             # README files, Architecture diagrams, runbooks, design notes
├── scripts/                          # Helper scripts for local execution
│   └── run.sh
├── .editorconfig                     # Consistent indentation and line endings
├── .gitignore                        # Ignore cache, venvs, and system artifacts
├── .gitlab-ci.yml                    # Base CI/CD pipeline definition
├── .pre-commit-config.yaml           # Local linting and validation hooks
├── CODEOWNERS                        # Default owners for merge approvals
├── CONTRIBUTING.md                   # Contribution guidelines
├── LICENSE                           # License information
├── Makefile                          # Local automation commands
└── README.md                         # You are here
```

---

## ⚙️ Getting Started

### 1. Install Dependencies

```bash
pip install ansible-core pre-commit
ansible-galaxy collection install -r ansible/collections/requirements.yml
pre-commit install
```

### 2. Run a Simple Connectivity Test

```bash
ansible-playbook ansible/playbooks/bootstrap/ping.yml   -i ansible/inventories/lab/inventory.ini
```

### 3. Lint and Validate

```bash
make lint
```

---

## 🧩 Design Principles

- **Modular Roles:** Each VMware component (vCenter, NSX-T, ESXi, etc.) is encapsulated in its own role.  
- **Environment-Aware:** Supports `lab`, `stage`, and `prod` inventory separation.  
- **Idempotent Execution:** Every playbook is safe to rerun; no destructive operations without intent.  
- **CI/CD Ready:** GitLab pipeline automates linting, syntax validation, and test runs.  
- **Extensible:** Designed for future automation such as SDDC Manager API integration and VM build pipelines.

---

## 📘 Next Steps

- Begin defining VMware credentials (via Vault, CI variables, or encrypted files).
- Add GitLab runners to automate linting and testing.

---

**Maintainer:** [Virtual Elephant Consulting, LLC](https://virtualelephant.com)  
**Author:** Chris Mutchler  
**License:** Apache 2.0
