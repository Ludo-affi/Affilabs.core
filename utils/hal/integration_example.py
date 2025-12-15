"""Hardware Abstraction Layer Integration Example

This script demonstrates how to integrate the new HAL system with
the existing SPR controller architecture.
"""

from typing import Any

from utils.logger import logger

# Import the new HAL system
try:
    from utils.hal import HALConnectionError, HALError, HALFactory, SPRControllerHAL
    from utils.hal.pico_p4spr_hal import PicoP4SPRHAL

    HAL_AVAILABLE = True
except ImportError as e:
    logger.warning(f"HAL system not available: {e}")
    HAL_AVAILABLE = False


class HALControllerAdapter:
    """Adapter class to integrate HAL controllers with existing codebase.

    This adapter maintains compatibility with existing code while providing
    the benefits of the HAL system.
    """

    def __init__(self) -> None:
        """Initialize adapter."""
        self.hal_controller: SPRControllerHAL | None = None
        self.legacy_controller: Any = None  # Fallback to old controller
        self.using_hal = False

    def connect(self, device_type: str | None = None, **connection_params: Any) -> bool:
        """Connect to controller using HAL if available, legacy otherwise.

        Args:
            device_type: Specific device type or None for auto-detection
            **connection_params: Connection parameters

        Returns:
            True if connection successful

        """
        if not HAL_AVAILABLE:
            return self._connect_legacy(device_type, **connection_params)

        try:
            # Try HAL first
            logger.info("Attempting HAL connection...")
            self.hal_controller = HALFactory.create_controller(
                device_type=device_type,
                connection_params=connection_params,
            )
            self.using_hal = True
            logger.info("Successfully connected using HAL")
            return True

        except (HALError, HALConnectionError) as e:
            logger.warning(f"HAL connection failed: {e}")
            logger.info("Falling back to legacy controller...")
            return self._connect_legacy(device_type, **connection_params)

    def disconnect(self) -> None:
        """Disconnect from controller."""
        if self.using_hal and self.hal_controller:
            try:
                self.hal_controller.disconnect()
            except Exception as e:
                logger.warning(f"HAL disconnect error: {e}")
            finally:
                self.hal_controller = None
                self.using_hal = False

        if self.legacy_controller:
            try:
                # Assuming legacy controller has close() method
                if hasattr(self.legacy_controller, "close"):
                    self.legacy_controller.close()
            except Exception as e:
                logger.warning(f"Legacy disconnect error: {e}")
            finally:
                self.legacy_controller = None

    def is_connected(self) -> bool:
        """Check if controller is connected."""
        if self.using_hal and self.hal_controller:
            return self.hal_controller.is_connected()
        if self.legacy_controller:
            return self.legacy_controller.valid()  # Existing method
        return False

    def turn_on_channel(self, ch: str = "a") -> bool:
        """Turn on specific channel."""
        if self.using_hal and self.hal_controller:
            from utils.hal.spr_controller_hal import ChannelID

            try:
                channel_map = {
                    "a": ChannelID.A,
                    "b": ChannelID.B,
                    "c": ChannelID.C,
                    "d": ChannelID.D,
                }
                channel = channel_map.get(ch.lower())
                if channel:
                    return self.hal_controller.activate_channel(channel)
                return False
            except Exception as e:
                logger.warning(f"HAL channel activation failed: {e}")
                return False
        elif self.legacy_controller:
            return self.legacy_controller.turn_on_channel(ch)
        return False

    def get_temp(self) -> float:
        """Get controller temperature."""
        if self.using_hal and self.hal_controller:
            try:
                temp = self.hal_controller.get_temperature()
                return temp if temp is not None else -1.0
            except Exception as e:
                logger.warning(f"HAL temperature read failed: {e}")
                return -1.0
        elif self.legacy_controller:
            return self.legacy_controller.get_temp()
        return -1.0

    def get_device_info(self) -> dict[str, Any]:
        """Get device information."""
        if self.using_hal and self.hal_controller:
            try:
                return self.hal_controller.get_device_info()
            except Exception as e:
                logger.warning(f"HAL device info failed: {e}")
                return {}
        elif self.legacy_controller:
            # Convert legacy info to standard format
            return {
                "model": getattr(self.legacy_controller, "name", "Unknown"),
                "firmware_version": getattr(
                    self.legacy_controller,
                    "version",
                    "Unknown",
                ),
                "connection_type": "Legacy",
            }
        return {}

    def get_capabilities(self) -> dict[str, Any] | None:
        """Get controller capabilities (HAL only)."""
        if self.using_hal and self.hal_controller:
            try:
                caps = self.hal_controller.get_capabilities()
                return {
                    "supported_channels": [ch.value for ch in caps.supported_channels],
                    "max_channels": caps.max_channels,
                    "supports_temperature": caps.supports_temperature,
                    "supports_led_control": caps.supports_led_control,
                    "device_model": caps.device_model,
                }
            except Exception as e:
                logger.warning(f"HAL capabilities query failed: {e}")
        return None

    def health_check(self) -> bool:
        """Perform health check."""
        if self.using_hal and self.hal_controller:
            try:
                return self.hal_controller.health_check()
            except Exception:
                return False
        elif self.legacy_controller:
            return self.is_connected()
        return False

    def _connect_legacy(
        self,
        device_type: str | None,
        **connection_params: Any,
    ) -> bool:
        """Connect using legacy controller system."""
        try:
            # Import legacy controllers
            from utils.controller import PicoP4SPR

            # For now, only support P4SPR legacy fallback
            if device_type and "P4SPR" not in device_type.upper():
                logger.warning(f"Legacy fallback not available for {device_type}")
                return False

            self.legacy_controller = PicoP4SPR()
            success = self.legacy_controller.open()

            if success:
                logger.info("Connected using legacy controller")
            else:
                logger.warning("Legacy controller connection failed")
                self.legacy_controller = None

            return success

        except Exception as e:
            logger.error(f"Legacy connection failed: {e}")
            return False


def demonstrate_hal_integration():
    """Demonstrate HAL integration with existing code patterns."""
    if not HAL_AVAILABLE:
        print("HAL system not available - check imports")
        return

    print("=== SPR Controller HAL Integration Demo ===\n")

    # 1. Show available controllers
    print("Available HAL Controllers:")
    for controller_type in HALFactory.get_available_controllers():
        print(f"  - {controller_type}")
        caps = HALFactory.get_controller_capabilities(controller_type)
        if caps:
            print(f"    Channels: {caps['max_channels']}")
            print(f"    Temperature: {caps['supports_temperature']}")
    print()

    # 2. Demonstrate device detection
    print("Detecting connected devices...")
    devices = HALFactory.detect_connected_devices()
    if devices:
        for device in devices:
            print(f"  Found: {device['model']} ({device['firmware_version']})")
    else:
        print("  No devices detected")
    print()

    # 3. Demonstrate adapter usage
    print("Testing HAL Adapter...")
    adapter = HALControllerAdapter()

    try:
        # Try to connect
        if adapter.connect():
            print(
                f"  Connection: SUCCESS (using {'HAL' if adapter.using_hal else 'Legacy'})",
            )

            # Get device info
            device_info = adapter.get_device_info()
            if device_info:
                print(f"  Device: {device_info.get('model', 'Unknown')}")
                print(f"  Firmware: {device_info.get('firmware_version', 'Unknown')}")

            # Test capabilities (HAL only)
            caps = adapter.get_capabilities()
            if caps:
                print(f"  Channels: {caps['supported_channels']}")
                print(f"  Temperature Support: {caps['supports_temperature']}")

            # Test basic operations
            print("  Testing channel activation...")
            for ch in ["a", "b"]:
                result = adapter.turn_on_channel(ch)
                print(f"    Channel {ch}: {'OK' if result else 'FAIL'}")

            # Test temperature
            temp = adapter.get_temp()
            print(
                f"  Temperature: {temp:.1f}°C"
                if temp > -1
                else "  Temperature: Not available",
            )

            # Health check
            health = adapter.health_check()
            print(f"  Health Check: {'PASS' if health else 'FAIL'}")

        else:
            print("  Connection: FAILED")

    except Exception as e:
        print(f"  Error: {e}")

    finally:
        adapter.disconnect()
        print("  Disconnected")

    print("\n=== Demo Complete ===")


if __name__ == "__main__":
    demonstrate_hal_integration()
