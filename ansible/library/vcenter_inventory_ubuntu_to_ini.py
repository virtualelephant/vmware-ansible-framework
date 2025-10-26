#!/usr/bin/env python3
"""
vc_inventory_ubuntu.py

Connects to a vCenter Server and generates an Ansible-style inventory for Ubuntu VMs.
It can print to stdout (default / dry-run) or write to a file only if content changes.

Example output:
  [ubuntu_hosts:children]
  ubuntu_cluster_Lab-Cluster
  ubuntu_cluster_Prod-Cluster

  [ubuntu_cluster_Lab-Cluster]
  web01.home.virtualelephant.com ansible_host=10.1.10.101
  gitlab.home.virtualelephant.com ansible_host=10.1.10.102

  [ubuntu_cluster_Prod-Cluster]
  api01.home.virtualelephant.com ansible_host=10.1.20.11

Usage:
  python3 vc_inventory_ubuntu.py \
    --vcenter vcenter.home.virtualelephant.com \
    --username 'administrator@vsphere.local' \
    --password '***' \
    --outfile inventories/inventory_ubuntu.ini

Notes:
- Host alias defaults to the VM's DNS name if available, else the VM name.
- "ansible_host" prefers an IPv4 from guest info; fallback to DNS name or VM name.
- Filter for Ubuntu via guestFullName/config strings containing "ubuntu" (case-insensitive).
"""

import argparse
import ssl
import sys
import socket
from typing import Dict, List, Tuple, Optional

try:
    from pyVim.connect import SmartConnect, Disconnect  # type: ignore
    from pyVmomi import vim  # type: ignore
except Exception as e:
    print("FATAL: pyVmomi is required. pip install pyvmomi")
    raise

def get_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build Ansible inventory for Ubuntu VMs from vCenter")
    p.add_argument("--vcenter", required=True, help="vCenter Server FQDN or IP")
    p.add_argument("--username", required=True, help="vCenter username")
    p.add_argument("--password", required=True, help="vCenter password")
    p.add_argument("--port", type=int, default=443, help="vCenter port (default: 443)")
    p.add_argument("--insecure", action="store_true", help="Ignore SSL verification")
    p.add_argument("--outfile", help="Path to write inventory (idempotent). If omitted, prints to stdout")
    p.add_argument("--dry-run", action="store_true", help="Do not write; just print generated inventory")
    p.add_argument("--prefer-fqdn", action="store_true",
                   help="Prefer using DNS name as host alias (default), otherwise use VM name")
    p.add_argument("--prefer-ip", action="store_true",
                   help="Prefer IP for ansible_host (default behavior). If disabled, prefer FQDN")
    return p.parse_args()

def connect_vsphere(host: str, user: str, pwd: str, port: int, insecure: bool):
    ctx = None
    if insecure:
        ctx = ssl._create_unverified_context()
    si = SmartConnect(host=host, user=user, pwd=pwd, port=port, sslContext=ctx)
    return si

def get_all_vms(content) -> List[vim.VirtualMachine]:
    view = content.viewManager.CreateContainerView(
        content.rootFolder, [vim.VirtualMachine], True
    )
    vms = list(view.view)
    view.Destroy()
    return vms

def is_ubuntu_vm(vm: vim.VirtualMachine) -> bool:
    try:
        # Prefer guest.guestFullName (runtime) then config.guestFullName (static)
        names = []
        if vm.guest and vm.guest.guestFullName:
            names.append(vm.guest.guestFullName)
        if vm.config and vm.config.guestFullName:
            names.append(vm.config.guestFullName)
        combined = " ".join(n for n in names if n) or ""
        return "ubuntu" in combined.lower()
    except Exception:
        return False

def get_cluster_name(vm: vim.VirtualMachine) -> str:
    try:
        parent = vm.resourcePool.owner if vm.resourcePool else None
        while parent:
            if isinstance(parent, vim.ClusterComputeResource):
                return parent.name
            parent = getattr(parent, "parent", None)
    except Exception:
        pass
    return "Unknown-Cluster"

def first_ipv4_addrs(vm: vim.VirtualMachine) -> List[str]:
    addrs = []
    try:
        if vm.guest and vm.guest.net:
            for n in vm.guest.net:
                for ip in n.ipAddress or []:
                    # keep only IPv4
                    try:
                        socket.inet_pton(socket.AF_INET, ip)
                        addrs.append(ip)
                    except OSError:
                        continue
    except Exception:
        pass
    return addrs

def best_alias(vm: vim.VirtualMachine, prefer_fqdn: bool) -> str:
    """
    Host alias used on the left side of the inventory line.
    """
    try:
        dns = (vm.guest.hostName or "").strip() if vm.guest else ""
        if prefer_fqdn and dns:
            return dns
    except Exception:
        pass
    # fallback to VM name
    return vm.name

def best_ansible_host(vm: vim.VirtualMachine, prefer_ip: bool) -> str:
    """
    ansible_host value; try IP first (default), else FQDN/name.
    """
    if prefer_ip:
        ips = first_ipv4_addrs(vm)
        if ips:
            return ips[0]
    # fallback path
    try:
        dns = (vm.guest.hostName or "").strip() if vm.guest else ""
        if dns:
            return dns
    except Exception:
        pass
    return vm.name

def build_inventory_map(vms: List[vim.VirtualMachine],
                        prefer_fqdn: bool,
                        prefer_ip: bool) -> Dict[str, List[Tuple[str, str]]]:
    """
    Returns {cluster_name: [(alias, ansible_host), ...], ...}
    """
    clusters: Dict[str, List[Tuple[str, str]]] = {}
    for vm in vms:
        if not is_ubuntu_vm(vm):
            continue
        # Skip powered-off VMs without a DNS/IP if we can't contact them
        alias = best_alias(vm, prefer_fqdn)
        ansible_host = best_ansible_host(vm, prefer_ip)
        cluster = get_cluster_name(vm)
        clusters.setdefault(cluster, []).append((alias, ansible_host))
    # sort deterministically
    for c in clusters:
        clusters[c] = sorted(set(clusters[c]), key=lambda x: x[0].lower())
    return dict(sorted(clusters.items(), key=lambda kv: kv[0].lower()))

def render_ini(clusters: Dict[str, List[Tuple[str, str]]]) -> str:
    """
    Build INI inventory with:
    - [ubuntu_hosts:children]
    - [ubuntu_cluster_<Cluster>]
    Lines formatted as: "<alias> ansible_host=<address>"
    """
    lines: List[str] = []
    lines.append("[ubuntu_hosts:children]")
    for cluster in clusters.keys():
        group = f"ubuntu_cluster_{cluster.replace(' ', '_')}"
        lines.append(group)
    lines.append("")  # spacer

    for cluster, entries in clusters.items():
        group = f"[ubuntu_cluster_{cluster.replace(' ', '_')}]"
        lines.append(group)
        for alias, addr in entries:
            if alias == addr:
                lines.append(f"{alias}")
            else:
                lines.append(f"{alias} ansible_host={addr}")
        lines.append("")  # spacer

    return "\n".join(lines).rstrip() + "\n"

def write_if_changed(path: str, content: str) -> bool:
    try:
        with open(path, "r", encoding="utf-8") as f:
            existing = f.read()
        if existing == content:
            return False
    except FileNotFoundError:
        pass
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return True

def main():
    args = get_args()

    try:
        si = connect_vsphere(args.vcenter, args.username, args.password, args.port, args.insecure)
    except Exception as e:
        print(f"FATAL: Failed to connect to vCenter {args.vcenter}: {e}")
        sys.exit(2)

    try:
        content = si.RetrieveContent()
        all_vms = get_all_vms(content)
        ubuntu_map = build_inventory_map(all_vms, prefer_fqdn=args.prefer_fqdn, prefer_ip=args.prefer_ip)
        inventory = render_ini(ubuntu_map)
    finally:
        try:
            Disconnect(si)
        except Exception:
            pass

    if args.dry_run or not args.outfile:
        print(inventory)
        return

    updated = write_if_changed(args.outfile, inventory)
    if updated:
        print(f"Wrote updated inventory to: {args.outfile}")
    else:
        print(f"No changes. Inventory already up-to-date: {args.outfile}")

if __name__ == "__main__":
    main()
