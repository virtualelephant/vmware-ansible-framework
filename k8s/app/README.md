# Ansible Runner: Daily CronJob (3AM America/Denver)

This Kubernetes app runs your **ansible-runner** container once per day at **3:00 AM America/Denver**, executing one or more playbooks baked into the image/repo.

> Uses the Kubernetes `timeZone` field so you don’t have to convert to UTC or worry about DST.

## Files
- `01-namespace.yaml` — optional namespace (`automation`).
- `02-secrets.example.yaml` — example Secrets for **Harbor image pull**, **Ansible Vault password**, and **SSH key** used by Ansible.
- `03-serviceaccount.yaml` — service account + minimal RBAC (not strictly required, but included for clarity).
- `04-cronjob.yaml` — the CronJob definition.
- `kustomization.yaml` — to apply as a single Kustomize unit (works great with Argo CD).

## Quick start

1. **Edit secrets:**
   - Replace the base64 placeholders in `02-secrets.example.yaml` with your values.
   - Commonly updated keys:
     - `harbor-creds` (image pull secret)
     - `ansible-vault.vault_pass` (contents of your vault password file)
     - `ansible-ssh.id_rsa`, `ansible-ssh.known_hosts`

2. **Update the image:** in `04-cronjob.yaml` set the image to your built runner, e.g.  
   `harbor.home.virtualelephant.com/ve-lab/ansible-runner:1.0.0`  
   (or `ansible-linux-playbooks:TAG` if that’s your chosen image name).

3. **Pick which playbooks to run:** set the `PLAYBOOKS` env var in `04-cronjob.yaml` to a space‑separated list, e.g.  
   ```
   ansible/playbooks/linux/20_linux_os_audit.yml ansible/playbooks/linux/03_linux_os_upgrades.yml
   ```

4. **Dry‑run mode (optional):** set `DRY_RUN: "true"` to add `--check` when invoking `ansible-playbook`.

5. **Apply:**
   ```bash
   kubectl apply -k .
   ```

6. **Logs:**
   ```bash
   kubectl -n automation logs job/$(kubectl -n automation get jobs --sort-by=.metadata.creationTimestamp -o jsonpath='{.items[-1].metadata.name}')
   ```
   Your cluster’s Fluentd/Fluent Bit should forward logs to your ELK stack automatically.

## Scheduling details

- The CronJob uses:
  - `schedule: "0 3 * * *"`
  - `timeZone: "America/Denver"` (requires K8s ≥ 1.27; your cluster is 1.32+)
- `concurrencyPolicy: Forbid` ensures only one run at a time.
- `startingDeadlineSeconds: 600` allows a 10‑minute grace period if the controller misses the exact tick.
- Job history limits are set to retain the last 3 successes and 3 failures.

## Security notes

- SSH keys are mounted read‑only at `/root/.ssh` with `0400` permissions.
- Vault password file is mounted at `/secrets/.vault_pass.txt` and used automatically when `VAULT_PASSWORD` is set (Secret presence).

## Customization tips

- Add more environment variables to control your playbooks (e.g., inventory path overrides).
- If your repo is baked into the image, nothing else is required. If you want the repo to be updated on each run, add a `git pull` step to the entry script/command.
- To run multiple regional CronJobs, duplicate `04-cronjob.yaml`, set labels/affinity/nodeSelectors, and different schedules if needed.
