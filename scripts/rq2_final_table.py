"""Write the contrast table from a stored RQ2 analysis summary: ``SUMMARY OUT``."""

import sys
from pathlib import Path

from ril.analysis.rq2_final_table import write_table

if __name__ == "__main__":
    sys.stdout.write(f"{write_table(Path(sys.argv[1]), Path(sys.argv[2]))}\n")
