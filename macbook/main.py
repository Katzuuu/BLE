import signal
import sys
import CoreBluetooth as CB
import objc
from Foundation import NSObject
from PyObjCTools import AppHelper

HASH = 'HESLO123'

STATES = {0: 'unknown', 1: 'resetting', 2: 'unsupported',
          3: 'unauthorized', 4: 'powered off', 5: 'powered on'}

def hash_to_uuid(hash_str):
    raw = hash_str.encode()
    if len(raw) > 16:
        raise ValueError('HASH must be at most 16 bytes to fit in a UUID')
    h = raw.ljust(16, b'\x00').hex().upper()
    return '%s-%s-%s-%s-%s' % (h[0:8], h[8:12], h[12:16], h[16:20], h[20:32])

HASH_UUID = hash_to_uuid(HASH)

class BeaconDelegate(NSObject):
    def init(self):
        self = objc.super(BeaconDelegate, self).init()
        if self is None:
            return None
        self.manager = CB.CBPeripheralManager.alloc().initWithDelegate_queue_(self, None)
        return self

    def peripheralManagerDidUpdateState_(self, manager):
        state = manager.state()
        print('Bluetooth state:', STATES.get(state, state))
        if state == CB.CBManagerStatePoweredOn:
            manager.startAdvertising_({
                CB.CBAdvertisementDataLocalNameKey: HASH,
                CB.CBAdvertisementDataServiceUUIDsKey: [CB.CBUUID.UUIDWithString_(HASH_UUID)],
            })
        elif state == CB.CBManagerStateUnauthorized:
            print('Allow Bluetooth for your terminal app in System Settings > '
                  'Privacy & Security > Bluetooth, then run again.')

    def peripheralManagerDidStartAdvertising_error_(self, manager, error):
        if error:
            print('Failed to start advertising:', error)
        else:
            print('Advertising HASH=%s' % HASH)
            print('  Local Name:   %s' % HASH)
            print('  Service UUID: %s' % HASH_UUID)
            print('Ctrl+C to stop.')


def main():
    delegate = BeaconDelegate.alloc().init()

    def stop(*_):
        delegate.manager.stopAdvertising()
        print('\nStopped.')
        AppHelper.stopEventLoop()
        sys.exit(0)

    signal.signal(signal.SIGINT, stop)
    AppHelper.runConsoleEventLoop(installInterrupt=True)


if __name__ == '__main__':
    main()