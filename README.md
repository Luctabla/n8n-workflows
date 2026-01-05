# N8n Workflows

Collection of N8n workflows managed as code (GitOps).

## Workflows

| File | Description |
|------|-------------|
| `deployment-notification.json` | Webhook trigger that verifies deployment health and responds with status |
| `cicd-pipeline-notification.json` | CI/CD pipeline notifications with Slack integration |

## Usage

### Prerequisites

- N8n instance running (self-hosted or cloud)
- N8n API key with workflow permissions
- Python 3.8+ with `httpx` installed

### Setup

1. Install dependencies:
```bash
pip install httpx
```

2. Set environment variables:
```bash
export N8N_URL="https://n8n.softbin.org"
export N8N_API_KEY="your-api-key"
```

### Sync Workflows

```bash
# Dry run - see what would change
python sync.py --dry-run

# Sync all workflows
python sync.py

# Sync and activate workflows
python sync.py --activate
```

## Workflow Details

### deployment-notification.json

Simple deployment verification workflow:

```
Webhook POST /deployment-webhook
    ↓
Health Check (agents-mcp-qa.softbin.org/health)
    ↓
If Healthy? ─── Yes → Success Response → HTTP 200
           └── No  → Failure Response → HTTP 500
```

**Trigger:**
```bash
curl -X POST "https://n8n.softbin.org/webhook/deployment-webhook" \
  -H "Content-Type: application/json" \
  -d '{"environment": "qa", "version": "1.0.0"}'
```

### cicd-pipeline-notification.json

CI/CD pipeline notification with Slack:

```
Webhook POST /cicd-webhook
    ↓
Parse Payload (extract repo, branch, status, etc.)
    ↓
Check Success? ─── Yes → Verify Deployment → Slack Success
              └── No  → Slack Failure
```

**Trigger from GitHub Actions:**
```yaml
- name: Notify N8n
  run: |
    curl -X POST "${{ secrets.N8N_WEBHOOK_URL }}/cicd-webhook" \
      -H "Content-Type: application/json" \
      -d '{
        "event": "deployment",
        "repository": "${{ github.repository }}",
        "branch": "${{ github.ref_name }}",
        "commit": "${{ github.sha }}",
        "status": "success",
        "environment": "qa",
        "actor": "${{ github.actor }}",
        "run_url": "${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"
      }'
```

## Creating New Workflows

1. Create workflow in N8n UI
2. Export as JSON: Settings → Export
3. Save to this repo with descriptive name
4. Commit and push

Or create manually following the N8n workflow JSON schema.

## CI/CD Integration

Add to your GitHub Actions workflow to auto-sync:

```yaml
- name: Sync N8n Workflows
  env:
    N8N_URL: ${{ secrets.N8N_URL }}
    N8N_API_KEY: ${{ secrets.N8N_API_KEY }}
  run: |
    pip install httpx
    python sync.py --activate
```

## Credentials

Workflows that require credentials (e.g., Slack) need manual credential setup in N8n:

1. Go to N8n → Credentials
2. Create credential with expected name (e.g., "Slack OAuth2")
3. Update workflow JSON `credentials.id` field if needed
