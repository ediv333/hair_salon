"""
Path handling utilities for the Anyada Salon application
Helps ensure correct file paths when running as an executable
"""
import os
import sys
import shutil
import json

def get_base_path():
    """
    Get the base path for the application, works both for development
    and when running as a packaged executable
    """
    # When running as PyInstaller bundle, use _MEIPASS
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        base_path = sys._MEIPASS
    else:
        # Running in normal Python environment
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    return base_path

def get_data_path():
    """
    Get the path to the data directory
    For executables, this is next to the executable file
    """
    if getattr(sys, 'frozen', False):
        # We're running as an executable
        # Use the directory where the executable is located
        base_dir = os.path.dirname(sys.executable)
        print(f"Running in executable mode. Base directory: {base_dir}")
    else:
        # We're running in development mode
        base_dir = os.path.dirname(os.path.abspath(__file__))
        print(f"Running in development mode. Base directory: {base_dir}")
    
    # Data directory is inside the base directory
    data_dir = os.path.join(base_dir, 'data')
    print(f"Data directory path: {data_dir}")
    
    # Ensure the data directory exists
    if not os.path.exists(data_dir):
        try:
            os.makedirs(data_dir)
            print(f"Created data directory: {data_dir}")
            
            # Copy default data files if they exist in the package
            default_data_path = os.path.join(get_base_path(), 'data')
            print(f"Looking for default data in: {default_data_path}")
            
            # Always try to sync customers.json since this is where the issue is occurring
            try:
                sync_data_files(default_data_path, data_dir)
            except Exception as e:
                print(f"Error syncing data files: {e}")
        except Exception as e:
            print(f"Error creating data directory: {e}")
    else:
        # Check if we need to sync data files even if directory exists
        default_data_path = os.path.join(get_base_path(), 'data')
        try:
            sync_data_files(default_data_path, data_dir)
        except Exception as e:
            print(f"Error syncing data files for existing directory: {e}")
            
    return data_dir

def sync_data_files(src_dir, dest_dir):
    """Synchronize data files between source and destination directories"""
    if not os.path.exists(src_dir):
        print(f"Source directory does not exist: {src_dir}")
        return
    
    print(f"Syncing data from {src_dir} to {dest_dir}")
    
    # Create destination directory if it doesn't exist
    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)
    
    # Copy default files only if they don't exist in the destination
    # or if the source file is newer
    for filename in os.listdir(src_dir):
        src_file = os.path.join(src_dir, filename)
        dst_file = os.path.join(dest_dir, filename)
        
        if os.path.isfile(src_file):
            # For customers.json, we need to merge data rather than replace
            if filename == 'customers.json':
                if os.path.exists(dst_file):
                    try:
                        # Load both files and merge customers
                        with open(src_file, 'r') as f:
                            src_data = json.load(f)
                        with open(dst_file, 'r') as f:
                            dst_data = json.load(f)
                            
                        # Create a set of existing customer names for quick lookup
                        existing_names = {customer.get('name') for customer in dst_data}
                        
                        # Add any customers from source that don't exist in destination
                        for customer in src_data:
                            if customer.get('name') not in existing_names:
                                dst_data.append(customer)
                                print(f"Adding customer {customer.get('name')} from source")
                        
                        # Write the merged data back
                        with open(dst_file, 'w') as f:
                            json.dump(dst_data, f, indent=2)
                            print(f"Merged customers.json with {len(dst_data)} customers")
                    except Exception as e:
                        print(f"Error merging customers.json: {e}")
                else:
                    # If destination doesn't exist, just copy the source file
                    shutil.copy2(src_file, dst_file)
                    print(f"Copied {filename} to {dst_file}")
            elif not os.path.exists(dst_file):
                # For other files, only copy if they don't exist
                shutil.copy2(src_file, dst_file)
                print(f"Copied {filename} to {dst_file}")
    
    print("Data sync complete")
    return

def get_data_file_path(filename):
    """Get the full path to a file in the data directory"""
    return os.path.join(get_data_path(), filename)
