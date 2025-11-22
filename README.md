# 🇮🇷 Iran Network Health Checker

An advanced, modern tool to check the real state of internet connectivity in Iran  
Automatically detects filtering, VPN interference, MCI restrictions, and more.

### Features

- Ping tests to Google DNS, Cloudflare, and Iranian servers
- HTTP connectivity checks for YouTube, Instagram, DigiKala, Snapp, MCI Academy, etc.
- Smart diagnosis:
  - Is MCI Academy blocked?
  - Is a VPN/active foreign IP causing the block?
  - Severe nationwide restrictions?
- Beautiful colored & tabular output using **Rich**
- Monitoring mode (`--watch`)
- Fully written following **SOLID principles** (clean, maintainable, extensible)

### Installation & Usage

```bash
pip install requests rich
python iran_network_check.py


### Continuous Monitoring

python iran_network_check.py --watch --interval 60

# Checks every 60 seconds and refreshes the screen


```
