import requests
import json
import sys
import time

USERNAME = 'elicollections'
TOKEN = '4a2f6bd86df6c5ae4af3d6b8cc780434f4a6765a'
api_base = f'https://www.pythonanywhere.com/api/v0/user/{USERNAME}/'
headers = {'Authorization': f'Token {TOKEN}'}

def run_sync():
    print("--- Starting Sync (v4) ---")
    
    # 1. List and delete all existing consoles to avoid state issues
    print("Cleaning up existing consoles...")
    resp = requests.get(api_base + 'consoles/', headers=headers)
    if resp.status_code == 200:
        consoles = resp.json()
        for c in consoles:
            print(f"Deleting console {c['id']}...")
            requests.delete(api_base + f'consoles/{c["id"]}/', headers=headers)
    
    # 2. Create a fresh console
    print(f"Creating fresh console at {api_base}consoles/...")
    resp = requests.post(api_base + 'consoles/', headers=headers, data={'executable': 'bash'})
    if resp.status_code not in [200, 201]:
        print(f"Failed to create console: {resp.status_code}")
        print(f"Response: {resp.text}")
        return False
    
    c_data = resp.json()
    c_id = c_data.get('id')
    c_url = c_data.get('url')
    
    if not c_id:
        print(f"No ID in console data: {c_data}")
        return False
        
    print(f"Console created, ID: {c_id}. Waking up via GET...")
    if c_url:
        requests.get(c_url, headers=headers)
    print("Waiting 30s for full initialization...")
    time.sleep(30)

    # 3. Send the sync command
    cmd = (
        "cd /home/elicollections/nyoroku && "
        "git fetch origin && "
        "git reset --hard origin/main && "
        "workon nyoroku-venv-312 && "
        "python manage.py migrate --noinput && "
        "python manage.py collectstatic --noinput && "
        "python manage.py shell -c 'from accounts.models import User; User.objects.filter(role=\"admin\").update(is_active=True); print(\"Admin profile activated!\")' && "
        "exit\n"
    )
    
    print("Sending sync command...")
    resp = requests.post(api_base + f'consoles/{c_id}/send_input/', headers=headers, data={'input': cmd})
    if resp.status_code != 200:
        print(f"Failed to send command: {resp.status_code}")
        print(f"Response: {resp.text}")
        return False

    print("Sync command sent successfully.")

    # 4. Reload the webapp
    print(f"Reloading webapp {USERNAME}.pythonanywhere.com...")
    resp = requests.post(api_base + f'webapps/{USERNAME}.pythonanywhere.com/reload/', headers=headers)
    if resp.status_code == 200:
        print("Webapp reloaded successfully.")
        return True
    else:
        print(f"Reload failed: {resp.status_code}")
        return False

if __name__ == "__main__":
    if run_sync():
        print("--- Deployment Complete ---")
    else:
        print("--- Deployment Failed ---")
        sys.exit(1)
