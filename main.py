import os
import msal
import requests
import psutil, shutil
import os as _os
import time
import platform
import re
import tempfile
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

# --- Config (from environment variables) ---
TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}" if TENANT_ID else None
SCOPE = ["https://graph.microsoft.com/.default"]

# Platform-agnostic default log folder
DEFAULT_LOG_FOLDER = "./logs" if _os.path.exists("./logs") else tempfile.gettempdir()

# --- Token Helper ---
def get_access_token():
    if not CLIENT_ID or not CLIENT_SECRET or not AUTHORITY:
        return None
    app = msal.ConfidentialClientApplication(
        CLIENT_ID, authority=AUTHORITY, client_credential=CLIENT_SECRET
    )
    result = app.acquire_token_for_client(scopes=SCOPE)
    return result.get("access_token")

def list_users_graph():
    """Call Microsoft Graph API to list users"""
    token = get_access_token()
    if not token:
        return {"error": "Failed to acquire token. Make sure TENANT_ID, CLIENT_ID, CLIENT_SECRET are set as environment variables."}
    
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get("https://graph.microsoft.com/v1.0/users", headers=headers)
    
    if resp.status_code == 200:
        users = [
            {"name": u.get("displayName"), "email": u.get("userPrincipalName")}
            for u in resp.json().get("value", [])
        ]
        return {"users": users}
    else:
        return {"error": resp.text, "status_code": resp.status_code}

# --- FastAPI App ---
app = FastAPI(
    title="Copilot Demo API",
    description="Cross-platform API: Graph users, system health, logs, and events.",
    version="2.1.0"
)

@app.get("/users", summary="List Microsoft 365 Users")
def api_list_users():
    return list_users_graph()

@app.get("/health", summary="Health Check")
def health_check():
    cpu = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory().percent
    # Cross-platform disk root
    disk_path = "C:\\" if platform.system() == "Windows" else "/"
    disk = psutil.disk_usage(disk_path).percent
    return {
        "status": "OK" if cpu < 80 and memory < 80 else "WARNING",
        "cpu": f"{cpu}%",
        "memory": f"{memory}%",
        "disk": f"{disk}%"
    }

# --- Log Management ---
@app.get("/logs/preview-delete")
def preview_logs(folder: str = DEFAULT_LOG_FOLDER, days: int = 30):
    """Preview logs that would be deleted (with delete URL)."""
    if not _os.path.exists(folder):
        return {"error": f"Folder not found: {folder}"}
    
    now = time.time()
    files_to_delete = []
    total_space = 0
    for f in _os.listdir(folder):
        path = _os.path.join(folder, f)
        if _os.path.isfile(path):
            mtime = _os.path.getmtime(path)
            if now - mtime > days * 86400:
                size = _os.path.getsize(path)
                files_to_delete.append({"file": f, "size_bytes": size})
                total_space += size
    
    delete_url = f"/logs/delete-confirmed?folder={folder}&days={days}&confirm=yes"

    return {
        "files_to_delete": files_to_delete,
        "total_space_to_free_mb": round(total_space / (1024*1024), 2),
        "delete_url": delete_url
    }

@app.delete("/logs/delete-confirmed")
def delete_logs(
    folder: str = DEFAULT_LOG_FOLDER, 
    days: int = 30, 
    confirm: str = Query(default="no", description="Must be 'yes' to actually delete")
):
    """Delete logs if ?confirm=yes is passed."""
    if confirm.lower() != "yes":
        return {
            "message": "Deletion not performed. Use ?confirm=yes to proceed.",
            "folder": folder,
            "days": days
        }

    if not _os.path.exists(folder):
        return {"error": f"Folder not found: {folder}"}

    now = time.time()
    deleted_files = []
    total_space = 0
    for f in _os.listdir(folder):
        path = _os.path.join(folder, f)
        if _os.path.isfile(path):
            mtime = _os.path.getmtime(path)
            if now - mtime > days * 86400:
                size = _os.path.getsize(path)
                try:
                    _os.remove(path)
                    deleted_files.append(f)
                    total_space += size
                except Exception as e:
                    # record failure but continue
                    deleted_files.append({"file": f, "error": str(e)})
    return {
        "deleted_files": deleted_files,
        "space_freed_mb": round(total_space / (1024*1024), 2),
        "folder": folder,
        "days": days
    }

@app.post("/logs/summarize")
def summarize_log(file_path: str):
    """Summarize a given log file (basic keyword frequency)."""
    if not _os.path.exists(file_path):
        return {"error": f"File not found: {file_path}"}
    
    summary = {"errors": 0, "warnings": 0, "info": 0, "total_lines": 0}
    try:
        with open(file_path, "r", errors="ignore") as f:
            for line in f:
                summary["total_lines"] += 1
                if re.search(r"error", line, re.IGNORECASE):
                    summary["errors"] += 1
                elif re.search(r"warn", line, re.IGNORECASE):
                    summary["warnings"] += 1
                elif re.search(r"info", line, re.IGNORECASE):
                    summary["info"] += 1
    except Exception as e:
        return {"error": str(e)}
    return summary

# --- Event Viewer / Syslog ---
@app.get("/events")
def get_events(
    source: str = Query("windows", enum=["windows", "linux"]), 
    level: str = Query("all", enum=["all", "error", "warning"])
):
    """Fetch system events (Windows Event Viewer or Linux Syslog)."""
    events = []

    if source == "windows" and platform.system() == "Windows":
        try:
            import win32evtlog
            log_type = "Application"
            hand = win32evtlog.OpenEventLog(None, log_type)
            flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
            events_read = win32evtlog.ReadEventLog(hand, flags, 0)
            for ev in events_read[:50]:
                if level == "error" and ev.EventType != 1:
                    continue
                if level == "warning" and ev.EventType != 2:
                    continue
                events.append({"source": ev.SourceName, "event_id": ev.EventID, "event_type": ev.EventType})
        except ImportError:
            return {"error": "win32evtlog not installed. Install pywin32 to use Windows Event Viewer."}
        except Exception as e:
            return {"error": str(e)}

    elif source == "linux" and platform.system() == "Linux":
        syslog_path = "/var/log/syslog" if _os.path.exists("/var/log/syslog") else "/var/log/messages"
        try:
            with open(syslog_path, "r", errors="ignore") as f:
                lines = f.readlines()[-200:]
                for line in lines:
                    if level == "error" and "error" not in line.lower():
                        continue
                    if level == "warning" and "warn" not in line.lower():
                        continue
                    events.append(line.strip())
        except Exception as e:
            return {"error": str(e)}

    else:
        return {"error": f"{source} logs not available on {platform.system()}"}

    return {"events": events}

# --- Azure OpenAPI Plugin Manifest ---
@app.get("/.well-known/ai-plugin.json", include_in_schema=False)
def ai_plugin_manifest():
    # Note: replace YOUR-DEPLOYED-API with your actual deployed hostname
    deployed_base = os.getenv("DEPLOYED_BASE_URL", "https://copilot-fastapi-demo.azurewebsites.net")
    manifest = {
        "schema_version": "v1",
        "name_for_human": "Copilot Demo API",
        "name_for_model": "copilot_demo",
        "description_for_human": "Cross-platform demo: Graph users, health, logs, and events.",
        "description_for_model": (
            "Use this API to fetch Microsoft 365 users, check system health, manage logs, "
            "summarize log files, and read Windows/Linux events."
        ),
        "auth": {"type": "none"},
        "api": {
            "type": "openapi",
            "url": f"{deployed_base}/openapi.json",
            "is_user_authenticated": False
        },
        "logo_url": f"{deployed_base}/static/logo.png",
        "contact_email": "admin@yourdomain.com",
        "legal_info_url": "https://yourdomain.com/legal"
    }
    return JSONResponse(content=manifest)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))




app = FastAPI()

@app.get("/health")
def health():
    cpu = psutil.cpu_percent()
    memory = psutil.virtual_memory().percent
    disk = shutil.disk_usage("/").used / shutil.disk_usage("/").total * 100
    return {
        "status": "OK",
        "cpu": f"{cpu}%",
        "memory": f"{memory}%",
        "disk": f"{disk:.1f}%"
    }

@app.get("/")
def root():
    return {"message": "Hello from Copilot FastAPI Demo!"}