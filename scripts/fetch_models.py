"""Pre-download the InsightFace models.

The first call to FaceAnalysis pulls ~300 MB.

    python scripts/fetch_models.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from faceproof import config  # noqa: E402


def main() -> int:
    from insightface.app import FaceAnalysis

    print(f"downloading insightface model pack: {config.INSIGHTFACE_MODEL}")
    app = FaceAnalysis(name=config.INSIGHTFACE_MODEL,
                       providers=["CPUExecutionProvider"],
                       allowed_modules=["detection", "recognition"])
    app.prepare(ctx_id=-1, det_size=(config.DET_SIZE, config.DET_SIZE))
    print("models ready (cached under ~/.insightface/models)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
