"""Pump Manager

Manages pump operations (prime, cleanup, run_buffer) for integration with UI,
calibration, and acquisition coordinators.

Provides high-level pump operations callable from multiple application contexts:
- UI buttons (Flow tab "Prime Pump", etc.)
- Calibration workflows (pump present → run prime/cleanup)
- Acquisition coordinators (run_buffer during experiments)
- Maintenance scripts (standalone operations)

Author: Affilabs
"""

from __future__ import annotations

import asyncio
import time
from enum import Enum
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

from affilabs.utils.logger import logger

if TYPE_CHECKING:
    from affilabs.core.hardware_manager import HardwareManager


class PumpOperation(Enum):
    """Pump operation types."""

    IDLE = "idle"
    PRIMING = "priming"
    CLEANING = "cleaning"
    RUNNING_BUFFER = "running_buffer"
    INJECTING = "injecting"
    EMERGENCY_STOP = "emergency_stop"


class PumpManager(QObject):
    """Manages high-level pump operations."""

    # Signals
    operation_started = Signal(str)  # operation_name
    operation_progress = Signal(str, int, str)  # operation, progress_percent, message
    operation_completed = Signal(str, bool)  # operation_name, success
    error_occurred = Signal(str, str)  # operation_name, error_message

    # Status update signals for UI
    status_updated = Signal(
        str, float, float, float, float
    )  # status, flow_rate, plunger_pos, contact_time_current, contact_time_expected

    def __init__(self, hardware_manager: HardwareManager) -> None:
        """Initialize pump manager.

        Args:
            hardware_manager: Reference to hardware manager for pump/controller access

        """
        super().__init__()
        self.hardware_manager = hardware_manager
        self._current_operation = PumpOperation.IDLE
        self._shutdown_requested = False

        logger.info("PumpManager initialized")

    @property
    def is_available(self) -> bool:
        """Check if pump hardware is available."""
        return self.hardware_manager.pump is not None

    @property
    def is_idle(self) -> bool:
        """Check if pump is currently idle."""
        return self._current_operation == PumpOperation.IDLE

    @property
    def current_operation(self) -> PumpOperation:
        """Get current pump operation."""
        return self._current_operation

    async def prime_pump(
        self,
        cycles: int = 6,
        volume_ul: float = 1000.0,
        aspirate_speed: float = 24000.0,
        dispense_speed: float = 5000.0,
    ) -> bool:
        """Prime BOTH pumps with multiple aspirate-dispense cycles.

        Priming sequence:
        - Cycles 1-2: Standard priming
        - Before cycle 3: Open both load valves (6-port)
        - Cycles 3-4: Prime with load valves open
        - Before cycle 5: Open channel valves (3-way)
        - Cycles 5-6: Prime with all valves open

        Args:
            cycles: Number of aspirate-dispense cycles (default: 6)
            volume_ul: Volume per cycle in µL (default: 1000)
            aspirate_speed: Aspiration speed in µL/min (default: 24000)
            dispense_speed: Dispense speed in µL/min (default: 5000)

        Returns:
            True if priming completed successfully

        """
        if not self.is_available:
            self.error_occurred.emit("prime", "No pump hardware available")
            return False

        if not self.is_idle:
            self.error_occurred.emit(
                "prime",
                f"Cannot start prime - pump is {self._current_operation.value}",
            )
            return False

        self._current_operation = PumpOperation.PRIMING
        self._shutdown_requested = False
        self.operation_started.emit("prime")

        try:
            logger.info("=== Dual Pump Priming Started ===")
            logger.info(f"  Cycles: {cycles}")
            logger.info(f"  Volume: {volume_ul} uL per pump")
            logger.info(f"  Aspirate: {aspirate_speed} uL/min")
            logger.info(f"  Dispense: {dispense_speed} uL/min")

            pump = self.hardware_manager.pump
            ctrl = self.hardware_manager._ctrl_raw

            # Initialize pumps before priming
            logger.info("🔧 Initializing pumps to zero position...")
            self.operation_progress.emit("prime", 0, "Initializing pumps...")
            pump._pump.pump.initialize_pumps()
            logger.info("✅ Pumps initialized and ready")

            aspirate_speed_ul_s = aspirate_speed / 60.0
            dispense_speed_ul_s = dispense_speed / 60.0

            for cycle in range(1, cycles + 1):
                if self._shutdown_requested:
                    logger.info("Prime operation cancelled by user")
                    self.operation_completed.emit("prime", False)
                    return False

                progress = int((cycle - 1) / cycles * 100)
                self.operation_progress.emit(
                    "prime",
                    progress,
                    f"Cycle {cycle}/{cycles}",
                )

                # Emit status update for UI
                self.status_updated.emit("Priming", dispense_speed, volume_ul, 0.0, 0.0)

                logger.info(f"\n🔄 Cycle {cycle}/{cycles}")

                # Open 6-port valves at cycle 3 (INJECT position for flow)
                if cycle == 3 and ctrl:
                    logger.info("  🔧 Opening 6-port valves to INJECT position")
                    ctrl.knx_six_both(state=1)  # Both channels: state 1 = INJECT
                    logger.info("     Both 6-port valves opened")

                # Set 3-way valves to OPEN at cycle 5 (KC1→B, KC2→D)
                elif cycle == 5 and ctrl:
                    logger.info("  🔧 Setting 3-way valves to OPEN position")
                    ctrl.knx_three_both(state=1)  # state=1 OPEN: KC1→B, KC2→D
                    logger.info("     Both 3-way valves in OPEN position")

                # Aspirate both pumps
                logger.info(f"  → Aspirate {volume_ul}uL (both pumps)")
                try:
                    pump._pump.pump.aspirate_both(volume_ul, aspirate_speed_ul_s)
                except Exception as e:
                    error_msg = f"Aspirate failed: {e}"
                    logger.exception(error_msg)
                    self.error_occurred.emit("prime", error_msg)
                    await self._home_plungers(pump)
                    self.operation_completed.emit("prime", False)
                    return False

                (
                    p1_ready,
                    p2_ready,
                    elapsed,
                    p1_time,
                    p2_time,
                ) = await asyncio.get_event_loop().run_in_executor(
                    None,
                    pump._pump.pump.wait_until_both_ready,
                    60.0,
                )

                if not (p1_ready and p2_ready):
                    error_msg = "Aspirate failed - pump(s) not responding"
                    logger.error(f"❌ {error_msg}")
                    self.error_occurred.emit("prime", error_msg)
                    await self._home_plungers(pump)
                    self.operation_completed.emit("prime", False)
                    return False

                # Check for blockage
                time_diff = abs(p1_time - p2_time)
                if time_diff > 1.5:
                    blocked_pump = "KC2" if p1_time > p2_time else "KC1"
                    error_msg = f"Blockage detected in {blocked_pump} during aspirate"
                    logger.error(f"❌ {error_msg}")
                    self.error_occurred.emit("prime", error_msg)
                    await self._home_plungers(pump)
                    self.operation_completed.emit("prime", False)
                    return False

                await asyncio.sleep(0.5)

                # Dispense both pumps
                logger.info(f"  → Dispense {volume_ul}uL (both pumps)")
                pump._pump.pump.dispense_both(volume_ul, dispense_speed_ul_s)

                (
                    p1_ready,
                    p2_ready,
                    elapsed,
                    p1_time,
                    p2_time,
                ) = await asyncio.get_event_loop().run_in_executor(
                    None,
                    pump._pump.pump.wait_until_both_ready,
                    60.0,
                )

                if not (p1_ready and p2_ready):
                    error_msg = "Dispense failed - pump(s) not responding"
                    logger.error(f"❌ {error_msg}")
                    self.error_occurred.emit("prime", error_msg)
                    await self._home_plungers(pump)
                    self.operation_completed.emit("prime", False)
                    return False

                # Check for blockage
                time_diff = abs(p1_time - p2_time)
                if time_diff > 2.0:
                    blocked_pump = "KC2" if p1_time > p2_time else "KC1"
                    error_msg = f"Blockage detected in {blocked_pump} during dispense"
                    logger.error(f"❌ {error_msg}")
                    self.error_occurred.emit("prime", error_msg)
                    await self._home_plungers(pump)
                    self.operation_completed.emit("prime", False)
                    return False

                logger.info("  ✅ Cycle completed")

            logger.info("\n✅ Priming completed successfully")

            # Return all valves to default after priming
            if ctrl:
                logger.info("🔧 Returning all valves to default position...")
                try:
                    # 3-way valves: state=0 CLOSED (KC1→A, KC2→C)
                    ctrl.knx_three_both(state=0)
                    # 6-port valves: state=0 CLOSED/LOAD position
                    ctrl.knx_six_both(state=0)
                    logger.info("✅ All valves in default position")
                except Exception as valve_err:
                    logger.error(f"⚠️ Valve close failed: {valve_err}")

            self.operation_progress.emit("prime", 100, "Complete")
            self.operation_completed.emit("prime", True)
            return True

        except Exception as e:
            error_msg = f"Prime operation failed: {e}"
            logger.exception(error_msg)
            self.error_occurred.emit("prime", error_msg)
            self.operation_completed.emit("prime", False)
            return False

        finally:
            # Always return valves to CLOSED position on exit (safety)
            if ctrl:
                try:
                    ctrl.knx_three(state=0, ch=1)  # KC1→A (CLOSED)
                    await asyncio.sleep(0.05)
                    ctrl.knx_three(state=0, ch=2)  # KC2→C (CLOSED)
                    await asyncio.sleep(0.05)
                    ctrl.knx_six(state=0, ch=1)
                    await asyncio.sleep(0.05)
                    ctrl.knx_six(state=0, ch=2)
                except Exception as e:
                    logger.error(f"Failed to close valves in finally: {e}")

            self._current_operation = PumpOperation.IDLE

    async def cleanup_pump(
        self,
        pulse_cycles: int = 10,
        prime_cycles: int = 6,
        speed: float = 5000.0,
    ) -> bool:
        """Complete pump cleaning sequence.

        Phases:
        1. Initialize pumps
        2. Initial fill: 3 cycles
        3. Pulsating: First round
        4. Re-initialize
        5. Prime: Full sequence with valve control
        6. Pulsating: Second round
        7. Close valves
        8. Pulsating: Final round
        9. Home plungers

        Args:
            pulse_cycles: Number of pulsating cycles per round (default: 10)
            prime_cycles: Number of prime cycles (default: 6)
            speed: Flow speed in µL/min (default: 5000)

        Returns:
            True if cleanup completed successfully

        """
        if not self.is_available:
            self.error_occurred.emit("cleanup", "No pump hardware available")
            return False

        if not self.is_idle:
            self.error_occurred.emit(
                "cleanup",
                f"Cannot start cleanup - pump is {self._current_operation.value}",
            )
            return False

        self._current_operation = PumpOperation.CLEANING
        self._shutdown_requested = False
        self.operation_started.emit("cleanup")

        try:
            logger.info("=== Pump Cleanup Started ===")
            pump = self.hardware_manager.pump
            ctrl = self.hardware_manager._ctrl_raw

            speed_ul_s = speed / 60.0

            # Phase 1: Initialize
            self.operation_progress.emit("cleanup", 5, "Initializing pumps")
            logger.info("\n🔧 Phase 1: Initializing pumps")
            pump._pump.pump.initialize_pumps()
            p1_ready, p2_ready, elapsed, _, _ = await asyncio.get_event_loop().run_in_executor(
                None,
                pump._pump.pump.wait_until_both_ready,
                30.0,
            )
            if not (p1_ready and p2_ready):
                self.error_occurred.emit("cleanup", "Initialization failed")
                self.operation_completed.emit("cleanup", False)
                return False
            logger.info(f"✅ Pumps initialized in {elapsed:.1f}s")

            # Phase 2: Initial fill (3 cycles)
            self.operation_progress.emit("cleanup", 10, "Initial fill")
            logger.info("\n🔧 Phase 2: Initial fill (3 cycles)")
            for cycle in range(1, 4):
                if self._shutdown_requested:
                    await self._home_plungers(pump)
                    self.operation_completed.emit("cleanup", False)
                    return False

                logger.info(f"  Fill cycle {cycle}/3")
                pump._pump.pump.aspirate_both(1000.0, speed_ul_s)
                p1_ready, p2_ready, _, _, _ = await asyncio.get_event_loop().run_in_executor(
                    None, pump._pump.pump.wait_until_both_ready, 60.0
                )
                if not (p1_ready and p2_ready):
                    self.error_occurred.emit("cleanup", "Fill aspirate failed")
                    await self._home_plungers(pump)
                    self.operation_completed.emit("cleanup", False)
                    return False

                await asyncio.sleep(0.2)

                pump._pump.pump.dispense_both(1000.0, speed_ul_s)
                p1_ready, p2_ready, _, _, _ = await asyncio.get_event_loop().run_in_executor(
                    None, pump._pump.pump.wait_until_both_ready, 60.0
                )
                if not (p1_ready and p2_ready):
                    self.error_occurred.emit("cleanup", "Fill dispense failed")
                    await self._home_plungers(pump)
                    self.operation_completed.emit("cleanup", False)
                    return False

                await asyncio.sleep(0.2)

            logger.info("✅ Initial fill complete")

            # Phase 3: First pulsating
            self.operation_progress.emit("cleanup", 25, "Pulsating (1/3)")
            logger.info(f"\n🌊 Phase 3: Pulsating round 1 ({pulse_cycles} cycles)")
            success = await self._pulsate_pumps(pump, pulse_cycles, speed)
            if not success:
                self.error_occurred.emit("cleanup", "Pulsating round 1 failed")
                await self._home_plungers(pump)
                self.operation_completed.emit("cleanup", False)
                return False

            # Phase 4: Re-initialize
            self.operation_progress.emit("cleanup", 40, "Re-initializing")
            logger.info("\n🔧 Phase 4: Re-initializing pumps")
            pump._pump.pump.initialize_pumps()
            p1_ready, p2_ready, elapsed, _, _ = await asyncio.get_event_loop().run_in_executor(
                None, pump._pump.pump.wait_until_both_ready, 30.0
            )
            if not (p1_ready and p2_ready):
                self.error_occurred.emit("cleanup", "Re-initialization failed")
                await self._home_plungers(pump)
                self.operation_completed.emit("cleanup", False)
                return False
            logger.info(f"✅ Pumps re-initialized in {elapsed:.1f}s")

            # Phase 5: Prime sequence
            self.operation_progress.emit("cleanup", 50, "Prime sequence")
            logger.info("\n⚖️  Phase 5: Prime Pump Sequence")
            success = await self._seesaw_pumps(pump, ctrl, prime_cycles, speed)
            if not success:
                self.error_occurred.emit("cleanup", "Prime sequence failed")
                await self._home_plungers(pump)
                self.operation_completed.emit("cleanup", False)
                return False

            # Phase 6: Second pulsating
            self.operation_progress.emit("cleanup", 65, "Pulsating (2/3)")
            logger.info(f"\n🌊 Phase 6: Pulsating round 2 ({pulse_cycles} cycles)")
            success = await self._pulsate_pumps(pump, pulse_cycles, speed)
            if not success:
                self.error_occurred.emit("cleanup", "Pulsating round 2 failed")
                await self._home_plungers(pump)
                self.operation_completed.emit("cleanup", False)
                return False

            # Phase 7: Close all valves
            self.operation_progress.emit("cleanup", 80, "Closing valves")
            logger.info("\n🔧 Phase 7: Closing all valves")
            if ctrl:
                ctrl.knx_six_both(0)  # 6-port CLOSED (LOAD)
                await asyncio.sleep(0.5)
                ctrl.knx_three_both(0)  # 3-way state=0 CLOSED: KC1→A, KC2→C
                await asyncio.sleep(0.5)
                logger.info("✅ All valves closed")

            # Phase 8: Final pulsating
            self.operation_progress.emit("cleanup", 90, "Pulsating (3/3)")
            logger.info(f"\n🌊 Phase 8: Final pulsating ({pulse_cycles} cycles)")
            success = await self._pulsate_pumps(pump, pulse_cycles, speed)
            if not success:
                logger.warning("⚠️ Final pulsating incomplete")

            # Phase 9: Home plungers
            self.operation_progress.emit("cleanup", 95, "Homing plungers")
            logger.info("\n🏠 Phase 9: Homing plungers to 0uL")
            await self._home_plungers(pump)

            logger.info("\n✅ Cleanup completed successfully")
            self.operation_progress.emit("cleanup", 100, "Complete")
            self.operation_completed.emit("cleanup", True)
            return True

        except Exception as e:
            error_msg = f"Cleanup operation failed: {e}"
            logger.exception(error_msg)
            self.error_occurred.emit("cleanup", error_msg)
            await self._home_plungers(pump)
            self.operation_completed.emit("cleanup", False)
            return False

        finally:
            self._current_operation = PumpOperation.IDLE

    async def run_buffer(
        self,
        cycles: int = 0,
        duration_min: float = 0,
        volume_ul: float = 1000.0,
        flow_rate: float = 50.0,
    ) -> bool:
        """Run continuous buffer flow.

        Args:
            cycles: Number of cycles (0 = use duration instead)
            duration_min: Duration in minutes (0 = use cycles instead)
            volume_ul: Volume per cycle in µL (default: 1000)
            flow_rate: Flow rate in µL/min (default: 50)

        Returns:
            True if buffer run completed successfully

        """
        if not self.is_available:
            self.error_occurred.emit("run_buffer", "No pump hardware available")
            return False

        if not self.is_idle:
            self.error_occurred.emit(
                "run_buffer",
                f"Cannot start buffer - pump is {self._current_operation.value}",
            )
            return False

        self._current_operation = PumpOperation.RUNNING_BUFFER
        self._shutdown_requested = False
        self.operation_started.emit("run_buffer")

        try:
            logger.info("=== Buffer Flow Started ===")
            logger.info(f"  Volume: {volume_ul} uL per cycle")
            logger.info(f"  Flow rate: {flow_rate} uL/min")

            # Determine mode
            if cycles > 0:
                logger.info(f"  Cycles: {cycles}")
                total_cycles = cycles
            elif duration_min > 0:
                logger.info(f"  Duration: {duration_min} min")
                total_volume_needed = flow_rate * duration_min
                total_cycles = int(total_volume_needed / volume_ul) + 1
                logger.info(f"  Estimated cycles: {total_cycles}")
            else:
                logger.info("  Mode: Continuous (until stopped)")
                total_cycles = 999999  # Large number for continuous

            pump = self.hardware_manager.pump
            speed_ul_s = flow_rate / 60.0

            cycle_count = 0
            start_time = asyncio.get_event_loop().time()

            for cycle in range(1, total_cycles + 1):
                if self._shutdown_requested:
                    logger.info(f"Buffer flow stopped by user after {cycle_count} cycles")
                    self.status_updated.emit("Stopped", 0.0, 0.0, 0.0, 0.0)
                    break

                # Check duration limit if in duration mode
                if duration_min > 0:
                    elapsed = asyncio.get_event_loop().time() - start_time
                    if elapsed >= duration_min * 60:
                        logger.info(f"Duration target reached: {duration_min} minutes")
                        break

                cycle_count = cycle

                if cycles > 0:
                    progress = int(cycle / cycles * 100)
                    self.operation_progress.emit(
                        "run_buffer",
                        progress,
                        f"Cycle {cycle}/{cycles}",
                    )
                else:
                    self.operation_progress.emit(
                        "run_buffer",
                        0,
                        f"Cycle {cycle}",
                    )

                # Aspirate
                pump._pump.pump.aspirate_both(volume_ul, 24000.0 / 60.0)  # Fast aspirate

                # Emit status update during aspirate
                self.status_updated.emit("Aspirating", flow_rate, volume_ul, 0.0, 0.0)

                p1_ready, p2_ready, _, _, _ = await asyncio.get_event_loop().run_in_executor(
                    None,
                    pump._pump.pump.wait_until_both_ready,
                    120.0,
                )

                if not (p1_ready and p2_ready):
                    self.error_occurred.emit("run_buffer", "Aspirate failed")
                    self.operation_completed.emit("run_buffer", False)
                    return False

                # Check for shutdown request after aspirate
                if self._shutdown_requested:
                    logger.info(
                        f"Buffer flow stopped by user after aspirate in cycle {cycle_count}"
                    )
                    self.status_updated.emit("Stopped", 0.0, 0.0, 0.0, 0.0)
                    break

                await asyncio.sleep(0.2)

                # Dispense at specified flow rate
                pump._pump.pump.dispense_both(volume_ul, speed_ul_s)

                # Emit status update during dispense with plunger position
                try:
                    p1_pos = pump._pump.pump.get_plunger_position(1) or 0.0
                    p2_pos = pump._pump.pump.get_plunger_position(2) or 0.0
                    avg_pos = (p1_pos + p2_pos) / 2.0
                    self.status_updated.emit("Dispensing", flow_rate, avg_pos, 0.0, 0.0)
                except Exception:
                    self.status_updated.emit("Dispensing", flow_rate, 0.0, 0.0, 0.0)

                p1_ready, p2_ready, _, _, _ = await asyncio.get_event_loop().run_in_executor(
                    None,
                    pump._pump.pump.wait_until_both_ready,
                    120.0,
                )

                if not (p1_ready and p2_ready):
                    self.error_occurred.emit("run_buffer", "Dispense failed")
                    self.operation_completed.emit("run_buffer", False)
                    return False

                # Check for shutdown request after dispense
                if self._shutdown_requested:
                    logger.info(
                        f"Buffer flow stopped by user after dispense in cycle {cycle_count}"
                    )
                    self.status_updated.emit("Stopped", 0.0, 0.0, 0.0, 0.0)
                    break

                await asyncio.sleep(0.2)

            elapsed_total = (asyncio.get_event_loop().time() - start_time) / 60.0
            total_volume = cycle_count * volume_ul

            logger.info("\n✅ Buffer flow completed")
            logger.info(f"   Cycles: {cycle_count}")
            logger.info(f"   Volume: {total_volume:.0f}uL")
            logger.info(f"   Time: {elapsed_total:.1f} min")

            self.operation_progress.emit("run_buffer", 100, "Complete")
            self.operation_completed.emit("run_buffer", True)
            return True

        except Exception as e:
            error_msg = f"Buffer flow failed: {e}"
            logger.exception(error_msg)
            self.error_occurred.emit("run_buffer", error_msg)
            self.operation_completed.emit("run_buffer", False)
            return False

        finally:
            self._current_operation = PumpOperation.IDLE

    async def emergency_stop(self) -> bool:
        """Emergency stop - terminate all pump operations immediately.

        Returns:
            True if stop command sent successfully

        """
        if not self.is_available:
            return False

        try:
            logger.warning("🛑 EMERGENCY STOP - Terminating all pump operations")
            self._shutdown_requested = True

            pump = self.hardware_manager.pump
            # Send terminate to both pumps individually (address 0 is NOT broadcast for Cavro)
            pump._pump.pump.send_command("/1TR")  # Terminate pump 1
            import time

            time.sleep(0.05)
            pump._pump.pump.send_command("/2TR")  # Terminate pump 2

            self._current_operation = PumpOperation.IDLE
            self.operation_completed.emit("emergency_stop", True)
            logger.info("✅ Emergency stop executed")
            return True

        except Exception as e:
            logger.exception(f"Emergency stop failed: {e}")
            return False

    async def home_pumps(self) -> bool:
        """Home both pumps to zero position.

        Returns:
            True if homing completed successfully

        """
        if not self.is_available:
            self.error_occurred.emit("home_pumps", "No pump hardware available")
            return False

        if not self.is_idle:
            self.error_occurred.emit(
                "home_pumps",
                f"Cannot home pumps - pump is {self._current_operation.value}",
            )
            return False

        self._current_operation = PumpOperation.IDLE  # Keep as idle since this is maintenance
        self.operation_started.emit("home_pumps")
        self.status_updated.emit("Homing...", 0.0, 0.0, 0.0, 0.0)

        try:
            logger.info("🏠 Homing both pumps to zero position...")

            pump = self.hardware_manager.pump
            success = await self._home_plungers(pump)

            if success:
                self.status_updated.emit("Homed", 0.0, 0.0, 0.0, 0.0)
                self.operation_completed.emit("home_pumps", True)
                return True
            else:
                self.error_occurred.emit("home_pumps", "Failed to home plungers")
                self.operation_completed.emit("home_pumps", False)
                return False

        except Exception as e:
            logger.exception(f"Homing failed: {e}")
            self.error_occurred.emit("home_pumps", str(e))
            self.operation_completed.emit("home_pumps", False)
            return False

    def change_flow_rate_on_the_fly(self, flow_rate: float) -> bool:
        """Change flow rate during active pump operation using V command.

        This allows changing the flow rate while pumps are actively dispensing
        without stopping and restarting the operation.

        Args:
            flow_rate: New flow rate in µL/min

        Returns:
            True if command sent successfully

        """
        if not self.is_available:
            logger.error("Cannot change flow rate - pump not available")
            return False

        try:
            logger.info(f"💧 Changing flow rate on-the-fly to {flow_rate} uL/min")

            # Convert µL/min to µL/s
            rate_ul_s = flow_rate / 60.0

            pump = self.hardware_manager.pump
            # Send V command to both pumps with mode parameter ,1
            # Use F suffix (modify on-the-fly) instead of R (execute) for smooth mid-motion speed change
            pump._pump.pump.send_command(f"/1V{rate_ul_s:.3f},1F")
            import time

            time.sleep(0.05)
            pump._pump.pump.send_command(f"/2V{rate_ul_s:.3f},1F")

            # Update internal flow rate tracker
            self._current_flow_rate = flow_rate

            logger.info(f"✅ Flow rate changed to {flow_rate} uL/min")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to change flow rate: {e}")
            return False

    def cancel_operation(self) -> None:
        """Request cancellation of current operation (graceful)."""
        if not self.is_idle:
            logger.info(f"Requesting cancellation of {self._current_operation.value}")
            self._shutdown_requested = True
            # Emit status update to show cancellation in progress
            self.status_updated.emit("Stopping...", 0.0, 0.0, 0.0, 0.0)

    async def stop_and_wait_for_idle(self, timeout: float = 30.0) -> bool:
        """Stop any running pump operation and wait until pump is idle.

        Used by the cycle orchestrator to ensure the pump is free
        before starting a new cycle's pump operation (buffer or injection).

        Args:
            timeout: Maximum seconds to wait for idle (default: 30)

        Returns:
            True if pump is idle (or was already idle), False if timeout
        """
        if self.is_idle:
            return True

        op = self._current_operation.value
        logger.info(f"Stopping pump operation '{op}' for cycle transition...")

        # Request graceful cancellation
        self._shutdown_requested = True

        # Also send terminate commands to stop plunger motion immediately
        try:
            pump = self.hardware_manager.pump
            if pump and pump._pump and pump._pump.pump:
                pump._pump.pump.send_command("/1TR")
                await asyncio.sleep(0.05)
                pump._pump.pump.send_command("/2TR")
        except Exception as e:
            logger.warning(f"Terminate command failed (non-fatal): {e}")

        # Wait for the operation thread to see _shutdown_requested and exit
        start = asyncio.get_event_loop().time()
        while not self.is_idle:
            elapsed = asyncio.get_event_loop().time() - start
            if elapsed >= timeout:
                logger.error(f"Timeout waiting for pump idle after {timeout}s")
                # Force idle state as last resort
                self._current_operation = PumpOperation.IDLE
                self._shutdown_requested = False
                return False
            await asyncio.sleep(0.2)

        self._shutdown_requested = False
        logger.info(
            f"Pump idle after stopping '{op}' ({asyncio.get_event_loop().time() - start:.1f}s)"
        )
        return True

    # ========================================================================
    # Helper Methods
    # ========================================================================

    async def _pulsate_pumps(
        self,
        pump,
        cycles: int,
        speed: float,
    ) -> bool:
        """Pulsating back-and-forth through OUTPUT port."""
        pulse_volume = 200.0
        push_volume = 250.0
        speed_ul_s = speed / 60.0

        # Fill syringes
        pump._pump.pump.aspirate_both(1000.0, speed_ul_s)
        p1_ready, p2_ready, _, _, _ = await asyncio.get_event_loop().run_in_executor(
            None,
            pump._pump.pump.wait_until_both_ready,
            60.0,
        )

        if not (p1_ready and p2_ready):
            return False

        await asyncio.sleep(0.2)

        # Set output valves
        pump._pump.pump.send_command("/1OR")
        await asyncio.sleep(0.5)
        pump._pump.pump.send_command("/2OR")
        await asyncio.sleep(0.5)

        for cycle in range(1, cycles + 1):
            if self._shutdown_requested:
                return False

            # Push out
            pump._pump.pump.send_command(f"/AV{int(speed_ul_s)},1R")
            await asyncio.sleep(0.1)
            steps = int(push_volume * 181.49)
            pump._pump.pump.send_command(f"/AD{steps}R")

            (
                p1_ready,
                p2_ready,
                _,
                p1_time,
                p2_time,
            ) = await asyncio.get_event_loop().run_in_executor(
                None,
                pump._pump.pump.wait_until_both_ready,
                30.0,
            )

            if not (p1_ready and p2_ready):
                return False

            # Check blockage
            time_diff = abs(p1_time - p2_time)
            if time_diff > 2.0:
                blocked_pump = "KC2" if p1_time > p2_time else "KC1"
                logger.error(f"❌ Blockage in {blocked_pump} during push")
                return False

            await asyncio.sleep(0.1)

            # Pull back
            pull_speed_ul_s = speed_ul_s / 2.0
            pump._pump.pump.send_command(f"/AV{int(pull_speed_ul_s)},1R")
            await asyncio.sleep(0.1)
            steps = int(pulse_volume * 181.49)
            pump._pump.pump.send_command(f"/AP{steps}R")

            (
                p1_ready,
                p2_ready,
                _,
                p1_time,
                p2_time,
            ) = await asyncio.get_event_loop().run_in_executor(
                None,
                pump._pump.pump.wait_until_both_ready,
                10.0,
            )

            if not (p1_ready and p2_ready):
                return False

            # Check blockage
            time_diff = abs(p1_time - p2_time)
            if time_diff > 1.5:
                blocked_pump = "KC2" if p1_time > p2_time else "KC1"
                logger.error(f"❌ Blockage in {blocked_pump} during pull")
                return False

            await asyncio.sleep(1.0)

        return True

    async def _seesaw_pumps(
        self,
        pump,
        ctrl,
        cycles: int,
        speed: float,
    ) -> bool:
        """Prime pump sequence - aspirate/dispense cycles with valve control."""
        aspirate_speed_ul_s = 24000.0 / 60.0
        dispense_speed_ul_s = speed / 60.0

        for cycle in range(1, cycles + 1):
            if self._shutdown_requested:
                return False

            logger.info(f"  Cycle {cycle}/{cycles}")

            # Valve operations
            if ctrl:
                if cycle == 3:
                    logger.info("    Opening 6-port valves...")
                    ctrl.knx_six_both(1)
                    await asyncio.sleep(0.5)
                elif cycle == 5:
                    logger.info("    Opening 3-way valves (KC1→B, KC2→D)...")
                    ctrl.knx_three_both(1)  # state=1 OPEN: KC1→B, KC2→D
                    await asyncio.sleep(0.5)

            # Aspirate
            pump._pump.pump.aspirate_both(1000.0, aspirate_speed_ul_s)
            (
                p1_ready,
                p2_ready,
                _,
                p1_time,
                p2_time,
            ) = await asyncio.get_event_loop().run_in_executor(
                None,
                pump._pump.pump.wait_until_both_ready,
                60.0,
            )

            if not (p1_ready and p2_ready):
                return False

            # Check blockage
            time_diff = abs(p1_time - p2_time)
            if time_diff > 1.5:
                blocked_pump = "KC2" if p1_time > p2_time else "KC1"
                logger.error(f"❌ Blockage in {blocked_pump} during aspirate")
                return False

            await asyncio.sleep(0.5)

            # Dispense
            pump._pump.pump.dispense_both(1000.0, dispense_speed_ul_s)
            (
                p1_ready,
                p2_ready,
                _,
                p1_time,
                p2_time,
            ) = await asyncio.get_event_loop().run_in_executor(
                None,
                pump._pump.pump.wait_until_both_ready,
                60.0,
            )

            if not (p1_ready and p2_ready):
                return False

            # Check blockage
            time_diff = abs(p1_time - p2_time)
            if time_diff > 2.0:
                blocked_pump = "KC2" if p1_time > p2_time else "KC1"
                logger.error(f"❌ Blockage in {blocked_pump} during dispense")
                return False

            await asyncio.sleep(0.2)

        return True

    async def _home_plungers(self, pump) -> bool:
        """Send plungers to home position (0µL)."""
        try:
            pump._pump.pump.initialize_pumps()
            p1_ready, p2_ready, elapsed, _, _ = await asyncio.get_event_loop().run_in_executor(
                None,
                pump._pump.pump.wait_until_both_ready,
                30.0,
            )
            if p1_ready and p2_ready:
                logger.info(f"✅ Plungers homed to 0uL in {elapsed:.1f}s")
                return True
            logger.warning("⚠️ Failed to home plungers")
            return False
        except Exception as e:
            logger.error(f"❌ Error homing plungers: {e}")
            return False

    async def inject_simple(self, flow_rate: float = 100.0) -> bool:
        """Run simple injection - full syringe dispense with contact time.

        This performs a basic injection:
        1. Aspirate full syringe volume from INPUT
        2. Switch valve to OUTPUT
        3. Dispense at specified flow rate to flow cell
        4. Calculate and display contact time

        Args:
            flow_rate: Dispense flow rate in µL/min (default: 100)

        Returns:
            True if injection completed successfully
        """
        if not self.is_available:
            self.error_occurred.emit("inject_simple", "No pump hardware available")
            return False

        if not self.is_idle:
            self.error_occurred.emit(
                "inject_simple",
                f"Cannot start injection - pump is {self._current_operation.value}",
            )
            return False

        self._current_operation = PumpOperation.INJECTING
        self._shutdown_requested = False
        self.operation_started.emit("inject_simple")

        try:
            pump = self.hardware_manager.pump
            ctrl = self.hardware_manager._ctrl_raw  # 6-port valve controller

            # DEBUG: Check controller availability
            logger.info(f"DEBUG: Controller object: {ctrl}")
            logger.info(f"DEBUG: Controller type: {type(ctrl)}")
            if ctrl:
                logger.info(f"DEBUG: Controller has knx_six_both: {hasattr(ctrl, 'knx_six_both')}")

            # Parameters matching test file exactly
            aspiration_flow_rate = 24000  # µL/min
            aspiration_flow_rate_ul_s = aspiration_flow_rate / 60.0
            assay_flow_rate_ul_s = flow_rate / 60.0
            load_volume_ul = 1000
            loop_volume_ul = 100

            logger.info("=== Simple Inject Started ===")
            logger.info(f"  Assay flow rate: {flow_rate:.1f} uL/min")
            logger.info(f"  Loop volume: {loop_volume_ul:.1f} uL")

            # Calculate contact time
            contact_time_s = (loop_volume_ul / flow_rate) * 60.0
            logger.info(f"  Calculated contact time: {contact_time_s:.2f}s")

            # STEP 1: Aspirate full volume (SAME AS PRIME PUMP)
            logger.info(f"\n[STEP 1] Aspirating {load_volume_ul:.1f} uL (both pumps)")
            logger.info(f"  (Flow rate: {aspiration_flow_rate:.1f} uL/min)")
            self.operation_progress.emit("inject_simple", 10, "Loading sample...")
            self.status_updated.emit("Loading", aspiration_flow_rate, 0.0, 0.0, 0.0)

            # Use aspirate_both - SAME AS PRIME PUMP (with try-catch)
            try:
                pump._pump.pump.aspirate_both(load_volume_ul, aspiration_flow_rate_ul_s)
            except Exception as e:
                error_msg = f"Aspirate failed: {e}"
                logger.exception(error_msg)
                self.error_occurred.emit("inject_simple", error_msg)
                await self._home_plungers(pump)
                self.operation_completed.emit("inject_simple", False)
                self.status_updated.emit("Idle", 0.0, 0.0, 0.0, 0.0)
                return False

            (
                p1_ready,
                p2_ready,
                elapsed,
                p1_time,
                p2_time,
            ) = await asyncio.get_event_loop().run_in_executor(
                None,
                pump._pump.pump.wait_until_both_ready,
                60.0,
            )

            if not (p1_ready and p2_ready):
                logger.error("❌ Aspirate failed - pump(s) not responding")
                self.error_occurred.emit("inject_simple", "Aspirate failed")
                await self._home_plungers(pump)
                self.operation_completed.emit("inject_simple", False)
                self.status_updated.emit("Idle", 0.0, 0.0, 0.0, 0.0)
                return False

            # Check for blockage (SAME AS PRIME PUMP)
            time_diff = abs(p1_time - p2_time)
            if time_diff > 1.5:
                blocked_pump = "KC2" if p1_time > p2_time else "KC1"
                error_msg = f"Blockage detected in {blocked_pump} during aspirate"
                logger.error(f"❌ {error_msg}")
                self.error_occurred.emit("inject_simple", error_msg)
                await self._home_plungers(pump)
                self.operation_completed.emit("inject_simple", False)
                self.status_updated.emit("Idle", 0.0, 0.0, 0.0, 0.0)
                return False

            pos1 = pump._pump.pump.get_plunger_position(1)
            pos2 = pump._pump.pump.get_plunger_position(2)
            logger.info(f"  ✓ Aspirate complete - P1: {pos1:.1f}uL / P2: {pos2:.1f}uL")

            # Delay between aspirate and dispense (SAME AS PRIME PUMP)
            await asyncio.sleep(0.5)

            # STEP 2: Start dispense - fills loop (pump valve switches to OUTPUT)
            logger.info(f"\n[STEP 2] Dispensing at {flow_rate:.1f} uL/min")
            logger.info("  (6-port valves in LOAD - filling loop, pump valve to OUTPUT)")
            self.operation_progress.emit("inject_simple", 30, "Dispensing...")
            self.status_updated.emit("Dispensing", flow_rate, load_volume_ul, 0.0, 0.0)

            # Dispense with pump valve switching to OUTPUT (chip)
            pump._pump.pump.dispense_both(load_volume_ul, assay_flow_rate_ul_s, switch_valve=True)
            logger.info(f"  ✓ Both pumps dispensing at {flow_rate:.1f} uL/min (valve → OUTPUT)")

            # STEP 3: Wait for loop to fill (dispense continues in parallel)
            valve_open_delay_s = 15.0  # seconds (BY DESIGN - loop fills while dispense runs)
            logger.info(f"\n[STEP 3] Waiting {valve_open_delay_s:.1f}s for loop to fill...")
            self.operation_progress.emit(
                "inject_simple", 40, f"Filling loop ({valve_open_delay_s}s)..."
            )
            await asyncio.sleep(valve_open_delay_s)

            # STEP 4: OPEN valves to INJECT position - loop content flows to sensor
            if ctrl:
                logger.info("\n[STEP 4] Opening 6-port valves to INJECT position")
                logger.info("  (Loop content now flows to sensor)")
                self.operation_progress.emit("inject_simple", 50, "Injecting to sensor...")
                valve_result = ctrl.knx_six_both(state=1)  # 1 = INJECT position (OPEN)
                if not valve_result:
                    logger.warning(
                        "⚠️ Valve command returned False (controller busy or error) - continuing anyway"
                    )
            else:
                logger.warning("\n[STEP 4] NO CONTROLLER - valves cannot be opened!")
                logger.warning("  ctrl is None - check hardware_manager._ctrl_raw")

            # STEP 5: Contact time - loop content flows through sensor
            logger.info(f"\n[STEP 5] Contact time: {contact_time_s:.2f}s")
            logger.info("  (Loop content flowing through sensor)")
            self.operation_progress.emit("inject_simple", 60, "Contact time...")

            # Update contact time display every 0.5 seconds during contact period
            start_time = asyncio.get_event_loop().time()
            while True:
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed >= contact_time_s:
                    break
                self.status_updated.emit(
                    "Contact", flow_rate, load_volume_ul, elapsed, contact_time_s
                )
                await asyncio.sleep(0.5)

            # Final update with full contact time
            self.status_updated.emit(
                "Contact", flow_rate, load_volume_ul, contact_time_s, contact_time_s
            )

            # STEP 6: CLOSE valves back to LOAD position - stop injection
            if ctrl:
                logger.info("\n[STEP 6] Closing 6-port valves back to LOAD position")
                logger.info("  (Sample injection complete)")
                self.operation_progress.emit("inject_simple", 70, "Closing valves...")

                # Send valve command and CHECK if it succeeded
                valve_result = ctrl.knx_six_both(state=0)  # 0 = LOAD position (CLOSED)
                if not valve_result:
                    logger.warning("⚠️ Failed to close 6-port valves - command rejected")

                await asyncio.sleep(0.5)  # Wait for valves to physically move
                logger.info("  ✓ Both 6-port valves in LOAD position (CLOSED)")
            else:
                logger.info("\n[STEP 6] Closing 6-port valves (SIMULATED - no controller)")

            # STEP 7: Wait for dispense to complete
            # Calculate dynamic timeout: 110% of time to dispense 1000 uL at given flow rate
            dispense_time = (1000.0 / flow_rate) * 60.0  # seconds
            timeout = dispense_time * 1.1  # 110% buffer
            logger.info("\n[STEP 7] Waiting for dispense to complete...")
            logger.info(f"  Expected time: {dispense_time:.1f}s, Timeout: {timeout:.1f}s")
            self.operation_progress.emit("inject_simple", 80, "Completing...")

            (
                p1_ready,
                p2_ready,
                elapsed,
                p1_time,
                p2_time,
            ) = await asyncio.get_event_loop().run_in_executor(
                None,
                pump._pump.pump.wait_until_both_ready,
                timeout,
            )

            if not (p1_ready and p2_ready):
                logger.error("❌ Dispense failed - pump(s) not responding")
                self.error_occurred.emit("inject_simple", "Dispense failed")
                await self._home_plungers(pump)
                self.operation_completed.emit("inject_simple", False)
                self.status_updated.emit("Idle", 0.0, 0.0, 0.0, 0.0)
                return False

            # Check for blockage during dispense (SAME AS PRIME PUMP)
            time_diff = abs(p1_time - p2_time)
            if time_diff > 2.0:
                blocked_pump = "KC2" if p1_time > p2_time else "KC1"
                error_msg = f"Blockage detected in {blocked_pump} during dispense"
                logger.error(f"❌ {error_msg}")
                self.error_occurred.emit("inject_simple", error_msg)
                await self._home_plungers(pump)
                self.operation_completed.emit("inject_simple", False)
                self.status_updated.emit("Idle", 0.0, 0.0, 0.0, 0.0)
                return False

            logger.info(f"  ✓ Dispense complete ({elapsed:.1f}s)")

            logger.info("\n✅ Simple inject completed")
            self.operation_progress.emit("inject_simple", 100, "Complete")
            self.operation_completed.emit("inject_simple", True)
            logger.info("=== Simple Injection Complete ===")
            return True

        except Exception as e:
            error_msg = f"Simple injection error: {e}"
            logger.exception(error_msg)
            self.error_occurred.emit("inject_simple", error_msg)
            self.operation_completed.emit("inject_simple", False)
            self.status_updated.emit("Idle", 0.0, 0.0, 0.0, 0.0)
            return False
        finally:
            self._current_operation = PumpOperation.IDLE
            # Set to idle after a short delay to show completion
            await asyncio.sleep(2.0)
            self.status_updated.emit("Idle", 0.0, 0.0, 0.0, 0.0)

    async def inject_partial_loop(self, flow_rate: float = 100.0) -> bool:
        """Run partial loop injection (14-step protocol) - EXACT match to test file.

        Args:
            flow_rate: Assay flow rate in µL/min (default: 100)

        Returns:
            True if injection completed successfully
        """
        if not self.is_available:
            self.error_occurred.emit("inject_partial", "No pump hardware available")
            return False

        if not self.is_idle:
            self.error_occurred.emit(
                "inject_partial",
                f"Cannot start injection - pump is {self._current_operation.value}",
            )
            return False

        # Validate pump connection before starting operation
        pump = self.hardware_manager.pump
        if not pump or not pump._pump or not pump._pump.pump:
            self.error_occurred.emit("inject_partial", "Pump not initialized")
            return False

        # Check if pump serial port is open
        if not pump._pump.pump.ser or not pump._pump.pump.ser.is_open:
            logger.error("Pump serial port is not open - attempting to reconnect...")
            try:
                # Try to reconnect
                pump._pump.pump.reconnect()
                if not pump._pump.pump.ser or not pump._pump.pump.ser.is_open:
                    self.error_occurred.emit(
                        "inject_partial", "Pump connection lost - port not open"
                    )
                    return False
                logger.info("Pump reconnected successfully")
            except Exception as e:
                self.error_occurred.emit("inject_partial", f"Pump reconnection failed: {e}")
                return False

        self._current_operation = PumpOperation.INJECTING
        self._shutdown_requested = False
        self.operation_started.emit("inject_partial")

        try:
            pump = self.hardware_manager.pump
            ctrl = self.hardware_manager._ctrl_raw  # 6-port and 3-way valve controller

            # Parameters matching test file exactly
            assay_flow_rate_ul_s = flow_rate / 60.0
            aspiration_flow_rate = 24000  # µL/min (fast aspirate)
            aspiration_flow_rate_ul_s = aspiration_flow_rate / 60.0
            output_aspirate_rate = (
                250  # µL/min (slow aspirate from output - reduced for small volumes)
            )
            output_aspirate_rate_ul_s = output_aspirate_rate / 60.0
            pulse_rate = 250  # µL/min (pulse rate - reduced for small 30µL spike)
            pulse_rate_ul_s = pulse_rate / 60.0
            loop_volume_ul = 100

            logger.info("=== Partial Loop Inject Started ===")
            logger.info(f"  Assay flow rate: {flow_rate} uL/min")
            logger.info(f"  Loop volume: {loop_volume_ul} uL")

            # Calculate contact time as 65% of loop volume (30µL spike + remaining ~70µL)
            contact_time_s = (loop_volume_ul * 0.65 / flow_rate) * 60.0
            logger.info(f"  Calculated contact time: {contact_time_s:.2f}s (65% of loop volume)")

            # STEP 1: Move to ABSOLUTE POSITION P950
            logger.info("\n[STEP 1] Moving plungers to ABSOLUTE POSITION P950...")
            logger.info(f"  (Moving to position 950 at {aspiration_flow_rate} uL/min)")
            self.operation_progress.emit("inject_partial", 7, "Loading P950...")
            self.status_updated.emit("Loading", aspiration_flow_rate, 0.0, 0.0, 0.0)

            await asyncio.get_event_loop().run_in_executor(
                None,
                pump._pump.pump.aspirate_both_to_position,
                950,
                aspiration_flow_rate_ul_s,
            )

            # Wait for movement to P950 to complete
            p1_ready, p2_ready, _, _, _ = await asyncio.get_event_loop().run_in_executor(
                None,
                pump._pump.pump.wait_until_both_ready,
                30.0,
            )

            if not (p1_ready and p2_ready):
                self.error_occurred.emit("inject_partial", "Step 1 move to P950 failed")
                self.operation_completed.emit("inject_partial", False)
                return False

            logger.info("  ✓ At P950")

            # STEP 2: Set 3-way valves to OPEN (KC1→B, KC2→D)
            logger.info("\n[STEP 2] Setting 3-way valves to OPEN...")
            self.operation_progress.emit("inject_partial", 14, "Opening 3-way...")
            if ctrl:
                ctrl.knx_three_both(state=1)  # state=1 OPEN: Both to LOAD (v331 broadcast)
                logger.info("  ✓ 3-way valves OPEN (KC1→B, KC2→D) - broadcast")
            else:
                logger.info("  ⚠ 3-way valves OPEN (SIMULATED)")

            # STEP 3: Open 6-port valves to inject position
            logger.info("\n[STEP 3] Opening 6-port valves (inject position)...")
            self.operation_progress.emit("inject_partial", 21, "Opening 6-port...")
            if ctrl:
                ctrl.knx_six_both(state=1)
                logger.info("  ✓ 6-port valves INJECT (REAL HARDWARE)")
            else:
                logger.info("  ⚠ 6-port valves INJECT (SIMULATED)")
            await asyncio.sleep(1.0)  # Valve switching delay

            # STEP 4: Aspirate 10µL (P950 → P960)
            logger.info("\n[STEP 4] Aspirating 10uL to P960...")
            logger.info(f"  (Aspirating at {output_aspirate_rate} uL/min)")
            self.operation_progress.emit("inject_partial", 28, "Loading P960...")
            self.status_updated.emit("Loading", output_aspirate_rate, 0.0, 0.0, 0.0)

            pump._pump.pump.aspirate_both(10.0, output_aspirate_rate_ul_s)
            await asyncio.sleep(0.5)  # Wait for command to be sent

            # Wait for aspirate to complete (10µL @ 250µL/min = ~2.4s)
            p1_ready, p2_ready, _, _, _ = await asyncio.get_event_loop().run_in_executor(
                None,
                pump._pump.pump.wait_until_both_ready,
                20.0,
            )

            if not (p1_ready and p2_ready):
                self.error_occurred.emit("inject_partial", "Step 4 aspirate failed")
                self.operation_completed.emit("inject_partial", False)
                return False

            logger.info("  ✓ 10µL aspirate completed (now at P960)")

            # STEP 5: Close 6-port valves to load position
            logger.info("\n[STEP 5] Closing 6-port valves (load position)...")
            self.operation_progress.emit("inject_partial", 35, "Closing 6-port...")
            if ctrl:
                ctrl.knx_six_both(state=0)
                logger.info("  ✓ 6-port valves LOAD (REAL HARDWARE)")
            else:
                logger.info("  ⚠ 6-port valves LOAD (SIMULATED)")
            await asyncio.sleep(1.0)  # Valve switching delay

            # STEP 6: Dispense 5µL (P960 → P955, pump valve to OUTPUT)
            logger.info("\n[STEP 6] Dispensing 5uL to P955...")
            logger.info("  (Pump valve switching to OUTPUT)")
            self.operation_progress.emit("inject_partial", 42, "Dispensing to P955...")
            self.status_updated.emit("Dispensing", output_aspirate_rate, 0.0, 0.0, 0.0)

            # Dispense 5µL (relative) at output aspirate rate
            pump._pump.pump.dispense_both(5.0, output_aspirate_rate_ul_s, switch_valve=True)
            await asyncio.sleep(0.5)  # Wait for command to be sent

            # Wait for dispense to complete (5µL @ 250µL/min = ~1.2s)
            p1_ready, p2_ready, _, _, _ = await asyncio.get_event_loop().run_in_executor(
                None,
                pump._pump.pump.wait_until_both_ready,
                15.0,
            )

            if not (p1_ready and p2_ready):
                self.error_occurred.emit("inject_partial", "Step 6 dispense failed")
                self.operation_completed.emit("inject_partial", False)
                return False

            logger.info("  ✓ 5µL dispense completed (now at P955)")

            # STEP 7: Wait 10 seconds
            logger.info("\n[STEP 7] Waiting 10 seconds...")
            self.operation_progress.emit("inject_partial", 49, "Waiting 10s...")
            await asyncio.sleep(10.0)

            # STEP 8: Open 6-port valves to inject position
            logger.info("\n[STEP 8] Opening 6-port valves (inject position)...")
            self.operation_progress.emit("inject_partial", 56, "Opening 6-port...")
            if ctrl:
                ctrl.knx_six_both(state=1)
                logger.info("  ✓ 6-port valves INJECT (REAL HARDWARE)")
            else:
                logger.info("  ⚠ 6-port valves INJECT (SIMULATED)")
            await asyncio.sleep(1.0)  # Valve switching delay

            # STEP 9: Dispense 12µL spike at pulse rate - EXACT VALIDATED COMMANDS
            logger.info(f"\n[STEP 9] Dispensing 12uL spike at {pulse_rate} uL/min...")
            self.operation_progress.emit("inject_partial", 63, "Spiking...")
            self.status_updated.emit("Spiking", pulse_rate, 0.0, 0.0, 0.0)

            # Use EXACT validated commands from test (valves already at OUTPUT from Step 6)
            spike_volume_ul = 12.0
            pump._pump.pump.send_command(f"/AV{pulse_rate_ul_s:.3f},1R")
            await asyncio.sleep(0.1)
            pump._pump.pump.send_command(f"/AD{spike_volume_ul:.3f},1R")
            await asyncio.sleep(0.5)

            # Wait for spike to complete
            p1_ready, p2_ready, _, _, _ = await asyncio.get_event_loop().run_in_executor(
                None,
                pump._pump.pump.wait_until_both_ready,
                15.0,
            )

            if not (p1_ready and p2_ready):
                self.error_occurred.emit("inject_partial", "Spike dispense failed")
                self.operation_completed.emit("inject_partial", False)
                return False

            logger.info("  ✓ 12µL spike completed")

            # STEP 11: Dispense remaining 945µL at assay flow rate - EXACT VALIDATED COMMANDS
            remaining_volume_ul = 945.0
            logger.info(f"\n[STEP 11] Starting slow dispense at {flow_rate} uL/min...")
            self.operation_progress.emit("inject_partial", 77, "Contact time...")
            self.status_updated.emit("Injecting", flow_rate, 0.0, 0.0, contact_time_s)

            # Use EXACT validated commands from test
            pump._pump.pump.send_command(f"/AV{assay_flow_rate_ul_s:.3f},1R")
            await asyncio.sleep(0.1)
            pump._pump.pump.send_command(f"/AD{remaining_volume_ul:.3f},1R")
            logger.info(
                f"  ✓ Slow dispense started at {assay_flow_rate_ul_s:.3f} uL/s ({flow_rate} uL/min)"
            )
            await asyncio.sleep(2.0)  # Wait for command to take effect

            # STEP 10: Set 3-way valves to CLOSED immediately after flow rate change (KC1→A, KC2→C)
            logger.info("\n[STEP 10] Setting 3-way valves to CLOSED...")
            self.operation_progress.emit("inject_partial", 70, "Closing 3-way...")
            if ctrl:
                ctrl.knx_three_both(state=0)  # state=0 CLOSED: Both to WASTE (v330 broadcast)
                logger.info("  ✓ 3-way valves CLOSED (KC1→A, KC2→C) - broadcast")
            else:
                logger.info("  ⚠ 3-way valves CLOSED (SIMULATED)")
            await asyncio.sleep(1.0)  # Valve switching delay

            # STEP 12: Contact time monitoring with motion detection and stall watchdog
            logger.info(f"\n[STEP 12] Contact time monitoring ({contact_time_s:.1f}s)...")
            start_time = time.time()

            # Immediate motion check (1-second intervals)
            await asyncio.sleep(1.0)
            pos1_before_1 = pump._pump.pump.get_plunger_position(1) or 0.0
            pos2_before_1 = pump._pump.pump.get_plunger_position(2) or 0.0
            await asyncio.sleep(1.0)
            pos1_after_1 = pump._pump.pump.get_plunger_position(1) or 0.0
            pos2_after_1 = pump._pump.pump.get_plunger_position(2) or 0.0

            moved_1 = (abs(pos1_after_1 - pos1_before_1) > 0.5) or (
                abs(pos2_after_1 - pos2_before_1) > 0.5
            )
            if not moved_1:
                logger.error("⚠ NO MOTION DETECTED in first 2 seconds!")
                self.error_occurred.emit("inject_partial", "Pump stalled immediately")
                self.operation_completed.emit("inject_partial", False)
                self.status_updated.emit("Idle", 0.0, 0.0, 0.0, 0.0)
                return False

            logger.info(
                f"✓ Motion detected: P1={pos1_before_1:.1f}→{pos1_after_1:.1f}, P2={pos2_before_1:.1f}→{pos2_after_1:.1f}"
            )

            # Contact time loop with 5-second intervals and stall detection
            last_pos1 = pos1_after_1
            last_pos2 = pos2_after_1
            stall_count = 0
            last_status_update = time.time()

            while True:
                elapsed = time.time() - start_time
                if elapsed >= contact_time_s:
                    break

                # Update UI more frequently (every 1 second) even if we only check for stalls every 5 seconds
                if time.time() - last_status_update >= 1.0:
                    try:
                        pos1_ui = pump._pump.pump.get_plunger_position(1) or 0.0
                        pos2_ui = pump._pump.pump.get_plunger_position(2) or 0.0
                        avg_pos_ui = (pos1_ui + pos2_ui) / 2.0
                        elapsed_ui = time.time() - start_time
                        self.status_updated.emit(
                            "Injecting", flow_rate, avg_pos_ui, elapsed_ui, contact_time_s
                        )
                        last_status_update = time.time()
                    except Exception:
                        pass

                # Check for stall every 5 seconds
                if elapsed % 5.0 < 1.0:  # Near a 5-second mark
                    # Get current positions
                    try:
                        pos1 = pump._pump.pump.get_plunger_position(1) or 0.0
                        pos2 = pump._pump.pump.get_plunger_position(2) or 0.0
                        avg_pos = (pos1 + pos2) / 2.0
                        elapsed_now = time.time() - start_time

                        # Log positions every 5 seconds
                        logger.info(
                            f"  Position check: P1={pos1:.1f} uL, P2={pos2:.1f} uL (t={elapsed_now:.1f}s)"
                        )

                        # Check for motion (threshold: 0.5 µL over 5 seconds)
                        moved = (abs(pos1 - last_pos1) > 0.5) or (abs(pos2 - last_pos2) > 0.5)

                        if not moved:
                            stall_count += 1
                            logger.warning(f"⚠ No motion detected ({stall_count}/2)")

                            if stall_count >= 2:  # 10 seconds of no motion
                                logger.error("⚠ STALL DETECTED - aborting injection!")
                                self.error_occurred.emit(
                                    "inject_partial", "Pump stalled during contact time"
                                )
                                self.operation_completed.emit("inject_partial", False)
                                self.status_updated.emit("Idle", 0.0, 0.0, 0.0, 0.0)
                                return False
                        else:
                            stall_count = 0  # Reset if motion detected

                        # Update last positions for next check
                        last_pos1 = pos1
                        last_pos2 = pos2
                    except Exception as e:
                        logger.warning(f"Position check failed: {e}")

                # Sleep briefly to avoid busy-waiting
                await asyncio.sleep(0.5)

            # Contact time completed successfully
            logger.info(f"✓ Contact time complete: {elapsed:.1f}s")

            # STEP 13: Close 6-port valves after contact time
            logger.info("\n[STEP 13] Closing 6-port valves after contact...")
            self.operation_progress.emit("inject_partial", 84, "Closing 6-port...")
            if ctrl:
                ctrl.knx_six_both(state=0)
                logger.info("  ✓ 6-port valves LOAD (REAL HARDWARE)")
            else:
                logger.info("  ⚠ 6-port valves LOAD (SIMULATED)")
            await asyncio.sleep(1.0)  # Valve switching delay

            # STEP 14: Continue dispensing for dissociation
            logger.info("\n[STEP 14] Dissociation - dispensing remaining volume...")
            self.operation_progress.emit("inject_partial", 91, "Dissociating...")

            # Poll until pumps finish
            p1_ready = p2_ready = False
            poll_start = time.time()
            while not (p1_ready and p2_ready) and (time.time() - poll_start) < 300.0:
                await asyncio.sleep(0.3)

                status1 = pump._pump.pump.get_status(1)
                status2 = pump._pump.pump.get_status(2)

                if status1 and status2:
                    p1_ready = not status1.get("busy", False)
                    p2_ready = not status2.get("busy", False)

                    try:
                        p1_pos = pump._pump.pump.get_plunger_position(1) or 0.0
                        p2_pos = pump._pump.pump.get_plunger_position(2) or 0.0
                        avg_pos = (p1_pos + p2_pos) / 2.0
                        elapsed_total = time.time() - start_time
                        self.status_updated.emit(
                            "Dissociating", flow_rate, avg_pos, elapsed_total, 0.0
                        )
                    except Exception:
                        pass

            if not (p1_ready and p2_ready):
                self.error_occurred.emit("inject_partial", "Dissociation failed")
                self.operation_completed.emit("inject_partial", False)
                self.status_updated.emit("Idle", 0.0, 0.0, 0.0, 0.0)
                return False

            total_time = time.time() - start_time
            logger.info(f"✓ Dissociation complete in {time.time() - poll_start:.1f}s")
            logger.info(f"✓ Total injection time: {total_time:.1f}s")

            self.operation_progress.emit("inject_partial", 100, "Complete")
            self.status_updated.emit("Complete", 0.0, 0.0, contact_time_s, contact_time_s)
            self.operation_completed.emit("inject_partial", True)
            logger.info("=== Partial Loop Injection Complete ===")
            return True

        except Exception as e:
            error_msg = f"Partial loop injection error: {e}"
            logger.exception(error_msg)

            # Handle port closure during shutdown gracefully
            if "Port not open" in str(e):
                logger.info(
                    "Pump port closed during operation (likely during shutdown) - operation cancelled"
                )
                self.error_occurred.emit(
                    "inject_partial", "Operation cancelled - system shutting down"
                )
            else:
                self.error_occurred.emit("inject_partial", error_msg)

            self.operation_completed.emit("inject_partial", False)
            self.status_updated.emit("Idle", 0.0, 0.0, 0.0, 0.0)
            return False
        finally:
            self._current_operation = PumpOperation.IDLE
            # Set to idle after a short delay to show completion
            await asyncio.sleep(2.0)
            self.status_updated.emit("Idle", 0.0, 0.0, 0.0, 0.0)
