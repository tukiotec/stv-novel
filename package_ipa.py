import os
import sys
import zipfile
import plistlib
import shutil
from PIL import Image

def build_stv_ipa():
    base_dir = r"g:\AI"
    app_dir = os.path.join(base_dir, "stv_novel_app")
    source_ipa = r"C:\Users\AT PC\Downloads\AuraBrowser-unsigned.ipa"
    output_ipa = os.path.join(base_dir, "STVNovel.ipa")
    temp_dir = os.path.join(base_dir, "temp_ipa_build")

    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir, exist_ok=True)

    print(f"1. Extracting source IPA: {source_ipa}...")
    with zipfile.ZipFile(source_ipa, "r") as z:
        z.extractall(temp_dir)

    payload_dir = os.path.join(temp_dir, "Payload")
    app_folders = [f for f in os.listdir(payload_dir) if f.endswith(".app")]
    if not app_folders:
        raise RuntimeError("No .app folder found in IPA!")
    
    old_app_path = os.path.join(payload_dir, app_folders[0])
    new_app_path = os.path.join(payload_dir, "STVNovel.app")
    if old_app_path != new_app_path:
        os.rename(old_app_path, new_app_path)

    # 2. Patch Info.plist
    print("2. Patching Info.plist for STV Novel...")
    plist_path = os.path.join(new_app_path, "Info.plist")
    with open(plist_path, "rb") as f:
        plist = plistlib.load(f)

    plist["CFBundleDisplayName"] = "STV Novel"
    plist["CFBundleName"] = "STVNovel"
    plist["CFBundleIdentifier"] = "com.ares.stvnovel.ios"
    plist["NSAppTransportSecurity"] = {
        "NSAllowsArbitraryLoads": True,
        "NSAllowsArbitraryLoadsInWebContent": True
    }
    plist["UIFileSharingEnabled"] = True
    plist["LSSupportsOpeningDocumentsInPlace"] = True

    with open(plist_path, "wb") as f:
        plistlib.dump(plist, f)

    # 3. Patch Mach-O Binary default URLs
    print("3. Patching Mach-O binary URLs to 14.225.254.182...")
    bin_name = plist.get("CFBundleExecutable", "AuraBrowser")
    bin_path = os.path.join(new_app_path, bin_name)

    with open(bin_path, "rb") as f:
        bin_data = bytearray(f.read())

    # Replace DuckDuckGo with Sáng Tác Việt
    # "https://duckduckgo.com" is 23 bytes -> "http://14.225.254.182/\x00" is 23 bytes
    old_ddg = b"https://duckduckgo.com"
    new_stv = b"http://14.225.254.182/\x00"
    
    count = 0
    idx = 0
    while True:
        pos = bin_data.find(old_ddg, idx)
        if pos == -1:
            break
        bin_data[pos:pos+len(new_stv)] = new_stv
        count += 1
        idx = pos + len(new_stv)
    print(f"Patched {count} instances of default URL to http://14.225.254.182/")

    # Also rename binary if needed or keep matching CFBundleExecutable
    with open(bin_path, "wb") as f:
        f.write(bin_data)

    # 4. Generate & Replace App Icons
    print("4. Replacing App Icons...")
    icon_src = os.path.join(app_dir, "assets", "stv_icon.png")
    if os.path.exists(icon_src):
        img = Image.open(icon_src)
        img.resize((120, 120), Image.Resampling.LANCZOS).save(os.path.join(new_app_path, "AppIcon60x60@2x.png"))
        img.resize((152, 152), Image.Resampling.LANCZOS).save(os.path.join(new_app_path, "AppIcon76x76@2x~ipad.png"))

    # 5. Copy STV Mobile Suite script into app bundle
    suite_src = os.path.join(app_dir, "stv_mobile_suite.js")
    if os.path.exists(suite_src):
        shutil.copy(suite_src, os.path.join(new_app_path, "stv_mobile_suite.js"))

    # 6. Repack into IPA
    print(f"5. Repacking into {output_ipa}...")
    with zipfile.ZipFile(output_ipa, "w", zipfile.ZIP_DEFLATED) as z_out:
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, temp_dir)
                z_out.write(full_path, rel_path)

    shutil.rmtree(temp_dir)
    ipa_size = os.path.getsize(output_ipa) / (1024 * 1024)
    print(f"SUCCESS! Created STVNovel.ipa ({ipa_size:.2f} MB) at:\n{output_ipa}")
    return output_ipa

if __name__ == "__main__":
    build_stv_ipa()
