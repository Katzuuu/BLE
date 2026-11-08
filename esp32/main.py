import bluetooth
import time
from machine import Pin, PWM
from micropython import const

HASH = "HESLO123"

SERVO_PIN = 13
ANGLE_CLOSED = 0
ANGLE_OPEN = 180

RSSI_AT_1M = -85        # average RSSI at 1 m (calibrate this)
HYSTERESIS = 4          # dB margin so the servo does not flip back and forth at the boundary
LOST_TIMEOUT_MS = 5000  # no packet for this long = device is gone
AVG_WINDOW = 8          # how many RSSI samples to average
PATH_LOSS_N = 2.0       # for the distance estimate in the log only

_IRQ_SCAN_RESULT = const(5)
_IRQ_SCAN_DONE = const(6)

_ADV_TYPE_UUID128_MORE = const(0x06)
_ADV_TYPE_UUID128_DONE = const(0x07)
_ADV_TYPE_NAME_SHORT = const(0x08)
_ADV_TYPE_NAME_FULL = const(0x09)

HASH_BYTES = HASH.encode()
HASH_UUID_LE = bytes(reversed(HASH_BYTES + b"\x00" * (16 - len(HASH_BYTES))))

def adv_fields(payload):
    i = 0
    n = len(payload)
    while i + 1 < n:
        length = payload[i]
        if length == 0 or i + 1 + length > n:
            break
        yield payload[i + 1], payload[i + 2:i + 1 + length]
        i += 1 + length

def has_hash(payload):
    for t, value in adv_fields(payload):
        if t in (_ADV_TYPE_NAME_FULL, _ADV_TYPE_NAME_SHORT) and value == HASH_BYTES:
            return True
        if t in (_ADV_TYPE_UUID128_MORE, _ADV_TYPE_UUID128_DONE):
            for j in range(0, len(value) - 15, 16):
                if value[j:j + 16] == HASH_UUID_LE:
                    return True
    return False

rssi_samples = []
last_seen_ms = 0
new_sample = False

def bt_irq(event, data):
    global last_seen_ms, new_sample
    if event == _IRQ_SCAN_RESULT:
        addr_type, addr, adv_type, rssi, adv_data = data

        if has_hash(bytes(adv_data)):
            rssi_samples.append(rssi)
            if len(rssi_samples) > AVG_WINDOW:
                rssi_samples.pop(0)
            last_seen_ms = time.ticks_ms()
            new_sample = True

    elif event == _IRQ_SCAN_DONE:
        start_scan()

def start_scan():
    ble.gap_scan(0, 30000, 30000, True)

# --- servo -------------------------------------------------------------------
servo = PWM(Pin(SERVO_PIN), freq=50)

def set_servo_angle(angle):
    duty = 1638 + (angle * 6554 // 180)
    servo.duty_u16(duty)

def estimate_distance(rssi):
    return 10 ** ((RSSI_AT_1M - rssi) / (10 * PATH_LOSS_N))

# --- main --------------------------------------------------------------------
ble = bluetooth.BLE()
ble.active(True)
ble.irq(bt_irq)
print("BLE initialized:", ble.active())

set_servo_angle(ANGLE_CLOSED)
is_open = False

print("Scanning for HASH=%s ..." % HASH)
start_scan()

def cleanup():
    try:
        ble.gap_scan(None)
    except Exception:
        pass
    ble.irq(None)
    ble.active(False)
    set_servo_angle(ANGLE_CLOSED)
    servo.deinit()
    print("Stopped.")

try:
    while True:
        now = time.ticks_ms()
        seen_recently = last_seen_ms and time.ticks_diff(now, last_seen_ms) < LOST_TIMEOUT_MS

        if not seen_recently:
            if rssi_samples:
                rssi_samples.clear()
            if is_open:
                print("Device lost -> servo %d" % ANGLE_CLOSED)
                set_servo_angle(ANGLE_CLOSED)
                is_open = False

        elif new_sample and rssi_samples:
            new_sample = False
            avg = sum(rssi_samples) / len(rssi_samples)
            print("HASH found | RSSI avg: %.1f dBm | ~%.2f m" % (avg, estimate_distance(avg)))

            if not is_open and avg >= RSSI_AT_1M + HYSTERESIS / 2:
                print("Device within 1 m -> servo %d" % ANGLE_OPEN)
                set_servo_angle(ANGLE_OPEN)
                is_open = True
            elif is_open and avg < RSSI_AT_1M - HYSTERESIS / 2:
                print("Device farther than 1 m -> servo %d" % ANGLE_CLOSED)
                set_servo_angle(ANGLE_CLOSED)
                is_open = False

        time.sleep_ms(100)
finally:
    cleanup()
