"""
PyInstaller spec file generator for Anyada Salon application
"""
import os
import PyInstaller.__main__
from PIL import Image
import io

# Convert the JPG logo to ICO format for the executable icon
def convert_jpg_to_ico():
    try:
        # Path to the source JPG image
        jpg_path = os.path.join('static', '1752007093880.jpg')
        ico_path = os.path.join('static', 'favicon.ico')
        
        if not os.path.exists(jpg_path):
            print(f"Warning: Logo file {jpg_path} not found. Using default icon.")
            return
        
        # Open the image and convert to ICO
        img = Image.open(jpg_path)
        img = img.resize((256, 256))  # Standard icon size
        
        # Save as ICO
        img.save(ico_path, format='ICO')
        print(f"Created icon file at {ico_path}")
        return ico_path
    except Exception as e:
        print(f"Error converting logo to icon: {e}")
        return None

# Create the icon
convert_jpg_to_ico()

# Get the current directory
current_dir = os.path.dirname(os.path.abspath(__file__))

# Define the application name
app_name = "anyada"

# Create the spec file content
spec_content = f"""# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

added_files = [
    ('templates', 'templates'),
    ('static', 'static'),
    ('data', 'data'),
]

a = Analysis(['launcher.py'],
             pathex=['{current_dir}'],
             binaries=[],
             datas=added_files,
             hiddenimports=['flask', 'pandas', 'matplotlib', 'plotly', 'requests', 'path_fix'],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)

pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='{app_name}',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=False,
          icon='static/favicon.ico')
"""

# Write the spec file
spec_file_path = os.path.join(current_dir, f"{app_name}.spec")
with open(spec_file_path, "w") as f:
    f.write(spec_content)

print(f"Spec file created: {spec_file_path}")
print("Now running PyInstaller to create the executable...")

# Run PyInstaller with the spec file
PyInstaller.__main__.run([
    '--clean',
    '--noconfirm',
    spec_file_path
])

print("Build complete. Look for the executable in the dist/ folder.")
