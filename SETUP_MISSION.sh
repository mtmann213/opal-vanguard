#!/bin/bash
# ==============================================================================
# OPAL VANGUARD - MISSION READY BOOTSTRAP SCRIPT
# ==============================================================================
# Run this on any new PC to install dependencies, verify SDR drivers, 
# and run the 18-point digital stress test.
# ==============================================================================

set -e

echo "--- [OPAL VANGUARD] Initializing Environment ---"

# 1. System Dependency Check
echo "--- [1/5] Checking GNU Radio and UHD ---"
if ! command -v uhd_find_devices &> /dev/null
then
    echo "ERROR: 'uhd_find_devices' not found. Please install UHD with: sudo apt install uhd-host libuhd-dev"
    exit 1
fi

# 2. Python Dependencies
echo "--- [2/5] Installing Python Dependencies ---"
pip install pyyaml cryptography numpy --quiet

# 3. UHD FPGA Images
echo "--- [3/5] Setting up UHD Images ---"
# Check if images exist in the current user's install path or standard path
if [ -d "/home/$USER/install/sdr/share/uhd/images/" ]; then
    export UHD_IMAGES_DIR="/home/$USER/install/sdr/share/uhd/images/"
    echo "UHD_IMAGES_DIR set to: $UHD_IMAGES_DIR"
elif [ -d "/usr/share/uhd/images/" ]; then
    export UHD_IMAGES_DIR="/usr/share/uhd/images/"
    echo "UHD_IMAGES_DIR set to standard: $UHD_IMAGES_DIR"
else
    echo "WARNING: UHD images not found. Attempting download..."
    sudo uhd_images_downloader
fi

# 4. Digital Verification Suite
echo "--- [4/5] Running 18-Point Stress Test (Digital Loopback) ---"
python3 src/test_all_configs.py

echo "--- [5/5] Checking Hardware Connection ---"
uhd_find_devices || echo "No USRPs detected. Ensure they are plugged into USB 3.0 ports."

echo "=============================================================================="
echo "MISSION READY: Environment is verified."
echo "To launch ALPHA: python3 src/usrp_transceiver.py --role ALPHA --serial <SERIAL>"
echo "To launch BRAVO: python3 src/usrp_transceiver.py --role BRAVO --serial <SERIAL>"
echo "=============================================================================="
