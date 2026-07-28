# Changelog

Version notes relative to the previous FullSoul prototype (Burian, K.),
which used a proprietary microcontroller supplied with the sensor and a
wired connection to a computer.

## This project (Maysa Ouaja)
- Replaced the proprietary controller with an **ESP32 DevKitC V4**.
- Added **BLE (Bluetooth Low Energy)** streaming, removing the wired
  tether to the computer.
- Wrote a new **Python real-time visualization** client
  (`software/foot_heatmap.py`) with filtering, temporal smoothing, and a
  live heatmap.
- Result: a portable, open-source, wireless prototype (vs. the previous
  wired, closed-source setup).

## Known carry-over issue
- One column of the physical pressure matrix (column index 3) is
  unreliable/broken on this specific sensor hardware and is masked in both
  firmware and software (see README "Hardware setup"). This is a defect of
  the physical sensor unit used, not of the previous group's design.
