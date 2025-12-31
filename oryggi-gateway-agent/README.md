# OryggiAI Gateway Agent

A lightweight on-premises agent that securely connects your local SQL Server database to the OryggiAI SaaS platform through a WebSocket tunnel.

## Why Use the Gateway Agent?

If your SQL Server database is:
- Behind a firewall or NAT
- On a private network without public IP
- Unable to accept inbound connections on port 1433

The Gateway Agent solves this by making **outbound** connections to OryggiAI, bypassing firewall restrictions.

```
┌─────────────────────┐                    ┌─────────────────────┐
│   Your Network      │                    │   OryggiAI Cloud    │
│                     │                    │                     │
│  ┌───────────────┐  │   OUTBOUND WSS     │  ┌───────────────┐  │
│  │ Gateway Agent │──┼───────────────────>│  │   WebSocket   │  │
│  │               │<─┼────────────────────│  │   Endpoint    │  │
│  └───────┬───────┘  │                    │  └───────┬───────┘  │
│          │          │                    │          │          │
│          v          │                    │          v          │
│  ┌───────────────┐  │                    │  ┌───────────────┐  │
│  │  SQL Server   │  │                    │  │   AI Chatbot  │  │
│  └───────────────┘  │                    │  └───────────────┘  │
└─────────────────────┘                    └─────────────────────┘
```

## Quick Start - Docker (Recommended)

The easiest way to run the Gateway Agent is with Docker. No Python installation required!

### 1. Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (free)
- Gateway Token from OryggiAI dashboard

### 2. Get Your Gateway Token

1. Log in to OryggiAI dashboard
2. Go to **Gateway Agent** page
3. Select your database
4. Click **Generate Token**
5. Copy the token (starts with `gw_`)

### 3. Run with One Command

```bash
docker run -d --name oryggi-gateway \
  --restart unless-stopped \
  -e GATEWAY_TOKEN=gw_YOUR_TOKEN_HERE \
  -e DB_HOST=host.docker.internal \
  -e DB_PORT=1433 \
  -e DB_DATABASE=YourDatabaseName \
  -e DB_USERNAME=sa \
  -e DB_PASSWORD=YourPassword \
  oryggi/gateway-agent:latest
```

**Note:** Use `host.docker.internal` to connect to SQL Server on your local machine.

### 4. Verify It's Running

```bash
# Check logs
docker logs oryggi-gateway -f

# Check status
docker ps | grep oryggi-gateway
```

### Docker Management Commands

```bash
# Stop the agent
docker stop oryggi-gateway

# Start the agent
docker start oryggi-gateway

# Restart with new settings
docker rm oryggi-gateway
# Then run the docker run command again with new settings

# View logs
docker logs oryggi-gateway -f
```

---

## Alternative: Docker Compose

For easier configuration management, use docker-compose:

```yaml
# docker-compose.yml
version: '3.8'
services:
  oryggi-gateway:
    image: oryggi/gateway-agent:latest
    container_name: oryggi-gateway-agent
    restart: unless-stopped
    environment:
      - GATEWAY_TOKEN=gw_YOUR_TOKEN_HERE
      - DB_HOST=host.docker.internal
      - DB_DATABASE=YourDatabaseName
      - DB_USERNAME=sa
      - DB_PASSWORD=YourPassword
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

Then run:
```bash
docker-compose up -d
```

---

## Alternative: Python Installation

If you prefer not to use Docker:

### 1. Prerequisites

- Python 3.9 or higher
- SQL Server ODBC Driver 17/18
- Network access to OryggiAI server

### 2. Installation

```bash
# Clone or download the agent
cd oryggi-gateway-agent

# Create virtual environment (recommended)
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration

```bash
# Create config file from example
copy config.yaml.example config.yaml

# Edit config.yaml with your settings
notepad config.yaml
```

Update these key settings:
- `database.host` - Your SQL Server hostname
- `database.database` - Database name
- `database.username` / `database.password` - Credentials
- `gateway.gateway_token` - Token from OryggiAI dashboard

### 4. Run the Agent

```bash
# Test database connection first
python -m gateway_agent --test

# Start the agent
python -m gateway_agent

# Or with custom config
python -m gateway_agent -c /path/to/config.yaml
```

## Command Line Options

```
gateway-agent [options]

Options:
  -c, --config PATH    Path to config file (default: config.yaml)
  --init               Create example configuration file
  --test               Test database connection and exit
  -v, --verbose        Enable debug logging
  --version            Show version and exit
  -h, --help           Show help message
```

## Environment Variables

Override config file settings with environment variables:

| Variable | Description |
|----------|-------------|
| `GATEWAY_TOKEN` | Gateway authentication token |
| `DB_HOST` | SQL Server hostname |
| `DB_PORT` | SQL Server port |
| `DB_DATABASE` | Database name |
| `DB_USERNAME` | Database username |
| `DB_PASSWORD` | Database password |
| `DB_USE_WINDOWS_AUTH` | Use Windows auth (true/false) |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) |

## Running as a Windows Service

### Using NSSM (Recommended)

1. Download [NSSM](https://nssm.cc/download)
2. Install the service:

```powershell
nssm install OryggiGatewayAgent "C:\path\to\venv\Scripts\python.exe" "-m gateway_agent -c C:\path\to\config.yaml"
nssm set OryggiGatewayAgent AppDirectory "C:\path\to\oryggi-gateway-agent"
nssm set OryggiGatewayAgent Description "OryggiAI Gateway Agent - Database Connection Service"
nssm start OryggiGatewayAgent
```

### Managing the Service

```powershell
# Check status
nssm status OryggiGatewayAgent

# Stop service
nssm stop OryggiGatewayAgent

# Restart service
nssm restart OryggiGatewayAgent

# Remove service
nssm remove OryggiGatewayAgent confirm
```

## Troubleshooting

### Connection Issues

**"Connection timed out"**
- Verify network access to `api.oryggi.ai:443`
- Check if a proxy is required
- Try: `curl https://api.oryggi.ai/health`

**"Authentication failed"**
- Verify your gateway token is correct
- Token should start with `gw_`
- Generate a new token if expired

**"Database connection failed"**
- Test with: `gateway-agent --test`
- Verify SQL Server is running
- Check firewall allows localhost:1433
- Verify ODBC driver is installed

### ODBC Driver Installation

**Windows:**
Download from [Microsoft](https://docs.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server)

**Linux (Ubuntu/Debian):**
```bash
curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add -
curl https://packages.microsoft.com/config/ubuntu/20.04/prod.list > /etc/apt/sources.list.d/mssql-release.list
apt-get update
ACCEPT_EULA=Y apt-get install -y msodbcsql17
```

### Logs

Check `gateway_agent.log` for detailed information:
```bash
tail -f gateway_agent.log
```

Enable debug logging:
```bash
gateway-agent -v
# or set LOG_LEVEL=DEBUG
```

## Security

- All traffic is encrypted (WSS/TLS)
- Gateway tokens are scoped to specific databases
- Queries are read-only by default
- All queries are logged for audit

## Support

- Documentation: https://docs.oryggi.ai/gateway-agent
- Issues: https://github.com/oryggi/gateway-agent/issues
- Email: support@oryggi.ai

## License

Copyright 2024 OryggiAI. All rights reserved.
