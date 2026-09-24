import os
import sys

def create_desktop_shortcut():
    try:
        import winshell
        from win32com.client import Dispatch
    except ImportError:
        # If pywin32 or winshell not installed, use PowerShell script
        pass

    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    shortcut_path = os.path.join(desktop, "STV Novel Studio.lnk")

    app_dir = os.path.dirname(os.path.abspath(__file__))
    main_py = os.path.join(app_dir, "main.py")
    icon_path = os.path.join(app_dir, "assets", "stv_icon.ico")

    # Find pythonw.exe
    python_dir = os.path.dirname(sys.executable)
    pythonw_exe = os.path.join(python_dir, "pythonw.exe")
    if not os.path.exists(pythonw_exe):
        pythonw_exe = sys.executable

    ps_script = f'''
    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
    $Shortcut.TargetPath = "{pythonw_exe}"
    $Shortcut.Arguments = '"{main_py}"'
    $Shortcut.WorkingDirectory = "{app_dir}"
    $Shortcut.IconLocation = "{icon_path}"
    $Shortcut.Description = "STV Novel Studio - Trình Lưu & Đọc Truyện Sáng Tác Việt 100% Offline"
    $Shortcut.Save()
    '''

    import subprocess
    res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True)
    # Shortcut 2: iPhone Mobile Server
    shortcut_iphone = os.path.join(desktop, "STV Novel - iPhone Server.lnk")
    server_py = os.path.join(app_dir, "server.py")
    ps_script_iphone = f'''
    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut("{shortcut_iphone}")
    $Shortcut.TargetPath = "{sys.executable}"
    $Shortcut.Arguments = '"{server_py}"'
    $Shortcut.WorkingDirectory = "{app_dir}"
    $Shortcut.IconLocation = "{icon_path}"
    $Shortcut.Description = "STV Novel - Máy Chủ Kết Nối iPhone (Đọc & Tải App)"
    $Shortcut.Save()
    '''
    subprocess.run(["powershell", "-NoProfile", "-Command", ps_script_iphone], capture_output=True, text=True)

    if res.returncode == 0 and os.path.exists(shortcut_path):
        print(f"Created desktop shortcuts:\n - {shortcut_path}\n - {shortcut_iphone}")
        return shortcut_path
    else:
        print(f"Shortcut creation error: {res.stderr}")
        return None

if __name__ == "__main__":
    create_desktop_shortcut()
