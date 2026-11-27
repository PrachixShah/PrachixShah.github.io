"""Run locally with Python and an authenticated GitHub CLI."""
import json
import subprocess
import time
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

REPO = "PrachixShah/PrachixShah.github.io"
AUTH = "https://login.microsoftonline.com/consumers/oauth2/v2.0/"


def post(endpoint, fields):
    req = Request(AUTH + endpoint, data=urlencode(fields).encode())
    try:
        with urlopen(req, timeout=25) as response:
            return json.load(response)
    except HTTPError as error:
        return json.load(error)


def main():
    subprocess.run(["gh", "auth", "status"], check=True, capture_output=True)
    client = input("Personal-account app registration client ID: ").strip()
    flow = post("devicecode", {"client_id": client, "scope": "https://graph.microsoft.com/Files.Read offline_access"})
    if "device_code" not in flow:
        raise SystemExit(flow.get("error_description", "Could not start sign-in"))
    print(flow["message"])
    end = time.monotonic() + flow["expires_in"]
    wait = flow["interval"]
    while time.monotonic() < end:
        time.sleep(wait)
        token = post("token", {"client_id": client, "device_code": flow["device_code"],
                               "grant_type": "urn:ietf:params:oauth:grant-type:device_code"})
        if "refresh_token" in token:
            subprocess.run(["gh", "secret", "set", "ONEDRIVE_REFRESH_TOKEN", "--repo", REPO],
                           input=token["refresh_token"], text=True, check=True)
            subprocess.run(["gh", "variable", "set", "ONEDRIVE_CLIENT_ID", "--repo", REPO,
                            "--body", client], check=True)
            print("Gallery credentials saved to GitHub.")
            return
        if token.get("error") == "slow_down":
            wait += 5
        elif token.get("error") != "authorization_pending":
            raise SystemExit(token.get("error", "Sign-in failed"))
    raise SystemExit("Sign-in expired")


if __name__ == "__main__":
    main()
