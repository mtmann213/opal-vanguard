# Use Ubuntu 24.04 to match the host OS and provide UHD 4.6+ natively
FROM ubuntu:24.04

# Prevent interactive prompts during apt installations
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies (including NumPy and PyQt5 from apt for stability)
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-numpy \
    python3-pyqt5 \
    python3-yaml \
    python3-cryptography \
    python3-flask \
    gnuradio \
    uhd-host \
    libuhd-dev \
    usbutils \
    && rm -rf /var/lib/apt/lists/*

# Download UHD FPGA images
RUN uhd_images_downloader

# Set environment variable to help UHD find the images
ENV UHD_IMAGES_DIR=/usr/share/uhd/images

# Set the working directory
WORKDIR /opt/opal-vanguard

# Default to launching the ALPHA node in Level 1 configuration
# Users can override this at runtime
CMD ["python3", "src/usrp_transceiver.py", "--role", "ALPHA", "--config", "mission_configs/level1_soft_link.yaml"]
