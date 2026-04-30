import requests
import os
import time
from datetime import datetime, timedelta

token = os.getenv("PA_TOKEN")
username = 'elicollections'
api_base = f'https://www.pythonanywhere.com/api/v0/user/{username}/'
headers = {'Authorization': f'Token {token}'}

def deploy():
    print("--- Starting Deployment via Task ---")
    
    # 1. Schedule a task for 2 minutes from now
    now = datetime.now()
    run_time = now + timedelta(minutes=2)
    
    # Deployment commands
    cmd = (
        "cd /home/elicollections/nyoroku && "
        "git fetch origin && "
        "git reset --hard origin/main && "
        "workon nyoroku-venv-312 && "
        "python manage.py migrate --noinput && "
        "python manage.py collectstatic --noinput && "
        "python manage.py shell -c 'from accounts.models import User; User.objects.filter(role=\"admin\").update(is_active=True);' "
    )
    
    payload = {
        'command': cmd,
        'descr': f'Deploy {now.strftime("%Y-%m-%d %H:%M")}',
        'hour': run_time.hour,
        'minute': run_time.minute,
        'enabled': True
    }
    
    print(f"Scheduling task for {run_time.hour:02d}:{run_time.minute:02d} UTC...")
    resp = requests.post(api_base + 'schedule/', headers=headers, json=payload)
    
    if resp.status_code == 201:
        task_id = resp.json()['id']
        print(f"Task {task_id} created successfully.")
        
        # 2. Trigger webapp reload (it will reflect changes after task finishes)
        print("Triggering webapp reload...")
        reload_resp = requests.post(api_base + 'webapps/elicollections.pythonanywhere.com/reload/', headers=headers)
        if reload_resp.status_code == 200:
            print("Reload triggered successfully.")
        else:
            print(f"Reload failed: {reload_resp.status_code}")
            
        print("\nDeployment sequence initiated.")
        print(f"The system will pull code and migrate at {run_time.hour:02d}:{run_time.minute:02d} UTC.")
        return True
    else:
        print(f"Failed to create task: {resp.status_code}")
        print(f"Response: {resp.text}")
        return False

if __name__ == "__main__":
    deploy()
