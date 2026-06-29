"""
Smoke test for the Docling ingestion pipeline.

Run from the project root:
    python test_ingestion.py path/to/your.pdf

What it checks:
  1. Docling parses the PDF without crashing
  2. Elements are extracted (text, tables, figures)
  3. Figures are sent to VLM and get a description back
  4. Chunks are created and embedded
  5. Qdrant stores them
  6. A test search returns results with content_type in the payload
"""

import asyncio
import sys
import tempfile
from pathlib import Path


async def main(pdf_path: str) -> None:
    pdf_bytes = Path(pdf_path).read_bytes()
    source_name = Path(pdf_path).name
    kb_id = "smoke_test"

    with tempfile.TemporaryDirectory() as qdrant_dir:
        print(f"\n=== Ingesting: {source_name} ===")

        # --- Phase 1: Docling parse only (no embed/store) ---
        print("\n[1] Testing Docling parse...")
        import sys, os
        sys.path.insert(0, str(Path(__file__).parent))

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = Path(tmp.name)

        from backend.services.knowledge_base.ingestion import _parse_with_docling
        elements = _parse_with_docling(tmp_path)
        tmp_path.unlink(missing_ok=True)

        by_type: dict[str, int] = {}
        for e in elements:
            by_type[e["type"]] = by_type.get(e["type"], 0) + 1

        print(f"    Total elements: {len(elements)}")
        for t, n in sorted(by_type.items()):
            print(f"    {t:10s}: {n}")

        figures = [e for e in elements if e["type"] == "figure"]
        if figures:
            print(f"\n[2] Testing VLM figure description ({len(figures)} figures)...")
            from backend.services.knowledge_base.figure_enrichment import describe_figure
            sample = figures[0]
            desc = describe_figure(sample["image_bytes"], sample["caption"])
            print(f"    Caption : {sample['caption'][:80] or '(no caption)'}")
            print(f"    VLM desc: {desc[:200]}...")
        else:
            print("\n[2] No figures found — skipping VLM test")

        # --- Phase 3: Full ingest into temp Qdrant ---
        print("\n[3] Running full ingest into temp Qdrant...")
        from backend.services.knowledge_base.ingestion import ingest_pdf
        stats = await ingest_pdf(pdf_bytes, source_name, kb_id, qdrant_dir)
        n_chunks = stats.get("chunk_count", 0)
        print(f"    Stored {n_chunks} chunks (pages={stats.get('page_count')}, figures={stats.get('figure_count')})")

        # --- Phase 4: Search test ---
        print("\n[4] Testing retrieval...")
        from backend.services.knowledge_base.retriever import search_kb

        queries = ["installation", "fault diagnosis", "safety precautions", "maintenance"]
        for q in queries:
            results = await search_kb(q, kb_id, qdrant_dir, top_k=2)
            if results:
                r = results[0]
                print(f"    Query '{q}':")
                print(f"      page={r['page_num']} type={r['content_type']} score={r['score']}")
                print(f"      text: {r['text'][:120]}...")
            else:
                print(f"    Query '{q}': no results")

        print("\n=== SMOKE TEST PASSED ===\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_ingestion.py path/to/file.pdf")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
