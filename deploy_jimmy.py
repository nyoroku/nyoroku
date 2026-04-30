import requests
import os
import time
import json

TOKEN = os.getenv("PA_TOKEN")
USERNAME = 'jimmyminimart'
GH_TOKEN = os.getenv("GH_TOKEN")
REPO_URL = f'https://nyoroku:{GH_TOKEN}@github.com/nyoroku/jimmyminimart.git'

api_base = f'https://www.pythonanywhere.com/api/v0/user/{USERNAME}/'
headers = {'Authorization': f'Token {TOKEN}'}

def run_cmd(console_id, cmd):
    print(f"Executing: {cmd}")
    resp = requests.post(f"{api_base}consoles/{console_id}/send_input/", headers=headers, data={'input': cmd + "\n"})
    if resp.status_code != 200:
        print(f"Command failed: {resp.status_code} - {resp.text}")
    return resp

def deploy():
    print("--- Jimmy Minimart Deployment ---")
    
    # 1. Create a console
    print("Creating bash console...")
    resp = requests.post(f"{api_base}consoles/", headers=headers, data={'executable': 'bash'})
    if resp.status_code not in [200, 201]:
        print(f"Failed to create console: {resp.status_code} - {resp.text}")
        return
    
    c_id = resp.json()['id']
    print(f"Console ID: {c_id}. Waiting 15s...")
    time.sleep(15)
    
    # 2. Setup script
    setup_cmd = (
        f"git clone {REPO_URL} ~/jimmyminimart || (cd ~/jimmyminimart && git fetch origin && git reset --hard origin/main) && "
        "mkvirtualenv jimmy-venv --python=python3.10 || workon jimmy-venv && "
        "pip install django django-htmx django-tailwind-cli dj-database-url whitenoise python-decouple requests && "
        "cd ~/jimmyminimart && "
        "python manage.py migrate --noinput && "
        "python manage.py collectstatic --noinput && "
        "echo 'Setup Complete!'"
    )
    
    run_cmd(c_id, setup_cmd)
    
    print("Waiting for setup to complete (60s)...")
    time.sleep(60)
    
    # 3. Create WebApp if it doesn't exist
    print("Checking webapps...")
    resp = requests.get(f"{api_base}webapps/", headers=headers)
    webapps = resp.json()
    
    domain = f"{USERNAME}.pythonanywhere.com"
    if not any(w['domain_name'] == domain for w in webapps):
        print(f"Creating webapp {domain}...")
        resp = requests.post(f"{api_base}webapps/", headers=headers, data={
            'domain_name': domain,
            'python_version': '3.10'
        })
        print(f"Webapp creation: {resp.status_code}")
    
    # 4. Configure WebApp (Virtualenv and Source Code)
    print("Configuring webapp paths...")
    requests.patch(f"{api_base}webapps/{domain}/", headers=headers, data={
        'virtualenv_path': f'/home/{USERNAME}/.virtualenvs/jimmy-venv',
        'source_directory': f'/home/{USERNAME}/jimmyminimart'
    })
    
    # 5. Reload
    print("Reloading webapp...")
    requests.post(f"{api_base}webapps/{domain}/reload/", headers=headers)
    
    print("Deployment finished!")

if __name__ == "__main__":
    deploy()
