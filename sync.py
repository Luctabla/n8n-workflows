#!/usr/bin/env python3
"""
N8n Workflow Sync Script

Synchronizes workflow JSON files with an N8n instance via API.

Usage:
    python sync.py [--dry-run] [--activate]

Environment variables:
    N8N_URL: Base URL of your N8n instance (e.g., https://n8n.softbin.org)
    N8N_API_KEY: API key for authentication

Examples:
    # Dry run (show what would be done)
    python sync.py --dry-run

    # Sync all workflows
    python sync.py

    # Sync and activate all workflows
    python sync.py --activate
"""

import os
import sys
import json
import argparse
from pathlib import Path

# Load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass  # dotenv not installed, use environment variables

try:
    import httpx
except ImportError:
    print("Error: httpx not installed. Run: pip install httpx")
    sys.exit(1)


def get_config():
    """Get configuration from environment variables."""
    url = os.getenv("N8N_URL")
    api_key = os.getenv("N8N_API_KEY")

    if not url:
        print("Error: N8N_URL environment variable not set")
        sys.exit(1)

    if not api_key:
        print("Error: N8N_API_KEY environment variable not set")
        sys.exit(1)

    return url.rstrip("/"), api_key


def get_existing_workflows(client: httpx.Client, base_url: str) -> dict:
    """Fetch all existing workflows from N8n."""
    response = client.get(f"{base_url}/api/v1/workflows")
    response.raise_for_status()
    data = response.json()

    # Return dict keyed by workflow name
    workflows = data.get("data", [])
    return {w["name"]: w for w in workflows}


def load_workflow_files(workflows_dir: Path) -> list:
    """Load all workflow JSON files from directory."""
    workflows = []

    for file_path in workflows_dir.glob("*.json"):
        if file_path.name == "package.json":
            continue

        try:
            with open(file_path) as f:
                workflow = json.load(f)
                workflow["_source_file"] = str(file_path)
                workflows.append(workflow)
        except json.JSONDecodeError as e:
            print(f"Warning: Failed to parse {file_path}: {e}")

    return workflows


def clean_workflow_for_api(workflow: dict) -> dict:
    """Remove fields that N8n API doesn't accept."""
    # Fields allowed when creating/updating workflows
    allowed_fields = {
        "name",
        "nodes",
        "connections",
        "settings",
        "staticData",
        "active",
    }

    # Clean the workflow
    cleaned = {k: v for k, v in workflow.items() if k in allowed_fields}

    # Clean nodes - remove fields N8n generates
    if "nodes" in cleaned:
        cleaned_nodes = []
        for node in cleaned["nodes"]:
            cleaned_node = {k: v for k, v in node.items() if k != "webhookId"}
            cleaned_nodes.append(cleaned_node)
        cleaned["nodes"] = cleaned_nodes

    return cleaned


def create_workflow(
    client: httpx.Client, base_url: str, workflow: dict, dry_run: bool = False
) -> dict:
    """Create a new workflow in N8n."""
    name = workflow.get("name", "Unknown")

    # Clean workflow for API
    payload = clean_workflow_for_api(workflow)

    if dry_run:
        print(f"  [DRY RUN] Would create workflow: {name}")
        return {"id": "dry-run", "name": name}

    response = client.post(f"{base_url}/api/v1/workflows", json=payload)
    response.raise_for_status()
    return response.json()


def update_workflow(
    client: httpx.Client,
    base_url: str,
    workflow_id: str,
    workflow: dict,
    dry_run: bool = False,
) -> dict:
    """Update an existing workflow in N8n."""
    name = workflow.get("name", "Unknown")

    # Clean workflow for API
    payload = clean_workflow_for_api(workflow)

    if dry_run:
        print(f"  [DRY RUN] Would update workflow: {name} (id: {workflow_id})")
        return {"id": workflow_id, "name": name}

    response = client.put(f"{base_url}/api/v1/workflows/{workflow_id}", json=payload)
    response.raise_for_status()
    return response.json()


def activate_workflow(
    client: httpx.Client, base_url: str, workflow_id: str, dry_run: bool = False
) -> bool:
    """Activate a workflow in N8n."""
    if dry_run:
        print(f"  [DRY RUN] Would activate workflow id: {workflow_id}")
        return True

    response = client.patch(
        f"{base_url}/api/v1/workflows/{workflow_id}", json={"active": True}
    )
    response.raise_for_status()
    return True


def sync_workflows(dry_run: bool = False, activate: bool = False):
    """Main sync function."""
    base_url, api_key = get_config()
    workflows_dir = Path(__file__).parent

    print(f"N8n URL: {base_url}")
    print(f"Workflows directory: {workflows_dir}")
    print(f"Dry run: {dry_run}")
    print(f"Auto-activate: {activate}")
    print("-" * 50)

    # Set up HTTP client with auth
    headers = {"X-N8N-API-KEY": api_key, "Content-Type": "application/json"}

    with httpx.Client(headers=headers, timeout=30.0) as client:
        # Get existing workflows
        print("Fetching existing workflows...")
        existing = get_existing_workflows(client, base_url)
        print(f"Found {len(existing)} existing workflows")

        # Load local workflows
        local_workflows = load_workflow_files(workflows_dir)
        print(f"Found {len(local_workflows)} local workflow files")
        print("-" * 50)

        created = 0
        updated = 0
        activated = 0

        for workflow in local_workflows:
            name = workflow.get("name", "Unknown")
            source = workflow.get("_source_file", "unknown")

            print(f"\nProcessing: {name}")
            print(f"  Source: {Path(source).name}")

            if name in existing:
                # Update existing workflow
                existing_id = existing[name]["id"]
                print(f"  Action: Update (id: {existing_id})")
                result = update_workflow(
                    client, base_url, existing_id, workflow, dry_run
                )
                updated += 1
                workflow_id = existing_id
            else:
                # Create new workflow
                print("  Action: Create")
                result = create_workflow(client, base_url, workflow, dry_run)
                created += 1
                workflow_id = result.get("id")

            # Activate if requested
            if activate and workflow_id and workflow_id != "dry-run":
                print(f"  Activating...")
                activate_workflow(client, base_url, workflow_id, dry_run)
                activated += 1

    print("\n" + "=" * 50)
    print("Summary:")
    print(f"  Created: {created}")
    print(f"  Updated: {updated}")
    if activate:
        print(f"  Activated: {activated}")
    print("=" * 50)


def main():
    parser = argparse.ArgumentParser(description="Sync N8n workflows from JSON files")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--activate", action="store_true", help="Activate workflows after syncing"
    )
    args = parser.parse_args()

    try:
        sync_workflows(dry_run=args.dry_run, activate=args.activate)
    except httpx.HTTPStatusError as e:
        print(f"\nHTTP Error: {e.response.status_code}")
        print(f"Response: {e.response.text}")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
