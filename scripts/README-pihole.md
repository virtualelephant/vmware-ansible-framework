# Pi-hole DNS Record Extractor

A **Python-based GitOps tool** to extract **A/AAAA** and **CNAME** local DNS records from one or more **Pi-hole v6+** instances using the official REST API and export them into a clean, version-controlled **YAML** file.

Perfect for:
- Backing up internal DNS configurations
- Synchronizing records across multiple Pi-hole servers
- Enabling **Infrastructure as Code (IaC)** with Ansible, Terraform, or GitOps
- Auditing and tracking changes over time

---

## Features

- Secure authentication via Pi-hole web password
- Full support for **A/AAAA** and **CNAME** records
- Merges records from **multiple Pi-hole servers**
- Deduplicates entries (last-write-wins on conflict)
- Outputs structured, Git-friendly YAML
- Built-in retry logic and detailed logging
- Configurable via CLI or environment variables
- MkDocs-compatible documentation header

---

## Prerequisites

- Python 3.8+
- Pi-hole **v6.0+** (required for REST API)
- Network access to Pi-hole admin interface (`/admin/api`)
- Pi-hole web password(s)

---

## Installation

1. Clone this repository (or copy the script):

```bash
git clone https://github.com/yourusername/pihole-dns-extractor.git
cd pihole-dns-extractor
pip install -r requirements.txt
```

requirements.txt
```bash
requests>=2.31.0
PyYAML>=6.0
urllib3>=2.0.0
python-dotenv>=1.0.0
```

Usage

Option 1: Environment Variables (Recommended)
```bash
bashexport PIHOLE_SERVERS="ns1.home.virtualelephant.com:yourpass1,ns2.home.virtualelephant.com:yourpass2"
python extract_pihole_dns.py --output dns_records.yaml --verbose
```

Option 2: CLI Arguments
```bash
python extract_pihole_dns.py \
  --servers "http://ns1.home.virtualelephant.com/admin/api:pass123,http://ns2.home.virtualelephant.com/admin/api:pass456" \
  --output inventory/dns_records.yaml \
  --verbose
```

Option 3: Short Hostnames (Auto-adds /admin/api)
```bash
python extract_pihole_dns.py \
  --servers "ns1.home.virtualelephant.com:pass1,ns2.home.virtualelephant.com:pass2" \
  --output dns_records.yaml
```

This automatically expands to http://<host>/admin/api

Example Output: dns_records.yaml
```yaml
yamla_aaaa:
  router.home.virtualelephant.com: 192.168.1.1
  nas.home.virtualelephant.com: 192.168.1.50
  printer.home.virtualelephant.com: 192.168.1.75
  server01.internal: 10.0.0.10
  server02.internal: 2001:db8::10
cname:
  www.home.virtualelephant.com: nas.home.virtualelephant.com
  plex.home.virtualelephant.com: nas.home.virtualelephant.com
  gitlab.internal: server01.internal
metadata:
  generated_by: extract_pihole_dns.py
  source: Pi-hole v6+ REST API
  count_a_aaaa: 5
  count_cname: 3
```

Commit this file to Git for version history and change tracking.

Security Best Practices

Never commit passwords to Git

Use environment variables or Ansible Vault

Store credentials in .env (and add to .gitignore):
env# .env
PIHOLE_SERVERS=ns1.home.virtualelephant.com:secret1,ns2.home.virtualelephant.com:secret2
Then load with python-dotenv or source before running:
bashsource .env && python extract_pihole_dns.py

GitOps Workflow Example
bash# 1. Extract current state
python extract_pihole_dns.py --output dns_records.yaml

# 2. Review changes
git diff dns_records.yaml

# 3. Commit
git add dns_records.yaml
git commit -m "chore(dns): update local records from Pi-hole"

# 4. Push
git push origin main
Later, use Ansible to apply changes back to Pi-hole from this YAML.

### Final Project Structure
pihole-dns-extractor/
├── extract_pihole_dns.py
├── requirements.txt
├── README.md
├── .gitignore
├── dns_records.yaml         # Generated output
└── .env                     # (optional, not tracked)
textAdd this to `.gitignore`:
```gitignore
.env
*.pyc
__pycache__
dns_records.yaml