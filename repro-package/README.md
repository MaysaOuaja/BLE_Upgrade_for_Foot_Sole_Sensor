# Wireless Bluetooth Upgrade of the FullSoul Pressure Sensing Insole

Reproducibility package for the CACoM project by Maysa Ouaja (M.Sc. Electrical
Engineering & IT), TUM.

This package upgrades the original wired FullSoul pressure-sensing insole
(Burian, K.) to a wireless, BLE-connected, open-source prototype with
real-time Python visualization.

## What's in this package

```
.
├── README.md              <- you are here
├── LICENSE
├── CHANGELOG.md            <- notes on what changed vs. the previous group's work
├── requirements.txt         <- Python dependencies
├── firmware/
│   └── foot_sole_sensor.ino <- ESP32 firmware: matrix scan, calibration, BLE streaming
├── software/
│   └── foot_heatmap.py      <- Python BLE client + live heatmap visualization
├── figures/
│   └── poster.pdf           <- project poster (system diagram, hardware photo, results)
└── report/
    └── report.md            <- short write-up (motivation, methods, results, discussion)
```

## Hardware setup

- 8×8 resistive pressure matrix (FullSoul insole), read via an **MCP3008**
  8-channel ADC over SPI.
- **ESP32 DevKitC V4** as the controller (SPI pins: CS=5, CLK=18, MISO=19,
  MOSI=23; row-select pins: `{13,12,14,27,26,25,33,32}`).
- One column (**column index 3**) is a known-broken/unreliable channel in
  this physical sensor. It is masked at the source in firmware
  (`sendRow()` forces `delta = 0` for `DEAD_COLUMN`) and is additionally
  excluded from row-average subtraction and interpolated for display on the
  Python side, so it does not visually appear as a fixed cold spot or bias
  the rest of the heatmap. If you rebuild the sensor and don't have this
  defect, set `DEAD_COLUMN` to an out-of-range value (e.g. `-1`) in both
  `foot_sole_sensor.ino` and `foot_heatmap.py`, or remove the corresponding
  logic.
- See `figures/poster.pdf` (sections 4 "System Overview" and 5 "Hardware")
  for the wiring diagram and a photo of the breadboard prototype.

## Firmware: `firmware/foot_sole_sensor.ino`

1. Open in the Arduino IDE with the **ESP32 board package** installed
   (Tools → Board → ESP32 Dev Module).
2. Required libraries (all part of the standard ESP32 Arduino BLE stack,
   install via Library Manager if missing): `BLEDevice`, `BLEServer`,
   `BLEUtils`, `BLE2902`, `SPI`.
3. Flash to the ESP32. On boot it:
   - calibrates a baseline (averages 10 scans; **keep the insole
     untouched** during this step — you'll see
     "Calibrating baseline, keep sensor untouched..." on Serial),
   - advertises as BLE peripheral `ESP32_FootSensor`
     (service UUID `12345678-1234-1234-1234-123456789abc`,
     characteristic UUID `abcd1234-abcd-1234-abcd-1234567890ab`),
   - then streams one row (17-byte packet: 1 row-index byte + 8×int16
     deltas) per BLE notification, ~10 fps for the full 8×8 frame.
4. Serial Monitor at 115200 baud also prints a per-row max-pressure trace
   for quick sanity-checking without BLE.

## Software: `software/foot_heatmap.py`

1. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Power on and flash the ESP32 first (it must be advertising).
3. Run:
   ```bash
   python software/foot_heatmap.py
   ```
   The script scans for `ESP32_FootSensor` over BLE, connects, and opens a
   live matplotlib heatmap window. It auto-reconnects if the link drops.
4. Processing pipeline applied to every incoming frame (see
   `apply_filtering_and_scaling()`): row-average (common-mode) subtraction →
   temporal EMA smoothing across frames → noise threshold + negative clip →
   dead-column interpolation for display → dynamic vmax scaling. This
   mirrors the "Apply filtering & scaling" step in the software diagram in
   `figures/poster.pdf` (section 6).

## Reproducing the poster results

- **Figure "Real-time Pressure Heatmap" (poster section 7):** run the
  firmware + `foot_heatmap.py` as above while applying pressure to the
  insole; the live heatmap window reproduces this figure directly (it is a
  live view, not a saved plot — see note below).
- **BLE connection screenshots (poster section 7):** obtained with the
  free **nRF Connect** app (see `report/report.md`, References [4]) while
  connected to the ESP32; not scriptable, included for documentation only.

Note: this pipeline was run live for demonstration and no raw sensor
recordings were saved. If you need a static/offline reproduction, capture a
short session yourself (e.g. add a `csv.writer` call inside
`notification_handler`) and note the change in `CHANGELOG.md`.

## Known limitations (see `report/report.md` §Discussion for full list)

- 8×8 breadboard prototype only (not the full 16×13 matrix).
- Requires per-device calibration (baseline capture on every boot).
- Column 3 is masked, not repaired — see Hardware setup above.

## Contact / acknowledgements

Original FullSoul prototype and dataset foundation: Kai Burian. Supervised
by Prof. Martin Daumer and the CACoM teaching team (TUM).
