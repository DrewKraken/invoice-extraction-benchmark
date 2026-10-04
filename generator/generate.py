"""
Write the benchmark corpus to disk: documents, answer keys and a manifest.

    python -m generator.generate                       # corpus/v1, seed 42
    python -m generator.generate --out /tmp/v1 --check  # regenerate and compare

Layout of the output folder:

    documents/<doc_id>.pdf|jpg|png   the documents, as a reader would receive them
    answers/<doc_id>.json            the answer key for one document
    manifest.json                    every document: category, difficulty,
                                     degradation, file hash, answer key
    metadata.jsonl                   one row per document (for dataset viewers)

Digital documents are PDFs with a real text layer; photos, scans and
handwritten documents are JPEG or PNG images. The same seed reproduces the
same documents byte for byte with the same library versions and, for the
handwritten ones, the same handwriting font (see handwriting.py).
`--check` compares the regenerated files with the sha256 sums in an
existing manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import random
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .corpus_v1 import SETS
from .degrade import apply as apply_degradations
from .handwriting import hand_font_fingerprint
from .layout import build_pages
from .render import render_images, render_pdf
from .spec import DocSpec

GENERATOR_VERSION = 1
ROOT = Path(__file__).resolve().parents[1]


def render_document(spec: DocSpec, seed: int) -> Tuple[bytes, str, int, Dict]:
    """(file bytes, extension, page count, extra manifest info)."""
    pages = build_pages(spec)
    info: Dict = {}
    if spec.render.mode == "pdf":
        data = render_pdf(pages, title=f"{spec.title} {spec.number or ''}".strip(), author=spec.vendor.name)
        return data, "pdf", len(pages), info
    images = render_images(pages, dpi=spec.render.dpi, seed=f"{seed}:{spec.doc_id}")
    if len(images) != 1:
        raise ValueError(f"{spec.doc_id}: an image document must be one page, got {len(images)}")
    rng = random.Random(f"{seed}:{spec.doc_id}:degrade")
    img = apply_degradations(images[0], spec.render.degradations, rng)
    dpi = int(img.info.get("eval_dpi", spec.render.dpi))
    buf = io.BytesIO()
    if spec.render.fmt == "png":
        img.save(buf, "PNG", dpi=(dpi, dpi), optimize=False)
        ext = "png"
    else:
        quality = int(img.info.get("eval_jpeg_quality", 90))
        img.save(buf, "JPEG", quality=quality, dpi=(dpi, dpi))
        ext = "jpg"
    info.update({"pixels": list(img.size), "dpi": dpi})
    return buf.getvalue(), ext, 1, info


def manifest_entry(spec: DocSpec, file_name: str, data: bytes, pages: int, info: Dict) -> Dict:
    return {
        "doc_id": spec.doc_id,
        "file": file_name,
        "category": spec.category,
        "difficulty": spec.difficulty,
        "kind": spec.kind,
        "description": spec.description,
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "pages": pages,
        "render": spec.render.mode,
        "severity": spec.severity,
        "degradations": [{"kind": d.kind, "severity": d.severity} for d in spec.render.degradations],
        "legibility": spec.render.handwriting,
        "currency": spec.currency,
        "tags": list(spec.tags),
        "base_id": spec.base_id,
        **info,
        "expected": spec.expected().as_dict(),
    }


def generate(set_name: str = "v1", seed: int = 42, out: Optional[Path] = None,
             only: Optional[Sequence[str]] = None, quiet: bool = False) -> Dict:
    if set_name not in SETS:
        raise SystemExit(f"unknown set {set_name!r}; known: {', '.join(SETS)}")
    specs = SETS[set_name](seed)
    if only:
        wanted = set(only)
        specs = [s for s in specs if s.doc_id in wanted]
    out = out or (ROOT / "corpus" / set_name)
    (out / "documents").mkdir(parents=True, exist_ok=True)
    (out / "answers").mkdir(parents=True, exist_ok=True)
    font_name, font_sha = hand_font_fingerprint()
    entries: List[Dict] = []
    for n, spec in enumerate(specs, 1):
        data, ext, pages, info = render_document(spec, seed)
        name = f"documents/{spec.doc_id}.{ext}"
        (out / name).write_bytes(data)
        entry = manifest_entry(spec, name, data, pages, info)
        with open(out / "answers" / f"{spec.doc_id}.json", "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(entry, indent=1) + "\n")
        entries.append(entry)
        if not quiet:
            print(f"[{n:3d}/{len(specs)}] {name} ({pages}p, {len(data) // 1024} KB)", flush=True)
    manifest = {
        "set": set_name,
        "seed": seed,
        "generator_version": GENERATOR_VERSION,
        "hand_font": {"file": font_name, "sha256_16": font_sha},
        "count": len(entries),
        "documents": entries,
    }
    if not only:
        with open(out / "manifest.json", "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(manifest, indent=1) + "\n")
        with open(out / "metadata.jsonl", "w", encoding="utf-8", newline="\n") as fh:
            for e in entries:
                row = {"file_name": e["file"], **{k: v for k, v in e.items() if k != "file"}}
                fh.write(json.dumps(row) + "\n")
    return manifest


def check(new: Dict, reference: Path) -> int:
    ref = json.loads(reference.read_text(encoding="utf-8"))
    want = {d["doc_id"]: d["sha256"] for d in ref["documents"]}
    got = {d["doc_id"]: d["sha256"] for d in new["documents"]}
    same = [i for i in want if got.get(i) == want[i]]
    differ = sorted(i for i in want if i in got and got[i] != want[i])
    missing = sorted(set(want) - set(got))
    print(f"{len(same)} of {len(want)} documents byte-identical to {reference}")
    if differ:
        print("different:", ", ".join(differ))
        print("(handwritten documents differ when another handwriting font is used; see handwriting.py)")
    if missing:
        print("missing:", ", ".join(missing))
    return 0 if not differ and not missing else 1


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Generate the invoice extraction benchmark corpus.")
    p.add_argument("--set", default="v1")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out", type=Path, default=None, help="output folder (default: corpus/<set>)")
    p.add_argument("--only", default="", help="comma-separated doc ids (no manifest written)")
    p.add_argument("--check", action="store_true",
                   help="compare the regenerated files with corpus/<set>/manifest.json")
    p.add_argument("--quiet", action="store_true")
    a = p.parse_args(argv)
    only = [x for x in a.only.split(",") if x] or None
    reference = ROOT / "corpus" / a.set / "manifest.json"
    out = a.out or (ROOT / "corpus" / a.set)
    if a.check and out.resolve() == reference.parent.resolve():
        raise SystemExit("--check needs --out pointing somewhere other than the published corpus")
    m = generate(a.set, a.seed, out, only, a.quiet)
    print(f"{m['count']} documents -> {out}")
    if a.check:
        return check(m, reference)
    return 0


if __name__ == "__main__":
    sys.exit(main())
