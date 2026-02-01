
class MockP4PROPLUS:
    def __init__(self):
        self._ser = None
        self.version = "V2.3"
        self.firmware_id = "P4PRO"
        self.name = "pico_p4pro"

    def has_internal_pumps(self):
        if not self.version:
            return False
        try:
            version_str = self.version.replace("V", "").replace("v", "")
            version_float = float(version_str)
            has_pumps = version_float >= 2.3
            if has_pumps:
                print("[OK] P4PROPLUS detected: {} has internal pumps".format(self.version))
            else:
                print("[INFO] Standard P4PRO: {} needs external AffiPump".format(self.version))
            return has_pumps
        except (ValueError, AttributeError) as e:
            print("[WARN] Version parse error: {}".format(e))
            return False

    def get_pump_capabilities(self):
        if not self.has_internal_pumps():
            return {}
        return {
            "type": "peristaltic",
            "bidirectional": False,
            "has_homing": False,
            "has_position_tracking": False,
            "supports_partial_loop": False,
            "max_flow_rate_ul_min": 300,
            "min_flow_rate_ul_min": 1,
            "supports_flow_rate_change": True,
            "ul_per_revolution": 3.0,
            "min_rpm": 5,
            "max_rpm": 220,
            "recommended_prime_cycles": 10,
            "requires_visual_verification": True,
            "suction_reliability_warning": "[CRITICAL] Peristaltic pumps may fail to pick up sample at START"
        }

    def _ul_min_to_rpm(self, rate_ul_min):
        caps = self.get_pump_capabilities()
        ul_per_rev = caps["ul_per_revolution"]
        rpm = rate_ul_min / ul_per_rev
        rpm = max(caps["min_rpm"], min(caps["max_rpm"], int(rpm)))
        return rpm

    def pump_start(self, rate_ul_min, ch=1):
        if not self.has_internal_pumps():
            print("[ERROR] No internal pumps available")
            return False

        caps = self.get_pump_capabilities()
        min_rate = caps["min_flow_rate_ul_min"]
        max_rate = caps["max_flow_rate_ul_min"]

        if rate_ul_min < min_rate or rate_ul_min > max_rate:
            print("[ERROR] Flow rate {} uL/min out of range [{}-{}]".format(rate_ul_min, min_rate, max_rate))
            return False

        rpm = self._ul_min_to_rpm(rate_ul_min)
        cmd = "pr{}{:04d}".format(ch, rpm)

        print("[CMD] Pump {}: {} uL/min -> {} RPM -> {}".format(ch, rate_ul_min, rpm, cmd))
        return True

    def pump_stop(self, ch=1):
        if not self.has_internal_pumps():
            print("[ERROR] No internal pumps available")
            return False
        cmd = "ps{}".format(ch)
        print("[CMD] Stop pump {}: {}".format(ch, cmd))
        return True

def test_detection():
    print("="*70)
    print("TEST 1: P4PROPLUS Detection")
    print("="*70)

    ctrl_plus = MockP4PROPLUS()
    ctrl_plus.version = "V2.3"
    has_pumps = ctrl_plus.has_internal_pumps()
    print("\nVersion: {}".format(ctrl_plus.version))
    print("Has internal pumps: {}".format(has_pumps))

    if has_pumps:
        caps = ctrl_plus.get_pump_capabilities()
        print("\nCapabilities:")
        print("  Type: {}".format(caps["type"]))
        print("  Bidirectional: {}".format(caps["bidirectional"]))
        print("  Flow rate range: {}-{} uL/min".format(caps["min_flow_rate_ul_min"], caps["max_flow_rate_ul_min"]))
        print("  RPM range: {}-{}".format(caps["min_rpm"], caps["max_rpm"]))
        print("\n{}".format(caps["suction_reliability_warning"]))

def test_pump_commands():
    print("\n" + "="*70)
    print("TEST 2: Pump Commands (uL/min -> RPM conversion)")
    print("="*70)

    ctrl = MockP4PROPLUS()
    ctrl.version = "V2.3"

    print("\nController: {}".format(ctrl.version))
    print("Has pumps: {}".format(ctrl.has_internal_pumps()))

    print("\n--- Flow Rate Conversions (3 uL/rev) ---")
    test_rates = [15, 50, 100, 150, 300]

    for rate in test_rates:
        ctrl.pump_start(rate_ul_min=rate, ch=1)

    print("\n--- Both Pumps ---")
    ctrl.pump_start(rate_ul_min=100, ch=3)
    ctrl.pump_stop(ch=3)

if __name__ == "__main__":
    print("="*70)
    print("  P4PROPLUS INTERNAL PUMP IMPLEMENTATION TEST")
    print("="*70)

    test_detection()
    test_pump_commands()

    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print("[OK] Detection: has_internal_pumps() checks version >= V2.3")
    print("[OK] Commands: pr{ch}{rpm:04d} for start, ps{ch} for stop")
    print("[OK] Conversion: uL/min / ul_per_rev = RPM (calibrated)")
    print("[WARN] Suction reliability: Visual verification required")
    print("="*70)
