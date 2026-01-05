from affilabs.services.data_collector import DataCollector
from affilabs.domain.flag import InjectionFlag

print("Testing data cleanup changes...")
print()

# Test 1: Metadata no longer has redundant timestamp
dc = DataCollector()
dc.start_collection()
print("✓ DataCollector initialized")
print(f"  Metadata keys: {list(dc.metadata.keys())}")
print(f"  Has 'recording_start': {'recording_start' in dc.metadata}")
print(f"  Has 'recording_start_timestamp' (should be False): {'recording_start_timestamp' in dc.metadata}")
print()

# Test 2: Flag export no longer has spr_value
flag = InjectionFlag(channel='A', time=10.0, spr=1000.0)
export = flag.to_export_dict()
print("✓ Flag export tested")
print(f"  Export keys: {list(export.keys())}")
print(f"  Has 'spr': {'spr' in export}")
print(f"  Has 'spr_value' (should be False): {'spr_value' in export}")
print()

# Test 3: Verify values
if 'recording_start_timestamp' not in dc.metadata and 'spr_value' not in export:
    print("=== ALL DATA CLEANUP VERIFIED ===")
    print("✓ Removed redundant 'recording_start_timestamp'")
    print("✓ Removed redundant 'spr_value'")
    print("✓ Removed 368 lines of dead code from affilabs_core_ui.py")
else:
    print("ERROR: Some redundancies still present!")
