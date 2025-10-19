# up_param Tool  
## Change Boot Screen on Samsung phones

A small Python utility that pulls the `up_param` partition, lets you edit the boot splash images, then repacks and flashes them back. The menu-driven script is `up_param_tool.py`.

> **Tested only** on **Samsung Galaxy S10+ (SM-G975F)**. Other Samsung models *may* work, but are **not guaranteed**.
>
> **⚠️ DISCLAIMER:** You do this at your own risk. This can brick your device. Back up everything first. I am **not responsible** for data loss or a bricked phone.

---

## Requirements

### On your Linux PC
- **Python 3.8+**
- **ADB** (Android Debug Bridge)
- **ImageMagick** (must provide the `magick` and `identify` commands)

#### Setup
```bash
# Debian/Ubuntu
sudo apt update
sudo apt install python3 adb imagemagick

# Fedora
sudo dnf install python3 android-tools ImageMagick

# Arch
sudo pacman -S python adb imagemagick
```

> If `magick` isn't on your PATH but `convert` is, you likely have an older ImageMagick. Install a recent version or add a `magick` alias.

### On your phone
- **Root access** (the phone must be rooted)
- **USB debugging enabled** in Developer Options
- **ADB authorized** (accept the prompt when you first connect)

---

## Usage

1) **Enable USB debugging and connect your phone**  
   - Go to Settings → Developer Options → Enable USB Debugging
   - Connect via USB and accept the ADB authorization prompt on your phone
   - Verify connection: `adb devices` should list your phone

   > **Note:** The script works both in **normal Android system** (rooted) and in **TWRP/custom recovery**. It will automatically use `su` (root) when needed for partition access.

2) **Run the script's first option to download & unpack**  
   ```bash
   python3 up_param_tool.py
   # Choose: 1) Retrieve + Unpack up_param.img from device
   ```
   This will:
   - `dd` the **up_param** partition to `/sdcard/up_param.img` and pull it to your PC.
   - Extract all images into `up_param_extracted/`.
   - Create an empty `patched/` folder for your replacements.

   After the first run, you'll see:
   ```
   up_param.img            # raw pulled partition image (tar archive)
   up_param_extracted/     # original images extracted here (read-only reference)
   patched/                # put your edited images here (same names & resolution)
   ```

3) **Edit images and place them in `patched/`**  
   - Use files from `up_param_extracted/` as a **base** for your edited pictures. Copy ones you want to edit to `patched/`.- Edit images in `patched/`. **Keep the same filename and resolution.**  
     The tool checks each replacement and—if needed—will re-encode and pad your file to match the original **byte size** (tar members must match).
   - Check your edited files in `patched/` have **exactly the same names** as in `up_param_extracted/`.

4) **Run "Fix patched images"**  
   ```bash
   python3 up_param_tool.py
   # Choose: 2) Fix patched images (re-encode + pad)
   ```
   What it does:
   - Verifies every file you replaced.
   - If sizes don't match, it automatically re-encodes (via ImageMagick) to the **original resolution** and pads to the **original byte size**.
   - You'll see "OK" when a file matches or is successfully fixed.

5) **If everything looks OK, patch + flash**  
   ```bash
   python3 up_param_tool.py
   # Choose: 3) Patch tar + flash to device
   ```
   This will:
   - Build `up_param_patched.img` by swapping in your `patched/` files.
   - Push to the phone and `dd` it back to `/dev/block/by-name/up_param` (using root access).
   - Sync and finish. Reboot with `adb reboot` or manually.

---

## Tips

- **Do not change file names** or add/remove files — replace **in place**.
- **Keep the exact resolution.** The fixer can adjust quality and pad bytes, but it **won't** invent new dimensions. (The script auto-detects geometry from the stock image; if detection fails, it uses a sane default.)
- **Root access:** If you see "Permission denied" errors, ensure your phone is properly rooted and that `su` works in ADB shell.
- **Backups:** Keep a copy of the original `up_param.img` before flashing!
- If ADB isn't detecting your device, try a different USB cable/port or reinstall ADB drivers.

---

## Compatibility

- **Confirmed** on Samsung Galaxy **S10+ SM-G975F** on **Fedora Workstation 42** but should work fine on any distro.
- **Maybe** will run on other Samsung devices with similar `up_param` partition layouts, might work if their splash assets live in the same TAR structure. **Not guaranteed.** Proceed carefully and check partition names first.

---

Happy theming — and be safe!