#!/usr/bin/env python3
"""
Ingest fashion dataset into local Qdrant for ecommerce mode.

Expects dataset layout (see data/fashion-dataset/README.md):
  data/fashion-dataset/
    images/{id}.jpg
    styles.csv
    images.csv

Run from drilldown-unified root:
  python3 scripts/ingest_fashion_dataset.py
  python3 scripts/ingest_fashion_dataset.py --limit 1000
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.shared.config import settings  # noqa: E402

BATCH_SIZE = 64


def _dataset_root(override: str | None) -> Path:
    if override:
        path = Path(override)
        return path if path.is_absolute() else ROOT / path
    # Default: parent of images dir from settings
    return settings.DATASET_IMAGES_DIR.parent


def ingest(limit: int | None = None, dataset_path: str | None = None) -> None:
    import pandas as pd
    from fashion_clip.fashion_clip import FashionCLIP
    from qdrant_client import QdrantClient
    from qdrant_client.http import models
    from tqdm import tqdm

    dataset_root = _dataset_root(dataset_path)
    images_dir = dataset_root / "images"
    styles_csv = dataset_root / "styles.csv"
    images_csv = dataset_root / "images.csv"

    for path, label in (
        (images_dir, "images/"),
        (styles_csv, "styles.csv"),
        (images_csv, "images.csv"),
    ):
        if not path.exists():
            raise FileNotFoundError(
                f"Missing {label} at {path}. See data/fashion-dataset/README.md"
            )

    settings.QDRANT_PATH.mkdir(parents=True, exist_ok=True)

    print("Loading CSV files...")
    styles_df = pd.read_csv(styles_csv, on_bad_lines="skip")
    images_df = pd.read_csv(images_csv)
    images_df["id"] = (
        images_df["filename"].str.replace(".jpg", "", regex=False).astype(int)
    )
    df = pd.merge(styles_df, images_df, on="id")

    if limit:
        df = df.head(limit)
        print(f"Limiting ingestion to first {limit} products.")

    print(f"Total products to ingest: {len(df)}")
    print(f"Qdrant path: {settings.QDRANT_PATH}")
    print(f"Collection: {settings.COLLECTION_NAME}")

    client = QdrantClient(path=str(settings.QDRANT_PATH))
    exists = any(c.name == settings.COLLECTION_NAME for c in client.get_collections().collections)
    if not exists:
        print(f"Creating collection: {settings.COLLECTION_NAME}")
        client.create_collection(
            collection_name=settings.COLLECTION_NAME,
            vectors_config=models.VectorParams(size=512, distance=models.Distance.COSINE),
        )

    print("Loading FashionCLIP...")
    fclip = FashionCLIP("fashion-clip")

    for i in tqdm(range(0, len(df), BATCH_SIZE)):
        batch_df = df.iloc[i : i + BATCH_SIZE]
        valid_paths: list[str] = []
        valid_indices: list[int] = []
        for idx, row in batch_df.iterrows():
            img_path = images_dir / row["filename"]
            if img_path.exists():
                valid_paths.append(str(img_path))
                valid_indices.append(idx)

        if not valid_paths:
            continue

        embeddings = fclip.encode_images(valid_paths, batch_size=BATCH_SIZE)
        points = []
        for j, idx in enumerate(valid_indices):
            row = df.loc[idx]
            payload = {k: v for k, v in row.to_dict().items() if pd.notna(v)}
            points.append(
                models.PointStruct(
                    id=int(row["id"]),
                    vector=embeddings[j].tolist(),
                    payload=payload,
                )
            )

        client.upsert(collection_name=settings.COLLECTION_NAME, points=points)

    print("Ingestion complete!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest fashion dataset into Qdrant")
    parser.add_argument("--limit", type=int, help="Max products to ingest (dev)")
    parser.add_argument(
        "--dataset-path",
        type=str,
        default=None,
        help="Dataset root (default: parent of DATASET_IMAGES_DIR from .env)",
    )
    args = parser.parse_args()
    ingest(limit=args.limit, dataset_path=args.dataset_path)
