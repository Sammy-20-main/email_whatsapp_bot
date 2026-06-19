"""
Run this ONCE on your laptop to generate token.json
After running, copy the contents of token.json into GitHub Secrets.
You never need to run this again.
"""

from google_auth_oauthlib.flow import InstalledAppFlow
import json

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

def generate_token():
    print("Opening browser for Gmail login...")
    print("Make sure credentials.json is in this folder.\n")

    flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
    creds = flow.run_local_server(port=0)

    token_data = {
        "token":         creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri":     creds.token_uri,
        "client_id":     creds.client_id,
        "client_secret": creds.client_secret,
        "scopes":        list(creds.scopes),
    }

    with open("token.json", "w") as f:
        json.dump(token_data, f, indent=2)

    print("\n✅ token.json created successfully!")
    print("📋 Next step: Copy the CONTENTS of token.json into GitHub Secrets as GMAIL_TOKEN_JSON")
    print("\nContents of token.json:")
    print(json.dumps(token_data, indent=2))

if __name__ == "__main__":
    generate_token()
