"""Test if the problem is with signal-to-signal connection in event bus
Event bus does: data_mgr.signal → event_bus.signal → app._on_spectrum_acquired
Maybe the double-emit is causing issues
"""

import sys

sys.path.insert(0, r"c:\Users\ludol\ezControl-AI\Affilabs.core beta")

import time

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import QApplication

print("=== TEST: SIGNAL-TO-SIGNAL CHAIN ===\n")


class SourceObject(QObject):
    """Simulates data_mgr"""

    data_signal = Signal(dict)


class RouterObject(QObject):
    """Simulates event_bus"""

    routed_signal = Signal(dict)


class ReceiverObject(QObject):
    """Simulates Application"""

    def __init__(self):
        super().__init__()
        self.received_count = 0

    def on_data_received(self, data):
        self.received_count += 1
        print(f"[RECEIVER] Got data #{self.received_count}: {data}")


print("[1] Creating test objects...")
source = SourceObject()
router = RouterObject()
receiver = ReceiverObject()
print("[OK] Objects created\n")

print("[2] Setting up signal chain...")
print("    source.data_signal -> router.routed_signal")
source.data_signal.connect(router.routed_signal.emit, Qt.QueuedConnection)
print("    router.routed_signal -> receiver.on_data_received")
router.routed_signal.connect(receiver.on_data_received, Qt.QueuedConnection)
print("[OK] Signal chain established\n")

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

print("[3] Emitting test signals...")
for i in range(3):
    test_data = {"test": i, "value": i * 100}
    print(f"[SOURCE] Emitting data #{i+1}: {test_data}")
    source.data_signal.emit(test_data)

# Process events to deliver queued signals
print("\n[4] Processing Qt events to deliver signals...")
app.processEvents()
time.sleep(0.1)
app.processEvents()

print(f"\n[RESULT] Receiver got {receiver.received_count}/3 signals")

if receiver.received_count == 3:
    print("\n✅ SIGNAL CHAIN WORKS!")
    print("The signal-to-signal relay is NOT the problem")
else:
    print("\n❌ SIGNAL CHAIN FAILED!")
    print("Some signals were lost - this could be the bug")

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)


def shutdown():
    app.quit()


QTimer.singleShot(1000, shutdown)
sys.exit(app.exec())
