import requests
import os

def create_repo(username, token, repo_name):
    url = "https://api.github.com/user/repos"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    data = {
        "name": repo_name,
        "private": True,
        "description": "Floki POS for Jimmy Minimart"
    }
    
    resp = requests.post(url, headers=headers, json=data)
    if resp.status_code == 201:
        print(f"Repository '{repo_name}' created successfully.")
        return True
    elif resp.status_code == 422:
        print(f"Repository '{repo_name}' already exists.")
        return True
    else:
        print(f"Failed to create repository: {resp.status_code}")
        print(resp.json())
        return False

if __name__ == "__main__":
    token = os.getenv("GH_TOKEN")
    if not token:
        print("Error: GH_TOKEN not set")
    else:
        create_repo("nyoroku", token, "jimmyminimart")
