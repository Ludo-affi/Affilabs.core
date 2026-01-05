#!/usr/bin/env python3
"""Simple UI for controlling 6-port valves"""

import sys
import os
import tkinter as tk
from tkinter import ttk, messagebox
import threading

# Add affilabs to path
parent_dir = os.path.dirname(os.path.abspath(__file__))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from affilabs.core.hardware_manager import HardwareManager
from affilabs.utils.logger import logger


class ValveControlUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Valve Control")
        self.root.geometry("400x300")
        
        self.hm = None
        self.connected = False
        
        # Create UI
        self.create_widgets()
        
        # Connect to hardware
        self.connect_hardware()
    
    def create_widgets(self):
        # Status frame
        status_frame = ttk.LabelFrame(self.root, text="Connection Status", padding=10)
        status_frame.pack(fill="x", padx=10, pady=10)
        
        self.status_label = ttk.Label(status_frame, text="Disconnected", foreground="red")
        self.status_label.pack()
        
        # KC1 control frame
        kc1_frame = ttk.LabelFrame(self.root, text="KC1 - 6-Port Valve", padding=10)
        kc1_frame.pack(fill="x", padx=10, pady=5)
        
        btn_frame_kc1 = ttk.Frame(kc1_frame)
        btn_frame_kc1.pack()
        
        self.kc1_open_btn = ttk.Button(btn_frame_kc1, text="INJECT (Open)", 
                                        command=lambda: self.set_valve(1, 1),
                                        width=15)
        self.kc1_open_btn.pack(side="left", padx=5)
        
        self.kc1_close_btn = ttk.Button(btn_frame_kc1, text="LOAD (Close)", 
                                         command=lambda: self.set_valve(1, 0),
                                         width=15)
        self.kc1_close_btn.pack(side="left", padx=5)
        
        self.kc1_status = ttk.Label(kc1_frame, text="State: Unknown", foreground="gray")
        self.kc1_status.pack(pady=5)
        
        # KC2 control frame
        kc2_frame = ttk.LabelFrame(self.root, text="KC2 - 6-Port Valve", padding=10)
        kc2_frame.pack(fill="x", padx=10, pady=5)
        
        btn_frame_kc2 = ttk.Frame(kc2_frame)
        btn_frame_kc2.pack()
        
        self.kc2_open_btn = ttk.Button(btn_frame_kc2, text="INJECT (Open)", 
                                        command=lambda: self.set_valve(2, 1),
                                        width=15)
        self.kc2_open_btn.pack(side="left", padx=5)
        
        self.kc2_close_btn = ttk.Button(btn_frame_kc2, text="LOAD (Close)", 
                                         command=lambda: self.set_valve(2, 0),
                                         width=15)
        self.kc2_close_btn.pack(side="left", padx=5)
        
        self.kc2_status = ttk.Label(kc2_frame, text="State: Unknown", foreground="gray")
        self.kc2_status.pack(pady=5)
        
        # Initially disable buttons
        self.disable_buttons()
    
    def connect_hardware(self):
        """Connect to hardware in background thread"""
        def connect():
            try:
                self.hm = HardwareManager()
                self.hm._connect_controller()
                
                if self.hm.ctrl:
                    self.connected = True
                    self.root.after(0, self.on_connected)
                else:
                    self.root.after(0, self.on_connect_failed)
            except Exception as e:
                logger.error(f"Connection error: {e}")
                self.root.after(0, self.on_connect_failed)
        
        thread = threading.Thread(target=connect, daemon=True)
        thread.start()
    
    def on_connected(self):
        """Called when hardware connected"""
        self.status_label.config(text=f"Connected: {self.hm.ctrl.get_device_type()}", 
                                foreground="green")
        self.enable_buttons()
        
        # Read initial states
        self.update_valve_states()
    
    def on_connect_failed(self):
        """Called when connection fails"""
        self.status_label.config(text="Connection Failed", foreground="red")
        messagebox.showerror("Connection Error", "Failed to connect to controller")
    
    def enable_buttons(self):
        """Enable all valve control buttons"""
        self.kc1_open_btn.config(state="normal")
        self.kc1_close_btn.config(state="normal")
        self.kc2_open_btn.config(state="normal")
        self.kc2_close_btn.config(state="normal")
    
    def disable_buttons(self):
        """Disable all valve control buttons"""
        self.kc1_open_btn.config(state="disabled")
        self.kc1_close_btn.config(state="disabled")
        self.kc2_open_btn.config(state="disabled")
        self.kc2_close_btn.config(state="disabled")
    
    def set_valve(self, pump, state):
        """Set valve state"""
        if not self.connected:
            messagebox.showerror("Error", "Not connected to hardware")
            return
        
        def execute():
            try:
                pump_name = f"KC{pump}"
                state_name = "INJECT" if state == 1 else "LOAD"
                
                success = self.hm._ctrl_raw.knx_six(state, pump)
                
                if success:
                    logger.info(f"✅ {pump_name} valve set to {state_name}")
                    self.root.after(0, lambda: self.update_valve_state(pump, state))
                else:
                    logger.error(f"❌ Failed to set {pump_name} valve")
                    self.root.after(0, lambda: messagebox.showerror("Error", 
                                    f"Failed to set {pump_name} valve"))
            except Exception as e:
                logger.error(f"Valve control error: {e}")
                self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
        
        # Disable buttons during operation
        self.disable_buttons()
        
        # Execute in background
        thread = threading.Thread(target=execute, daemon=True)
        thread.start()
        
        # Re-enable after short delay
        self.root.after(500, self.enable_buttons)
    
    def update_valve_state(self, pump, state):
        """Update valve state display"""
        state_name = "INJECT" if state == 1 else "LOAD"
        color = "blue" if state == 1 else "green"
        
        if pump == 1:
            self.kc1_status.config(text=f"State: {state_name}", foreground=color)
        else:
            self.kc2_status.config(text=f"State: {state_name}", foreground=color)
    
    def update_valve_states(self):
        """Read and display current valve states"""
        try:
            kc1_state = self.hm._ctrl_raw.knx_six_state(1)
            kc2_state = self.hm._ctrl_raw.knx_six_state(2)
            
            if kc1_state is not None:
                self.update_valve_state(1, kc1_state)
            
            if kc2_state is not None:
                self.update_valve_state(2, kc2_state)
        except Exception as e:
            logger.error(f"Error reading valve states: {e}")


def main():
    root = tk.Tk()
    app = ValveControlUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
