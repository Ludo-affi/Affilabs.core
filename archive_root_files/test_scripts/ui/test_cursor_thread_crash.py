"""
Test if cursor.setValue() from worker thread causes crash
This simulates what happens in main_simplified._process_spectrum_data
"""
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QThread, QTimer
import pyqtgraph as pg
from threading import Thread
import time

class CursorTestThread(Thread):
    def __init__(self, cursor):
        super().__init__(daemon=True)
        self.cursor = cursor
        
    def run(self):
        print("[THREAD] Worker thread started")
        time.sleep(0.5)  # Wait for main window to be ready
        
        print("[THREAD] Calling cursor.setValue from WORKER THREAD...")
        try:
            self.cursor.setValue(1.0)  # ACCESSING QT OBJECT FROM WRONG THREAD
            print("[THREAD] cursor.setValue succeeded (shouldn't reach here)")
        except Exception as e:
            print(f"[THREAD] cursor.setValue crashed: {e}")
            import traceback
            traceback.print_exc()

print("=== CURSOR THREAD CRASH TEST ===")
print("This tests if Qt crashes when accessing cursor from worker thread\n")

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

# Create plot with cursor (like full_timeline_graph)
plot_widget = pg.PlotWidget()
cursor = pg.InfiniteLine(pos=0, angle=90, movable=True)
plot_widget.addItem(cursor)
plot_widget.show()

print("[MAIN] Main window created with cursor")
print("[MAIN] Starting worker thread that will call cursor.setValue()...")

# Start worker thread that will call cursor.setValue()
worker = CursorTestThread(cursor)
worker.start()

# Keep app alive for 2 seconds
def shutdown():
    print("\n[MAIN] 2 seconds elapsed")
    if app:
        print("[MAIN] If you see this, the cursor thread-safety didn't crash!")
        print("[MAIN] (But real Qt might crash silently or give runtime warnings)")
        app.quit()

QTimer.singleShot(2000, shutdown)

print("[MAIN] Running Qt event loop...\n")
sys.exit(app.exec())
