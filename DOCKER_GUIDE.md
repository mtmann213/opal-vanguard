# Opal Vanguard: Docker Deployment Guide

Containerizing the Opal Vanguard environment ensures that anyone can run the project without having to fight OS-level dependencies, conflicting GNU Radio versions, or Python path issues.

This guide explains how to build and run the Opal Vanguard environment using Docker.

---

## Prerequisites
1.  **Docker:** Ensure Docker is installed on your machine.
2.  **Docker Compose:** (Optional but recommended) For easy USB passthrough and GUI rendering.

---

## 1. Building the Environment

The provided `Dockerfile` uses Ubuntu 22.04 as a base and installs GNU Radio 3.10, UHD drivers, and all required Python packages. It also downloads the UHD FPGA images automatically.

To build the image, run this from the root of the repository:
```bash
docker build -t opal-vanguard .
```
*(Note: This process may take 5-10 minutes as it installs GNU Radio and downloads the USRP firmware.)*

---

## 2. Running with Docker Compose (Recommended)

Because this project interacts with physical USB hardware (USRPs) and uses PyQt5 for visual dashboards, running the container requires specific permissions and volume mounts. 

The included `docker-compose.yml` handles:
*   USB Device Passthrough (`/dev/bus/usb`)
*   X11 GUI Forwarding (`/tmp/.X11-unix`)
*   Local Code Mounting (Changes to your code reflect instantly in the container)

### Step 1: Allow Local X11 Connections (Host Machine)
To allow the Docker container to pop up GUI windows on your host's screen, you must allow local connections to your X server. Run this on your **host machine**:
```bash
xhost +local:docker
```

### Step 2: Start the Container
```bash
docker-compose run --rm opal-vanguard bash
```
This drops you into an interactive bash shell *inside* the fully configured container.

### Step 3: Verify Hardware inside Docker
Once inside the container shell, verify it can see your plugged-in USRPs:
```bash
uhd_find_devices
```

### Step 4: Run a Mission
You can now run any command as if you were native. For example:
```bash
python3 src/usrp_transceiver.py --role ALPHA --serial 3449AC1 --config mission_configs/level1_soft_link.yaml
```

---

## 3. Running with Raw Docker (Alternative)

If you don't want to use Docker Compose, you can run the image using the standard Docker CLI. You still need to pass through the USB bus and display variables.

```bash
docker run -it --rm 
  --privileged 
  -v /dev/bus/usb:/dev/bus/usb 
  -v /tmp/.X11-unix:/tmp/.X11-unix 
  -e DISPLAY=$DISPLAY 
  -v $(pwd):/opt/opal-vanguard 
  opal-vanguard bash
```

---

## Troubleshooting

**1. No USRPs Found (`uhd_find_devices` fails)**
Ensure you ran the container with `--privileged` and mapped the volume `-v /dev/bus/usb:/dev/bus/usb`. Also ensure the USRPs are plugged into the host before starting the container.

**2. Cannot Connect to X Server (GUI won't launch)**
Ensure you ran `xhost +local:docker` on your host machine before starting the container. If you are using Wayland, X11 forwarding can be temperamental.

**3. UHD Image Path Errors**
The Dockerfile downloads the images to the default Ubuntu location (`/usr/share/uhd/images`). The `UHD_IMAGES_DIR` environment variable is automatically set in the Dockerfile to point to this location. You do not need to export it manually inside the container.
