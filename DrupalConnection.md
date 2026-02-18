# Connecting to Remote Drupal Server

This guide explains how to run DrupalMind and connect to a remote Drupal server instead of running Drupal locally.

## Prerequisites

- Docker and Docker Compose installed
- Access to a remote Drupal 10 server with JSON:API enabled
- API credentials (if the remote server requires authentication)

## Option 1: Connect to Remote Drupal (No Local Drupal)

### 1. Configure Environment Variables

Edit the `.env` file to point to your remote Drupal server:

```bash
# Remote Drupal Server URL
DRUPAL_BASE_URL=https://your-drupal-site.com
DRUPAL_USERNAME=admin
DRUPAL_PASSWORD=your_password

# Or use API key authentication
DRUPAL_API_KEY=your_api_key
```

### 2. Start Only Required Services

Start only the UI and agents services (skip Drupal, database, etc.):

```bash
# Start only drupalmind-ui and drupalmind-agents
docker compose up -d drupalmind-ui drupalmind-agents
```

### 3. Update UI Configuration

The UI will automatically try to connect to the Drupal server configured in the environment. Make sure the `DRUPAL_BASE_URL` points to your remote server.

## Option 2: Mixed Setup (Local UI + Remote Drupal)

### 1. Start Local Services

```bash
# Start UI and agents locally
docker compose up -d drupalmind-ui drupalmind-agents
```

### 2. Configure Remote Connection

Update the `.env` file:

```bash
# Point to remote Drupal
DRUPAL_BASE_URL=https://remote-drupal.example.com
DRUPAL_USERNAME=admin
DRUPAL_PASSWORD=your_remote_password
```

### 3. Restart Agents

```bash
docker compose restart drupalmind-agents
```

## Option 3: Full Remote Setup

If you want to run everything remotely (UI hosted remotely + remote Drupal):

### 1. Deploy UI to Cloud

Build and push the UI image to a container registry:

```bash
docker build -t your-registry/drupalmind-ui:latest ./ui
docker push your-registry/drupalmind-ui:latest
```

### 2. Deploy Agents to Cloud

```bash
docker build -t your-registry/drupalmind-agents:latest ./agents
docker push your-registry/drupalmind-agents:latest
```

### 3. Run Containers Remotely

```bash
docker run -d \
  -e DRUPAL_BASE_URL=https://your-remote-drupal.com \
  -e DRUPAL_USERNAME=admin \
  -e DRUPAL_PASSWORD=password \
  -e LLM_PROVIDER=anthropic \
  -e ANTHROPIC_API_KEY=sk-... \
  -p 5510:80 \
  your-registry/drupalmind-ui:latest
```

## Required Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DRUPAL_BASE_URL` | Remote Drupal server URL | `https://drupal.example.com` |
| `DRUPAL_USERNAME` | Drupal admin username | `admin` |
| `DRUPAL_PASSWORD` | Drupal admin password | `secure_password` |
| `DRUPAL_API_KEY` | Drupal API key (alternative to username/password) | `api_key_string` |
| `DRUPAL_JSON_API_ENDPOINT` | JSON:API endpoint path | `/jsonapi` (default) |

## Testing the Connection

### Check Agent Health

```bash
curl http://localhost:5511/health
```

Expected response:
```json
{
  "status": "healthy",
  "drupal": "connected"
}
```

### Check Drupal Connection

The agents will automatically check the Drupal connection on startup. Check the logs:

```bash
docker compose logs drupalmind-agents
```

Look for messages like:
- `Drupal: connected` - Connection successful
- `Drupal: disconnected` - Check your credentials

## Troubleshooting

### "Drupal: disconnected" Error

1. Verify the remote Drupal server URL is correct
2. Ensure JSON:API module is enabled on Drupal
3. Check username/password are correct
4. Verify the remote server allows connections from your IP

### Enable JSON:API on Remote Drupal

If JSON:API is not enabled on your remote Drupal:

```bash
# SSH into your Drupal server
drush en jsonapi
drush cr
```

### SSL Certificate Issues

If your remote Drupal uses HTTPS with a self-signed certificate:

```bash
# Add to your docker run command:
- e DRUPAL_SSL_VERIFY=false
```

## Network Diagram

```
┌─────────────────┐      ┌─────────────────┐
│  DrupalMind UI  │      │  DrupalMind    │
│  (localhost)    │─────▶│  Agents        │
│  Port 5510      │      │  Port 5511     │
└─────────────────┘      └────────┬────────┘
                                  │
                                  ▼
                         ┌────────────────────┐
                         │  Remote Drupal     │
                         │  Server            │
                         │  your-drupal.com   │
                         └────────────────────┘
```

## Security Notes

- Never commit credentials to version control
- Use Docker secrets or environment files for production
- Consider using API keys instead of username/password
- Enable HTTPS for all production connections
