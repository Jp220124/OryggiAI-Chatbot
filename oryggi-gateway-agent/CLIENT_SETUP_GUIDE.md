# OryggiAI Gateway Agent - Client Setup Guide

## Quick Setup (3-5 Minutes)

### Prerequisites
- Docker Desktop installed ([Download here](https://www.docker.com/products/docker-desktop/))
- SQL Server running on your machine
- Access to OryggiAI Dashboard

---

## Option A: One-Click Setup (Recommended)

### Step 1: Install Docker Desktop
1. Download Docker Desktop from https://www.docker.com/products/docker-desktop/
2. Run the installer and follow the prompts
3. Restart your computer after installation
4. Open Docker Desktop and wait for it to start (whale icon in system tray)

### Step 2: Generate Token & Download Installer
1. Log in to **OryggiAI Dashboard** (https://oryggi.ai)
2. Go to **Databases** > Select your database
3. Click **Gateway Agent** tab
4. Fill in your database configuration:
   - **Database Name**: Your SQL Server database name
   - **SQL Server Host**: `host.docker.internal` (for local SQL Server)
   - **Port**: `1433` (default SQL Server port)
   - **Username**: Your SQL Server username (e.g., `sa`)
5. Click **Generate Token**
6. Click **Download PowerShell Installer** (Windows) or **Download Docker Compose**

### Step 3: Run the Installer
**For PowerShell (Recommended):**
1. Right-click the downloaded `.ps1` file
2. Select **Run with PowerShell**
3. If prompted, click "Yes" to allow
4. Enter your SQL Server password when asked
5. The script will automatically:
   - Check Docker is installed
   - Pull the gateway agent image
   - Start the container with your configuration

**For Docker Compose:**
1. Open the downloaded `docker-compose.yml` file in a text editor
2. Replace `YOUR_PASSWORD_HERE` with your SQL Server password
3. Open Command Prompt in the same folder
4. Run: `docker-compose up -d`

### Step 4: Verify Connection
In the OryggiAI Dashboard, you should see the Gateway Agent status change to **Connected** (green).

---

## Option B: Manual Setup

### Step 1: Get Your Gateway Token
1. Log in to **OryggiAI Dashboard**
2. Go to **Databases** > Select your database
3. Click **Gateway Agent** tab
4. Click **Generate Token**
5. Copy the token (starts with `gw_`)

### Step 2: Run the Docker Command
Open **Command Prompt** or **PowerShell** and run:

```cmd
docker run -d --name oryggi-gateway ^
  --restart unless-stopped ^
  -e GATEWAY_TOKEN=gw_YOUR_TOKEN_HERE ^
  -e DB_HOST=host.docker.internal ^
  -e DB_PORT=1433 ^
  -e DB_DATABASE=YourDatabaseName ^
  -e DB_USERNAME=sa ^
  -e DB_PASSWORD=YourPassword ^
  oryggiai/gateway-agent:latest
```

**Replace these values:**
| Variable | Replace With |
|----------|-------------|
| `gw_YOUR_TOKEN_HERE` | Your gateway token from Step 1 |
| `YourDatabaseName` | Your SQL Server database name |
| `sa` | Your SQL Server username |
| `YourPassword` | Your SQL Server password |

### Step 3: Verify Connection
Check if the agent is running:
```cmd
docker logs oryggi-gateway -f
```

You should see:
```
OryggiAI Gateway Agent Starting
Testing database connection...
Connected to database: YourDatabaseName
Connecting to OryggiAI server...
Authentication successful!
Gateway agent is now connected and ready.
```

---

## That's It! You're Done!

Your database is now securely connected to OryggiAI. You can start chatting with your data.

---

## Common Commands

| Action | Command |
|--------|---------|
| View logs | `docker logs oryggi-gateway -f` |
| Stop agent | `docker stop oryggi-gateway` |
| Start agent | `docker start oryggi-gateway` |
| Restart agent | `docker restart oryggi-gateway` |
| Remove agent | `docker rm -f oryggi-gateway` |
| Check status | `docker ps -f name=oryggi-gateway` |

---

## Troubleshooting

### "Cannot connect to database"

1. **Check SQL Server is running:**
   - Open SQL Server Configuration Manager
   - Ensure "SQL Server (MSSQLSERVER)" is running

2. **Check SQL Server allows TCP/IP:**
   - SQL Server Configuration Manager > Network Configuration
   - Enable TCP/IP protocol
   - Restart SQL Server

3. **Check credentials:**
   - Verify username and password are correct
   - Try connecting with SQL Server Management Studio first

4. **Check firewall:**
   - Ensure port 1433 is open for local connections

### "Cannot connect to OryggiAI server"

1. **Check internet connection**
2. **Check firewall allows outbound connections**
3. **Verify gateway token is correct**

### "Docker command not found"

1. Install Docker Desktop from https://www.docker.com/products/docker-desktop/
2. Restart your computer after installation
3. Open Docker Desktop and wait for it to start

### "Docker is not running"

1. Open Docker Desktop application
2. Wait for the whale icon to appear in your system tray
3. Try the command again

---

## Configuration Options

| Environment Variable | Description | Default |
|---------------------|-------------|---------|
| `GATEWAY_TOKEN` | Your gateway token (required) | - |
| `DB_HOST` | SQL Server hostname | `host.docker.internal` |
| `DB_PORT` | SQL Server port | `1433` |
| `DB_DATABASE` | Database name (required) | - |
| `DB_USERNAME` | SQL Server username (required) | - |
| `DB_PASSWORD` | SQL Server password (required) | - |
| `DB_USE_WINDOWS_AUTH` | Use Windows authentication | `false` |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | `INFO` |

---

## Windows Authentication (Optional)

If your SQL Server uses Windows Authentication instead of SQL authentication:

```cmd
docker run -d --name oryggi-gateway ^
  --restart unless-stopped ^
  -e GATEWAY_TOKEN=gw_YOUR_TOKEN_HERE ^
  -e DB_HOST=host.docker.internal ^
  -e DB_DATABASE=YourDatabaseName ^
  -e DB_USE_WINDOWS_AUTH=true ^
  oryggiai/gateway-agent:latest
```

> Note: Windows Authentication from Docker may require additional network configuration.

---

## Security Notes

- The Gateway Agent only makes **outbound** connections (no inbound firewall rules needed)
- All traffic is encrypted with TLS/SSL
- Your database credentials stay on your machine
- Queries are executed locally; only results are sent to OryggiAI
- Your gateway token is unique to your database - keep it secure

---

## Support

- **Dashboard Help:** Click the ? icon in the dashboard
- **Email:** support@oryggi.ai
- **Documentation:** https://docs.oryggi.ai/gateway-agent
