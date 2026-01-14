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
    EMERGENCY_STOP = "emergency_stop"


class PumpManager(QObject):
    """Manages high-level pump operations."""

    # Signals
    operation_started = Signal(str)  # operation_name
    operation_progress = Signal(str, int, str)  # operation, progress_percent, message
    operation_completed = Signal(str, bool)  # operation_name, success
    error_occurred = Signal(str, str)  # operation_name, error_message
    
    # Status update signals for UI
    status_updated = Signal(str, float, float, float)  # status, flow_rate, plunger_pos, contact_time

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
            logger.info(f"  Volume: {volume_ul} µL per pump")
            logger.info(f"  Aspirate: {aspirate_speed} µL/min")
            logger.info(f"  Dispense: {dispense_speed} µL/min")

            pump = self.hardware_manager.pump
            ctrl = self.hardware_manager._ctrl_raw  # For valve control

            # DEBUG: Check controller availability
            logger.info(f"🔍 Controller for valves: {ctrl}")
            logger.info(f"🔍 Controller type: {type(ctrl).__name__ if ctrl else 'None'}")
            if ctrl:
                logger.info(f"🔍 Has knx_six_both: {hasattr(ctrl, 'knx_six_both')}")
                logger.info(f"🔍 Has knx_three_both: {hasattr(ctrl, 'knx_three_both')}")

            # CRITICAL: Initialize pumps before priming!
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
                self.status_updated.emit("Priming", dispense_speed, volume_ul, 0.0)

                logger.info(f"\n🔄 Cycle {cycle}/{cycles}")

                # Valve operations at specific cycles
                if ctrl:
                    if cycle == 3:
                        logger.info("  🔧 Opening BOTH load valves (6-port)...")
                        result = ctrl.knx_six_both(1)
                        logger.info(f"  🔍 knx_six_both(1) returned: {result}")
                        if result:
                            logger.info("  ✅ Both 6-port valves opened")
                        else:
                            logger.error("  ❌ Failed to open 6-port valves!")
                        await asyncio.sleep(0.5)

                    elif cycle == 5:
                        logger.info("  🔧 Opening BOTH channel valves (3-way)...")
                        result = ctrl.knx_three_both(1)
                        logger.info(f"  🔍 knx_three_both(1) returned: {result}")
                        if result:
                            logger.info("  ✅ Both 3-way valves opened")
                        else:
                            logger.error("  ❌ Failed to open 3-way valves!")
                        await asyncio.sleep(0.5)
                else:
                    logger.warning(f"  ⚠️ No controller available for valve control at cycle {cycle}")

                # Aspirate both pumps
                logger.info(f"  → ASPIRATE {volume_ul}µL BOTH PUMPS (KC1 & KC2)")
                logger.debug(f"  → pump object: {type(pump)}")
                logger.debug(f"  → pump._pump object: {type(pump._pump)}")
                logger.debug(f"  → pump._pump.pump object: {type(pump._pump.pump)}")

                # Use broadcast command to control BOTH pumps
                try:
                    pump._pump.pump.aspirate_both(volume_ul, aspirate_speed_ul_s)
                    logger.info("  → Both pumps started SIMULTANEOUSLY via broadcast command")
                except AttributeError as e:
                    error_msg = f"aspirate_both() method not available: {e}"
                    logger.error(f"❌ {error_msg}")
                    logger.error("  → Falling back to individual pump control")
                    # Fallback to individual control
                    pump._pump.aspirate(1, volume_ul, aspirate_speed * 60.0)
                    pump._pump.aspirate(2, volume_ul, aspirate_speed * 60.0)
                except Exception as e:
                    error_msg = f"Unexpected error during aspirate_both: {e}"
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
                logger.info(f"  → DISPENSE {volume_ul}µL BOTH PUMPS (KC1 & KC2)")

                # Use broadcast command to control BOTH pumps
                pump._pump.pump.dispense_both(volume_ul, dispense_speed_ul_s)
                logger.info("  → Both pumps started SIMULTANEOUSLY via broadcast command")

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

            # CRITICAL: Close all valves after priming to prevent overheating
            if ctrl:
                logger.info("🔧 Closing valves after priming...")
                try:
                    # Close 3-way channel valves first
                    if ctrl.knx_three_both(0):
                        logger.info("  ✅ 3-way valves closed")
                    await asyncio.sleep(0.2)

                    # Close 6-port load valves
                    if ctrl.knx_six_both(0):
                        logger.info("  ✅ 6-port valves closed")
                    logger.info("  [OK] All valves closed - device safe from heating")
                except Exception as valve_err:
                    logger.error(f"  ⚠️ Valve close failed: {valve_err}")

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
            # SAFETY: Always close valves on exit (success or failure)
            if ctrl:
                try:
                    logger.info("🔧 [SAFETY] Closing valves in finally block...")
                    ctrl.knx_three_both(0)
                    ctrl.knx_six_both(0)
                    logger.info("  [OK] Valves closed")
                except Exception as e:
                    logger.error(f"  Failed to close valves: {e}")

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
            pump.initialize_pumps()
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
            pump.initialize_pumps()
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
                ctrl.knx_six_both(0)  # Close 6-port
                await asyncio.sleep(0.5)
                ctrl.knx_three_both(0)  # Close 3-way
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
            logger.info("\n🏠 Phase 9: Homing plungers to 0µL")
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
            logger.info(f"  Volume: {volume_ul} µL per cycle")
            logger.info(f"  Flow rate: {flow_rate} µL/min")

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
                self.status_updated.emit("Aspirating", flow_rate, volume_ul, 0.0)
                
                p1_ready, p2_ready, _, _, _ = await asyncio.get_event_loop().run_in_executor(
                    None,
                    pump._pump.pump.wait_until_both_ready,
                    120.0,
                )

                if not (p1_ready and p2_ready):
                    self.error_occurred.emit("run_buffer", "Aspirate failed")
                    self.operation_completed.emit("run_buffer", False)
                    return False

                await asyncio.sleep(0.2)

                # Dispense at specified flow rate
                pump._pump.pump.dispense_both(volume_ul, speed_ul_s)
                
                # Emit status update during dispense with plunger position
                try:
                    p1_pos = pump._pump.pump.get_plunger_position(1) or 0.0
                    p2_pos = pump._pump.pump.get_plunger_position(2) or 0.0
                    avg_pos = (p1_pos + p2_pos) / 2.0
                    self.status_updated.emit("Dispensing", flow_rate, avg_pos, 0.0)
                except Exception:
                    self.status_updated.emit("Dispensing", flow_rate, 0.0, 0.0)
                
                p1_ready, p2_ready, _, _, _ = await asyncio.get_event_loop().run_in_executor(
                    None,
                    pump._pump.pump.wait_until_both_ready,
                    120.0,
                )

                if not (p1_ready and p2_ready):
                    self.error_occurred.emit("run_buffer", "Dispense failed")
                    self.operation_completed.emit("run_buffer", False)
                    return False

                await asyncio.sleep(0.2)

            elapsed_total = (asyncio.get_event_loop().time() - start_time) / 60.0
            total_volume = cycle_count * volume_ul

            logger.info("\n✅ Buffer flow completed")
            logger.info(f"   Cycles: {cycle_count}")
            logger.info(f"   Volume: {total_volume:.0f}µL")
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
            pump._pump.pump.send_command("/0TR")  # Broadcast terminate

            self._current_operation = PumpOperation.IDLE
            self.operation_completed.emit("emergency_stop", True)
            logger.info("✅ Emergency stop executed")
            return True

        except Exception as e:
            logger.exception(f"Emergency stop failed: {e}")
            return False

    def cancel_operation(self) -> None:
        """Request cancellation of current operation (graceful)."""
        if not self.is_idle:
            logger.info(f"Requesting cancellation of {self._current_operation.value}")
            self._shutdown_requested = True

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
                    logger.info("    Opening 3-way valves...")
                    ctrl.knx_three_both(1)
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
            pump.initialize_pumps()
            p1_ready, p2_ready, elapsed, _, _ = await asyncio.get_event_loop().run_in_executor(
                None,
                pump._pump.pump.wait_until_both_ready,
                30.0,
            )
            if p1_ready and p2_ready:
                logger.info(f"✅ Plungers homed to 0µL in {elapsed:.1f}s")
                return True
            logger.warning("⚠️ Failed to home plungers")
            return False
        except Exception as e:
            logger.error(f"❌ Error homing plungers: {e}")
            return False
