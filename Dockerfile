# Use Ubuntu 22.04 which includes GNU Radio 3.10 in its default repositories
FROM ubuntu:22.04

# Prevent interactive prompts during apt installations
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y python3 python3-pip gnuradio uhd-host libuhd-dev python3-pyqt5 usbutils && rm -rf /var/lib/apt/lists/*

# Install Python requirements
RUN pip3 install pyyaml cryptography numpy

# Download UHD FPGA images so they are baked into the container
RUN uhd_images_downloader

# Set environment variable to help UHD find the images
ENV UHD_IMAGES_DIR=/usr/share/uhd/images

# Set the working directory
WORKDIR /opt/opal-vanguard

# By default, drop the user into a bash shell inside the container
CMD ["/bin/bash"]
