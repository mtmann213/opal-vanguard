# Opal Vanguard: Docker Deployment Guide

Containerizing the Opal Vanguard environment ensures that anyone can run the project without having to fight OS-level dependencies, conflicting GNU Radio versions, or Python path issues.

---

## 🏗️ 1. Building the Environment (Requires Internet)

The provided `Dockerfile` uses Ubuntu 22.04 as a base and installs GNU Radio 3.10, UHD drivers, and all required Python packages. It also downloads the UHD FPGA images automatically (~500MB).

To build the image, run this from the root of the repository:
```bash
docker build -t opal-vanguard .
```
*(Note: This process may take 5-10 minutes. The final image size is approximately 3.5 GB.)*

---

## 📦 2. Offline Deployment (Air-Gapped Systems)

Follow these steps to move the entire environment to a computer with **zero internet access**.

### Step A: Export the Image (On the Online PC)
1. Build the image first (see Section 1).
2. Save the image to a compressed tarball:
   ```bash
   docker save opal-vanguard | gzip > opal_vanguard_offline.tar.gz
   ```
3. Copy `opal_vanguard_offline.tar.gz` and the entire `opal-vanguard` source code folder to a USB drive.

### Step B: Prepare the Offline PC
1. **Docker Engine:** Ensure Docker is installed on the offline machine. (If it isn't, you must pre-download the `.deb` or `.rpm` packages for Docker and its dependencies).
2. **USRP udev Rules:** The host needs to recognize the USRP. Run this on the offline machine:
   ```bash
   sudo cp /opt/opal-vanguard/SETUP_MISSION.sh /tmp/setup.sh
   # (Manually ensure udev rules are set if SETUP_MISSION.sh fails due to no apt)
   # Or run:
   sudo libuhd-pkg/uhd_utils/uhd_udev_installer.py # If available
   ```

### Step C: Import and Run (On the Offline PC)
1. Plug in the USB drive and copy the files to the machine.
2. Load the image into Docker:
   ```bash
   docker load < opal_vanguard_offline.tar.gz
   ```
3. Verify the image is loaded:
   ```bash
   docker images # You should see 'opal-vanguard' in the list
   ```
4. Start the environment using the instructions in Section 3.

---

## 🚀 3. Running the Environment

Because this project interacts with physical USB hardware (USRPs) and uses PyQt5 for visual dashboards, specific permissions and volume mounts are required.

### Step 1: Allow Local X11 Connections (Host Machine)
To allow the container to display GUI windows on your host's screen, run this on your **host machine**:
```bash
xhost +local:docker
```

### Step 2: Start with Docker Compose (Recommended)
The `docker-compose.yml` handles USB passthrough and X11 forwarding automatically.
```bash
docker-compose run --rm opal-vanguard bash
```

### Step 3: Run a Mission
Once inside the container shell, verify hardware and launch:
```bash
uhd_find_devices
python3 src/usrp_transceiver.py --role ALPHA --serial <SERIAL> --config mission_configs/level4_stealth.yaml
```

---

## ❓ Docker FAQ

**Q: Does the host computer need to be Ubuntu 22.04?**
**A:** No. The host can be any modern Linux distribution (Ubuntu 20.04+, Fedora, Debian, etc.). The container handles its own internal Ubuntu 22.04 environment.

**Q: Will Docker slow down my radio performance?**
**A:** No. Docker shares the host's kernel. By using `--privileged` and `network_mode: host`, the overhead is negligible. You will get the same sample rates as a native install.

**Q: Can I edit code while the container is running?**
**A:** Yes. The repository folder is mounted as a "Volume." Any changes you make to files on your host machine are instantly updated inside the running container.

**Q: Why do I need `xhost +local:docker`?**
**A:** Linux security prevents unauthorized applications from drawing on your screen. This command gives the Docker engine permission to open the Opal Vanguard dashboard windows.

**Q: How do I persist logs or captures?**
**A:** All files created in `/opt/opal-vanguard/` (like `mission_history.log` or `.cf32` captures) are saved directly to your host's hard drive because of the volume mount.

---

## Troubleshooting

1. **No USRPs Found:** Ensure you ran with `privileged: true` or `--privileged`. Check `lsusb` on the host to ensure the radio is connected.
2. **GUI Error:** If the app crashes with "Could not connect to display," re-run `xhost +local:docker` on the host.
3. **Permission Denied:** If Docker requires sudo, run `sudo docker-compose ...`.
