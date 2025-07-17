"""
Anyada Salon Application Launcher
This script starts the Anyada Salon Flask application and handles updates and service installation
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
from pathlib import Path
import json
import ctypes
import tempfile
import urllib.request
from flask import Flask, request, jsonify, render_template_string
from app import app

# Process management - kill any existing anyada.exe processes
def kill_existing_processes():
    """Check for and kill any existing anyada.exe processes"""
    current_pid = os.getpid()
    executable_name = 'anyada.exe'
    
    print(f"Checking for existing {executable_name} processes...")
    killed_count = 0
    
    # Get our own process name for comparison
    try:
        this_process = psutil.Process(current_pid)
        our_name = this_process.name()
        print(f"Current process name: {our_name}, PID: {current_pid}")
    except Exception as e:
        print(f"Error getting current process name: {e}")
        our_name = executable_name
    
    # Look for other instances of our process
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            # Check if this process matches our executable name and is not the current process
            if (proc.info['name'].lower() == executable_name.lower() or 
                (getattr(sys, 'frozen', False) and proc.info['name'].lower() == our_name.lower())) \
                and proc.info['pid'] != current_pid:
                    print(f"Found existing process: {proc.info['name']} (PID: {proc.info['pid']})")
                    proc.kill()
                    print(f"Killed process with PID: {proc.info['pid']}")
                    killed_count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    
    if killed_count > 0:
        print(f"Killed {killed_count} existing instances of {executable_name}")
        # Give processes time to fully terminate
        time.sleep(1)
    else:
        print("No existing instances found")
    
    return killed_count

# Configuration
REPO_URL = "https://github.com/ediv333/hair_salon"
REPO_API_URL = "https://api.github.com/repos/ediv333/hair_salon"
REPO_ZIP_URL = "https://github.com/ediv333/hair_salon/archive/refs/heads/main.zip"
UPDATE_CHECK_INTERVAL = 3600  # Check for updates every hour (in seconds)
VERSION_FILE = "version.json"
PROTECTED_FOLDERS = ["data"]  # Folders to preserve during updates

# Service configuration
NSSM_URL = "https://nssm.cc/release/nssm-2.24.zip"
NSSM_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools", "nssm")
SERVICE_NAME = "anyada"
SERVICE_DISPLAY_NAME = "Anyada Hair Salon"
SERVICE_DESCRIPTION = "Hair salon management application"

# Create version file if it doesn't exist
def ensure_version_file():
    if not os.path.exists(VERSION_FILE):
        with open(VERSION_FILE, 'w') as f:
            json.dump({"version": "1.0.0", "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")}, f)

# Get current local version
def get_local_version():
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
                return False, local_version, None
            
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

def perform_update():
    """Download and apply updates while preserving data folder"""
    try:
        # Create backup of data folder
        backup_data_folders()
        
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
                return False, "Failed to extract update files"
            
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
            
            # Update version file with new version information
            updates_available, _, remote_version = check_for_updates()
            if remote_version:
                with open(VERSION_FILE, 'w') as f:
                    json.dump(remote_version, f, indent=2)
            
            # Flag to indicate server should restart
            need_restart = True
            
            return True, "Update successful! Application will restart shortly.", need_restart
        else:
            return False, f"Failed to download update. Status code: {response.status_code}", False
    except Exception as e:
        restore_data_folders()  # Attempt to restore data on failure
        return False, f"Update failed: {str(e)}", False

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

def open_browser():
    """Open the web browser after a short delay"""
    time.sleep(2)
    webbrowser.open_new('http://127.0.0.1:5000/')

# Service management functions
def is_admin():
    """Check if the script is running with administrator privileges"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def ensure_nssm_installed():
    """Download and install NSSM if not already installed"""
    nssm_exe = os.path.join(NSSM_DIR, "nssm.exe")
    
    # If NSSM already exists, return its path
    if os.path.exists(nssm_exe):
        print("NSSM already installed.")
        return nssm_exe
    
    print("Downloading NSSM...")
    
    # Create directories if they don't exist
    os.makedirs(NSSM_DIR, exist_ok=True)
    
    # Download NSSM zip file
    temp_zip = os.path.join(tempfile.gettempdir(), "nssm.zip")
    try:
        urllib.request.urlretrieve(NSSM_URL, temp_zip)
    except Exception as e:
        print(f"Failed to download NSSM: {e}")
        return None
    
    # Extract the zip file
    try:
        with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
            zip_ref.extractall(tempfile.gettempdir())
            
        # Find the correct nssm.exe based on architecture
        if sys.maxsize > 2**32:  # 64-bit system
            source_path = os.path.join(tempfile.gettempdir(), "nssm-2.24", "win64", "nssm.exe")
        else:  # 32-bit system
            source_path = os.path.join(tempfile.gettempdir(), "nssm-2.24", "win32", "nssm.exe")
        
        # Copy to our tools directory
        shutil.copy2(source_path, nssm_exe)
        
        # Clean up
        os.remove(temp_zip)
        shutil.rmtree(os.path.join(tempfile.gettempdir(), "nssm-2.24"), ignore_errors=True)
        
        print("NSSM installed successfully.")
        return nssm_exe
        
    except Exception as e:
        print(f"Failed to extract or install NSSM: {e}")
        if os.path.exists(temp_zip):
            os.remove(temp_zip)
        return None

def is_service_installed():
    """Check if the service is already installed"""
    try:
        result = subprocess.run(
            ['sc', 'query', SERVICE_NAME], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True
        )
        return "SERVICE_NAME" in result.stdout
    except:
        return False

def install_service(nssm_path):
    """Install anyada.exe as a Windows service using NSSM"""
    if is_service_installed():
        print(f"Service '{SERVICE_NAME}' is already installed.")
        return True, f"Service '{SERVICE_NAME}' is already installed"
    
    # Get the path to anyada.exe
    exe_path = sys.executable if getattr(sys, 'frozen', False) else os.path.join(os.path.dirname(os.path.abspath(__file__)), "anyada.exe")
    if not os.path.exists(exe_path):
        print("anyada.exe not found!")
        return False, "anyada.exe not found"
    
    print(f"Installing service '{SERVICE_NAME}'...")
    
    try:
        # Install the service
        subprocess.run([
            nssm_path, 'install', SERVICE_NAME, exe_path
        ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Configure service
        subprocess.run([nssm_path, 'set', SERVICE_NAME, 'DisplayName', SERVICE_DISPLAY_NAME], check=True)
        subprocess.run([nssm_path, 'set', SERVICE_NAME, 'Description', SERVICE_DESCRIPTION], check=True)
        subprocess.run([nssm_path, 'set', SERVICE_NAME, 'Start', 'SERVICE_DELAYED_AUTO_START'], check=True)
        subprocess.run([nssm_path, 'set', SERVICE_NAME, 'AppDirectory', os.path.dirname(exe_path)], check=True)
        
        # Set restart on failure
        subprocess.run([nssm_path, 'set', SERVICE_NAME, 'AppExit', 'Default', 'Restart'], check=True)
        subprocess.run([nssm_path, 'set', SERVICE_NAME, 'AppRestartDelay', '5000'], check=True)
        
        print(f"Service '{SERVICE_NAME}' installed successfully!")
        return True, f"Service '{SERVICE_NAME}' installed successfully"
        
    except subprocess.CalledProcessError as e:
        print(f"Failed to install service: {e}")
        return False, f"Failed to install service: {str(e)}"

def restart_as_admin():
    """Restart the script with administrator privileges"""
    if hasattr(sys, '_MEIPASS'):
        # Running as PyInstaller executable
        script = sys.executable
    else:
        script = os.path.abspath(__file__)
    
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{script}" --install-service', None, 1)

# Register update routes
@app.route('/check-update')
def check_update():
    """Check if updates are available without performing the update"""
    has_updates, local_version, remote_version = check_for_updates()
    
    # Initialize version.json on first run
    ensure_version_file()
    
    # Build HTML components conditionally
    icon_class = "fas fa-check-circle text-success" if not has_updates else "fas fa-exclamation-circle text-warning"
    status_text_class = "text-success" if not has_updates else "text-warning"
    status_text = "Up to date" if not has_updates else "Update available"
    message_text = "An update is available for your Anyada Salon application." if has_updates else "Your Anyada Salon application is up to date."
    button_class = "btn-outline-secondary" if has_updates else "btn-primary"
    
    # Build update info section if updates are available
    update_info = ""
    if has_updates and remote_version:
        commit_sha = remote_version.get('commit_sha', '')[:7] if remote_version and 'commit_sha' in remote_version else ''
        update_message = remote_version.get('message', 'No update information available') if remote_version else ''
        
        update_info = f'''
        <div class="version-info">
            <h5>Available Update</h5>
            <div class="d-flex justify-content-between align-items-center">
                <div>
                    <span class="badge bg-success version-badge">v{remote_version.get('version', 'latest')}</span>
                    <p class="text-muted small mb-0 mt-2">Released: {remote_version.get('last_updated', 'Unknown')}</p>
                </div>
                <div>
                    <span class="badge bg-light text-dark">{commit_sha}</span>
                </div>
            </div>
            <p class="mt-3 small">{update_message}</p>
        </div>
        '''
    
    # Build update button if updates are available
    update_button = ""
    if has_updates:
        update_button = '<a href="/update" class="btn btn-primary update-btn me-2"><i class="fas fa-download me-2"></i>Install Update</a>'
    
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Anyada Salon - Update</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <style>
            body {{ padding-top: 50px; font-family: 'Montserrat', sans-serif; }}
            .update-container {{ max-width: 600px; margin: 0 auto; text-align: center; }}
            .version-badge {{ font-size: 0.9rem; padding: 5px 10px; }}
            .version-info {{ text-align: left; border-radius: 8px; padding: 15px; background-color: #f8f9fa; margin: 20px 0; }}
            .update-btn {{ margin-top: 20px; }}
            .back-btn {{ margin-top: 20px; }}
            .update-message {{ margin: 20px 0; }}
        </style>
    </head>
    <body>
        <div class="update-container">
            <div class="d-flex align-items-center justify-content-center mb-4">
                <i class="fas fa-sync-alt me-3" style="font-size: 2rem; color: #5a189a;"></i>
                <h2>Anyada Salon Updates</h2>
            </div>
            
            <div class="version-info">
                <h5>Current Version</h5>
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <span class="badge bg-info version-badge">v{local_version.get('version', '1.0.0')}</span>
                        <p class="text-muted small mb-0 mt-2">Last Updated: {local_version.get('last_updated', 'Never')}</p>
                    </div>
                    <div class="text-end">
                        <i class="{icon_class}"></i>
                        <span class="{status_text_class}">{status_text}</span>
                    </div>
                </div>
            </div>
            
            {update_info}
            
            <div class="update-message">
                <p>{message_text}</p>
                <p class="text-muted small">Note: Updates will not affect your data in the data folder.</p>
            </div>
            
            <div class="d-flex justify-content-center">
                {update_button}
                <a href="/" class="btn {button_class} back-btn">Return to Application</a>
            </div>
        </div>
    '''

@app.route('/update')
def update():
    """Perform the actual update"""
    success, message, need_restart = perform_update()
    
    # Build HTML components conditionally
    icon_class = "fas fa-check-circle text-success" if success else "fas fa-times-circle text-danger"
    title_text = "Update Successful" if success else "Update Failed"
    alert_class = "alert-success" if success else "alert-danger"
    info_text = "The application will restart automatically in a few seconds..." if (success and need_restart) else "You can try again later or contact support."
    
    # For successful updates, add auto-refresh to restart page
    meta_refresh = '<meta http-equiv="refresh" content="5;url=/" />' if (success and need_restart) else ''
    
    # If update was successful and we need to restart, schedule a restart
    if success and need_restart:
        # Schedule application restart in a separate thread after a short delay
        # This gives the response time to be sent back to the browser
        def delayed_restart():
            time.sleep(3)  # Wait 3 seconds to ensure response is sent
            print("Restarting application after update...")
            if getattr(sys, 'frozen', False):
                # If running as executable, use different restart approach
                # Start a new process of the same executable
                subprocess.Popen([sys.executable], close_fds=True)
                # Then exit this process
                os._exit(0)
            else:
                # If running as script, restart Flask
                os.execv(sys.executable, [sys.executable] + sys.argv)
        
        restart_thread = threading.Thread(target=delayed_restart)
        restart_thread.daemon = True
        restart_thread.start()
    
    # Create the HTML content based on whether we're restarting or not
    if success and need_restart:
        content = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Anyada Salon - Update Status</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
            {meta_refresh}
            <style>
                body {{ padding-top: 50px; font-family: 'Montserrat', sans-serif; }}
                .update-container {{ max-width: 500px; margin: 0 auto; text-align: center; }}
            </style>
        </head>
        <body>
            <div class="update-container">
                <div class="mb-4">
                    <i class="{icon_class}" style="font-size: 3rem;"></i>
                </div>
                <h2>{title_text}</h2>
                <div class="alert {alert_class} mt-3">{message}</div>
                
                <p class="text-muted mt-3">{info_text}</p>
                
                <div class="mt-4">
                    <div class="spinner-border text-primary" role="status">
                        <span class="visually-hidden">Restarting...</span>
                    </div>
                    <p class="mt-2">Restarting application...</p>
                </div>
            </div>
        </body>
        </html>
        '''
    else:
        content = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Anyada Salon - Update Status</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
            <style>
                body {{ padding-top: 50px; font-family: 'Montserrat', sans-serif; }}
                .update-container {{ max-width: 500px; margin: 0 auto; text-align: center; }}
            </style>
        </head>
        <body>
            <div class="update-container">
                <div class="mb-4">
                    <i class="{icon_class}" style="font-size: 3rem;"></i>
                </div>
                <h2>{title_text}</h2>
                <div class="alert {alert_class} mt-3">{message}</div>
                
                <p class="text-muted mt-3">{info_text}</p>
                
                <div class="mt-4">
                    <a href="/" class="btn btn-primary">Return to Application</a>
                </div>
            </div>
        </body>
        </html>
        '''
    
    return content

@app.route('/install-service')
def service_install_page():
    """Service installation page"""
    service_status = is_service_installed()
    
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Anyada Salon - Service Installation</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <style>
            body { padding-top: 50px; font-family: 'Montserrat', sans-serif; }
            .service-container { max-width: 600px; margin: 0 auto; text-align: center; }
            .info-box { background-color: #f8f9fa; border-radius: 8px; padding: 20px; margin: 20px 0; text-align: left; }
        </style>
    </head>
    <body>
        <div class="service-container">
            <div class="d-flex align-items-center justify-content-center mb-4">
                <i class="fas fa-cog me-3" style="font-size: 2rem; color: #5a189a;"></i>
                <h2>Anyada Salon Service Manager</h2>
            </div>
            
            <div class="info-box">
                <h4>
                    <i class="fas {% if ''' + str(service_status) + ''' %}fa-check-circle text-success{% else %}fa-times-circle text-secondary{% endif %} me-2"></i>
                    Service Status: {% if ''' + str(service_status) + ''' %}<span class="text-success">Installed</span>{% else %}<span class="text-secondary">Not Installed</span>{% endif %}
                </h4>
                <p class="mt-3">Installing Anyada Salon as a Windows service allows it to:</p>
                <ul>
                    <li>Start automatically when your computer boots</li>
                    <li>Run in the background without requiring login</li>
                    <li>Automatically restart if it crashes</li>
                </ul>
            </div>
            
            <div class="mt-4">
                {% if not ''' + str(service_status) + ''' %}
                <a href="/install-service-action" class="btn btn-primary me-2">
                    <i class="fas fa-wrench me-2"></i>Install as Service
                </a>
                {% else %}
                <button disabled class="btn btn-secondary me-2">
                    <i class="fas fa-check me-2"></i>Service Already Installed
                </button>
                {% endif %}
                <a href="/" class="btn btn-outline-secondary">
                    <i class="fas fa-arrow-left me-2"></i>Return to Application
                </a>
            </div>
            
            <div class="mt-4 text-muted small">
                <p>Note: Service installation requires administrator privileges.</p>
            </div>
        </div>
    </body>
    </html>
    ''')

@app.route('/install-service-action')
def service_install_action():
    """Handle service installation"""
    if not is_admin():
        # We need admin rights to install service
        restart_as_admin()
        return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Anyada Salon - Admin Rights Required</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
            <meta http-equiv="refresh" content="5;url=/" />
            <style>
                body { padding-top: 50px; font-family: 'Montserrat', sans-serif; }
                .container { max-width: 500px; margin: 0 auto; text-align: center; }
            </style>
        </head>
        <body>
            <div class="container">
                <i class="fas fa-user-shield" style="font-size: 4rem; color: #5a189a; margin-bottom: 20px;"></i>
                <h2>Administrator Rights Required</h2>
                <div class="alert alert-info mt-3">
                    <p>You'll be prompted to grant administrator rights to install the service.</p>
                    <p>Please approve the User Account Control (UAC) prompt when it appears.</p>
                </div>
                <div class="spinner-border text-primary mt-3" role="status">
                    <span class="visually-hidden">Waiting...</span>
                </div>
                <p class="mt-3">Redirecting back to application in 5 seconds...</p>
            </div>
        </body>
        </html>
        ''')
    
    nssm_path = ensure_nssm_installed()
    if not nssm_path:
        return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Anyada Salon - Service Installation</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
            <style>
                body { padding-top: 50px; font-family: 'Montserrat', sans-serif; }
                .container { max-width: 500px; margin: 0 auto; text-align: center; }
            </style>
        </head>
        <body>
            <div class="container">
                <i class="fas fa-times-circle text-danger" style="font-size: 4rem; margin-bottom: 20px;"></i>
                <h2>NSSM Installation Failed</h2>
                <div class="alert alert-danger mt-3">
                    <p>Could not install or download NSSM (Non-Sucking Service Manager).</p>
                    <p>Please check your internet connection and try again.</p>
                </div>
                <a href="/" class="btn btn-primary mt-3">Return to Application</a>
            </div>
        </body>
        </html>
        ''')
    
    success, message = install_service(nssm_path)
    success_str = "true" if success else "false"
    
    # Build HTML components conditionally
    icon_class = "fas fa-check-circle text-success" if success else "fas fa-times-circle text-danger"
    title_text = "Service Installed Successfully" if success else "Service Installation Failed"
    alert_class = "alert-success" if success else "alert-danger"
    
    return render_template_string(f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Anyada Salon - Service Installation</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <style>
            body {{ padding-top: 50px; font-family: 'Montserrat', sans-serif; }}
            .container {{ max-width: 500px; margin: 0 auto; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="mb-4">
                <i class="{icon_class}" style="font-size: 3rem;"></i>
            </div>
            <h2>{title_text}</h2>
            <div class="alert {alert_class} mt-3">{message}</div>
            
            {{% if {success_str} %}}
            <p class="mt-3">The service has been set to start automatically when your computer boots.</p>
            <p>You can manage the service through Windows Services Manager.</p>
            {{% else %}}
            <p class="mt-3">Please try again or check the logs for more information.</p>
            {{% endif %}}
            
            <a href="/" class="btn btn-primary mt-4">Return to Application</a>
        </div>
    </body>
    </html>
    ''')

# Main execution
if __name__ == '__main__':
    # Check for command line arguments
    if len(sys.argv) > 1 and sys.argv[1] == '--install-service':
        if is_admin():
            print("Installing service with admin privileges...")
            nssm_path = ensure_nssm_installed()
            if nssm_path:
                success, message = install_service(nssm_path)
                print(message)
                if success:
                    print("Service installed successfully. Starting service...")
                    try:
                        subprocess.run(['net', 'start', SERVICE_NAME], check=True)
                        print(f"Service '{SERVICE_NAME}' started.")
                    except subprocess.CalledProcessError as e:
                        print(f"Could not start service: {e}")
            else:
                print("Failed to install NSSM. Service installation aborted.")
            # Exit after service installation attempt
            sys.exit(0)
        else:
            print("Administrator privileges required for service installation.")
            restart_as_admin()
            sys.exit(0)

    # Check for and kill any existing instances of the application
    if getattr(sys, 'frozen', False):
        # Only check for other processes when running as executable
        print("Running as executable, checking for other instances...")
        killed_count = kill_existing_processes()
        if killed_count > 0:
            print(f"Killed {killed_count} existing instance(s) of anyada.exe")
    
    # Add a menu item to the app for service installation
    app.config['SERVICE_MENU_ENABLED'] = True
    
    # Start browser in a separate thread
    threading.Thread(target=open_browser).start()
    
    # Run the Flask application
    app.run(debug=False)
