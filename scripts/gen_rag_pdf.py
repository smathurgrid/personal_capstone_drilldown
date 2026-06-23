#!/usr/bin/env python3
"""Generate a PDF describing the current RAG approach (docs/RAG-Approach.pdf)."""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Preformatted, HRFlowable,
)

OUT = Path(__file__).resolve().parents[1] / "docs" / "RAG-Approach.pdf"
OUT.parent.mkdir(parents=True, exist_ok=True)

ORANGE = colors.HexColor("#ed6a2c")
DARK = colors.HexColor("#1f2633")
GREY = colors.HexColor("#5b6472")

ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Heading1"], textColor=ORANGE, spaceBefore=14, spaceAfter=6, fontSize=16)
H2 = ParagraphStyle("H2", parent=ss["Heading2"], textColor=DARK, spaceBefore=10, spaceAfter=4, fontSize=12.5)
BODY = ParagraphStyle("Body", parent=ss["BodyText"], fontSize=9.5, leading=14, alignment=TA_LEFT, spaceAfter=5)
SMALL = ParagraphStyle("Small", parent=BODY, fontSize=8.5, textColor=GREY)
MONO = ParagraphStyle("Mono", parent=ss["Code"], fontSize=7.6, leading=9.5, textColor=DARK)
TITLE = ParagraphStyle("Title", parent=ss["Title"], textColor=DARK, fontSize=22)
SUB = ParagraphStyle("Sub", parent=ss["Normal"], fontSize=11, textColor=GREY, spaceAfter=2)

F = []  # flowables


def p(text, style=BODY): F.append(Paragraph(text, style))
def gap(h=4): F.append(Spacer(1, h))
def rule(): F.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#d8dde6"), spaceBefore=6, spaceAfter=8))
def mono(text): F.append(Preformatted(text, MONO))


def kvtable(rows, col_widths):
    t = Table(rows, colWidths=col_widths, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.2),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cfd5df")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f6f9")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    F.append(t)


# ---------------- Title ----------------
F.append(Paragraph("Semantic Drill-Down — RAG Pipeline", TITLE))
F.append(Paragraph("How the knowledge-base retrieval works, end to end", SUB))
F.append(Paragraph("Current implementation overview &middot; grounded, cited answers from the organization's own manuals", SMALL))
rule()

# ---------------- 1. What & why ----------------
p("1. What this is", H1)
p("RAG = <b>Retrieval-Augmented Generation</b>. Instead of letting an AI answer from its general "
  "training, we first <b>retrieve</b> the relevant passages from the organization's own approved "
  "manual, then <b>augment</b> the AI's prompt with that verified text, so the <b>generated</b> "
  "answer is grounded in real documentation and can cite the exact source page.")
p("In this product a technician points at equipment and clicks a part. The system identifies it, "
  "looks it up in the uploaded manual, and returns the answer <b>with a citation</b> "
  "(e.g. &ldquo;IFB MACHINE.pdf, page 7&rdquo;) instead of a guess.")
p("<b>Analogy (non-technical):</b> a fast librarian reads the manual once — every page, table, and "
  "diagram — and files it on index cards. Later it instantly pulls the cards that answer your "
  "question and tells you which page they came from.", SMALL)

# ---------------- 2. Two phases ----------------
p("2. Two phases", H1)
p("The pipeline has two clearly separated phases. Most quality issues live in one or the other.")
kvtable([
    ["Phase", "When", "What it does"],
    ["Ingestion", "Once per PDF (offline)", "Read the manual, break it into searchable pieces, store them with two search 'fingerprints'."],
    ["Retrieval + Generation", "Every drill (online)", "Turn the user's target into a query, find the right page, cite it, and ground the generated answer."],
], [70, 90, 290])

# ---------------- 3. Ingestion ----------------
p("3. Ingestion pipeline (building the index)", H1)
mono(
"PDF upload\n"
"   |  kb_id = sha256(pdf)[:16]   (idempotent: re-upload rebuilds)\n"
"   v\n"
"Docling  ->  layout-aware parse: headers / text / tables / figures (with page numbers)\n"
"   |\n"
"   +-- TEXT track    -> word-window chunks (320 words, 60 overlap), section-prefixed\n"
"   +-- TABLE track   -> one chunk per ROW (header-prefixed) + table summary\n"
"   |                    (table-of-contents tables are detected & skipped)\n"
"   +-- FIGURE track  -> Qwen2.5-VL vision model writes a TEXT description of the diagram\n"
"   v\n"
"Each chunk -> TWO vectors:\n"
"   - dense  (BAAI/bge-small-en-v1.5, 384-dim)  = meaning\n"
"   - sparse (BM25 via fastembed)               = exact keywords / part numbers\n"
"   v\n"
"Qdrant (local)  ->  collection kb_{id}, named vectors {dense + sparse}\n"
"                    payload: text, page_id, page_num, source_name, zone\n"
)
p("<b>Why three tracks?</b> A manual is not flat text. Tables and diagrams carry critical "
  "information, so each content type is handled its own way: prose is windowed, tables are split "
  "row-by-row so a single row is a precise answer, and diagrams are converted to searchable text "
  "by a local vision model.", SMALL)

# ---------------- 4. Retrieval ----------------
p("4. Retrieval + generation pipeline (answering a drill)", H1)
mono(
"User clicks a region (optionally types a label, e.g. 'Control Panel')\n"
"   v\n"
"Vision model (Qwen2.5-VL) describes the clicked region\n"
"   v\n"
"QUERY = label (typed)  ->  object name (1st sentence)  ->  analysis slice\n"
"        (NOT the verbose generation prompt -- it invents detail not in the manual)\n"
"   v\n"
"Embed query: dense (BGE) + sparse (BM25)\n"
"   v\n"
"Qdrant hybrid search  ->  RRF fusion of the two ranked lists\n"
"   v\n"
"Re-join all chunks on the winning page (by page_id) into one context block\n"
"   v\n"
"Confidence = best dense COSINE on the page;  if < 0.60 -> 'No strong manual match'\n"
"   v\n"
"Inject verified page text into the generation prompt  +  show citation\n"
"        'IFB MACHINE.pdf, page 7 - 70% match'\n"
)
p("<b>Hybrid search</b> runs meaning-search (dense) and keyword-search (BM25) in parallel and "
  "merges them with Reciprocal Rank Fusion (RRF), so exact terms like part numbers and fault "
  "codes are caught alongside semantic matches.")
p("<b>Gating:</b> in Generic mode (no knowledge base selected) this whole block is skipped — no "
  "retrieval, no citation. KB retrieval runs only when a manual is selected.", SMALL)

# ---------------- 5. Design decisions ----------------
p("5. Key design decisions &amp; trade-offs", H1)
kvtable([
    ["Decision", "Why", "Trade-off"],
    ["Hybrid dense + BM25", "Meaning + exact codes/part numbers", "Two indexes to maintain"],
    ["BGE-small (local)", "CPU-friendly, 512-token context", "Lower ceiling; compressed score range"],
    ["RRF fusion", "Merges rankings w/o normalizing scores", "Rank score != true relevance"],
    ["One chunk per table row", "Precise row-level answers", "More chunks"],
    ["VLM caption for figures", "Diagrams become searchable text", "Caption can miss detail"],
    ["Page re-join", "Full context + clean page citation", "Coarser than chunk-level cite"],
    ["Label-first query", "Concise term matches manual wording", "Pure clicks less precise"],
    ["Confidence floor (0.60)", "Honest 'no match' > wrong citation", "Can't fully separate weak vs junk"],
    ["Local Qdrant (file mode)", "Simple, private, on-prem", "Single-process; not concurrent yet"],
], [120, 200, 130])

# ---------------- 6. Limitations ----------------
p("6. Honest limitations", H1)
for t in [
    "<b>Query quality dominates.</b> Retrieval is only as good as the query; a typed component label is the most reliable.",
    "<b>Compressed similarity.</b> BGE cosine clusters ~0.6–0.9, so a weak real match can overlap off-topic noise; a re-ranker would fix this.",
    "<b>Coverage is a hard limit.</b> RAG can only cite what the manual contains (a mechanical manual has no 'LCD / circuit board').",
    "<b>Captioning, not true multimodal.</b> Diagrams are converted to text once at ingestion; fine print can be lost.",
    "<b>Single-process store.</b> Local file-mode Qdrant needs server mode to scale to many concurrent users.",
]:
    p("&bull; " + t, BODY)

# ---------------- 7. Q&A ----------------
p("7. Anticipated questions", H1)
p("Manager", H2)
qa = [
    ("How accurate is it?", "Cites the right page with high confidence when the manual covers the part; when unsure it says 'no strong match' instead of guessing."),
    ("What if it's wrong?", "Every citation shows a confidence %, and weak matches are suppressed. The user always sees and can verify the source."),
    ("Is our data safe?", "Everything runs locally/on-prem — vision model, embeddings, and vector DB. The manual never leaves the machine."),
    ("What does it cost?", "No per-query cloud cost. The heavy work happens once at upload; queries are cheap."),
]
for q, a in qa:
    p(f"<b>{q}</b> {a}", SMALL)
p("AI architect", H2)
qa2 = [
    ("Chunking?", "320-word windows / 60 overlap for prose; row-level for tables; whole-caption for figures; section headers prefixed; sized to the embedder's 512-token budget."),
    ("Why BGE-small?", "Local/CPU/private constraint; pluggable — a larger or cloud embedder would improve separation."),
    ("Fusion?", "RRF over independent dense + sparse prefetches; confidence taken from dense cosine, not the fused rank."),
    ("Re-ranking?", "None yet — a cross-encoder re-ranker on top-k is the natural next precision upgrade."),
    ("Grounding/hallucination?", "Generation is grounded on retrieved verified text with a citation; below-threshold matches are suppressed."),
    ("Scaling?", "Move local Qdrant to server mode; batch/queue embedding + VLM for concurrency. Multi-manual org-wide search is an extension."),
    ("Evaluation?", "Known-answer queries with expected page + score; automated precision/recall regression is a gap to close."),
]
for q, a in qa2:
    p(f"<b>{q}</b> {a}", SMALL)

rule()
p("Stack: Docling (parse) &middot; Qwen2.5-VL (figure captioning, region analysis) &middot; "
  "BAAI/bge-small-en-v1.5 (dense) &middot; BM25/fastembed (sparse) &middot; Qdrant (hybrid vector store). "
  "All local.", SMALL)

doc = SimpleDocTemplate(str(OUT), pagesize=A4,
                        leftMargin=18*mm, rightMargin=18*mm, topMargin=16*mm, bottomMargin=16*mm,
                        title="Semantic Drill-Down — RAG Pipeline")
doc.build(F)
print("WROTE", OUT)
