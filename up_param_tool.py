#!/usr/bin/env python3
import os
import sys
import tarfile
import subprocess
import tempfile
import shutil

BLOCK = 512

def run_adb(cmd, check=True, use_su=False):
    """Run adb command, retry with su if permission denied"""
    full_cmd = ["adb"] + cmd
    print(f"[CMD] {' '.join(full_cmd)}")
    
    try:
        result = subprocess.run(full_cmd, check=check, capture_output=True, text=True)
        return result
    except subprocess.CalledProcessError as e:
        # Check if it's a permission error
        if "Permission denied" in e.stderr or "Permission denied" in e.stdout:
            if not use_su:
                print("[!] Permission denied, retrying with su...")
                # Retry with su prefix for shell commands
                if cmd[0] == "shell":
                    su_cmd = ["adb", "shell", "su", "-c"] + [" ".join(cmd[1:])]
                    print(f"[CMD] {' '.join(su_cmd)}")
                    try:
                        result = subprocess.run(su_cmd, check=check, capture_output=True, text=True)
                        return result
                    except subprocess.CalledProcessError as e2:
                        print(f"[ERR] Command failed even with su: {e2}")
                        if check:
                            sys.exit(1)
                else:
                    print(f"[ERR] Permission denied but not a shell command")
                    if check:
                        sys.exit(1)
            else:
                print(f"[ERR] Command failed with su: {e}")
                if check:
                    sys.exit(1)
        else:
            print(f"[ERR] Command failed: {e}")
            if check:
                sys.exit(1)
    
    return None

def run(cmd, check=True):
    """Run regular command (non-adb)"""
    print(f"[CMD] {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=check)
    except subprocess.CalledProcessError as e:
        print(f"[ERR] Command failed: {e}")
        if check:
            sys.exit(1)

def retrieve_and_unpack():
    print("[*] Retrieving up_param.img from device...")
    run_adb(["shell", "dd", "if=/dev/block/by-name/up_param", "of=/sdcard/up_param.img", "bs=4M"])
    run_adb(["pull", "/sdcard/up_param.img", "."])
    
    if not os.path.exists("up_param.img"):
        print("[ERR] Failed to retrieve up_param.img")
        sys.exit(1)
    print("[OK] Retrieved up_param.img")

    outdir = "up_param_extracted"
    if os.path.exists(outdir):
        shutil.rmtree(outdir)
    os.makedirs(outdir)

    print(f"[*] Unpacking images to {outdir}...")
    try:
        # Use filter='data' for Python 3.12+, otherwise extract without filter
        if sys.version_info >= (3, 12):
            with tarfile.open("up_param.img", "r") as tar:
                tar.extractall(outdir, filter="data")
        else:
            with tarfile.open("up_param.img", "r") as tar:
                tar.extractall(outdir)
    except Exception as e:
        print(f"[ERR] Failed to unpack tar: {e}")
        sys.exit(1)

    # chmod all extracted files to 777
    for root, _, files in os.walk(outdir):
        for f in files:
            try:
                os.chmod(os.path.join(root, f), 0o777)
            except Exception as e:
                print(f"[WARN] Could not chmod {f}: {e}")

    # ensure patched/ exists
    if not os.path.exists("patched"):
        os.makedirs("patched")
        print("[*] Created patched/ folder for replacements.")

    print("[OK] Retrieved, unpacked, and prepared images.")

def get_geometry(path):
    try:
        out = subprocess.check_output(
            ["identify", "-format", "%wx%h", path],
            stderr=subprocess.DEVNULL
        ).decode().strip()
        return out
    except Exception:
        return None

def reencode_to_target(src_path, dst_path, geometry, target_size):
    tmp_path = dst_path + ".tmp.jpg"
    quality = 85
    while quality > 5:
        try:
            run([
                "magick", src_path,
                "-resize", geometry + "!",
                "-colorspace", "sRGB",
                "-depth", "8",
                "-type", "TrueColor",
                "-interlace", "none",
                "-sampling-factor", "4:2:0",
                "-strip",
                "-quality", str(quality),
                tmp_path
            ], check=True)
        except:
            quality -= 5
            continue

        size = os.path.getsize(tmp_path)
        if size <= target_size:
            with open(tmp_path, "rb") as f:
                data = f.read()
            with open(dst_path, "wb") as f:
                f.write(data + b"\x00" * (target_size - len(data)))
            os.remove(tmp_path)
            print(f"[OK] {os.path.basename(dst_path)} re-encoded at quality {quality}, size={size}, padded to {target_size}")
            return True
        quality -= 5
    
    if os.path.exists(tmp_path):
        os.remove(tmp_path)
    print(f"[ERR] Could not shrink {dst_path} to <= {target_size} bytes")
    return False

def fix_images():
    if not os.path.exists("up_param.img"):
        print("[ERR] up_param.img not found.")
        sys.exit(1)
    if not os.path.exists("patched"):
        print("[ERR] patched/ folder not found.")
        sys.exit(1)

    print("[*] Checking and fixing patched images...")
    with tarfile.open("up_param.img", "r") as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
                
            fname = member.name
            orig_size = member.size
            patched_file = os.path.join("patched", fname)
            
            if os.path.exists(patched_file):
                patched_size = os.path.getsize(patched_file)
                if patched_size == orig_size:
                    print(f"{fname}: OK (size={patched_size})")
                else:
                    print(f"{fname}: size mismatch (orig={orig_size}, patched={patched_size})")
                    with tar.extractfile(member) as f:
                        tmp_stock = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
                        tmp_stock.write(f.read())
                        tmp_stock.close()
                    geometry = get_geometry(tmp_stock.name) or "1248x584"
                    os.unlink(tmp_stock.name)
                    reencode_to_target(patched_file, patched_file, geometry, orig_size)
            else:
                print(f"{fname}: no patched version")

def patch_and_flash():
    if not os.path.exists("up_param.img"):
        print("[ERR] up_param.img not found.")
        sys.exit(1)
    if not os.path.exists("patched"):
        print("[ERR] patched/ folder not found.")
        sys.exit(1)

    output_img = "up_param_patched.img"
    print(f"[*] Patching into {output_img}...")

    try:
        with open("up_param.img", "rb") as fin, open(output_img, "wb") as fout:
            while True:
                header = fin.read(BLOCK)
                if len(header) == 0 or header == b"\0" * BLOCK:
                    fout.write(header)
                    break
                fout.write(header)
                
                name = header[:100].rstrip(b"\0").decode("utf-8", errors="ignore")
                size_field = header[124:136].rstrip(b"\0").decode("utf-8", errors="ignore").strip()
                filesize = int(size_field, 8) if size_field else 0
                blocks = (filesize + BLOCK - 1) // BLOCK
                data = fin.read(blocks * BLOCK)

                patched_file = os.path.join("patched", name)
                if os.path.exists(patched_file):
                    rep_size = os.path.getsize(patched_file)
                    if rep_size == filesize:
                        with open(patched_file, "rb") as rep:
                            rep_data = rep.read()
                        fout.write(rep_data + b"\x00" * (blocks * BLOCK - rep_size))
                        print(f"[+] Replaced {name} ({filesize} bytes)")
                    else:
                        fout.write(data)
                        print(f"[!] Skipped {name}, size mismatch")
                else:
                    fout.write(data)

            fout.write(fin.read())
    except Exception as e:
        print(f"[ERR] Failed to create patched image: {e}")
        sys.exit(1)

    print("[OK] Patched image built.")

    print("[*] Flashing to device...")
    run_adb(["push", output_img, "/sdcard/new_up.img"])
    run_adb(["shell", "dd", "if=/sdcard/new_up.img", "of=/dev/block/by-name/up_param", "bs=4M"])
    run_adb(["shell", "sync"])
    print("[OK] Flashed successfully. Reboot device manually or run: adb reboot")

def main_menu():
    while True:
        print("\n=== up_param Tool ===")
        print("1) Retrieve + Unpack up_param.img from device")
        print("2) Fix patched images (re-encode + pad)")
        print("3) Patch tar + flash to device")
        print("0) Exit")
        choice = input("Select option: ").strip()
        if choice == "1":
            retrieve_and_unpack()
        elif choice == "2":
            fix_images()
        elif choice == "3":
            patch_and_flash()
        elif choice == "0":
            sys.exit(0)
        else:
            print("[ERR] Invalid choice.")


if __name__ == "__main__":
    main_menu()