"""Common Utilities"""

import csv
import json
import os
import sys
import threading

_cur_dir = os.path.dirname(os.path.realpath(__file__))
_par_dir = os.path.join(_cur_dir, os.path.pardir)
if _par_dir not in sys.path:
    sys.path.append(_par_dir)

from settings import CH_LIST, CONFIG_FILE
from utils.logger import logger


def update_dict_recursively(dest, updated):
    """Update dictionary recursively.
    :param dest: Destination dict.
    :type dest: dict
    :param updated: Updated dict to be applied.
    :type updated: dict
    :return:
    """
    for k, v in updated.items():
        if isinstance(dest, dict):
            if isinstance(v, dict):
                r = update_dict_recursively(dest.get(k, {}), v)
                dest[k] = r
            else:
                dest[k] = updated[k]
        else:
            dest = {k: updated[k]}
    return dest


def number_to_ordinal(n):
    """Convert number to ordinal number string"""
    return "%d%s" % (n, "tsnrhtdd"[(n / 10 % 10 != 1) * (n % 10 < 4) * n % 10 :: 4])


lock = threading.Lock()


def update_config_file(data):
    old_data = update_dict_recursively(dest=get_config(), updated=data)
    with lock:
        with open(CONFIG_FILE, "w") as jp:
            json.dump(old_data, jp, indent=2)


def get_config():
    with lock:
        try:
            conf = json.loads(open(CONFIG_FILE).read())
            return conf
        except Exception as e:
            logger.error(f"Failed to read config file ({e})")


def export_segments(segments, path, value_list, ts_list):
    data = []
    for seg in segments:
        data.append(
            {
                "Name": seg["name"],
                "StartTime": seg["start_ts"],
                "EndTime": seg["end_ts"],
                "ShiftA": seg.get("shift_a", ""),
                "ShiftB": seg.get("shift_b", ""),
                "ShiftC": seg.get("shift_c", ""),
                "ShiftD": seg.get("shift_d", ""),
                "ShiftM": seg.get("shift_m", ""),
                "UserNote": seg.get("note", ""),
            },
        )
    keys = list(data[0].keys())
    try:
        with open(
            os.path.join(path, "segments_table.csv"),
            "w",
            newline="",
        ) as output_file:
            dict_writer = csv.DictWriter(output_file, keys, delimiter="\t")
            dict_writer.writeheader()
            dict_writer.writerows(data)
    except Exception as e:
        logger.error(f"Failed to export segment table - {e}")
    for seg in segments:
        data = {ch: [] for ch in CH_LIST}
        for ch in CH_LIST:
            start_val = None
            for i, ts in enumerate(ts_list[ch]):
                if seg["start_ts"] <= ts <= seg["end_ts"]:
                    if start_val is None:
                        start_val = value_list[ch][i]
                        start_time = ts_list[ch][i]
                    data[ch].append(
                        {
                            "ts": (ts - start_time),
                            "val": round(value_list[ch][i] - start_val, 3),
                        },
                    )

        # Fill blank cells
        max_len = max([len(v) for v in data.values()])
        for ch in CH_LIST:
            for _ in range(max_len - len(data[ch])):
                data[ch].append({"ts": "", "val": ""})
        headers = [
            [
                f"X_{seg['name']}_{ch}_{seg['start_ts']}",
                f"Y_{seg['name']}_{ch}_{seg['start_ts']}",
            ]
            for ch in ["A", "B", "C", "D", "M"]
        ]
        with open(
            os.path.join(path, f"{seg['name']}.csv"),
            "w",
            newline="",
        ) as csv_file:
            writer = csv.writer(
                csv_file,
                delimiter="\t",
                quotechar="|",
                quoting=csv.QUOTE_MINIMAL,
            )
            writer.writerow([h for sublist in headers for h in sublist])
            for i in range(max_len):
                writer.writerow(
                    [
                        data["a"][i]["ts"],
                        data["a"][i]["val"],
                        data["b"][i]["ts"],
                        data["b"][i]["val"],
                        data["c"][i]["ts"],
                        data["c"][i]["val"],
                        data["d"][i]["ts"],
                        data["d"][i]["val"],
                    ],
                )
    return True


def load_segment(path):
    try:
        seg_list = []
        with open(path, newline="") as csvfile:
            reader = csv.DictReader(csvfile)
            for r in reader:
                for k, v in r.items():
                    try:
                        r[k] = float(v)
                    except ValueError:
                        pass
                seg_list.append(r)
        return sorted(seg_list, key=lambda s: s["Concentration"])
    except Exception as e:
        logger.error(f"Failed to read segment file({path}) - {e}")
