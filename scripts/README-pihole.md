# Pi-hole DNS Import/Export (GitOps-Friendly)

This repo contains two complementary Python 3 scripts to **extract** and **apply** local DNS records on **Pi-hole v6+** using its REST API. Together they enable a simple GitOps loop:

1) **Export** from one or more Pi-hole servers → commits YAML to Git  
2) **Edit/Review** YAML in Git  
3) **Import** YAML back to Pi-hole servers (idempotent apply)

---

## Scripts

### 1) `extract_pihole_dns.py` — Export DNS to YAML
Extracts **A/AAAA** and **CNAME** records from one or more Pi-hole instances and writes a clean, stable, version-control–friendly **YAML** file.

**Key points**
- Authenticates using the Pi-hole **web password** (per‑server).
- Reads A/AAAA from `/config/dns/hosts` and CNAMEs from `/config/dns/cnames`.
- Merges results from multiple servers and **deduplicates** (last-write-wins).
- Produces a single YAML with two top‑level maps: `a_aaaa` and `cname`, plus `metadata`.

**CLI**
```bash
# Basic: single server by host (the tool appends /admin/api automatically)
python3 extract_pihole_dns.py   --servers ns1.home.virtualelephant.com:YOUR_WEB_PASSWORD   --output dns_records.yaml

# Multiple servers (comma-separated). You can also pass full http(s) URLs.
python3 extract_pihole_dns.py   --servers ns1.home.virtualelephant.com:secret1,ns2.home.virtualelephant.com:secret2   --output dns_records.yaml   -v

# Environment variable alternative for servers (same format):
#   export PIHOLE_SERVERS="ns1:secret1,ns2:secret2"
#   python3 extract_pihole_dns.py --output dns_records.yaml
```

**Arguments**
- `--servers` (or `PIHOLE_SERVERS` env var): Comma‑separated list of `host:password` or full `http(s)://host[:port]/admin/api:password`.  
  If only a host is given, the script uses `http://<host>/admin/api` by default.
- `--output / -o`: Path to write the YAML (default: `dns_records.yaml`).
- `--verbose / -v`: Enable debug logs.

---

### 2) `import_pihole_dns.py` — Apply YAML to Pi-hole
Reads the exported YAML and **creates/updates/deletes** A/AAAA and CNAME entries to match the file. Safe to run repeatedly (idempotent).

**Key points**
- Full CRUD reconciliation against each target server.
- **Dry-run** mode shows planned changes without applying.
- Optional **conflict policy** for how to handle differences vs. server state.

**CLI**
```bash
# Dry-run first (recommended)
python3 import_pihole_dns.py   --input dns_records.yaml   --servers ns1.home.virtualelephant.com:YOUR_WEB_PASSWORD   --dry-run   -v

# Then apply for real to one or more servers
python3 import_pihole_dns.py   --input dns_records.yaml   --servers ns1.home.virtualelephant.com:secret1,ns2.home.virtualelephant.com:secret2
```

**Arguments**
- `--input / -i` (required): Path to the YAML produced by the exporter.
- `--servers` (required): Same format as exporter (`host:password` or `url:password`, comma-separated).
- `--dry-run`: Print planned adds/updates/deletes without changing the server.
- `--conflict-policy`: How to handle differences when a record exists on the server with a different value than in the file. Choices:  
  - `file` (default): Prefer values from the YAML file (apply updates).  
  - `local`: Prefer existing server values (skip updates for conflicting entries).  
  - `fail`: Stop with an error when conflicts are detected.
- `--verbose / -v`: Enable debug logs.

> **Tip:** As with export, the tool assumes `/admin/api` if you provide only a hostname for each server.

---

## YAML Schema & Example

The exporter writes (and the importer expects) a YAML document with **three** top-level keys:

- `a_aaaa`: a map of **hostname → IP** (IPv4 or IPv6).  
- `cname`: a map of **domain → target**.  
- `metadata`: auxiliary information about the export (not used for apply).

**Example (`dns_records.yaml`):**
```yaml
metadata:
  generated_by: extract_pihole_dns.py
  source: Pi-hole v6+ REST API
  count_a_aaaa: 3
  count_cname: 2

a_aaaa:
  nas.home.virtualelephant.com: 10.1.10.50
  grafana.home.virtualelephant.com: 10.10.50.20
  ipv6-only.example.home: "2001:db8::1234"

cname:
  prometheus.home.virtualelephant.com: grafana.home.virtualelephant.com
  www.home.virtualelephant.com: nas.home.virtualelephant.com
```

> Notes
> - `a_aaaa` values can be **IPv4** or **IPv6**; the script doesn’t distinguish at the schema level.  
> - Keys must be unique within each map; last‑write wins during export when multiple servers define the same name.

---

## Requirements

- **Pi-hole v6+** (uses the REST endpoints under `/admin/api`).  
- **Python 3.10+** (recommended).
- Python packages: `requests`, `PyYAML` (and `urllib3` which ships with `requests`).  
```bash
  pip install requests pyyaml
```

---

## Security

- The scripts authenticate with the **Pi-hole web password**. Passing secrets on the command line will put them in your shell history. Consider environment variable management, CI/CD secret stores, or wrapper scripts if needed.
- Connections can be made to `http://` or `https://` endpoints; use TLS whenever possible.

---

## Troubleshooting

- **401/403 errors**: verify the correct **web password** and that you are talking to a **v6+** Pi-hole endpoint at `/admin/api`.
- **Network timeouts**: ensure the container/host running the script can reach the Pi-hole server(s). Use `-v` for detailed logs.
- **Conflict policy behavior**: start with `--dry-run` to see what would change before applying for real.

---

## License / Author

- License: Apache 2.0 
- Author: Chris Mutchler <chris@virtualelephant.com>
