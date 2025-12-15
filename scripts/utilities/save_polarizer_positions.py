import json

from utils.device_configuration import DeviceConfiguration

cfg = DeviceConfiguration()
config_dict = cfg.to_dict()

# Add polarizer positions to baseline
if "baseline" not in config_dict:
    config_dict["baseline"] = {}

config_dict["baseline"]["oem_polarizer_s_position"] = 50
config_dict["baseline"]["oem_polarizer_p_position"] = 138

# Save back to file
with open(cfg.config_path, "w") as f:
    json.dump(config_dict, f, indent=2)

print(f"Saved polarizer positions to {cfg.config_path}")
print("S position: 50")
print("P position: 138")
