"""
Anyada Salon Application Launcher
This script checks for updates, handles the update process, and starts the Anyada Salon Flask application
"""
import sys
import os
import subprocess
import threading
import webbrowser
import time
import requests
import io
import zipfile
import shutil
import psutil
import json
from pathlib import Path

# Configuration
REPO_URL = "https://github.com/ediv333/hair_salon"
REPO_API_URL = "https://api.github.com/repos/ediv333/hair_salon"
REPO_ZIP_URL = "https://github.com/ediv333/hair_salon/archive/refs/heads/main.zip"
VERSION_FILE = "version.json"
PROTECTED_FOLDERS = ["data"]  # Folders to preserve during updates

def ensure_version_file():
    """Create version file if it doesn't exist"""
    if not os.path.exists(VERSION_FILE):
        with open(VERSION_FILE, 'w') as f:
            json.dump({"version": "1.0.0", "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")}, f)

def get_local_version():
    """Get current local version"""
    try:
        if os.path.exists(VERSION_FILE):
            with open(VERSION_FILE, 'r') as f:
                return json.load(f)
        return {"version": "1.0.0", "last_updated": "Never"}
    except Exception as e:
        print(f"Error reading version file: {e}")
        return {"version": "1.0.0", "last_updated": "Error"}

def check_for_updates():
    """Check if updates are available from the GitHub repository"""
    try:
        # Get the latest commit information from GitHub API
        response = requests.get(f"{REPO_API_URL}/commits/main", 
                              headers={"Accept": "application/vnd.github.v3+json"})
        
        if response.status_code == 200:
            latest_commit = response.json()
            latest_sha = latest_commit["sha"]
            latest_date = latest_commit["commit"]["author"]["date"]
            
            # Get current local version info
            local_version = get_local_version()
            
            # Check if we have this SHA recorded
            if "commit_sha" in local_version and local_version["commit_sha"] == latest_sha:
                print("No updates available")
                return False, local_version, None
            
            print("Updates available!")
            return True, local_version, {
                "version": "latest",
                "commit_sha": latest_sha,
                "last_updated": latest_date,
                "message": latest_commit["commit"]["message"]
            }
            
        return False, get_local_version(), None
    except Exception as e:
        print(f"Update check error: {e}")
        return False, get_local_version(), None

def backup_data_folders():
    """Create backups of protected folders"""
    try:
        for folder in PROTECTED_FOLDERS:
            if os.path.exists(folder):
                backup_path = f"{folder}_backup"
                if os.path.exists(backup_path):
                    shutil.rmtree(backup_path)
                shutil.copytree(folder, backup_path)
                print(f"Backed up {folder} to {backup_path}")
    except Exception as e:
        print(f"Backup error: {e}")

def restore_data_folders():
    """Restore protected folders from backups if update fails"""
    try:
        for folder in PROTECTED_FOLDERS:
            backup_path = f"{folder}_backup"
            if os.path.exists(backup_path):
                if os.path.exists(folder):
                    shutil.rmtree(folder)
                shutil.copytree(backup_path, folder)
                print(f"Restored {folder} from backup")
                shutil.rmtree(backup_path)
    except Exception as e:
        print(f"Restore error: {e}")

def close_browser_tabs():
    """Close any browser tabs with 127.0.0.1:500 in the URL"""
    try:
        # This is a PowerShell command that closes Chrome tabs matching the pattern
        # It will work for Chrome, Edge, and other Chromium-based browsers
        ps_command = """
        $pattern = "*127.0.0.1:5000*"
        
        # Try for Edge
        try {
            $edge = Get-Process msedge -ErrorAction SilentlyContinue
            if ($edge) {
                $edge | Where-Object {$_.MainWindowTitle -like $pattern} | ForEach-Object { $_.CloseMainWindow() }
            }
        } catch {}

        # Try for Chrome
        try {
            $chrome = Get-Process chrome -ErrorAction SilentlyContinue
            if ($chrome) {
                $chrome | Where-Object {$_.MainWindowTitle -like $pattern} | ForEach-Object { $_.CloseMainWindow() }
            }
        } catch {}
        
        # Try for Firefox
        try {
            $firefox = Get-Process firefox -ErrorAction SilentlyContinue
            if ($firefox) {
                $firefox | Where-Object {$_.MainWindowTitle -like $pattern} | ForEach-Object { $_.CloseMainWindow() }
            }
        } catch {}
        """
        
        # Execute PowerShell command
        subprocess.run(["powershell", "-Command", ps_command], capture_output=True, text=True)
        print("Closed browser tabs containing 127.0.0.1:5000")
    except Exception as e:
        print(f"Error closing browser tabs: {e}")

def kill_app_processes():
    """Kill all processes that are running app.py"""
    try:
        current_pid = os.getpid()
        killed_count = 0
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                # Skip current process
                if proc.info['pid'] == current_pid:
                    continue
                    
                # Check command line for app.py
                cmdline = proc.info.get('cmdline', [])
                if cmdline and any('app.py' in cmd for cmd in cmdline if cmd):
                    print(f"Found app.py process: PID {proc.info['pid']}")
                    proc.kill()
                    killed_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
                
        if killed_count > 0:
            print(f"Killed {killed_count} app.py processes")
            time.sleep(1)  # Give processes time to fully terminate
        else:
            print("No app.py processes found running")
            
    except Exception as e:
        print(f"Error killing app processes: {e}")

def update_code():
    """Download and apply updates while preserving data folder"""
    try:
        print("Starting code update...")
        # Download the latest code as a zip file
        print("Downloading latest code...")
        response = requests.get(REPO_ZIP_URL, stream=True)
        
        if response.status_code == 200:
            # Extract the zip file to a temporary directory
            temp_dir = "temp_update"
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            os.makedirs(temp_dir)
            
            # Unzip the downloaded file
            print("Extracting files...")
            zip_file = zipfile.ZipFile(io.BytesIO(response.content))
            zip_file.extractall(temp_dir)
            
            # Get the name of the extracted folder
            extracted_dir = None
            for item in os.listdir(temp_dir):
                if os.path.isdir(os.path.join(temp_dir, item)):
                    extracted_dir = os.path.join(temp_dir, item)
                    break
            
            if not extracted_dir:
                print("Failed to extract update files")
                return False
            
            # Copy files from extracted directory to current directory
            # Skip protected folders
            print("Updating files...")
            for item in os.listdir(extracted_dir):
                src_path = os.path.join(extracted_dir, item)
                dst_path = os.path.join(os.getcwd(), item)
                
                # Skip protected folders
                if item in PROTECTED_FOLDERS:
                    print(f"Skipping protected folder: {item}")
                    continue
                    
                # Remove existing file/folder before copying
                if os.path.exists(dst_path):
                    if os.path.isdir(dst_path):
                        shutil.rmtree(dst_path)
                    else:
                        os.remove(dst_path)
                        
                # Copy the new file/folder
                if os.path.isdir(src_path):
                    shutil.copytree(src_path, dst_path)
                else:
                    shutil.copy2(src_path, dst_path)
            
            # Clean up temporary directory
            shutil.rmtree(temp_dir)
            
            print("Code update successful!")
            return True
        else:
            print(f"Failed to download update. Status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"Update failed: {str(e)}")
        return False

def update_version_json(remote_version):
    """Update the version.json file with new version information"""
    try:
        if remote_version:
            with open(VERSION_FILE, 'w') as f:
                json.dump(remote_version, f, indent=2)
            print(f"Updated version information: {remote_version.get('commit_sha', '')[:7]}")
            return True
        return False
    except Exception as e:
        print(f"Error updating version file: {e}")
        return False

def run_app():
    """Run the app.py file"""
    try:
        print("Starting app.py...")
        # Start app.py in a new process and detach it
        subprocess.Popen([sys.executable, "app.py"], creationflags=subprocess.CREATE_NEW_CONSOLE)
 
        # Open browser after a short delay
        threading.Thread(target=lambda: (time.sleep(2), webbrowser.open('http://127.0.0.1:5000/'))).start()
        
        print("Application started!")
        return True
    except Exception as e:
        print(f"Error running app: {e}")
        return False

def update_requirements():
    """Install packages from requirements.txt"""
    try:
        print("Updating packages from requirements.txt...")
        if os.path.exists("requirements.txt"):
            # Use pip to install requirements
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                print("Requirements updated successfully")
                return True
            else:
                print(f"Error updating requirements: {result.stderr}")
                return False
        else:
            print("requirements.txt not found, skipping package updates")
            return True
    except Exception as e:
        print(f"Error updating requirements: {e}")
        return False

def main():
    """Main function to run the launcher"""
    print("Anyada Salon Launcher starting...")
    
    # Ensure version file exists
    ensure_version_file()
    
    # Check for updates
    has_updates, local_version, remote_version = check_for_updates()
    
    if has_updates:
        print(f"Update available: {remote_version.get('message', 'No message')}")
        print(f"Last updated: {local_version.get('last_updated', 'Unknown')}")
        
        # Close browser tabs
        close_browser_tabs()
        
        # Kill existing app processes
        kill_app_processes()
        
        # Backup data folder
        backup_data_folders()
        
        # Update code
        if update_code():
            # Update version.json
            update_version_json(remote_version)
            
            # Restore data folder
            restore_data_folders()
            
            # Update requirements.txt packages
            update_requirements()
            
            print("Update completed successfully!")
        else:
            print("Update failed, restoring data folders...")
            restore_data_folders()
    
    # Run the application
    run_app()

if __name__ == "__main__":
    main()
