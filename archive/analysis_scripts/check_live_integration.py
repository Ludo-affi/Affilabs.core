"""Quick diagnostic to check actual integration times being used in live mode.
Run this AFTER calibration completes and live mode starts.
"""

import logging

logger = logging.getLogger(__name__)


def check_integration_times():
    """Check what integration times are actually set."""
    try:
        # Import app context
        from main.main import app

        if not hasattr(app, "state_machine") or app.state_machine is None:
            print("❌ State machine not available")
            return

        sm = app.state_machine

        print("\n" + "=" * 80)
        print("INTEGRATION TIME DIAGNOSTIC")
        print("=" * 80)

        # Check if calibration state has per-channel integration
        if hasattr(sm, "calib_state") and sm.calib_state:
            cs = sm.calib_state
            print("\n📊 CALIBRATION STATE:")
            if hasattr(cs, "integration_per_channel") and cs.integration_per_channel:
                print("   Per-channel integration times:")
                for ch, integ in cs.integration_per_channel.items():
                    print(f"      {ch.upper()}: {integ*1000:.1f}ms")
            elif hasattr(cs, "integration") and cs.integration:
                print(f"   Global integration: {cs.integration*1000:.1f}ms")
            else:
                print("   ⚠️ No integration times found")

        # Check if state machine has live boost values
        print("\n🚀 LIVE MODE BOOST:")
        if (
            hasattr(sm, "live_integration_per_channel")
            and sm.live_integration_per_channel
        ):
            print("   Boosted per-channel integration times:")
            for ch, integ in sm.live_integration_per_channel.items():
                print(f"      {ch.upper()}: {integ*1000:.1f}ms")
        else:
            print("   ⚠️ No live_integration_per_channel found")

        # Check if data acquisition wrapper has the values
        print("\n🔧 DATA ACQUISITION WRAPPER:")
        if hasattr(sm, "data_acquisition") and sm.data_acquisition:
            daq = sm.data_acquisition
            if hasattr(daq, "data_acquisition") and daq.data_acquisition:
                actual_daq = daq.data_acquisition
                if (
                    hasattr(actual_daq, "integration_per_channel")
                    and actual_daq.integration_per_channel
                ):
                    print("   DAQ integration_per_channel:")
                    for ch, integ in actual_daq.integration_per_channel.items():
                        print(f"      {ch.upper()}: {integ*1000:.1f}ms")
                else:
                    print("   ⚠️ No integration_per_channel in actual DAQ")
            else:
                print("   ⚠️ No data_acquisition object")
        else:
            print("   ⚠️ No DataAcquisitionWrapper")

        # Check actual spectrometer setting
        print("\n🔬 ACTUAL SPECTROMETER:")
        if hasattr(sm, "usb_adapter") and sm.usb_adapter:
            try:
                if hasattr(sm.usb_adapter, "integration_time"):
                    actual_int = sm.usb_adapter.integration_time
                    print(f"   Current integration time: {actual_int*1000:.1f}ms")
                else:
                    print("   ⚠️ Cannot read integration_time property")
            except Exception as e:
                print(f"   ❌ Error reading integration time: {e}")
        else:
            print("   ⚠️ No usb_adapter")

        print("\n" + "=" * 80)

    except Exception as e:
        print(f"❌ Error in diagnostic: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    check_integration_times()
