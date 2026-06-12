"""Explainer page persistence — paths, cache, and metadata storage."""

import hashlib
import json
from pathlib import Path


class PageRepository:
    """Data access for explainer static pages on disk."""

    def __init__(self, static_dir: Path | str) -> None:
        self._static_dir = Path(static_dir)
        self._static_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def compute_content_hash(key: str) -> str:
        return hashlib.sha256(key.encode()).hexdigest()

    def image_url(self, page_id: str) -> str:
        return f"/static/{page_id}.png"

    def initial_page_paths(self, query: str) -> tuple[str, Path]:
        page_id = self.compute_content_hash(f"initial_{query}")
        return page_id, self._static_dir / f"{page_id}.png"

    def drill_hash_key(
        self,
        parent_id: str,
        x: float,
        y: float,
        vision_model: str,
        grounding_mode: str,
        coord_precision: int,
        custom_topic: str | None = None,
        *,
        include_custom_topic_in_hash: bool = False,
    ) -> str:
        rx, ry = round(x, coord_precision), round(y, coord_precision)
        key = f"drill_{parent_id}_{rx}_{ry}_{vision_model}_{grounding_mode}"
        if include_custom_topic_in_hash and custom_topic:
            key += f"_{custom_topic}"
        return key

    def drill_page_paths(self, page_id: str) -> tuple[Path, Path]:
        return (
            self._static_dir / f"{page_id}.png",
            self._static_dir / f"{page_id}.json",
        )

    def parent_image_path(self, parent_id: str) -> Path:
        return self._static_dir / f"{parent_id}.png"

    def segment_image_path(self, page_id: str) -> Path:
        return self._static_dir / f"seg_{page_id}.png"

    def marked_image_path(self, page_id: str) -> Path:
        return self._static_dir / f"marked_{page_id}.png"

    def page_image_path(self, page_id: str) -> Path:
        return self._static_dir / f"{page_id}.png"

    def load_drill_cache(self, page_id: str) -> dict | None:
        image_path, metadata_path = self.drill_page_paths(page_id)
        if not (image_path.exists() and metadata_path.exists()):
            return None
        with metadata_path.open() as handle:
            cached_data = json.load(handle)
        return {"id": page_id, "imageUrl": self.image_url(page_id), **cached_data}

    def save_drill_metadata(self, metadata_path: Path | str, metadata: dict) -> None:
        with Path(metadata_path).open("w") as handle:
            json.dump(metadata, handle)

    @staticmethod
    def cleanup_temp_files(*paths: str | Path | None) -> None:
        for path in paths:
            if not path:
                continue
            file_path = Path(path)
            if file_path.exists():
                try:
                    file_path.unlink()
                except OSError:
                    pass
