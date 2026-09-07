"""Stage 2 - face detection and encoding.

InsightFace `buffalo_l`: RetinaFace detection + 5-point alignment + ArcFace,
producing a 512-d L2-normalized embedding. Runs on ONNX Runtime, so there is
no compiler dependency on Windows (unlike dlib / face_recognition).
"""

from __future__ import annotations

import contextlib
import io
import os
import sys
import warnings
from pathlib import Path

import numpy as np

from . import config
from .hashutil import embedding_hash

# InsightFace announces every model file it loads with bare print() calls, and
# scikit-image raises a FutureWarning from inside insightface's own alignment
# code on every encode. Neither is actionable and both land in the middle of a
# rendered panel, which ruins a screen recording. Set FACEPROOF_VERBOSE=1 to see
# them again when debugging a model-loading problem.
VERBOSE = os.getenv("FACEPROOF_VERBOSE", "0") != "0"

if not VERBOSE:
    warnings.filterwarnings(
        "ignore", category=FutureWarning, module=r"insightface\..*"
    )
    warnings.filterwarnings("ignore", message=r".*`estimate` is deprecated.*")


@contextlib.contextmanager
def _quiet_load():
    """Swallow the loader's stdout chatter, but never swallow a real failure.

    Only stdout is captured; exceptions propagate untouched, and anything the
    loader printed is replayed to stderr if it raised -- so a genuine model
    download or ONNX error stays fully diagnosable.
    """
    if VERBOSE:
        yield
        return

    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            yield
    except Exception:
        captured = buf.getvalue()
        if captured:
            print(captured, file=sys.stderr)
        raise

# cv2 and insightface are imported lazily. They are heavy (and unavailable on
# Python 3.13+), and the pure-logic modules that import this one -- verify.py in
# particular -- must stay importable without them.
_app = None


def _cv2():
    import cv2
    return cv2


def _get_app():
    global _app
    if _app is None:
        with _quiet_load():
            try:
                import onnxruntime
                # 3 = ERROR. Silences the ONNX Runtime C++ provider banner.
                onnxruntime.set_default_logger_severity(3)
            except Exception:
                pass

            from insightface.app import FaceAnalysis

            _app = FaceAnalysis(
                name=config.INSIGHTFACE_MODEL,
                providers=["CPUExecutionProvider"],
                allowed_modules=["detection", "recognition"],
            )
            _app.prepare(ctx_id=-1, det_size=(config.DET_SIZE, config.DET_SIZE))
    return _app


def _read(path: str | Path) -> np.ndarray:
    cv2 = _cv2()
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"unreadable image: {path}")
    return img


def detect_all(image_path: str | Path) -> list:
    return _get_app().get(_read(image_path))


def encode(image_path: str | Path) -> dict:
    """Encode the largest face in the image.

    Raises ValueError when no face is found -- callers treat that as a hard
    failure for the probe and as a skip for a search candidate.
    """
    faces = detect_all(image_path)
    if not faces:
        raise ValueError("no face detected")

    f = max(faces, key=lambda x: (x.bbox[2] - x.bbox[0]) * (x.bbox[3] - x.bbox[1]))
    emb = np.asarray(f.normed_embedding, dtype=np.float32)  # already unit length
    return {
        "bbox": [round(float(v), 2) for v in f.bbox],
        "det_score": float(f.det_score),
        "faces_in_image": len(faces),
        "embedding": emb,
        "embedding_hash": embedding_hash(emb),
    }


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity of two unit vectors."""
    return float(np.dot(np.asarray(a, dtype=np.float32), np.asarray(b, dtype=np.float32)))


def save_probe_crop(image_path: str | Path, bbox, dest: str | Path,
                    margin: float | None = None) -> str:
    """Write a context-padded crop around the face.

    A tight face chip performs badly in reverse image search; engines match on
    whole-scene features too. A ~60% margin is the sweet spot.
    """
    cv2 = _cv2()
    margin = config.CROP_MARGIN if margin is None else margin
    img = _read(image_path)
    h, w = img.shape[:2]
    x1, y1, x2, y2 = bbox
    bw, bh = x2 - x1, y2 - y1
    x1 = int(max(0, x1 - bw * margin))
    y1 = int(max(0, y1 - bh * margin))
    x2 = int(min(w, x2 + bw * margin))
    y2 = int(min(h, y2 + bh * margin))
    crop = img[y1:y2, x1:x2]
    dest = Path(dest)
    cv2.imwrite(str(dest), crop)
    return str(dest)


def save_annotated(image_path: str | Path, bbox, det_score: float,
                   dest: str | Path) -> str:
    """Bounding-box overlay -- purely for the demo recording."""
    cv2 = _cv2()
    img = _read(image_path)
    x1, y1, x2, y2 = [int(v) for v in bbox]
    cv2.rectangle(img, (x1, y1), (x2, y2), (0, 220, 0), 3)
    cv2.putText(img, f"det {det_score:.3f}", (x1, max(24, y1 - 10)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 220, 0), 2, cv2.LINE_AA)
    dest = Path(dest)
    cv2.imwrite(str(dest), img)
    return str(dest)
