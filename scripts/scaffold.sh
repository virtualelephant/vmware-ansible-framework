#!/usr/bin/env bash
set -euo pipefail

# scaffold.sh — Create a GitLab-ready Ansible repo structure for VMware VCF
# Usage: ./scaffold.sh [target_dir]
# Example: ./scaffold.sh vmware-ansible-vcf

TARGET_DIR="${1:-vmware-ansible-vcf}"

# -------- helpers --------
mkd() { mkdir -p "$1"; }
create_file() {
  local path="$1"; shift
  if [[ ! -f "$path" ]]; then
    mkd "$(dirname "$path")"
    printf "%s\n" "${*:-}" > "$path"
  fi
}
touch_if_absent() { [[ -f "$1" ]] || ( mkd "$(dirname "$1")"; touch "$1" ); }

# -------- begin --------
echo "Scaffolding repo in: $TARGET_DIR"
mkd "$TARGET_DIR"
cd "$TARGET_DIR"

# --- Top-level project hygiene & GitLab bits ---
mkd ".gitlab/ci/templates" ".gitlab/issue_templates" ".gitlab/merge_request_templates"
mkd "docs/architecture" "docs/runbooks"

create_file ".gitignore" \
"# Ansible & Python" \
"*.retry" \
"__pycache__/" \
".venv/" \
".pytest_cache/" \
".molecule/" \
"*.pyc" \
"*.pyo" \
"*.egg-info/" \
"venv/" \
"env/" \
"# IDEs" \
".idea/" \
".vscode/" \
"# OS" \
".DS_Store"

create_file ".editorconfig" \
"root = true" \
"" \
"[*]" \
"charset = utf-8" \
"end_of_line = lf" \
"insert_final_newline = true" \
"indent_style = space" \
"indent_size = 2" \
"trim_trailing_whitespace = true"

create_file ".pre-commit-config.yaml" \
"repos:" \
"- repo: https://github.com/pre-commit/pre-commit-hooks" \
"  rev: v4.6.0" \
"  hooks:" \
"    - id: end-of-file-fixer" \
"    - id: trailing-whitespace" \
"- repo: https://github.com/adrienverge/yamllint" \
"  rev: v1.35.1" \
"  hooks:" \
"    - id: yamllint" \
"- repo: https://github.com/ansible-community/ansible-lint" \
"  rev: v24.7.0" \
"  hooks:" \
"    - id: ansible-lint"

create_file "README.md" \
"# VMware VCF Ansible Playbooks" \
"" \
"Framework to manage VMware Cloud Foundation (VCF) at scale: drift remediation (vCenter, ESXi, NSX-T), VM lifecycle, and guest OS config. " \
"Designed for GitLab CI/CD with environments (lab/stage/prod)." \
"" \
"## Quick start" \
"1. Create a Python venv and install requirements (if used)." \
"2. Populate \`ansible/inventories/*\` and \`group_vars/host_vars\`." \
"3. Run \`ansible-playbook ansible/playbooks/bootstrap/ping.yml -i ansible/inventories/lab/inventory.ini\`."

create_file "CONTRIBUTING.md" \
"# Contributing" \
"- Use feature branches + MR with CI green checks." \
"- Keep roles atomic; prefer idempotence and check-mode support." \
"- Add docs to \`docs/runbooks\` for operational procedures."

create_file "SECURITY.md" \
"# Security Policy" \
"- Secrets live in external vaults or GitLab CI variables—never in repo." \
"- Use Ansible Vault only for non-critical bootstrap where required." \
"- Report issues via Merge Requests or designated security contact."

create_file "CODEOWNERS" \
"# Example owners; adjust to your usernames/groups" \
"* @virtualelephant" \
"/ansible/roles/* @virtualelephant"

create_file "LICENSE" "Apache License 2.0 — replace with your preferred license."

# Lightweight CI to start (extend later)
create_file ".gitlab-ci.yml" \
"stages: [lint, test]" \
"" \
"variables:" \
"  ANSIBLE_STDOUT_CALLBACK: yaml" \
"" \
"lint:yamllint:" \
"  stage: lint" \
"  image: cytopia/yamllint:latest" \
"  script: [\"yamllint -c ci/yamllint.yml .\"]" \
"" \
"lint:ansible-lint:" \
"  stage: lint" \
"  image: pipelinecomponents/ansible-lint:latest" \
"  script: [\"ansible-lint -c ci/ansible-lint.yml ansible/\"]" \
"" \
"test:syntax-check:" \
"  stage: test" \
"  image: python:3.12-slim" \
"  before_script:" \
"    - pip install ansible-core" \
"  script:" \
"    - ansible-playbook ansible/playbooks/bootstrap/ping.yml -i ansible/inventories/lab/inventory.ini --syntax-check"

# CI config snippets
mkd "ci"
create_file "ci/yamllint.yml" \
"extends: default" \
"rules:" \
"  line-length: disable"
create_file "ci/ansible-lint.yml" \
"skip_list: [\"role-name\"]"

# --- Ansible workspace ---
mkd "ansible/playbooks/bootstrap" \
    "ansible/playbooks/operations" \
    "ansible/playbooks/compliance" \
    "ansible/playbooks/vm_lifecycle" \
    "ansible/roles" \
    "ansible/group_vars" \
    "ansible/host_vars" \
    "ansible/filter_plugins" \
    "ansible/collections" \
    "ansible/inventories/lab/group_vars" \
    "ansible/inventories/lab/host_vars" \
    "ansible/inventories/stage/group_vars" \
    "ansible/inventories/stage/host_vars" \
    "ansible/inventories/prod/group_vars" \
    "ansible/inventories/prod/host_vars"

create_file "ansible/ansible.cfg" \
"[defaults]" \
"inventory = inventories/lab/inventory.ini" \
"roles_path = roles" \
"host_key_checking = False" \
"stdout_callback = yaml" \
"timeout = 30" \
"interpreter_python = auto" \
"retry_files_enabled = False" \
"" \
"[ssh_connection]" \
"pipelining = True" \
"ssh_args = -o ControlMaster=auto -o ControlPersist=60s"

create_file "ansible/collections/requirements.yml" \
"---" \
"collections:" \
"  - name: community.vmware" \
"  - name: vmware.vmware_rest" \
"  - name: community.general"

# Global vars stub
create_file "ansible/group_vars/all.yml" \
"---" \
"vcf_region: dc1" \
"change_window_approved: false"

# Inventories (ini placeholders)
create_file "ansible/inventories/lab/inventory.ini" \
"[sddc_manager]" \
"sddc-mgr-01 ansible_host=10.0.0.10" \
"" \
"[vcenter]" \
"vc-01 ansible_host=10.0.0.11" \
"" \
"[nsxt_managers]" \
"nsxt-mgr-01 ansible_host=10.0.0.12" \
"" \
"[esxi_hosts]" \
"esxi-01 ansible_host=10.0.0.21" \
"esxi-02 ansible_host=10.0.0.22"

create_file "ansible/inventories/stage/inventory.ini" "# Fill in stage hosts"
create_file "ansible/inventories/prod/inventory.ini"  "# Fill in prod hosts"

# Bootstrap & example playbooks
create_file "ansible/playbooks/bootstrap/ping.yml" \
"---" \
"- name: Connectivity sanity" \
"  hosts: all" \
"  gather_facts: false" \
"  tasks:" \
"    - name: Ping" \
"      ansible.builtin.ping:"

create_file "ansible/playbooks/operations/check_drift.yml" \
"---" \
"- name: VCF drift check (vCenter, ESXi, NSX-T)" \
"  hosts: vcenter:nsxt_managers:esxi_hosts" \
"  gather_facts: false" \
"  roles:" \
"    - role: vcenter_drift" \
"    - role: esxi_drift" \
"    - role: nsxt_drift"

create_file "ansible/playbooks/vm_lifecycle/provision_vm.yml" \
"---" \
"- name: Provision VM on vSphere" \
"  hosts: vcenter" \
"  gather_facts: false" \
"  roles:" \
"    - role: vsphere_vm"

create_file "ansible/playbooks/compliance/hardening_linux.yml" \
"---" \
"- name: Linux baseline hardening" \
"  hosts: linux_vms" \
"  become: true" \
"  roles:" \
"    - role: linux_hardening"

# Role skeleton function
make_role() {
  local role="ansible/roles/$1"
  mkd "$role/tasks" "$role/defaults" "$role/vars" "$role/handlers" "$role/templates" "$role/files" "$role/meta"
  create_file "$role/tasks/main.yml"       "---"
  create_file "$role/defaults/main.yml"    "---"
  create_file "$role/vars/main.yml"        "---"
  create_file "$role/handlers/main.yml"    "---"
  touch_if_absent "$role/templates/.gitkeep"
  touch_if_absent "$role/files/.gitkeep"
  create_file "$role/meta/main.yml"        "---\ndependencies: []"
}

# Core roles for VCF mgmt
for r in vcf_sddc_manager vcenter_drift esxi_drift nsxt_drift vsphere_vm linux_hardening; do
  make_role "$r"
done

# Seed the vcf_sddc_manager role with minimal task placeholders
create_file "ansible/roles/vcf_sddc_manager/tasks/main.yml" \
"---" \
"- name: Placeholder — query SDDC Manager facts" \
"  ansible.builtin.debug:" \
"    msg: \"SDDC Manager tasks go here (API auth, inventory, drift, etc.)\""

# Filter plugins placeholder
touch_if_absent "ansible/filter_plugins/.gitkeep"

# Scripts & Makefile
mkd "scripts"
create_file "scripts/run.sh" \
'#!/usr/bin/env bash' \
'set -euo pipefail' \
'inv=${1:-ansible/inventories/lab/inventory.ini}' \
'ansible-playbook ansible/playbooks/bootstrap/ping.yml -i "$inv"'
chmod +x "scripts/run.sh"

create_file "Makefile" \
".PHONY: deps lint ping" \
"deps:" \
"\tansible-galaxy collection install -r ansible/collections/requirements.yml" \
"lint:" \
"\tansible-lint -c ci/ansible-lint.yml ansible/ || true" \
"ping:" \
"\tansible-playbook ansible/playbooks/bootstrap/ping.yml -i ansible/inventories/lab/inventory.ini"


# Templates for issues/MRs
create_file ".gitlab/issue_templates/Bug.md" \
"### Summary\n\n### Steps to reproduce\n\n### Expected\n\n### Actual\n\n### Logs"
create_file ".gitlab/merge_request_templates/Default.md" \
"### What\n\n### Why\n\n### Testing\n\n### Checklist\n- [ ] CI green\n- [ ] Docs updated"

echo "Done. Next:"
echo "  cd $TARGET_DIR"
echo "  git init && git add . && git commit -m \"chore: initial scaffolding\""
echo "  # Optional: pre-commit install (if you use it)"
echo "  # pip install pre-commit && pre-commit install"
