"""Cloudflare R2 configuration for static assets.

To complete R2 setup (requires manual dashboard action):
1. Log into https://dash.cloudflare.com → R2 → "Enable R2"
2. The bucket 'aethera-static' will be created automatically after enablement.
3. Run: python -m aethera.r2_config create_bucket
4. Set these environment variables in Vercel:
   - R2_ACCESS_KEY_ID
   - R2_SECRET_ACCESS_KEY
   - R2_ENDPOINT_URL
   - NEXT_PUBLIC_CLOUDFLARE_R2_URL

Once enabled, this module manages the bucket and syncs static assets.
"""

import os
import json
import requests

CF_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN", "cfat_5gl3LhFAe5zaIkdGvoiH0QzNAdn45PTd34HlZWrMe170b451")
CF_ACCOUNT_ID = "f52c5572cb32923b31c5d4980986054b"
BUCKET_NAME = "aethera-static"


def create_bucket():
    """Create the R2 bucket (requires R2 to be enabled in dashboard first)."""
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/r2/buckets"
    resp = requests.post(url,
        headers={"Authorization": f"Bearer {CF_TOKEN}", "Content-Type": "application/json"},
        json={"name": BUCKET_NAME, "locationHint": "enam"},
        timeout=30,
    )
    data = resp.json()
    if data.get("success"):
        print(f"Bucket '{BUCKET_NAME}' created successfully.")
    else:
        errors = data.get("errors", [])
        if any("already exists" in e.get("message", "") for e in errors):
            print(f"Bucket '{BUCKET_NAME}' already exists.")
        else:
            print(f"Error: {json.dumps(errors, indent=2)}")
            print("\nTo enable R2:")
            print("1. Go to https://dash.cloudflare.com → R2")
            print("2. Click 'Enable R2' (requires adding a payment method)")
            print("3. Re-run: python -m aethera.r2_config create_bucket")
    return data


def list_buckets():
    """List all R2 buckets."""
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/r2/buckets"
    resp = requests.get(url,
        headers={"Authorization": f"Bearer {CF_TOKEN}"},
        timeout=30,
    )
    data = resp.json()
    if data.get("success"):
        for b in data.get("result", {}).get("buckets", []):
            print(f"  {b['name']}: {b.get('creationDate', 'unknown')}")
    else:
        print(f"Error: {json.dumps(data.get('errors'), indent=2)}")
    return data


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    if cmd == "create":
        create_bucket()
    elif cmd == "list":
        list_buckets()
    else:
        print(f"Usage: python -m aethera.r2_config [create|list]")
