"""AutoApply Native Windows Desktop Application Launcher.

Runs AutoApply as a full, standalone native Windows desktop application with:
- Native Windows Electron application container (not a browser tab or Edge container).
- Dedicated desktop icon, native titlebar, and independent Windows taskbar identity.
- Automated Python FastAPI backend lifecycle management.
- Desktop shortcut creation with custom app icon.
- Clean exit on window close.
"""

import os
import sys
import subprocess
import urllib.request

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")
ICON_ICO = os.path.join(FRONTEND_DIR, "public", "icon.ico")
ICON_PNG = os.path.join(FRONTEND_DIR, "public", "icon.png")

def find_electron_exe() -> str:
    """Locate local Electron executable."""
    local_electron = os.path.join(FRONTEND_DIR, "node_modules", "electron", "dist", "electron.exe")
    if os.path.exists(local_electron):
        return local_electron
    return "electron"

def create_desktop_shortcut():
    """Create a Windows desktop shortcut for AutoApply with native icon."""
    if sys.platform != "win32":
        return
    try:
        desktop_dir = os.path.expanduser(r"~\Desktop")
        shortcut_path = os.path.join(desktop_dir, "AutoApply.lnk")
        target_bat = os.path.join(PROJECT_ROOT, "start-desktop.bat")
        
        icon_setting = f'oLink.IconLocation = "{ICON_ICO}"' if os.path.exists(ICON_ICO) else ''
        
        vbs_script = f'''
Set oWS = WScript.CreateObject("WScript.Shell")
sLinkFile = "{shortcut_path}"
Set oLink = oWS.CreateShortcut(sLinkFile)
oLink.TargetPath = "{target_bat}"
oLink.WorkingDirectory = "{PROJECT_ROOT}"
oLink.Description = "AutoApply Desktop Application"
{icon_setting}
oLink.Save
'''
        vbs_file = os.path.join(PROJECT_ROOT, "_temp_shortcut.vbs")
        with open(vbs_file, "w", encoding="utf-8") as f:
            f.write(vbs_script)
        subprocess.run(["cscript", "//nologo", vbs_file], capture_output=True)
        if os.path.exists(vbs_file):
            os.remove(vbs_file)
        print(f"[Desktop] Shortcut ready at: {shortcut_path}")
    except Exception as e:
        print(f"[Desktop] Note: Could not create desktop shortcut: {e}")

def ensure_frontend_built():
    """Build the production frontend bundle if missing."""
    dist_index = os.path.join(FRONTEND_DIR, "dist", "index.html")
    if not os.path.exists(dist_index):
        print("[AutoApply] Building frontend bundle for desktop shell...")
        npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
        try:
            subprocess.run([npm_cmd, "run", "build"], cwd=FRONTEND_DIR, check=True)
        except Exception as e:
            print(f"[AutoApply] Warning: Could not pre-build frontend: {e}")

def main():
    print("=================================================================")
    print("           AutoApply — Native Windows Desktop Application        ")
    print("=================================================================")

    ensure_frontend_built()
    create_desktop_shortcut()

    electron_exe = find_electron_exe()
    if not os.path.exists(electron_exe) and electron_exe != "electron":
        print(f"[AutoApply] Electron not found at {electron_exe}. Please run 'npm install' in frontend.")
        sys.exit(1)

    print(f"[AutoApply] Launching native desktop container via {electron_exe}...")
    
    # Launch Electron in frontend dir (Electron automatically handles backend lifecycle & loading)
    proc = subprocess.Popen(
        [electron_exe, FRONTEND_DIR],
        cwd=FRONTEND_DIR,
    )

    try:
        proc.wait()
    except KeyboardInterrupt:
        print("\n[AutoApply] Interrupted by user. Closing...")
        try:
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/pid", str(proc.pid), "/f", "/t"], capture_output=True)
            else:
                proc.terminate()
        except Exception:
            pass

    print("[AutoApply] Desktop session ended cleanly.")

if __name__ == "__main__":
    main()
