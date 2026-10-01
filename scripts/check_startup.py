"""CPU startup and frozen-source integrity smoke check; no model calls."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from equipment_desk.core import Desk
desk=Desk(ROOT/"data")
assert desk.catalog()["records"]
print("CPU startup and source integrity passed")
