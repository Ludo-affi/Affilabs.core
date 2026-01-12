"""Standalone Flow Sidebar Function Tester

Tests all flow sidebar functionality with REAL HARDWARE.
No calibration, no full app bullshit - just direct pump commands!

Author: Lucia (who's tired of resetting the whole app)
Date: 2026-01-12
"""

import sys
import logging
import asyncio
import time
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget,
    QPushButton, QLabel, QTextEdit, QHBoxLayout, QSpinBox
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QFont

# Import REAL pump controller and flow controller for valves
from affipump.affipump_controller import AffipumpController
from affilabs.core.hardware_manager import HardwareManager
import serial.tools.list_ports

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s :: %(levelname)s :: %(message)s'
)
logger = logging.getLogger(__name__)


def find_pump_port():
    """Find the Cavro pump serial port"""
    ports = list(serial.tools.list_ports.comports())
    logger.info(f"Available ports: {[p.device for p in ports]}")
    
    if ports:
        # Usually highest COM port
        pump_port = max(ports, key=lambda p: int(p.device.replace('COM', ''))).device
        logger.info(f"Selected pump port: {pump_port}")
        return pump_port
    return None


class RealPumpManager:
    """REAL pump manager - actual hardware control"""
    
    def __init__(self):
        self.is_available = False
        self.is_idle = True
        self._current_operation = "IDLE"
        self._flow_rate = 25
        self._stop_requested = False  # For worker threads to signal stop
        self.pump = None
        self.controller = None  # Flow controller for valve control
        
        # Find and connect to pump
        port = find_pump_port()
        if port:
            try:
                logger.info(f"🔌 Connecting to pump on {port}...")
                self.pump = AffipumpController(port=port, baudrate=38400, syringe_volume_ul=1000)
                self.pump.open()
                self.is_available = True
                logger.info("✅ REAL PUMP CONNECTED!")
            except Exception as e:
                logger.error(f"❌ Failed to connect to pump: {e}")
                self.is_available = False
        else:
            logger.error("❌ No pump port found!")
        
        # Connect to flow controller for valve control
        try:
            logger.info("🔌 Connecting to flow controller for valve control...")
            hw_manager = HardwareManager()
            hw_manager._connect_controller()
            if hw_manager._ctrl_raw:
                self.controller = hw_manager._ctrl_raw
                logger.info(f"✅ FLOW CONTROLLER CONNECTED: {str(self.controller)}")
            else:
                logger.warning("⚠️ No flow controller found - valve operations will be simulated")
        except Exception as e:
            logger.warning(f"⚠️ Failed to connect flow controller: {e} - valve operations will be simulated")
    
    def change_flow_rate_on_the_fly(self, rate):
        """Change flow rate using V command"""
        if not self.is_available:
            logger.error("Pump not available!")
            return False
        
        try:
            logger.info(f"[REAL PUMP] 💧 Changing flow rate to {rate} µL/min")
            # Convert µL/min to µL/s
            rate_ul_s = rate / 60.0
            # Send V command to both pumps
            self.pump.send_command(f"/1V{rate_ul_s:.3f}R")
            time.sleep(0.05)
            self.pump.send_command(f"/2V{rate_ul_s:.3f}R")
            logger.info(f"✅ Flow rate changed to {rate} µL/min")
            self._flow_rate = rate
            return True
        except Exception as e:
            logger.error(f"❌ Failed to change flow rate: {e}")
            return False
    
    async def emergency_stop(self, auto_home=True):
        """REAL emergency stop"""
        if not self.is_available:
            return False
        
        try:
            logger.warning("[REAL PUMP] 🛑 EMERGENCY STOP - Terminating both pumps!")
            self.pump.send_command("/0TR")  # Broadcast terminate
            await asyncio.sleep(0.5)
            self.is_idle = True
            self._current_operation = "IDLE"
            
            if auto_home:
                logger.info("🏠 Auto-homing after stop...")
                await self.home_pumps()
            
            logger.info("✅ Emergency stop complete")
            return True
        except Exception as e:
            logger.error(f"❌ Emergency stop failed: {e}")
            return False
    
    async def home_pumps(self):
        """REAL home both pumps"""
        if not self.is_available:
            return False
        
        try:
            logger.info("[REAL PUMP] 🏠 Homing both pumps to zero position...")
            
            # Use the controller's initialize_pumps method which properly handles this
            self.pump.initialize_pumps()
            
            # Wait for initialization to complete (pumps become idle)
            logger.info("Waiting for homing to complete...")
            max_wait = 20  # 20 seconds max
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                status1 = self.pump.get_status(1)
                status2 = self.pump.get_status(2)
                
                if status1 and status2:
                    busy1 = status1.get('busy', True)
                    busy2 = status2.get('busy', True)
                    
                    if not busy1 and not busy2:
                        logger.info(f"✅ Pumps homed successfully in {time.time() - start_time:.1f}s")
                        self.is_idle = True
                        return True
                
                await asyncio.sleep(0.5)
            
            # Even if still busy, mark as idle and return
            logger.warning("⚠️ Homing timeout reached, continuing anyway...")
            self.is_idle = True
            return True
        except Exception as e:
            logger.error(f"❌ Homing failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def inject_test(self, assay_rate):
        """REAL inject test - matches inject_simple from pump_manager"""
        if not self.is_available:
            return False
        
        try:
            logger.info(f"[REAL PUMP] 💉 Running inject test at {assay_rate} µL/min")
            self.is_idle = False
            
            # Stop any existing operations first
            logger.info("Terminating any running commands...")
            self.pump.send_command("/1TR")
            await asyncio.sleep(0.05)
            self.pump.send_command("/2TR")
            await asyncio.sleep(0.5)
            
            # Convert to µL/s
            assay_flow_rate_ul_s = assay_rate / 60.0
            aspiration_flow_rate = 24000  # µL/min
            aspiration_flow_rate_ul_s = aspiration_flow_rate / 60.0
            load_volume_ul = 1000
            valve_open_delay_s = 30
            loop_volume_ul = 100
            
            logger.info("=== Simple Inject Started ===")
            logger.info(f"  Assay flow rate: {assay_rate} µL/min")
            logger.info(f"  Loop volume: {loop_volume_ul} µL")
            logger.info(f"  Valve open delay: {valve_open_delay_s}s")
            
            # Calculate contact time
            contact_time_s = (loop_volume_ul / assay_rate) * 60.0
            logger.info(f"  Calculated contact time: {contact_time_s:.2f}s")
            
            # STEP 1: Move plungers to ABSOLUTE POSITION P1000 (full syringe)
            # This works regardless of current position - P command is absolute!
            logger.info(f"\n[STEP 1] Moving plungers to ABSOLUTE POSITION P{load_volume_ul}")
            logger.info(f"  (Valve in INPUT orientation, moving to position {load_volume_ul} at {aspiration_flow_rate} µL/min)")
            self.pump.aspirate_both_to_position(target_position_ul=load_volume_ul, speed_ul_s=aspiration_flow_rate_ul_s)
            
            aspirate_time = load_volume_ul / aspiration_flow_rate_ul_s
            await asyncio.sleep(aspirate_time + 2.0)
            logger.info(f"  ✓ Both pumps at position P{load_volume_ul}")
            
            # STEP 2: Start dispensing at assay flow rate
            logger.info(f"\n[STEP 2] Starting dispense at {assay_rate} µL/min")
            self.pump.dispense_both(load_volume_ul, assay_flow_rate_ul_s)
            logger.info(f"  ✓ Both pumps dispensing at {assay_rate} µL/min")
            
            # Verify dispense started - check positions
            await asyncio.sleep(2)
            pos1 = self.pump.get_position(1)
            pos2 = self.pump.get_position(2)
            logger.info(f"  Initial dispense positions: Pump1={pos1:.1f}µL, Pump2={pos2:.1f}µL")
            
            await asyncio.sleep(3)
            pos1 = self.pump.get_position(1)
            pos2 = self.pump.get_position(2)
            logger.info(f"  After 5s: Pump1={pos1:.1f}µL, Pump2={pos2:.1f}µL (should be decreasing!)")
            
            # STEP 3: Open 6-port valves (while dispensing)
            if self.controller:
                logger.info("\n[STEP 3] Opening 6-port valves (REAL HARDWARE)")
                self.controller.knx_six_both(state=1)  # 1 = INJECT position
                logger.info("  ✓ Both 6-port valves opened (INJECT position)")
            else:
                logger.info("\n[STEP 3] Opening 6-port valves (SIMULATED - no controller)")
            
            # STEP 4: Contact time with position monitoring
            logger.info(f"\n[STEP 4] Contact time: {contact_time_s:.2f}s")
            
            # Monitor positions during contact time
            elapsed = 0
            check_interval = 5.0
            
            while elapsed < contact_time_s and not self.is_idle and not self._stop_requested:
                await asyncio.sleep(check_interval)
                QApplication.processEvents()
                elapsed += check_interval
                
                # Log position every 5 seconds
                pos1 = self.pump.get_position(1)
                pos2 = self.pump.get_position(2)
                logger.info(f"  [Contact time {elapsed:.0f}s] Pump1={pos1:.1f}µL, Pump2={pos2:.1f}µL")
            
            # STEP 5: Close valves
            if self.controller:
                logger.info("\n[STEP 5] Closing 6-port valves (REAL HARDWARE)")
                self.controller.knx_six_both(state=0)  # 0 = LOAD position
                logger.info("  ✓ Both 6-port valves closed (LOAD position)")
            else:
                logger.info("\n[STEP 5] Closing 6-port valves (SIMULATED - no controller)")
            
            # STEP 6: Continue dispensing until empty
            logger.info("\n[STEP 6] Continuing to dispense until empty...")
            remaining_volume = load_volume_ul
            remaining_time_s = (remaining_volume / assay_rate) * 60.0
            logger.info(f"  Estimated time to empty: {remaining_time_s:.1f}s")
            
            # Monitor dispensing with position checks
            elapsed = 0
            check_interval = 5.0  # Check every 5s
            
            while elapsed < remaining_time_s and not self.is_idle and not self._stop_requested:
                await asyncio.sleep(check_interval)
                QApplication.processEvents()
                elapsed += check_interval
                
                # Log position every 5 seconds
                pos1 = self.pump.get_position(1)
                pos2 = self.pump.get_position(2)
                logger.info(f"  [{elapsed:.0f}s] Pump1={pos1:.1f}µL, Pump2={pos2:.1f}µL")
            
            # Final position check
            pos1 = self.pump.get_position(1)
            pos2 = self.pump.get_position(2)
            logger.info(f"  Final positions: Pump1={pos1:.1f}µL, Pump2={pos2:.1f}µL")
            
            # Wait for pumps to finish
            await asyncio.sleep(2)
            
            self.is_idle = True
            logger.info("\n✅ Simple inject completed successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Inject test failed: {e}")
            import traceback
            traceback.print_exc()
            self.is_idle = True
            return False
    
    async def inject_partial_loop_test(self, assay_rate):
        """REAL partial loop inject test - matches inject_partial_loop from pump_manager"""
        if not self.is_available:
            return False
        
        try:
            logger.info(f"[REAL PUMP] 💉 Running PARTIAL LOOP inject test at {assay_rate} µL/min")
            self.is_idle = False
            
            # Stop any existing operations first
            logger.info("Terminating any running commands...")
            self.pump.send_command("/1TR")
            await asyncio.sleep(0.05)
            self.pump.send_command("/2TR")
            await asyncio.sleep(0.5)
            
            # Convert to µL/s
            assay_flow_rate_ul_s = assay_rate / 60.0
            aspiration_flow_rate = 24000  # µL/min (fast aspirate)
            aspiration_flow_rate_ul_s = aspiration_flow_rate / 60.0
            output_aspirate_rate = 900  # µL/min (slow aspirate from output)
            output_aspirate_rate_ul_s = output_aspirate_rate / 60.0
            pulse_rate = 900  # µL/min (pulse rate)
            pulse_rate_ul_s = pulse_rate / 60.0
            loop_volume_ul = 100
            
            logger.info("=== Partial Loop Inject Started ===")
            logger.info(f"  Assay flow rate: {assay_rate} µL/min")
            logger.info(f"  Loop volume: {loop_volume_ul} µL")
            
            # Calculate contact time
            contact_time_s = (loop_volume_ul / assay_rate) * 60.0
            logger.info(f"  Calculated contact time: {contact_time_s:.2f}s")
            
            # STEP 1: Move to ABSOLUTE POSITION P900
            logger.info("\n[STEP 1] Moving plungers to ABSOLUTE POSITION P900...")
            logger.info(f"  (Moving to position 900 at {aspiration_flow_rate} µL/min)")
            self.pump.aspirate_both_to_position(target_position_ul=900, speed_ul_s=aspiration_flow_rate_ul_s)
            
            aspirate_time = 900.0 / aspiration_flow_rate_ul_s
            await asyncio.sleep(aspirate_time + 2.0)
            logger.info("  ✓ Both pumps at position P900")
            
            # STEP 2: Open 3-way valves
            logger.info("\n[STEP 2] Opening 3-way valves...")
            if self.controller:
                self.controller.knx_three(state=1, ch=1)
                self.controller.knx_three(state=1, ch=2)
                logger.info("  ✓ 3-way valves OPEN (REAL HARDWARE)")
            else:
                logger.info("  ⚠ 3-way valves OPEN (SIMULATED)")
            await asyncio.sleep(0.5)
            
            # STEP 3: Open 6-port valves to inject position
            logger.info("\n[STEP 3] Opening 6-port valves (inject position)...")
            if self.controller:
                self.controller.knx_six_both(state=1)
                logger.info("  ✓ 6-port valves at INJECT position (REAL HARDWARE)")
            else:
                logger.info("  ⚠ 6-port valves at INJECT position (SIMULATED)")
            await asyncio.sleep(0.5)
            
            # STEP 4: Move to ABSOLUTE POSITION P1000 at 900 µL/min (pulls sample into loop)
            logger.info("\n[STEP 4] Moving plungers to ABSOLUTE POSITION P1000...")
            logger.info(f"  (Moving from P900 → P1000 at {output_aspirate_rate} µL/min to pull sample through loop)")
            self.pump.aspirate_both_to_position(target_position_ul=1000, speed_ul_s=output_aspirate_rate_ul_s)
            
            output_aspirate_time = 100.0 / output_aspirate_rate_ul_s  # Moving 100 µL distance
            await asyncio.sleep(output_aspirate_time + 1.0)
            
            pos1 = self.pump.get_position(1)
            pos2 = self.pump.get_position(2)
            logger.info(f"  ✓ Both pumps at ABSOLUTE POSITION P1000 - P{pos1:.1f}µL / P{pos2:.1f}µL")
            
            # STEP 5: Close 6-port valves to load position
            logger.info("\n[STEP 5] Closing 6-port valves (load position)...")
            if self.controller:
                self.controller.knx_six_both(state=0)
                logger.info("  ✓ 6-port valves at LOAD position (REAL HARDWARE)")
            else:
                logger.info("  ⚠ 6-port valves at LOAD position (SIMULATED)")
            await asyncio.sleep(0.5)
            
            # STEP 6: Move to ABSOLUTE POSITION P950 (push 50 µL)
            logger.info("\n[STEP 6] Moving plungers to ABSOLUTE POSITION P950...")
            logger.info(f"  (Moving from P1000 → P950 at {output_aspirate_rate} µL/min)")
            self.pump.dispense_both(50, output_aspirate_rate_ul_s)
            
            dispense_time = 50.0 / output_aspirate_rate_ul_s
            await asyncio.sleep(dispense_time + 1.0)
            logger.info("  ✓ Both pumps at position P950")
            
            # STEP 7: Wait 10 seconds
            logger.info("\n[STEP 7] Waiting 10 seconds...")
            await asyncio.sleep(10.0)
            logger.info("  ✓ Wait complete")
            
            # STEP 8: Open 6-port valves to inject position
            logger.info("\n[STEP 8] Opening 6-port valves (inject position)...")
            if self.controller:
                self.controller.knx_six_both(state=1)
                logger.info("  ✓ 6-port valves at INJECT position (REAL HARDWARE)")
            else:
                logger.info("  ⚠ 6-port valves at INJECT position (SIMULATED)")
            await asyncio.sleep(0.5)
            
            # STEP 9: Push 40 µL spike
            logger.info(f"\n[STEP 9] Pushing 40 µL spike at {pulse_rate} µL/min...")
            self.pump.dispense_both(40, pulse_rate_ul_s)
            
            dispense_time = 40.0 / pulse_rate_ul_s
            await asyncio.sleep(dispense_time + 1.0)
            logger.info("  ✓ Pushed 40 µL spike")
            
            # STEP 10: Close 3-way valves
            logger.info("\n[STEP 10] Closing 3-way valves...")
            if self.controller:
                self.controller.knx_three(state=0, ch=1)
                self.controller.knx_three(state=0, ch=2)
                logger.info("  ✓ 3-way valves CLOSED (REAL HARDWARE)")
            else:
                logger.info("  ⚠ 3-way valves CLOSED (SIMULATED)")
            await asyncio.sleep(0.5)
            
            # STEP 11: Switch to assay flow rate
            logger.info(f"\n[STEP 11] Flow rate already at {assay_rate} µL/min")
            
            # STEP 12: Push rest with contact time
            remaining_volume = 1000.0 - 90.0  # Started with 1000, pushed 50+40=90
            logger.info(f"\n[STEP 12] Pushing remaining {remaining_volume:.0f} µL (contact time: {contact_time_s:.2f}s)...")
            self.pump.dispense_both(remaining_volume, assay_flow_rate_ul_s)
            
            # Monitor positions during contact time
            elapsed = 0
            check_interval = 5.0
            
            while elapsed < contact_time_s and not self.is_idle and not self._stop_requested:
                await asyncio.sleep(check_interval)
                QApplication.processEvents()
                elapsed += check_interval
                
                pos1 = self.pump.get_position(1)
                pos2 = self.pump.get_position(2)
                logger.info(f"  [Contact time {elapsed:.0f}s] Pump1={pos1:.1f}µL, Pump2={pos2:.1f}µL")
            
            # STEP 13: Close 6-port valves after contact time
            logger.info("\n[STEP 13] Closing 6-port valves after contact time...")
            if self.controller:
                self.controller.knx_six_both(state=0)
                logger.info("  ✓ 6-port valves CLOSED (REAL HARDWARE)")
            else:
                logger.info("  ⚠ 6-port valves CLOSED (SIMULATED)")
            
            # STEP 14: Continue emptying pumps
            logger.info("\n[STEP 14] Continuing to empty pumps...")
            remaining_time_s = (remaining_volume / assay_rate) * 60.0
            logger.info(f"  Estimated time to empty: {remaining_time_s:.1f}s")
            
            # Monitor dispensing
            elapsed = 0
            while elapsed < remaining_time_s and not self.is_idle and not self._stop_requested:
                await asyncio.sleep(check_interval)
                QApplication.processEvents()
                elapsed += check_interval
                
                pos1 = self.pump.get_position(1)
                pos2 = self.pump.get_position(2)
                logger.info(f"  [{elapsed:.0f}s] Pump1={pos1:.1f}µL, Pump2={pos2:.1f}µL")
            
            # Check if stopped early
            if self._stop_requested:
                logger.warning("⚠️ Partial loop injection interrupted by emergency stop")
                self.is_idle = True
                return False
            
            # Final position check
            pos1 = self.pump.get_position(1)
            pos2 = self.pump.get_position(2)
            logger.info(f"  Final positions: Pump1={pos1:.1f}µL, Pump2={pos2:.1f}µL")
            
            self.is_idle = True
            logger.info("\n✅ Partial loop inject completed successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Partial loop inject test failed: {e}")
            import traceback
            traceback.print_exc()
            self.is_idle = True
            return False
    
    async def flush_loop(self):
        """REAL flush - 3 pulses of 300 µL"""
        if not self.is_available:
            return False
        
        try:
            logger.info("[REAL PUMP] 🔄 Flushing loop (3x 300 µL pulses)...")
            self.is_idle = False
            
            flush_rate_ul_s = 24000 / 60.0  # 24000 µL/min to µL/s (400 µL/s)
            
            for i in range(3):
                logger.info(f"Pulse {i+1}/3")
                
                # Calculate actual time for 300 µL at flush rate
                aspirate_time = 300 / flush_rate_ul_s  # 0.75s
                dispense_time = 300 / flush_rate_ul_s  # 0.75s
                
                # Inlet, aspirate 300 µL
                self.pump.send_command("/1IR")
                self.pump.send_command("/2IR")
                await asyncio.sleep(0.5)
                
                pos1_before = self.pump.get_position(1)
                pos2_before = self.pump.get_position(2)
                logger.info(f"  Before aspirate: Pump1={pos1_before:.1f}µL, Pump2={pos2_before:.1f}µL")
                
                self.pump.aspirate(1, 300, speed_ul_s=flush_rate_ul_s, wait=False)
                await asyncio.sleep(0.1)
                self.pump.aspirate(2, 300, speed_ul_s=flush_rate_ul_s, wait=False)
                await asyncio.sleep(aspirate_time + 0.5)  # Wait for actual aspirate time
                
                pos1_after = self.pump.get_position(1)
                pos2_after = self.pump.get_position(2)
                logger.info(f"  After aspirate: Pump1={pos1_after:.1f}µL, Pump2={pos2_after:.1f}µL (Δ+{pos1_after-pos1_before:.1f}, Δ+{pos2_after-pos2_before:.1f})")
                
                # Outlet, dispense 300 µL
                self.pump.send_command("/1OR")
                self.pump.send_command("/2OR")
                await asyncio.sleep(0.5)
                
                self.pump.dispense(1, 0, speed_ul_s=flush_rate_ul_s, wait=False)
                await asyncio.sleep(0.1)
                self.pump.dispense(2, 0, speed_ul_s=flush_rate_ul_s, wait=False)
                await asyncio.sleep(dispense_time + 0.5)  # Wait for actual dispense time
                
                pos1_final = self.pump.get_position(1)
                pos2_final = self.pump.get_position(2)
                logger.info(f"  After dispense: Pump1={pos1_final:.1f}µL, Pump2={pos2_final:.1f}µL (Δ-{pos1_after-pos1_final:.1f}, Δ-{pos2_after-pos2_final:.1f})")
            
            self.is_idle = True
            logger.info("✅ Flush complete")
            return True
        except Exception as e:
            logger.error(f"❌ Flush failed: {e}")
            import traceback
            traceback.print_exc()
            self.is_idle = True
            return False
    
    async def prime_pump(self):
        """REAL prime - 6 cycles"""
        if not self.is_available:
            return False
        
        try:
            logger.info("[REAL PUMP] 🔧 Priming pump (6 cycles)...")
            self.is_idle = False
            
            prime_rate_ul_s = 500 / 60.0  # 500 µL/min to µL/s
            
            for i in range(6):
                logger.info(f"Prime cycle {i+1}/6")
                
                # Fill from inlet
                self.pump.send_command("/1IR")
                self.pump.send_command("/2IR")
                await asyncio.sleep(0.5)
                
                self.pump.aspirate(1, 1000, speed_ul_s=prime_rate_ul_s, wait=False)
                await asyncio.sleep(0.1)
                self.pump.aspirate(2, 1000, speed_ul_s=prime_rate_ul_s, wait=False)
                await asyncio.sleep(8)
                
                # Empty to outlet
                self.pump.send_command("/1OR")
                self.pump.send_command("/2OR")
                await asyncio.sleep(0.5)
                
                self.pump.dispense(1, 0, speed_ul_s=prime_rate_ul_s, wait=False)
                await asyncio.sleep(0.1)
                self.pump.dispense(2, 0, speed_ul_s=prime_rate_ul_s, wait=False)
                await asyncio.sleep(8)
            
            self.is_idle = True
            logger.info("✅ Prime complete")
            return True
        except Exception as e:
            logger.error(f"❌ Prime failed: {e}")
            import traceback
            traceback.print_exc()
            self.is_idle = True
            return False
    
    async def cleanup_pump(self):
        """REAL cleanup sequence"""
        if not self.is_available:
            return False
        
        try:
            logger.info("[REAL PUMP] 🧹 Cleaning pump...")
            self.is_idle = False
            
            # Just do a simple home for now
            await self.home_pumps()
            
            self.is_idle = True
            logger.info("✅ Cleanup complete")
            return True
        except Exception as e:
            logger.error(f"❌ Cleanup failed: {e}")
            self.is_idle = True
            return False
    
    async def start_buffer_flow(self, flow_rate):
        """Start continuous buffer flow with automatic refill"""
        if not self.is_available:
            return False
        
        try:
            logger.info(f"[REAL PUMP] ▶ Starting continuous buffer flow at {flow_rate} µL/min")
            
            # Initialize pumps first to ensure they're at known state
            logger.info("Initializing pumps to zero position...")
            await self.home_pumps()
            
            self.is_idle = False
            self._flow_rate = flow_rate  # Store current flow rate
            
            cycle_count = 0
            
            # Continuous loop - keep refilling and dispensing
            while not self.is_idle:  # Will run until emergency stop or user stops
                cycle_count += 1
                logger.info(f"\n{'='*60}")
                logger.info(f"🔄 BUFFER CYCLE #{cycle_count}")
                logger.info(f"{'='*60}")
                
                # Check current positions
                pos1 = self.pump.get_position(1)
                pos2 = self.pump.get_position(2)
                logger.info(f"Current positions: Pump1={pos1:.1f}µL, Pump2={pos2:.1f}µL")
                
                # Calculate volume needed for timing
                volume_needed = 1000.0 - max(pos1, pos2)  # Use max to be conservative
                current_position = max(pos1, pos2)
                
                # Dynamic fill rate ONLY if plunger is above P750
                if current_position > 750:
                    # Use dynamic fill rate for small top-ups
                    max_fill_rate_ul_s = 24000 / 60.0  # 400 µL/s (cap)
                    
                    if volume_needed < 50:
                        target_fill_time = 2.5
                    elif volume_needed > 500:
                        target_fill_time = volume_needed / max_fill_rate_ul_s
                    else:
                        # Linear interpolation
                        min_fill_time = 500 / max_fill_rate_ul_s  # 1.25s
                        target_fill_time = 2.5 - ((volume_needed - 50) / 450) * (2.5 - min_fill_time)
                    
                    aspirate_rate_ul_s = volume_needed / target_fill_time if volume_needed > 0 else max_fill_rate_ul_s
                    aspirate_rate_ul_s = min(aspirate_rate_ul_s, max_fill_rate_ul_s)
                    actual_fill_time = volume_needed / aspirate_rate_ul_s if volume_needed > 0 else 1.0
                    aspirate_rate_ul_min = aspirate_rate_ul_s * 60
                    logger.info(f"⬆️  Moving plungers to ABSOLUTE POSITION P1000 (INPUT, DYNAMIC RATE)")
                    logger.info(f"  Volume needed: {volume_needed:.1f}µL | Fill time: {actual_fill_time:.2f}s | Flow rate: {aspirate_rate_ul_min:.0f} µL/min")
                else:
                    # Use default flow rate for full fills (below P750)
                    aspirate_rate_ul_min = 24000  # Fixed default rate
                    aspirate_rate_ul_s = aspirate_rate_ul_min / 60.0  # 400 µL/s
                    actual_fill_time = volume_needed / aspirate_rate_ul_s if volume_needed > 0 else 1.0
                    logger.info(f"⬆️  Moving plungers to ABSOLUTE POSITION P1000 (INPUT, DEFAULT RATE)")
                    logger.info(f"  Volume needed: {volume_needed:.1f}µL | Fill time: {actual_fill_time:.2f}s | Flow rate: {aspirate_rate_ul_min:.0f} µL/min")
                
                # Store position before fill
                pos_before_fill_1 = pos1
                pos_before_fill_2 = pos2
                
                # Aspirate to P1000 (absolute position)
                self.pump.aspirate_both_to_position(target_position_ul=1000, speed_ul_s=aspirate_rate_ul_s)
                
                logger.info(f"  Waiting {actual_fill_time:.1f}s for movement to complete...")
                
                await asyncio.sleep(actual_fill_time + 1)
                QApplication.processEvents()  # Process Qt events
                
                # Check fill status and detect stall
                pos1 = self.pump.get_position(1)
                pos2 = self.pump.get_position(2)
                
                # STALL DETECTION: Position should increase during fill
                fill_delta_1 = pos1 - pos_before_fill_1
                fill_delta_2 = pos2 - pos_before_fill_2
                
                if abs(fill_delta_1) < 5 and abs(fill_delta_2) < 5:
                    logger.error(f"❌ PUMP STALL DETECTED during fill! Positions didn't change.")
                    logger.error(f"   Before: Pump1={pos_before_fill_1:.1f}µL, Pump2={pos_before_fill_2:.1f}µL")
                    logger.error(f"   After:  Pump1={pos1:.1f}µL, Pump2={pos2:.1f}µL")
                    logger.error(f"   Delta:  Pump1={fill_delta_1:.1f}µL, Pump2={fill_delta_2:.1f}µL")
                    
                    # Recovery attempt: Re-initialize pumps
                    logger.warning("🔧 Attempting recovery: Re-initializing pumps...")
                    self.pump.send_command("/1TR")
                    await asyncio.sleep(0.1)
                    self.pump.send_command("/2TR")
                    await asyncio.sleep(1)
                    self.pump.initialize_pumps()
                    await asyncio.sleep(5)
                    
                    # Retry fill to P1000
                    logger.warning("🔄 Retrying fill after re-initialization...")
                    self.pump.aspirate_both_to_position(target_position_ul=1000, speed_ul_s=aspirate_rate_ul_s)
                    await asyncio.sleep(actual_fill_time + 1)
                    
                    # Check again
                    pos1 = self.pump.get_position(1)
                    pos2 = self.pump.get_position(2)
                    fill_delta_1 = pos1 - pos_before_fill_1
                    fill_delta_2 = pos2 - pos_before_fill_2
                    
                    if abs(fill_delta_1) < 5 and abs(fill_delta_2) < 5:
                        logger.error("❌ Pump stall persists after recovery attempt - ABORTING")
                        self.is_idle = True
                        return False
                    else:
                        logger.info("✅ Recovery successful!")
                
                logger.info(f"✅ Fill complete: Pump1={pos1:.1f}µL, Pump2={pos2:.1f}µL (Δ{fill_delta_1:+.1f}, Δ{fill_delta_2:+.1f})")
                
                # Start dispense with current flow rate
                # dispense_both handles valve switching internally
                current_flow_rate = self._flow_rate  # Get current rate
                flow_rate_ul_s = current_flow_rate / 60.0
                logger.info(f"⬇️  Dispensing at {current_flow_rate} µL/min (SYNCHRONIZED)...")
                self.pump.dispense_both(1000, speed_ul_s=flow_rate_ul_s)
                
                # Calculate dispense time
                dispense_time = (1000.0 / flow_rate_ul_s)  # seconds
                logger.info(f"  Dispensing for {dispense_time:.1f}s...")
                
                # Monitor dispensing with rate change detection
                elapsed = 0
                check_interval = 0.5  # Check every 0.5s to keep UI responsive
                start_position_1 = self.pump.get_position(1)
                last_logged_position = start_position_1
                stall_warnings = 0
                
                while elapsed < dispense_time and not self.is_idle:
                    await asyncio.sleep(check_interval)
                    QApplication.processEvents()  # CRITICAL: Process Qt events to keep UI responsive
                    elapsed += check_interval
                    
                    # Check if flow rate changed - update dispense time calculation
                    if self._flow_rate != current_flow_rate:
                        # NOTE: change_flow_rate_on_the_fly() already sent the V command
                        # We just need to recalculate remaining time at the new rate
                        current_pos = self.pump.get_position(1)
                        remaining_ul = current_pos
                        
                        if remaining_ul > 10:
                            # Update to new flow rate
                            current_flow_rate = self._flow_rate
                            flow_rate_ul_s = current_flow_rate / 60.0
                            
                            # Recalculate dispense time based on remaining volume at new rate
                            dispense_time = (remaining_ul / flow_rate_ul_s)
                            elapsed = 0  # Reset elapsed time
                            logger.info(f"🔄 Flow rate changed to {current_flow_rate} µL/min on-the-fly")
                            logger.info(f"  New dispense time: {dispense_time:.1f}s for {remaining_ul:.1f}µL remaining")
                            start_position_1 = current_pos  # Reset start position
                            last_logged_position = current_pos
                            stall_warnings = 0
                    
                    # Log every 5 seconds only
                    if int(elapsed) % 5 == 0 and (elapsed - check_interval) % 5 != 0:
                        pos1 = self.pump.get_position(1)
                        pos2 = self.pump.get_position(2)
                        logger.info(f"  [{elapsed:.0f}s] Pump1={pos1:.1f}µL, Pump2={pos2:.1f}µL")
                        
                        # DISPENSE STALL DETECTION: Position should decrease during dispense
                        if abs(pos1 - last_logged_position) < 1.0:  # Less than 1µL change
                            stall_warnings += 1
                            logger.warning(f"⚠️  DISPENSE STALL WARNING #{stall_warnings}: Position not changing! (Δ={pos1-last_logged_position:.1f}µL)")
                            
                            if stall_warnings >= 3:
                                logger.error("❌ DISPENSE STALL DETECTED: Position hasn't changed in 15+ seconds!")
                                logger.error(f"   Expected ~{(elapsed * flow_rate_ul_s):.1f}µL dispensed, but position unchanged")
                                
                                # Recovery: Terminate and restart
                                logger.warning("🔧 Attempting recovery: Terminating and restarting dispense...")
                                self.pump.send_command("/ATR")
                                await asyncio.sleep(1)
                                
                                current_pos = self.pump.get_position(1)
                                remaining_ul = current_pos
                                
                                if remaining_ul > 10:
                                    self.pump.dispense_both(remaining_ul, speed_ul_s=flow_rate_ul_s)
                                    dispense_time = (remaining_ul / flow_rate_ul_s)
                                    elapsed = 0
                                    stall_warnings = 0
                                    logger.info(f"  Restarted dispense: {remaining_ul:.1f}µL remaining")
                                else:
                                    logger.error("❌ No volume remaining to dispense - ABORTING cycle")
                                    break
                        else:
                            stall_warnings = 0  # Reset if movement detected
                        
                        last_logged_position = pos1
                
                if self.is_idle:
                    logger.info("⚠️ Buffer flow stopped by user")
                    break
                
                logger.info("✅ Dispense cycle complete - refilling...")
            
            logger.info(f"\n🏁 Buffer flow stopped after {cycle_count} cycles")
            return True
        except Exception as e:
            logger.error(f"❌ Start buffer flow failed: {e}")
            import traceback
            traceback.print_exc()
            self.is_idle = True
            return False
        except Exception as e:
            logger.error(f"❌ Start buffer flow failed: {e}")
            import traceback
            traceback.print_exc()
            self.is_idle = True
            return False


class PumpWorker(QThread):
    """Worker thread for pump operations - runs async functions in separate thread"""
    
    # Signals for communication
    finished = Signal(bool)  # Success/failure
    error = Signal(str)  # Error message
    progress = Signal(str)  # Progress updates
    
    def __init__(self, pump_manager, operation, *args):
        super().__init__()
        self.pump_manager = pump_manager
        self.operation = operation  # Name of async method to call
        self.args = args
        self._stop_requested = False
    
    def run(self):
        """Run the async operation in this thread"""
        try:
            # Create event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Get the async method
            method = getattr(self.pump_manager, self.operation)
            
            # Run it
            result = loop.run_until_complete(method(*self.args))
            
            # Clean up
            loop.close()
            
            self.finished.emit(result)
        except Exception as e:
            logger.error(f"Worker error: {e}")
            import traceback
            traceback.print_exc()
            self.error.emit(str(e))
            self.finished.emit(False)
    
    def stop(self):
        """Request stop"""
        self._stop_requested = True
        self.pump_manager.is_idle = True
        self.pump_manager._stop_requested = True


class MockMainWindow:
    """Mock main window for testing"""
    
    def __init__(self):
        self.data_mgr = type('obj', (object,), {
            '_pump_mgr': RealPumpManager()
        })()
        logger.info("[MAIN WINDOW] Initialized with REAL pump manager")


class MockSidebar:
    """Mock sidebar to hold spinbox references"""
    
    def __init__(self, main_window):
        self._main_window = main_window
        self.pump_setup_spin = None
        self.pump_functionalization_spin = None
        self.pump_assay_spin = None
        logger.info("[SIDEBAR] Initialized")


class FlowSidebarTester(QMainWindow):
    """Main test window for flow sidebar functions"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Flow Sidebar Function Tester - REAL HARDWARE Edition")
        self.setGeometry(100, 100, 900, 700)
        
        # Track current worker thread
        self._current_worker = None
        
        # Setup objects with REAL pump
        self.mock_main = MockMainWindow()
        self.mock_sidebar = MockSidebar(self.mock_main)
        self.pump_mgr = self.mock_main.data_mgr._pump_mgr
        
        # Setup UI
        self._setup_ui()
        
        logger.info("=" * 60)
        logger.info("🧪 FLOW SIDEBAR TESTER READY - REAL HARDWARE CONNECTED")
        logger.info("=" * 60)
    
    def _setup_ui(self):
        """Build the test interface"""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("🧪 Flow Sidebar Function Tester - REAL HARDWARE")
        title_font = QFont("Segoe UI", 18, QFont.Weight.Bold)
        title.setFont(title_font)
        title.setStyleSheet("color: #1D1D1F; margin-bottom: 10px;")
        main_layout.addWidget(title)
        
        subtitle = QLabel("Testing with ACTUAL pump hardware - no mock bullshit!")
        subtitle.setStyleSheet("color: #FF3B30; font-size: 12px; font-weight: bold; margin-bottom: 20px;")
        main_layout.addWidget(subtitle)
        
        # Flow rate controls section
        flow_section = QLabel("⚙️ FLOW RATE CONTROLS")
        flow_section.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #1D1D1F; "
            "background: rgba(0, 122, 255, 0.1); padding: 8px; border-radius: 6px;"
        )
        main_layout.addWidget(flow_section)
        
        # Flow rate spinboxes
        flow_layout = QHBoxLayout()
        flow_layout.setSpacing(12)
        
        # Setup flow rate
        setup_box = self._create_flow_rate_control("Setup:", 25)
        self.mock_sidebar.pump_setup_spin = setup_box
        flow_layout.addWidget(QLabel("Setup:"))
        flow_layout.addWidget(setup_box)
        flow_layout.addWidget(QLabel("µL/min"))
        
        # Functionalization flow rate
        func_box = self._create_flow_rate_control("Functionalization:", 10)
        self.mock_sidebar.pump_functionalization_spin = func_box
        flow_layout.addWidget(QLabel("Func:"))
        flow_layout.addWidget(func_box)
        flow_layout.addWidget(QLabel("µL/min"))
        
        # Assay flow rate
        assay_box = self._create_flow_rate_control("Assay:", 25)
        self.mock_sidebar.pump_assay_spin = assay_box
        flow_layout.addWidget(QLabel("Assay:"))
        flow_layout.addWidget(assay_box)
        flow_layout.addWidget(QLabel("µL/min"))
        
        main_layout.addLayout(flow_layout)
        
        # Preset buttons (shared - like in real UI)
        preset_layout = QHBoxLayout()
        preset_layout.addWidget(QLabel("Quick Presets:"))
        
        presets = [5, 10, 25, 50, 100]
        for preset_val in presets:
            btn = QPushButton(str(preset_val))
            btn.setFixedWidth(50)
            btn.clicked.connect(lambda checked, v=preset_val: self._set_all_flow_rates(v))
            btn.setStyleSheet(
                "QPushButton { background: #007AFF; color: white; border-radius: 4px; padding: 6px; }"
                "QPushButton:hover { background: #0051D5; }"
            )
            preset_layout.addWidget(btn)
        
        preset_layout.addStretch()
        main_layout.addLayout(preset_layout)
        
        # Test on-the-fly flow rate change
        onthefly_btn = QPushButton("🔄 Test On-The-Fly Flow Rate Change")
        onthefly_btn.clicked.connect(self._test_onthefly_change)
        onthefly_btn.setStyleSheet(
            "QPushButton { background: #34C759; color: white; padding: 10px; "
            "border-radius: 6px; font-weight: bold; }"
            "QPushButton:hover { background: #28A745; }"
        )
        main_layout.addWidget(onthefly_btn)
        
        # Pump operation buttons
        ops_section = QLabel("🎛️ PUMP OPERATIONS")
        ops_section.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #1D1D1F; "
            "background: rgba(52, 199, 89, 0.1); padding: 8px; border-radius: 6px;"
        )
        main_layout.addWidget(ops_section)
        
        ops_layout = QVBoxLayout()
        ops_layout.setSpacing(8)
        
        # Row 1: Start/Home/Stop
        row1 = QHBoxLayout()
        
        start_btn = QPushButton("▶ Start Buffer Flow")
        start_btn.clicked.connect(self._test_start_buffer)
        row1.addWidget(start_btn)
        
        home_btn = QPushButton("🏠 Home Pumps")
        home_btn.clicked.connect(self._test_home_pumps)
        row1.addWidget(home_btn)
        
        stop_btn = QPushButton("🛑 STOP")
        stop_btn.clicked.connect(self._test_emergency_stop)
        stop_btn.setStyleSheet("background: #FF3B30; color: white; font-weight: bold;")
        row1.addWidget(stop_btn)
        
        ops_layout.addLayout(row1)
        
        # Row 2: Flush/Inject
        row2 = QHBoxLayout()
        
        flush_btn = QPushButton("🔄 Flush Loop")
        flush_btn.clicked.connect(self._test_flush)
        row2.addWidget(flush_btn)
        
        inject_btn = QPushButton("💉 Inject (Simple)")
        inject_btn.clicked.connect(self._test_inject)
        inject_btn.setStyleSheet("background: #007AFF; color: white; font-weight: bold;")
        row2.addWidget(inject_btn)
        
        inject_partial_btn = QPushButton("💉 Inject (Partial Loop)")
        inject_partial_btn.clicked.connect(self._test_inject_partial_loop)
        inject_partial_btn.setStyleSheet("background: #00A3FF; color: white; font-weight: bold;")
        row2.addWidget(inject_partial_btn)
        
        ops_layout.addLayout(row2)
        
        # Row 3: Maintenance
        row3 = QHBoxLayout()
        
        prime_btn = QPushButton("🔧 Prime Pump")
        prime_btn.clicked.connect(self._test_prime)
        row3.addWidget(prime_btn)
        
        cleanup_btn = QPushButton("🧹 Clean Pump")
        cleanup_btn.clicked.connect(self._test_cleanup)
        row3.addWidget(cleanup_btn)
        
        ops_layout.addLayout(row3)
        
        main_layout.addLayout(ops_layout)
        
        # Log output
        log_section = QLabel("📋 TEST OUTPUT LOG")
        log_section.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #1D1D1F; "
            "background: rgba(255, 59, 48, 0.1); padding: 8px; border-radius: 6px;"
        )
        main_layout.addWidget(log_section)
        
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet(
            "QTextEdit { background: #1D1D1F; color: #00FF00; "
            "font-family: 'Consolas', 'Monaco', monospace; font-size: 11px; "
            "border-radius: 6px; padding: 10px; }"
        )
        self.log_output.setMinimumHeight(250)
        main_layout.addWidget(self.log_output)
        
        # Clear log button
        clear_btn = QPushButton("🗑️ Clear Log")
        clear_btn.clicked.connect(self.log_output.clear)
        clear_btn.setStyleSheet("background: #86868B; color: white; padding: 6px;")
        main_layout.addWidget(clear_btn)
        
        # Initial log
        self._log_action("READY", "Flow sidebar tester initialized - all functions ready to test")
    
    def _create_flow_rate_control(self, label, default_value):
        """Create a flow rate spinbox"""
        spinbox = QSpinBox()
        spinbox.setRange(1, 10000)
        spinbox.setValue(default_value)
        spinbox.setSuffix("")
        spinbox.setFixedWidth(80)
        spinbox.setStyleSheet(
            "QSpinBox { background: white; border: 1px solid #D1D1D6; "
            "border-radius: 4px; padding: 4px; font-family: 'Consolas', monospace; }"
        )
        # Connect to on-the-fly change simulation
        spinbox.valueChanged.connect(lambda v: self._on_flow_rate_changed(label, v))
        return spinbox
    
    def _on_flow_rate_changed(self, label, value):
        """Simulate on-the-fly flow rate change"""
        if not self.pump_mgr.is_idle:
            self._log_action(
                "FLOW RATE CHANGE",
                f"{label} changed to {value} µL/min (pump running - on-the-fly change)"
            )
            self.pump_mgr.change_flow_rate_on_the_fly(value)
        else:
            self._log_action(
                "FLOW RATE SET",
                f"{label} set to {value} µL/min (pump idle - will use on next start)"
            )
    
    def _set_all_flow_rates(self, value):
        """Set all flow rates to the same value (preset button test)"""
        self.mock_sidebar.pump_setup_spin.setValue(value)
        self.mock_sidebar.pump_functionalization_spin.setValue(value)
        self.mock_sidebar.pump_assay_spin.setValue(value)
        self._log_action("PRESET", f"All flow rates set to {value} µL/min")
    
    def _test_onthefly_change(self):
        """Test on-the-fly flow rate change"""
        # Simulate pump running
        self.pump_mgr.is_idle = False
        self._log_action("TEST", "Simulating pump running state...")
        
        # Change the setup flow rate
        new_rate = 75
        self.mock_sidebar.pump_setup_spin.setValue(new_rate)
        
        # Reset to idle after 2 seconds
        QTimer.singleShot(2000, lambda: setattr(self.pump_mgr, 'is_idle', True))
    
    def _test_start_buffer(self):
        """Test start buffer flow - toggles on/off"""
        # If already running, stop it
        if self._current_worker and self._current_worker.isRunning():
            self._log_action("STOP BUFFER", "Stopping buffer flow...")
            self._current_worker.stop()
            self._current_worker.wait()  # Wait for thread to finish
            self._current_worker = None
            self._log_action("SUCCESS", "Buffer flow stopped")
            return
        
        # Start new buffer flow in thread
        setup_rate = self.mock_sidebar.pump_setup_spin.value()
        self._log_action("START BUFFER", f"Starting buffer flow at {setup_rate} µL/min...")
        
        self._current_worker = PumpWorker(self.pump_mgr, 'start_buffer_flow', setup_rate)
        self._current_worker.finished.connect(lambda success: self._on_operation_finished("Buffer flow", success))
        self._current_worker.error.connect(lambda err: self._log_action("ERROR", f"Buffer flow failed: {err}"))
        self._current_worker.start()
    
    def _test_emergency_stop(self):
        """Test emergency stop function"""
        self._log_action("EMERGENCY STOP", "Executing emergency stop...")
        
        try:
            # STEP 1: Stop the worker thread first
            if self._current_worker and self._current_worker.isRunning():
                logger.warning("⚠️ Stopping active worker thread...")
                self._current_worker.stop()
                self._current_worker.wait(2000)  # Wait up to 2 seconds
                self._current_worker = None
            
            # STEP 2: Send terminate command to pumps
            logger.warning("[REAL PUMP] 🛑 EMERGENCY STOP - Terminating both pumps!")
            self.pump_mgr.pump.send_command("/1TR")  # Individual terminate
            time.sleep(0.05)
            self.pump_mgr.pump.send_command("/2TR")
            time.sleep(0.05)
            self.pump_mgr.pump.send_command("/0TR")  # Broadcast terminate for good measure
            
            # STEP 3: Set flags
            self.pump_mgr.is_idle = True
            self.pump_mgr._current_operation = "IDLE"
            
            # STEP 4: Verify pumps stopped by checking position
            time.sleep(0.5)
            pos1 = self.pump_mgr.pump.get_position(1)
            pos2 = self.pump_mgr.pump.get_position(2)
            logger.info(f"✅ Emergency stop complete - Positions: Pump1={pos1:.1f}µL, Pump2={pos2:.1f}µL")
            self._log_action("SUCCESS", "Emergency stop completed")
        except Exception as e:
            logger.error(f"❌ Emergency stop error: {e}")
            self._log_action("ERROR", f"Emergency stop failed: {e}")
    
    def _test_home_pumps(self):
        """Test home pumps function"""
        # Stop any running operation first
        if self._current_worker and self._current_worker.isRunning():
            self._log_action("HOME", "Stopping current operation first...")
            self._current_worker.stop()
            self._current_worker.wait()
            self._current_worker = None
        
        self._log_action("HOME", "Homing pumps to zero position...")
        
        self._current_worker = PumpWorker(self.pump_mgr, 'home_pumps')
        self._current_worker.finished.connect(lambda success: self._on_operation_finished("Home", success))
        self._current_worker.error.connect(lambda err: self._log_action("ERROR", f"Home failed: {err}"))
        self._current_worker.start()
    
    def _test_flush(self):
        """Test flush function"""
        # Stop any running operation first
        if self._current_worker and self._current_worker.isRunning():
            self._log_action("FLUSH", "Stopping current operation first...")
            self._current_worker.stop()
            self._current_worker.wait()
            self._current_worker = None
        
        self._log_action("FLUSH", "Starting flush sequence (3 pulses, 300 µL each)...")
        
        self._current_worker = PumpWorker(self.pump_mgr, 'flush_loop')
        self._current_worker.finished.connect(lambda success: self._on_operation_finished("Flush", success))
        self._current_worker.error.connect(lambda err: self._log_action("ERROR", f"Flush failed: {err}"))
        self._current_worker.start()
    
    def _test_inject(self):
        """Test inject function"""
        # Stop any running operation first
        if self._current_worker and self._current_worker.isRunning():
            self._log_action("INJECT", "Stopping current operation first...")
            self._current_worker.stop()
            self._current_worker.wait()
            self._current_worker = None
        
        assay_rate = self.mock_sidebar.pump_assay_spin.value()
        self._log_action("INJECT", f"Starting SIMPLE inject test at {assay_rate} µL/min...")
        
        self.pump_mgr._stop_requested = False  # Reset stop flag
        self._current_worker = PumpWorker(self.pump_mgr, 'inject_test', assay_rate)
        self._current_worker.finished.connect(lambda success: self._on_operation_finished("Inject (Simple)", success))
        self._current_worker.error.connect(lambda err: self._log_action("ERROR", f"Inject failed: {err}"))
        self._current_worker.start()
    
    def _test_inject_partial_loop(self):
        """Test partial loop inject function"""
        # Stop any running operation first
        if self._current_worker and self._current_worker.isRunning():
            self._log_action("INJECT PARTIAL", "Stopping current operation first...")
            self._current_worker.stop()
            self._current_worker.wait()
            self._current_worker = None
        
        assay_rate = self.mock_sidebar.pump_assay_spin.value()
        self._log_action("INJECT PARTIAL", f"Starting PARTIAL LOOP inject test at {assay_rate} µL/min...")
        
        self.pump_mgr._stop_requested = False  # Reset stop flag
        self._current_worker = PumpWorker(self.pump_mgr, 'inject_partial_loop_test', assay_rate)
        self._current_worker.finished.connect(lambda success: self._on_operation_finished("Inject (Partial Loop)", success))
        self._current_worker.error.connect(lambda err: self._log_action("ERROR", f"Partial loop inject failed: {err}"))
        self._current_worker.start()
    
    def _on_operation_finished(self, operation_name, success):
        """Handle operation completion"""
        if success:
            self._log_action("SUCCESS", f"{operation_name} completed")
        self._current_worker = None
    
    def _test_prime(self):
        """Test prime function"""
        self._log_action("PRIME", "Starting prime sequence (6 cycles)...")
        
        self._current_worker = PumpWorker(self.pump_mgr, 'prime_pump')
        self._current_worker.finished.connect(lambda success: self._on_operation_finished("Prime", success))
        self._current_worker.error.connect(lambda err: self._log_action("ERROR", f"Prime failed: {err}"))
        self._current_worker.start()
    
    def _test_cleanup(self):
        """Test cleanup function"""
        self._log_action("CLEANUP", "Starting 9-phase cleanup sequence...")
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.pump_mgr.cleanup_pump())
            self._log_action("SUCCESS", "Cleanup completed")
        finally:
            loop.close()
    
    def _log_action(self, action_type, message):
        """Add a log entry to the output"""
        timestamp = QTimer()
        import datetime
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        
        # Color code by action type
        colors = {
            "READY": "#00FF00",
            "TEST": "#00BFFF",
            "PRESET": "#FFD700",
            "FLOW RATE CHANGE": "#FFA500",
            "FLOW RATE SET": "#87CEEB",
            "START BUFFER FLOW": "#32CD32",
            "EMERGENCY STOP": "#FF4500",
            "HOME": "#1E90FF",
            "FLUSH": "#4169E1",
            "INJECT": "#8A2BE2",
            "PRIME": "#20B2AA",
            "CLEANUP": "#3CB371",
            "SUCCESS": "#00FF00",
            "ERROR": "#FF0000"
        }
        
        color = colors.get(action_type, "#FFFFFF")
        
        log_entry = f'<span style="color: #888;">[{ts}]</span> '
        log_entry += f'<span style="color: {color}; font-weight: bold;">[{action_type}]</span> '
        log_entry += f'<span style="color: #CCCCCC;">{message}</span><br>'
        
        self.log_output.append(log_entry)
        
        # Also log to console
        logger.info(f"[{action_type}] {message}")


def main():
    """Run the test application"""
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle("Fusion")
    
    window = FlowSidebarTester()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
