"""Add the mandala's script-driven user properties to the live project.json (idempotent; keeps the
values already set).

scripts/mandala_controller.js reads them in applyUserProperties:
  mandalaglitch / mandalaglitchstrength       beat glitch (slice shove) on/off + strength %
  mandaladatamosh / mandaladatamoshstrength   datamosh noise frames on/off + strength % (opacity)
  mandalabpmspin / mandalabeatsperpiece       spin follows the detected tempo: one piece (of 13)
                                              every N beats
Usage: python scripts/add_mandala_properties.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from we_paths import PROJ  # noqa: E402

PROPS = {
    "mandalaglitch": {"index": 7, "order": 107, "text": "Mandala beat glitch", "type": "bool", "value": True},
    "mandalaglitchstrength": {"index": 8, "order": 108, "text": "Glitch strength (%)", "type": "slider",
                              "min": 0, "max": 300, "step": 1, "precision": 0, "value": 100,
                              "condition": "mandalaglitch.value == true"},
    "mandaladatamosh": {"index": 9, "order": 109, "text": "Mandala datamosh noise", "type": "bool", "value": True},
    "mandaladatamoshstrength": {"index": 10, "order": 110, "text": "Datamosh strength (%)", "type": "slider",
                                "min": 0, "max": 300, "step": 1, "precision": 0, "value": 100,
                                "condition": "mandaladatamosh.value == true"},
    "mandalabpmspin": {"index": 11, "order": 111, "text": "Mandala spin follows BPM", "type": "bool", "value": False},
    "mandalabeatsperpiece": {"index": 12, "order": 112, "text": "Beats per piece (13 pieces per turn)",
                             "type": "slider", "min": 1, "max": 16, "step": 1, "precision": 0, "value": 4,
                             "condition": "mandalabpmspin.value == true"},
}

path = PROJ / "project.json"
p = json.loads(path.read_text(encoding="utf-8"))
props = p["general"]["properties"]
for k, v in PROPS.items():
    if k in props:
        v = {**v, "value": props[k].get("value", v["value"])}   # keep the user's current setting
    props[k] = v
path.write_text(json.dumps(p, indent=4, ensure_ascii=False), encoding="utf-8")
print("project.json:", ", ".join(PROPS))
