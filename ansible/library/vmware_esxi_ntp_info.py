#!/usr/bin/python
# -*- coding: utf-8 -*-
# Custom Ansible module to READ NTP service status and configured servers from an ESXi host via vSphere API

DOCUMENTATION = r"""
---
module: vmware_esxi_ntp_info
short_description: Read NTP service status and configured servers from ESXi via vSphere API
description:
  - Uses pyVmomi to connect to vCenter (or standalone ESXi) and retrieve NTP service state
    and configured NTP servers for a specific ESXi host.
version_added: "1.0.0"
author: "ChatGPT"
options:
  hostname:
    description: vCenter/ESXi hostname or IP to connect to
    required: true
    type: str
  username:
    description: Username for API auth
    required: true
    type: str
  password:
    description: Password for API auth
    required: true
    type: str
  esxi_hostname:
    description: Target ESXi host name as it appears in vCenter
    required: true
    type: str
  port:
    description: API port
    required: false
    type: int
    default: 443
  validate_certs:
    description: Validate SSL certs on connect
    required: false
    type: bool
    default: False
notes:
  - No changes are made; this module is read-only.
requirements:
  - pyvmomi
"""
EXAMPLES = r"""
- name: Read NTP info
  vmware_esxi_ntp_info:
    hostname: "vcenter.home.virtualelephant.com"
    username: "administrator@vsphere.local"
    password: "{{ vault_vcenter_password }}"
    esxi_hostname: "esxi-01.home.virtualelephant.com"
    validate_certs: false
  register: ntp_info
"""
RETURN = r"""
ansible_facts:
  description: NTP-related facts
  returned: always
  type: dict
  sample:
    ntp:
      service_key: ntpd
      running: true
      policy: on
      servers:
        - time.cloudflare.com
        - pool.ntp.org
esxi_hostname:
  description: ESXi host target
  returned: always
  type: str
changed:
  description: Always false (read-only)
  returned: always
  type: bool
"""

from ansible.module_utils.basic import AnsibleModule

import ssl
import traceback

try:
    from pyVim.connect import SmartConnect, Disconnect
    from pyVmomi import vim
except Exception:
    # Defer error to runtime check
    pass

def _get_host(si, esxi_name):
    content = si.RetrieveContent()
    container = content.viewManager.CreateContainerView(content.rootFolder, [vim.HostSystem], True)
    for host in container.view:
        if host.name == esxi_name:
            return host
    return None

def run_module():
    module_args = dict(
        hostname=dict(type='str', required=True),
        username=dict(type='str', required=True),
        password=dict(type='str', required=True, no_log=True),
        esxi_hostname=dict(type='str', required=True),
        port=dict(type='int', required=False, default=443),
        validate_certs=dict(type='bool', required=False, default=False),
    )

    result = {
        "changed": False,
        "ansible_facts": {},
        "esxi_hostname": None,
    }

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)

    # Dependencies check
    try:
        from pyVim.connect import SmartConnect  # noqa: F401
        from pyVmomi import vim  # noqa: F401
    except Exception:
        module.fail_json(msg="Missing Python dependency: pyvmomi")

    params = module.params
    host = params['hostname']
    user = params['username']
    pwd = params['password']
    port = params['port']
    validate = params['validate_certs']
    esxi_name = params['esxi_hostname']

    context = None
    if not validate:
        try:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        except Exception:
            context = None

    si = None
    try:
        si = SmartConnect(host=host, user=user, pwd=pwd, port=port, sslContext=context)
        target = _get_host(si, esxi_name)
        if target is None:
            module.fail_json(msg="ESXi host '{}' not found in inventory.".format(esxi_name))

        # Get NTP configured servers
        servers = []
        try:
            dts = target.configManager.dateTimeSystem
            if hasattr(dts, 'dateTimeInfo') and dts.dateTimeInfo:
                ntp_cfg = getattr(dts.dateTimeInfo, 'ntpConfig', None)
                if ntp_cfg and hasattr(ntp_cfg, 'server') and ntp_cfg.server:
                    servers = list(ntp_cfg.server)
        except Exception:
            servers = []

        # Get NTP service status
        running = None
        policy = None
        service_key = 'ntpd'
        try:
            svc_sys = target.configManager.serviceSystem
            svc_info = svc_sys.serviceInfo
            for svc in getattr(svc_info, 'service', []):
                if svc.key.lower() in ('ntpd', 'ntp'):
                    service_key = svc.key
                    running = bool(getattr(svc, 'running', None))
                    policy = getattr(svc, 'policy', None)
                    break
        except Exception:
            pass

        result["ansible_facts"]["ntp"] = {
            "service_key": service_key,
            "running": running,
            "policy": policy,
            "servers": servers,
        }
        result["esxi_hostname"] = esxi_name
        module.exit_json(**result)

    except Exception as e:
        module.fail_json(msg="Error while retrieving NTP info: {}".format(str(e)),
                         exception=traceback.format_exc())
    finally:
        try:
            if si:
                Disconnect(si)
        except Exception:
            pass

def main():
    run_module()

if __name__ == '__main__':
    main()
