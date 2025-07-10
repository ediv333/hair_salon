"""
Path handling utilities for the Anyada Salon application
Helps ensure correct file paths when running as an executable
"""
import os
import sys
import shutil

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
    else:
        # We're running in development mode
        base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Data directory is inside the base directory
    data_dir = os.path.join(base_dir, 'data')
    
    # Ensure the data directory exists
    if not os.path.exists(data_dir):
        try:
            os.makedirs(data_dir)
            print(f"Created data directory: {data_dir}")
            
            # Copy default data files if they exist in the package
            default_data_path = os.path.join(get_base_path(), 'data')
            if os.path.exists(default_data_path):
                for filename in os.listdir(default_data_path):
                    src_file = os.path.join(default_data_path, filename)
                    dst_file = os.path.join(data_dir, filename)
                    if os.path.isfile(src_file) and not os.path.exists(dst_file):
                        shutil.copy2(src_file, dst_file)
                        print(f"Copied default data file: {filename}")
        except Exception as e:
            print(f"Error creating data directory: {e}")
    
    return data_dir

def get_data_file_path(filename):
    """Get the full path to a file in the data directory"""
    return os.path.join(get_data_path(), filename)
