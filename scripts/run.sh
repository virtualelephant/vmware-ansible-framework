#!/usr/bin/env bash set -euo pipefail inv=${1:-ansible/inventories/lab/inventory.ini} ansible-playbook ansible/playbooks/bootstrap/ping.yml -i "$inv"
