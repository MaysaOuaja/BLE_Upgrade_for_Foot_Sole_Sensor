import asyncio
import struct
import threading
import time

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.colors import LinearSegmentedColormap
from bleak import BleakClient, BleakScanner

DEVICE_NAME = "ESP32_FootSensor"
CHARACTERISTIC_UUID = "abcd1234-abcd-1234-abcd-1234567890ab"

DEAD_COLUMN = 3
NOISE_THRESHOLD = 35
TEMPORAL_SMOOTHING = 0.3  # EMA factor across frames -- lower = more smoothing,
                           # filters out frame-to-frame electrical noise while
                           # still tracking real, sustained presses
SCALE_FLOOR = 20       # minimum dynamic vmax, so a quiet mat doesn't look "hot"
SCALE_MAX = 150         # hard ceiling for vmax -- lower this to hit red with less pressure
SCALE_SMOOTHING = 0.3   # EMA factor for adapting vmax frame-to-frame -- higher reacts faster

# ---- Shared state between the BLE thread and the plotting (main) thread ----
lock = threading.Lock()
matrix_raw = np.zeros((8, 8), dtype=np.int16)     # raw deltas as received from ESP32
matrix_display = np.full((8, 8), np.nan)           # filtered, scaled, dead-column masked
smoothed_matrix = np.zeros((8, 8))                 # EMA-smoothed across frames, reduces noise
connection_status = "Connecting..."
current_vmax = SCALE_FLOOR


def apply_filtering_and_scaling(raw):
    """Python-side 'Apply filtering & scaling' step from the software diagram:
    row-average (common-mode) subtraction, temporal smoothing across frames,
    noise threshold, negative clip, dead-column interpolation, and dynamic
    vmax scaling for the plot."""
    global current_vmax, smoothed_matrix
    filtered = raw.astype(float).copy()

    cols = [c for c in range(8) if c != DEAD_COLUMN]
    for r in range(8):
        row_avg = filtered[r, cols].mean()
        filtered[r, cols] -= row_avg
        filtered[r, DEAD_COLUMN] = 0  # unreliable channel, ESP32 always sends 0 for it anyway

    # Temporal smoothing (EMA across frames) -- random electrical/mechanical
    # noise tends to be uncorrelated frame-to-frame and gets averaged down,
    # while a real, sustained press stays elevated and comes through.
    smoothed_matrix = TEMPORAL_SMOOTHING * filtered + (1 - TEMPORAL_SMOOTHING) * smoothed_matrix

    display = smoothed_matrix.copy()
    sub = display[:, cols]
    sub[np.abs(sub) < NOISE_THRESHOLD] = 0
    sub[sub < 0] = 0  # clip negatives for heatmap simplicity
    display[:, cols] = sub

    # The dead column has no real data. Fill it from its neighbors instead of
    # leaving it at 0/NaN -- with interpolation="bicubic", a flat/NaN column
    # gets smeared into a wide band across neighboring columns because the
    # interpolation kernel spans multiple cells. A static marker box (drawn
    # once, on the axes) shows it's not real data instead.
    display[:, DEAD_COLUMN] = (display[:, DEAD_COLUMN - 1] + display[:, DEAD_COLUMN + 1]) / 2

    frame_max = display.max() if display.size else 0
    target = min(max(frame_max, SCALE_FLOOR), SCALE_MAX)
    current_vmax = (1 - SCALE_SMOOTHING) * current_vmax + SCALE_SMOOTHING * target

    return display


def notification_handler(sender, data):
    global matrix_raw, matrix_display
    if len(data) != 17:
        print(f"Unexpected packet size: {len(data)} bytes (expected 17)")
        return
    row = data[0]
    if row > 7:
        return
    values = struct.unpack("<8h", data[1:17])
    with lock:
        matrix_raw[row, :] = values
        matrix_display = apply_filtering_and_scaling(matrix_raw)


async def ble_session():
    global connection_status
    print("Scanning for device...")
    device = await BleakScanner.find_device_by_name(DEVICE_NAME, timeout=10.0)
    if device is None:
        connection_status = "Device not found"
        print(f"Could not find device named '{DEVICE_NAME}'")
        return

    disconnected_event = asyncio.Event()

    def handle_disconnect(_client):
        global connection_status
        connection_status = "Disconnected - reconnecting..."
        disconnected_event.set()

    async with BleakClient(device, disconnected_callback=handle_disconnect) as client:
        connection_status = f"Connected to {DEVICE_NAME}"
        print(connection_status)
        await client.start_notify(CHARACTERISTIC_UUID, notification_handler)
        await disconnected_event.wait()


def run_ble_background(loop):
    """Runs forever: connects, streams data, and automatically retries the
    scan/connect cycle if the link drops (out of range, ESP32 reset, etc.)."""
    global connection_status
    asyncio.set_event_loop(loop)
    while True:
        try:
            loop.run_until_complete(ble_session())
        except Exception as e:
            print("BLE error:", e)
        connection_status = "Reconnecting..."
        time.sleep(2)  # brief pause before retrying scan/connect


# ---- Custom colormap: blue (0 pressure) -> green -> yellow -> red (max pressure) ----
colors = ["#0000ff", "#00ff00", "#ffff00", "#ff0000"]
custom_cmap = LinearSegmentedColormap.from_list("pressure_map", colors)

# ---- Matplotlib live heatmap ----
fig, ax = plt.subplots()
heat = ax.imshow(
    matrix_display,
    cmap=custom_cmap,
    vmin=0,
    vmax=SCALE_FLOOR,
    interpolation="bicubic",  # smooth gradient instead of blocky 8x8 cells
)
plt.colorbar(heat, ax=ax, label="Relative Pressure")
title = ax.set_title(connection_status)


def update(frame):
    with lock:
        heat.set_data(matrix_display)
        heat.set_clim(vmin=0, vmax=current_vmax)
    title.set_text(connection_status)
    return [heat, title]


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    t = threading.Thread(target=run_ble_background, args=(loop,), daemon=True)
    t.start()

    ani = FuncAnimation(fig, update, interval=150, blit=False, cache_frame_data=False)
    plt.show()