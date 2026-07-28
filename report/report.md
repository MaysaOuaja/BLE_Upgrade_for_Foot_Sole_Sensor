# Wireless Bluetooth Upgrade of the FullSoul Pressure Sensing Insole

**Maysa Ouaja** — M.Sc. Electrical Engineering & IT, TUM
CACoM (Computer Aided Clinical Medicine)

## 1. Motivation

Animals walk barefoot by default, and modern footwear reduces the sensory
feedback the sole of the foot naturally receives. Thin-soled footwear is
thought to better preserve this natural sensation. Pressure measurements
across the sole provide a way to evaluate this hypothesis quantitatively,
motivating an instrumented, foot-pressure-sensing insole.

## 2. Previous Work

The starting point for this project was the FullSoul running-pad prototype
(Burian, K.), which used a proprietary microcontroller supplied with the
pressure sensor and a wired connection to a host computer. This made the
device accurate for bench testing but not portable: it could not be used
wirelessly during natural walking or running.

## 3. Contribution

This project adapts the FullSoul system for untethered use:

- Replaced the original proprietary controller with an ESP32 DevKitC V4.
- Added Bluetooth Low Energy (BLE) communication in place of the wired link.
- Implemented a Python application for real-time reception and
  visualization of the pressure data.
- Delivered a portable, open-source hardware/software prototype.

## 4. System Overview

The signal path is: pressure matrix (16×13 design, 8×8 subsection used in
this prototype) → FPC breakout boards → MCP3008 ADC → ESP32 (Arduino
firmware) → BLE → host computer running the Python application.

## 5. Methods

### 5.1 Hardware

The 8×8 resistive matrix is read row-by-row: one row is driven high at a
time while all 8 columns are digitized through an MCP3008 ADC over SPI
(pins CS=5, CLK=18, MISO=19, MOSI=23 on the ESP32; row-select pins
`{13,12,14,27,26,25,33,32}`). Each channel is averaged over 4 ADC samples
per read to reduce quantization noise. The current build is a breadboard
prototype covering an 8×8 subsection of the full sensor.

One column of the physical sensor (column index 3) is a broken/unreliable
channel and is treated as dead: the firmware forces its transmitted value
to zero rather than sending noisy data.

### 5.2 Firmware (ESP32, Arduino)

On boot, the firmware performs a baseline calibration (10 averaged scans of
the full matrix while the insole is untouched), then advertises as a BLE
peripheral (`ESP32_FootSensor`) with a single notify characteristic. Each
loop iteration re-scans the full 8×8 matrix, subtracts the calibrated
baseline, masks the dead column, and streams one row per BLE packet (17
bytes: row index + 8 signed 16-bit deltas), yielding roughly 10 full-frame
updates per second.

### 5.3 Software (Python)

The Python client (`software/foot_heatmap.py`) uses `bleak` to scan for and
connect to the ESP32, reconstructing the 8×8 delta matrix from incoming BLE
notifications. Before display, each frame is processed as follows:

1. **Row-average (common-mode) subtraction** — removes a shared offset
   across each row's active columns.
2. **Temporal smoothing** — an exponential moving average across frames,
   which averages down uncorrelated frame-to-frame electrical/mechanical
   noise while preserving sustained real presses.
3. **Noise threshold and negative clipping** — small residual values are
   zeroed, and negative deltas (below baseline) are clipped for a clean
   heatmap.
4. **Dead-column interpolation** — the masked column (index 3) is filled by
   averaging its two neighboring columns purely for smooth display, since a
   flat/zero column would otherwise smear into a visible band under
   bicubic interpolation.
5. **Dynamic color-scale adaptation** — the heatmap's upper color limit
   adapts smoothly toward the current frame's peak (bounded between a
   floor and a ceiling), so a light touch and a firm press both remain
   visible without manual rescaling.

The result is rendered live as an 8×8 heatmap (blue → green → yellow → red)
using `matplotlib`.

## 6. Results

- The wireless link was verified using both the custom Python client and
  the third-party nRF Connect app to confirm BLE advertising, connection,
  and notification delivery (MTU negotiated up to 185).
- The Python client reproduces a real-time 8×8 pressure heatmap that
  responds to applied pressure with a visibly localized, sustained hotspot,
  distinguishing genuine presses from transient sensor noise.

See `figures/poster.pdf` (sections 6 and 7) for the software pipeline
diagram, BLE connection screenshots, and an example heatmap frame.

## 7. Discussion

**Advantages:** wireless operation, low hardware cost, portable form
factor.

**Limitations:**
- Only an 8×8 subsection of the full 16×13 sensor matrix is implemented.
- The system requires calibration (baseline capture) on every startup.
- The current build is a breadboard implementation, not a finished
  wearable.
- One sensor column is non-functional and is masked rather than repaired.

## 8. Future Work

- Extend acquisition to the full 16×13 matrix.
- Improve calibration and linearization of the pressure readings.
- Increase spatial resolution and sampling rate.
- Add advanced analytics and gait-analysis features on top of the raw
  pressure stream.

## 9. Acknowledgements

Thanks to Prof. Martin Daumer, the CACoM teaching team, and Kai Burian for
providing the original FullSoul prototype that this project builds on.

## 10. References

[1] Burian, K. *FullSoul Running Pad* (previous group's prototype and
    report).
[2] ESP32 DevKitC V4 User Guide.
[3] MCP3008 Datasheet.
[4] nRF Connect Documentation.
