# Mission Hand-off: Project Opal Vanguard (HARDWARE DEPLOYMENT)
## Session State: Friday, February 27, 2026

### 1. Hardware Integration Status
The system is ready for a 2-node secure link test using USRP B205mini hardware.
*   **ALPHA Serial:** 3449AC1
*   **BRAVO Serial:** 3457464
*   **UHD Images Path:** `/home/tx15/install/sdr/share/uhd/images/`

### 2. Recent Updates
*   **`config.yaml`**: Reconfigured for "Field Ready" mission (915MHz, 2MHz BW, GFSK, DSSS-31, TOD-AES Hopping).
*   **`src/depacketizer.py`**: Diagnostics logic restored. The hardware dashboard will now display CRC and Sync health.
*   **`src/test_link16.py`**: Verified the Link-16 (RS 31,15) logic in digital loopback.

### 3. Resumption Instructions
1.  **Set Environment:** `export UHD_IMAGES_DIR=/home/tx15/install/sdr/share/uhd/images/`
2.  **Verify Hardware:** Run `uhd_find_devices` to ensure all 3 B205minis are visible.
3.  **Establish Link:** 
    *   `python3 src/usrp_transceiver.py --role ALPHA --serial 3449AC1`
    *   `python3 src/usrp_transceiver.py --role BRAVO --serial 3457464`
4.  **Monitor:** Check `mission_history.log` for throughput statistics.

### 4. Next Objectives
*   **Verification:** Confirm "Mission Data" is scrolling on both terminals.
*   **Jamming Test:** Prepare the Red Team script to test DSSS/Hopping resilience against AWGN.
*   **Link-16 Challenge:** Switch to `link16_config.yaml` to test the experimental 10ms fast-hopping mode.
