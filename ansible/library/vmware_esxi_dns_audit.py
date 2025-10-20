#!/usr/bin/env python3
"""
Read current DNS config from ESXi hosts and compare to desired values in
ansible/group_vars/all/globals.yml.

Usage:
  export VCENTER_HOSTNAME=vcenter.home.virtualelephant.com
  export VCENTER_USERNAME=administrator@vsphere.local
  export VCENTER_PASSWORD='***'
  python3 tools/esxi_dns_audit.py [--inventory ansible/inventories/lab/inventory.ini]

If --inventory is provided, restricts to those hostnames. Otherwise audits all ESXi HostSystems.
"""

import argparse
import os
import sys
import ssl
import yaml
from collections import defaultdict

try:
    from pyVim.connect import SmartConnect, Disconnect
    from pyVmomi import vim
except Exception as e:
    print("Missing pyVmomi. Install with: pip install pyvmomi", file=sys.stderr)
    sys.exit(2)

def load_desired(globals_path="ansible/group_vars/all/globals.yml"):
    with open(globals_path, "r") as f:
        data = yaml.safe_load(f) or {}
    desired_servers = [str(x) for x in data.get("dns_nameservers", [])]
    desired_search = [str(x) for x in data.get("dns_search_domains", [])]
    return desired_servers, desired_search

def load_inventory_hosts(path):
    if not path:
        return None
    hosts = []
    with open(path, "r") as f:
        for line in f:
            line=line.strip()
            if not line or line.startswith("#") or line.startswith("["):
                continue
            hosts.append(line.split()[0])
    return set(hosts)

def connect_vcenter():
    vc = os.environ.get("VCENTER_HOSTNAME")
    vu = os.environ.get("VCENTER_USERNAME")
    vp = os.environ.get("VCENTER_PASSWORD")
    if not all([vc, vu, vp]):
        print("Set VCENTER_HOSTNAME, VCENTER_USERNAME, VCENTER_PASSWORD environment variables.", file=sys.stderr)
        sys.exit(2)
    context = ssl._create_unverified_context()
    si = SmartConnect(host=vc, user=vu, pwd=vp, sslContext=context)
    return si

def walk(container, vimtype):
    view = container.CreateContainerView(container, vimtype, True)
    try:
        for obj in view.view:
            yield obj
    finally:
        view.Destroy()

def get_host_dns(host_obj):
    # host_obj: vim.HostSystem
    try:
        dns_cfg = host_obj.config.network.dnsConfig
        servers = [str(s) for s in (dns_cfg.address or [])]
        search  = [str(s) for s in (dns_cfg.searchDomain or [])]
        return servers, search
    except Exception:
        return [], []

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", help="INI file to limit hosts (group [esxi])", default=None)
    parser.add_argument("--globals", help="Path to globals.yml", default="ansible/group_vars/all/globals.yml")
    args = parser.parse_args()

    desired_servers, desired_search = load_desired(args.globals)
    inv_hosts = load_inventory_hosts(args.inventory)

    si = connect_vcenter()
    try:
        content = si.RetrieveContent()
        container = content.rootFolder
        results = []

        for host in walk(container, [vim.HostSystem]):
            name = host.name
            if inv_hosts and name not in inv_hosts:
                continue
            cur_servers, cur_search = get_host_dns(host)

            match = (set(cur_servers) == set(desired_servers)) and (set(cur_search) == set(desired_search))
            results.append({
                "host": name,
                "current_servers": cur_servers,
                "current_search": cur_search,
                "desired_servers": desired_servers,
                "desired_search": desired_search,
                "status": "MATCH" if match else "DIFF",
            })

        # Pretty print table
        if not results:
            print("No hosts found.")
            return

        # Column widths
        w_host = max(len(r["host"]) for r in results) + 2
        print(f"{'HOST'.ljust(w_host)} | STATUS | CURRENT DNS                    | CURRENT SEARCH                 | DESIRED DNS                    | DESIRED SEARCH")
        print("-" * (w_host + 108))
        for r in sorted(results, key=lambda x: x["host"]):
            print(
                f"{r['host'].ljust(w_host)} | {r['status']:^6} | "
                f"{','.join(r['current_servers']):<28} | {','.join(r['current_search']):<28} | "
                f"{','.join(r['desired_servers']):<28} | {','.join(r['desired_search'])}"
            )
    finally:
        Disconnect(si)

if __name__ == "__main__":
    main()
