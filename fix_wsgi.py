import requests
import os

token = os.getenv("PA_TOKEN")
username = 'jimmyminimart'
domain = 'jimmyminimart.pythonanywhere.com'
filename = 'jimmyminimart_pythonanywhere_com_wsgi.py'
 
headers = {'Authorization': f'Token {token}'}

wsgi_content = f"""import os
import sys

path = '/home/{username}/jimmyminimart'
if path not in sys.path:
    sys.path.append(path)

os.environ['DJANGO_SETTINGS_MODULE'] = 'floki.settings.base'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
"""

url = f'https://www.pythonanywhere.com/api/v0/user/{username}/files/path/var/www/{filename}'

print(f"Uploading WSGI to {url}...")
resp = requests.post(url, headers=headers, files={'content': wsgi_content})

if resp.status_code in [200, 201]:
    print("WSGI file updated successfully.")
    print("Reloading webapp...")
    reload_url = f'https://www.pythonanywhere.com/api/v0/user/{username}/webapps/{domain}/reload/'
    reload_resp = requests.post(reload_url, headers=headers)
    if reload_resp.status_code == 200:
        print("Webapp reloaded successfully.")
    else:
        print(f"Reload failed: {reload_resp.status_code}")
else:
    print(f"Failed to upload WSGI: {resp.status_code}")
    print(resp.text)
