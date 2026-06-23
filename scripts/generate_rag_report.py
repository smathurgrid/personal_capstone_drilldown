"""Generates a PDF report describing the RAG pipeline in drilldown-cap-int."""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
import datetime

OUTPUT = "docs/RAG_Architecture_Report.pdf"

# ── Colour palette ──────────────────────────────────────────────────────────
INDIGO   = colors.HexColor("#4f46e5")
INDIGO_L = colors.HexColor("#eef2ff")
SLATE    = colors.HexColor("#1e293b")
MUTED    = colors.HexColor("#64748b")
BORDER   = colors.HexColor("#e2e8f0")
GREEN    = colors.HexColor("#10b981")
GREEN_L  = colors.HexColor("#f0fdf4")
AMBER    = colors.HexColor("#f59e0b")
AMBER_L  = colors.HexColor("#fffbeb")
PINK     = colors.HexColor("#ec4899")
PINK_L   = colors.HexColor("#fff1f2")
BLUE     = colors.HexColor("#3b82f6")
BLUE_L   = colors.HexColor("#eff6ff")
WHITE    = colors.white
LIGHT_BG = colors.HexColor("#f8fafc")


def build_styles():
    base = getSampleStyleSheet()

    styles = {
        "cover_title": ParagraphStyle(
            "cover_title",
            fontSize=28, leading=34, textColor=WHITE,
            fontName="Helvetica-Bold", alignment=TA_CENTER,
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub",
            fontSize=13, leading=18, textColor=colors.HexColor("#c7d2fe"),
            fontName="Helvetica", alignment=TA_CENTER,
        ),
        "cover_meta": ParagraphStyle(
            "cover_meta",
            fontSize=10, leading=14, textColor=colors.HexColor("#a5b4fc"),
            fontName="Helvetica", alignment=TA_CENTER,
        ),
        "section": ParagraphStyle(
            "section",
            fontSize=15, leading=20, textColor=INDIGO,
            fontName="Helvetica-Bold", spaceBefore=18, spaceAfter=6,
        ),
        "subsection": ParagraphStyle(
            "subsection",
            fontSize=11, leading=15, textColor=SLATE,
            fontName="Helvetica-Bold", spaceBefore=10, spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body",
            fontSize=10, leading=15, textColor=SLATE,
            fontName="Helvetica", spaceAfter=6, alignment=TA_JUSTIFY,
        ),
        "mono": ParagraphStyle(
            "mono",
            fontSize=9, leading=13, textColor=colors.HexColor("#1e3a5f"),
            fontName="Courier", spaceAfter=4,
        ),
        "caption": ParagraphStyle(
            "caption",
            fontSize=8.5, leading=12, textColor=MUTED,
            fontName="Helvetica-Oblique", alignment=TA_CENTER, spaceAfter=6,
        ),
        "bullet": ParagraphStyle(
            "bullet",
            fontSize=10, leading=14, textColor=SLATE,
            fontName="Helvetica", leftIndent=14, bulletIndent=0, spaceAfter=3,
        ),
        "tag": ParagraphStyle(
            "tag",
            fontSize=8, leading=11, textColor=INDIGO,
            fontName="Helvetica-Bold",
        ),
        "toc_entry": ParagraphStyle(
            "toc_entry",
            fontSize=10, leading=16, textColor=SLATE,
            fontName="Helvetica", leftIndent=10,
        ),
    }
    return styles


def hr(color=BORDER, thickness=0.75, space_before=4, space_after=8):
    return HRFlowable(width="100%", thickness=thickness, color=color,
                      spaceAfter=space_after, spaceBefore=space_before)


def code_block(s, styles, bg=LIGHT_BG):
    """Single-cell table that renders a monospaced code block."""
    cell = Paragraph(s, styles["mono"])
    t = Table([[cell]], colWidths=[6.5 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("BOX",        (0, 0), (-1, -1), 0.5, BORDER),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
        ("ROUNDEDCORNERS", [4]),
    ]))
    return t


def badge(text, bg, fg, styles):
    cell = Paragraph(f"<b>{text}</b>", ParagraphStyle(
        "b", fontSize=8, leading=10, textColor=fg, fontName="Helvetica-Bold",
    ))
    t = Table([[cell]], colWidths=None)
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), bg),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING",   (0, 0), (-1, -1), 7),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 7),
    ]))
    return t


def info_row(label, value, styles, label_w=1.5 * inch, value_w=5.0 * inch):
    lp = Paragraph(f"<b>{label}</b>", styles["body"])
    vp = Paragraph(value, styles["mono"])
    t = Table([[lp, vp]], colWidths=[label_w, value_w])
    t.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
    ]))
    return t


def phase_card(number, title, file_ref, description, config_rows, color, light, styles):
    """Coloured card for each pipeline phase."""
    header = Table(
        [[
            Paragraph(f"<b>Phase {number}</b>", ParagraphStyle(
                "ph", fontSize=9, leading=11, textColor=WHITE, fontName="Helvetica-Bold")),
            Paragraph(f"<b>{title}</b>", ParagraphStyle(
                "pt", fontSize=11, leading=14, textColor=WHITE, fontName="Helvetica-Bold")),
            Paragraph(file_ref, ParagraphStyle(
                "pf", fontSize=8, leading=10, textColor=colors.HexColor("#e0e7ff"),
                fontName="Courier")),
        ]],
        colWidths=[0.65 * inch, 3.2 * inch, 2.65 * inch],
    )
    header.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), color),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("ROUNDEDCORNERS", [6, 6, 0, 0]),
    ]))

    desc_para = Paragraph(description, styles["body"])

    cfg_rows_built = []
    for k, v in config_rows:
        cfg_rows_built.append([
            Paragraph(f"<b>{k}</b>", styles["body"]),
            Paragraph(v, styles["mono"]),
        ])

    cfg_table = Table(cfg_rows_built, colWidths=[1.6 * inch, 4.9 * inch])
    cfg_table.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("LINEBELOW",     (0, 0), (-1, -2), 0.4, BORDER),
    ]))

    body_inner = Table(
        [[desc_para], [Spacer(1, 6)], [cfg_table]],
        colWidths=[6.5 * inch],
    )
    body_inner.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), light),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING",   (0, 0), (-1, -1), 12),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
        ("ROUNDEDCORNERS", [0, 0, 6, 6]),
    ]))

    wrapper = Table([[header], [body_inner]], colWidths=[6.5 * inch])
    wrapper.setStyle(TableStyle([
        ("BOX",           (0, 0), (-1, -1), 0.75, BORDER),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("ROUNDEDCORNERS", [6]),
    ]))
    return wrapper


def build_story(styles):
    story = []
    today = datetime.date.today().strftime("%B %d, %Y")

    # ── Cover page ───────────────────────────────────────────────────────────
    cover_bg = Table(
        [
            [Spacer(1, 1.1 * inch)],
            [Paragraph("RAG Pipeline", styles["cover_title"])],
            [Spacer(1, 0.15 * inch)],
            [Paragraph("Architecture &amp; Implementation Guide", styles["cover_sub"])],
            [Spacer(1, 0.4 * inch)],
            [hr(colors.HexColor("#6366f1"), thickness=1)],
            [Spacer(1, 0.3 * inch)],
            [Paragraph("drilldown-cap-int · feat/RAG/sid", styles["cover_meta"])],
            [Paragraph(f"Generated {today}", styles["cover_meta"])],
            [Spacer(1, 0.3 * inch)],
            [Paragraph(
                "A technical deep-dive into the Retrieval-Augmented Generation ingestion and "
                "retrieval pipeline powering the drill-down explainer feature.",
                styles["cover_sub"],
            )],
        ],
        colWidths=[6.5 * inch],
    )
    cover_bg.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), INDIGO),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING",   (0, 0), (-1, -1), 40),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 40),
        ("ROUNDEDCORNERS", [10]),
    ]))
    story.append(cover_bg)
    story.append(Spacer(1, 0.5 * inch))

    # Quick-stat bar
    stats = [
        ("Embedding Model", "all-MiniLM-L6-v2"),
        ("Vector Dims", "384"),
        ("Chunk Size", "400 words"),
        ("Overlap", "80 words"),
        ("Vector DB", "Qdrant (local)"),
        ("Vision LLM", "Qwen 2.5VL 7B"),
    ]
    stat_cells = [[Paragraph(f"<b>{k}</b><br/><font size=9 color='#4f46e5'>{v}</font>", ParagraphStyle(
        "s", fontSize=8, leading=12, textColor=SLATE, fontName="Helvetica",
        alignment=TA_CENTER,
    ))] for k, v in stats]

    stat_table = Table([stat_cells[i:i+3] for i in range(0, len(stat_cells), 3)],
                       colWidths=[2.16 * inch] * 3)
    stat_table.setStyle(TableStyle([
        ("BOX",        (0, 0), (-1, -1), 0.75, BORDER),
        ("INNERGRID",  (0, 0), (-1, -1), 0.5, BORDER),
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BG),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("ROUNDEDCORNERS", [6]),
    ]))
    story.append(stat_table)
    story.append(PageBreak())

    # ── 1. Overview ──────────────────────────────────────────────────────────
    story.append(Paragraph("1. Overview", styles["section"]))
    story.append(hr(INDIGO, thickness=1.5, space_before=0, space_after=10))
    story.append(Paragraph(
        "The RAG (Retrieval-Augmented Generation) pipeline in <i>drilldown-cap-int</i> enriches "
        "drill-down component explanations with grounded, citation-backed context extracted from "
        "user-uploaded PDF documents. Instead of relying solely on a vision language model's "
        "parametric knowledge, the system first searches an indexed knowledge base and injects "
        "the most relevant passage into the generation prompt — providing verifiable, "
        "document-specific answers.",
        styles["body"],
    ))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "The pipeline has two primary phases: <b>Ingestion</b> (offline, triggered on PDF upload) "
        "and <b>Retrieval</b> (online, triggered on each drill-down query). Both phases share the "
        "same embedding model to ensure query-document vector space alignment.",
        styles["body"],
    ))
    story.append(Spacer(1, 10))

    # High-level flow table
    flow_data = [
        [Paragraph("<b>Stage</b>", styles["body"]),
         Paragraph("<b>Trigger</b>", styles["body"]),
         Paragraph("<b>Output</b>", styles["body"])],
        [Paragraph("Ingestion", styles["body"]),
         Paragraph("POST /api/kb/upload", styles["mono"]),
         Paragraph("Qdrant collection + registry entry", styles["body"])],
        [Paragraph("Retrieval", styles["body"]),
         Paragraph("Drill-down request with kb_id", styles["mono"]),
         Paragraph("Top-k chunks + citations injected into prompt", styles["body"])],
    ]
    flow_table = Table(flow_data, colWidths=[1.4 * inch, 2.3 * inch, 2.8 * inch])
    flow_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), INDIGO),
        ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
        ("BACKGROUND",    (0, 1), (-1, 1), INDIGO_L),
        ("BACKGROUND",    (0, 2), (-1, 2), WHITE),
        ("BOX",           (0, 0), (-1, -1), 0.75, BORDER),
        ("INNERGRID",     (0, 0), (-1, -1), 0.5, BORDER),
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("ROUNDEDCORNERS", [4]),
    ]))
    story.append(flow_table)
    story.append(Spacer(1, 16))

    # ── 2. Ingestion Pipeline ────────────────────────────────────────────────
    story.append(Paragraph("2. Ingestion Pipeline", styles["section"]))
    story.append(hr(INDIGO, thickness=1.5, space_before=0, space_after=10))
    story.append(Paragraph(
        "When a user uploads a PDF via the knowledge base UI, the following pipeline runs "
        "synchronously (inside a thread executor so the async FastAPI event loop is not blocked). "
        "The six phases below transform raw bytes into indexed, searchable vector embeddings.",
        styles["body"],
    ))
    story.append(Spacer(1, 10))

    phases = [
        (
            1, "Upload & ID Generation",
            "controllers/kb.py",
            "The FastAPI controller validates the uploaded file is a PDF, reads the raw bytes, "
            "and derives a content-based identifier using SHA-256. The first 16 hex characters "
            "become the kb_id, making re-uploads of the same file fully idempotent.",
            [
                ("Entry point", "handle_upload_kb()"),
                ("ID scheme",   "sha256(pdf_bytes)[:16]  →  e.g. a942cbba4b145e1a"),
                ("Validation",  "MIME check — 400 returned if not application/pdf"),
            ],
            INDIGO, INDIGO_L,
        ),
        (
            2, "PDF Parsing — Docling",
            "ingestion.py · _parse_with_docling()",
            "A global DocumentConverter singleton (from the docling library) parses the PDF into "
            "a typed element stream. Each element is classified into one of five types. The last "
            "seen SectionHeaderItem is tracked and prepended as context to subsequent text and "
            "list items, preserving the document's logical hierarchy.",
            [
                ("Library",    "docling · DocumentConverter (lazy singleton)"),
                ("Elements",   "SectionHeaderItem, TextItem, ListItem, TableItem, PictureItem"),
                ("Context",    "[section header] text — prepended to text/list items"),
                ("Tables",     "export_to_markdown() → single Markdown string"),
            ],
            colors.HexColor("#6366f1"), colors.HexColor("#eef2ff"),
        ),
        (
            3, "Figure Description — Vision LLM",
            "ingestion.py · _describe_figure()",
            "Each PictureItem is exported to PNG bytes and sent to a locally running Ollama "
            "instance with the Qwen 2.5VL 7B vision model. The function detects whether the "
            "figure is a flowchart (via keyword matching on the caption) and tailors the prompt "
            "accordingly. Flowcharts receive step-by-step numbered extraction; other diagrams "
            "receive component, label, and connection descriptions. If the VLM is unavailable, "
            "the raw caption is used as a graceful fallback.",
            [
                ("VLM",        "qwen2.5vl:7b via Ollama (http://localhost:11434)"),
                ("Flowchart",  "Keyword detect: 'flow', 'procedure', 'cycle', 'diagram', …"),
                ("Output",     "Step-by-step (IF/THEN/ELSE) or component description"),
                ("Fallback",   "Caption text if VLM call fails or Ollama is not running"),
            ],
            BLUE, BLUE_L,
        ),
        (
            4, "Chunking",
            "ingestion.py · _chunk_text()",
            "Parsed elements are chunked using a sliding word-window approach. Text and list "
            "items use the standard window with overlap to preserve cross-chunk context. Tables "
            "and figures are kept as single atomic chunks unless they exceed double the chunk "
            "size, in which case they are split at word boundaries. Every chunk retains its "
            "source page number and content type for downstream citation.",
            [
                ("Chunk size", "_CHUNK_SIZE = 400 words"),
                ("Overlap",    "_CHUNK_OVERLAP = 80 words"),
                ("Tables",     "Single chunk; split only if > 800 words"),
                ("Figures",    "Single chunk; split only if > 800 words"),
                ("Metadata",   "page_num, content_type, chunk_index preserved per chunk"),
            ],
            GREEN, GREEN_L,
        ),
        (
            5, "Embedding",
            "embedder.py · get_embedder()",
            "All chunk texts are batch-encoded by the all-MiniLM-L6-v2 sentence-transformer "
            "model. The model is loaded once at startup and cached for the process lifetime. "
            "The same model is used at retrieval time, guaranteeing that query vectors and "
            "document vectors live in the same semantic space.",
            [
                ("Model",      "sentence-transformers/all-MiniLM-L6-v2"),
                ("Dimensions", "384 (float32)"),
                ("Distance",   "Cosine similarity"),
                ("Batch size", "32 samples per encode() call"),
                ("Lifecycle",  "Lazy singleton — loaded once, reused for queries"),
            ],
            AMBER, AMBER_L,
        ),
        (
            6, "Vector Storage — Qdrant + Registry",
            "ingestion.py · store.py",
            "Embedded points are upserted into a Qdrant collection named kb_{kb_id}. The "
            "collection is dropped and recreated on each upload, making the operation fully "
            "idempotent. Points are written in batches of 100. After storage completes, "
            "register_kb() appends a metadata record to the JSON registry.",
            [
                ("Collection", "kb_{sha256[:16]}  — one isolated collection per KB"),
                ("Point ID",   "uint32 from md5('{kb_id}_{chunk_idx}')[:8]"),
                ("Payload",    "text, page_num, source_name, content_type, chunk_index"),
                ("Batch size", "100 points per upsert call"),
                ("Registry",   "data/kb/registry.json — id, name, page_count, created_at"),
                ("DB path",    "data/kb/qdrant/  (local file-based Qdrant)"),
            ],
            PINK, PINK_L,
        ),
    ]

    for i, ph in enumerate(phases):
        story.append(KeepTogether([
            phase_card(*ph, styles=styles),
            Spacer(1, 10),
        ]))

    story.append(PageBreak())

    # ── 3. Retrieval Pipeline ────────────────────────────────────────────────
    story.append(Paragraph("3. Retrieval Pipeline", styles["section"]))
    story.append(hr(INDIGO, thickness=1.5, space_before=0, space_after=10))
    story.append(Paragraph(
        "Retrieval is triggered at query time when a drill-down request includes a kb_id. "
        "The system encodes the free-text analysis query, searches the corresponding Qdrant "
        "collection, and injects the best-matching chunk into the LLM generation prompt as "
        "grounded context.",
        styles["body"],
    ))
    story.append(Spacer(1, 10))

    retrieval_steps = [
        ("Query arrives", "Drill-down request contains kb_id, triggering _enrich_with_kb()",
         "drill_context_resolver.py"),
        ("Embed query",
         "The same all-MiniLM-L6-v2 model encodes the component analysis text → float32[384]",
         "retriever.py · search_kb()"),
        ("Vector search",
         "Qdrant cosine search over kb_{kb_id} with top_k=4, returning payloads + scores",
         "QdrantClient.query_points()"),
        ("Inject context",
         "Top hit's text is added to the LLM prompt; 2nd–4th hits stored as kb_extra_hits",
         "drill_context_resolver.py"),
        ("Citation attached",
         "Result includes kb_citation ('filename, page N'), kb_score, kb_mode=True",
         "DrillResult payload"),
    ]

    for i, (step, desc, ref) in enumerate(retrieval_steps):
        row_data = [
            Paragraph(f"<b>{i+1}</b>", ParagraphStyle(
                "n", fontSize=13, leading=16, textColor=INDIGO,
                fontName="Helvetica-Bold", alignment=TA_CENTER)),
            Paragraph(f"<b>{step}</b><br/>{desc}", styles["body"]),
            Paragraph(ref, styles["mono"]),
        ]
        row_table = Table([row_data], colWidths=[0.35 * inch, 4.05 * inch, 2.1 * inch])
        row_table.setStyle(TableStyle([
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING",    (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("BACKGROUND",    (0, 0), (-1, -1), INDIGO_L if i % 2 == 0 else WHITE),
            ("BOX",           (0, 0), (-1, -1), 0.5, BORDER),
            ("LINEABOVE",     (0, 0), (-1, 0), 0.5, BORDER),
        ]))
        story.append(row_table)
        story.append(Spacer(1, 3))

    story.append(Spacer(1, 14))

    # Retrieval result schema
    story.append(Paragraph("3.1 Retrieval Result Schema", styles["subsection"]))
    story.append(code_block(
        "{\n"
        '  "text":         str,    # Chunk content\n'
        '  "page_num":     int,    # Source PDF page\n'
        '  "source_name":  str,    # Original filename\n'
        '  "score":        float,  # Cosine similarity (0–1)\n'
        '  "content_type": str     # "text" | "table" | "figure"\n'
        "}",
        styles,
    ))
    story.append(Spacer(1, 14))

    # Drill-down enrichment schema
    story.append(Paragraph("3.2 Enriched Drill-Down Fields", styles["subsection"]))
    story.append(Paragraph(
        "When KB retrieval succeeds, the following fields are added to the drill-down result "
        "and surfaced in the metadata panel:",
        styles["body"],
    ))
    story.append(Spacer(1, 6))
    enrich_data = [
        [Paragraph("<b>Field</b>", styles["body"]),
         Paragraph("<b>Type</b>", styles["body"]),
         Paragraph("<b>Description</b>", styles["body"])],
        [Paragraph("kb_description", styles["mono"]), Paragraph("str", styles["mono"]),
         Paragraph("Top chunk text injected into prompt", styles["body"])],
        [Paragraph("kb_citation", styles["mono"]), Paragraph("str", styles["mono"]),
         Paragraph('"filename, page N" — shown to user', styles["body"])],
        [Paragraph("kb_score", styles["mono"]), Paragraph("float", styles["mono"]),
         Paragraph("Cosine similarity of top hit", styles["body"])],
        [Paragraph("kb_extra_hits", styles["mono"]), Paragraph("list", styles["mono"]),
         Paragraph("2nd–4th results for optional display", styles["body"])],
        [Paragraph("kb_mode", styles["mono"]), Paragraph("bool", styles["mono"]),
         Paragraph("True when KB enrichment active", styles["body"])],
    ]
    enrich_table = Table(enrich_data, colWidths=[1.6 * inch, 0.7 * inch, 4.2 * inch])
    enrich_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), INDIGO),
        ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
        ("BACKGROUND",    (0, 1), (-1, 1), INDIGO_L),
        ("BACKGROUND",    (0, 2), (-1, 2), WHITE),
        ("BACKGROUND",    (0, 3), (-1, 3), INDIGO_L),
        ("BACKGROUND",    (0, 4), (-1, 4), WHITE),
        ("BACKGROUND",    (0, 5), (-1, 5), INDIGO_L),
        ("BOX",           (0, 0), (-1, -1), 0.75, BORDER),
        ("INNERGRID",     (0, 0), (-1, -1), 0.5, BORDER),
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("ROUNDEDCORNERS", [4]),
    ]))
    story.append(enrich_table)
    story.append(PageBreak())

    # ── 4. Data Model ────────────────────────────────────────────────────────
    story.append(Paragraph("4. Data Model", styles["section"]))
    story.append(hr(INDIGO, thickness=1.5, space_before=0, space_after=10))

    story.append(Paragraph("4.1 Qdrant Point Structure", styles["subsection"]))
    story.append(code_block(
        "PointStruct(\n"
        "  id     = uint32  # md5(f'{kb_id}_{chunk_index}')[:8]\n"
        "  vector = float32[384]  # cosine distance space\n"
        "  payload = {\n"
        '    "text":         str,  # chunk text (400-word window)\n'
        '    "page_num":     int,  # 1-indexed page from Docling\n'
        '    "source_name":  str,  # original PDF filename\n'
        '    "chunk_index":  int,  # position in document order\n'
        '    "content_type": str   # "text" | "table" | "figure"\n'
        "  }\n"
        ")",
        styles,
    ))
    story.append(Spacer(1, 10))

    story.append(Paragraph("4.2 Registry Record (registry.json)", styles["subsection"]))
    story.append(code_block(
        "{\n"
        '  "id":         "a942cbba4b145e1a",     // sha256(bytes)[:16]\n'
        '  "name":       "equipment_manual.pdf",  // original filename\n'
        '  "page_count": 312,                     // chunk count (not pages)\n'
        '  "created_at": "2026-06-23T14:00:00Z"   // ISO 8601 UTC\n'
        "}",
        styles,
    ))
    story.append(Spacer(1, 10))

    story.append(Paragraph("4.3 Collection Naming & Isolation", styles["subsection"]))
    story.append(Paragraph(
        "Each uploaded PDF gets its own isolated Qdrant collection named "
        "<font name='Courier'>kb_{sha256[:16]}</font>. This means queries never "
        "cross-contaminate between knowledge bases, and deleting a KB is a simple "
        "collection drop — no filtering required. The tradeoff is that multi-KB "
        "cross-search would require aggregating results across collections manually.",
        styles["body"],
    ))
    story.append(Spacer(1, 16))

    # ── 5. Configuration Reference ───────────────────────────────────────────
    story.append(Paragraph("5. Configuration Reference", styles["section"]))
    story.append(hr(INDIGO, thickness=1.5, space_before=0, space_after=10))
    story.append(Paragraph(
        "All settings are defined in <font name='Courier'>backend/shared/config.py</font> "
        "as a Pydantic <i>Settings</i> class and can be overridden via environment variables.",
        styles["body"],
    ))
    story.append(Spacer(1, 8))

    cfg_data = [
        [Paragraph("<b>Env Var</b>", styles["body"]),
         Paragraph("<b>Default</b>", styles["body"]),
         Paragraph("<b>Purpose</b>", styles["body"])],
        ["KB_DIR",            "data/kb",                   "Registry JSON location"],
        ["KB_QDRANT_PATH",    "data/kb/qdrant",            "Local Qdrant database root"],
        ["OLLAMA_BASE",       "http://localhost:11434",     "Ollama base URL for VLM calls"],
        ["VISION_MODEL",      "qwen2.5vl:7b",              "Figure description model"],
        ["QDRANT_PATH",       "data/qdrant_storage",       "Separate ecommerce Qdrant DB"],
        ["COLLECTION_NAME",   "fashion_products",          "Ecommerce vector collection"],
    ]
    fmt_cfg = [[Paragraph("<b>Env Var</b>", styles["body"]),
                Paragraph("<b>Default</b>", styles["body"]),
                Paragraph("<b>Purpose</b>", styles["body"])]]
    for row in cfg_data[1:]:
        fmt_cfg.append([Paragraph(row[0], styles["mono"]),
                        Paragraph(row[1], styles["mono"]),
                        Paragraph(row[2], styles["body"])])

    cfg_table = Table(fmt_cfg, colWidths=[1.8 * inch, 2.0 * inch, 2.7 * inch])
    cfg_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), INDIGO),
        ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
        *[("BACKGROUND", (0, i), (-1, i), INDIGO_L if i % 2 == 1 else WHITE)
          for i in range(1, len(fmt_cfg))],
        ("BOX",           (0, 0), (-1, -1), 0.75, BORDER),
        ("INNERGRID",     (0, 0), (-1, -1), 0.5, BORDER),
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("ROUNDEDCORNERS", [4]),
    ]))
    story.append(cfg_table)
    story.append(Spacer(1, 16))

    # ── 6. API Endpoints ─────────────────────────────────────────────────────
    story.append(Paragraph("6. API Endpoints", styles["section"]))
    story.append(hr(INDIGO, thickness=1.5, space_before=0, space_after=10))

    api_data = [
        [Paragraph("<b>Method</b>", styles["body"]),
         Paragraph("<b>Path</b>", styles["body"]),
         Paragraph("<b>Handler</b>", styles["body"]),
         Paragraph("<b>Description</b>", styles["body"])],
        ["POST",   "/api/kb/upload",    "handle_upload_kb()",  "Upload PDF, trigger ingestion"],
        ["GET",    "/api/kb/list",      "handle_list_kbs()",   "List all registered KBs"],
        ["DELETE", "/api/kb/{kb_id}",   "handle_delete_kb()",  "Delete KB + Qdrant collection"],
    ]
    method_colors = {"POST": GREEN, "GET": BLUE, "DELETE": colors.HexColor("#ef4444")}

    fmt_api = [api_data[0]]
    for row in api_data[1:]:
        m = row[0]
        fmt_api.append([
            Paragraph(f"<b>{m}</b>", ParagraphStyle(
                "meth", fontSize=9, leading=12, textColor=method_colors.get(m, SLATE),
                fontName="Helvetica-Bold")),
            Paragraph(row[1], styles["mono"]),
            Paragraph(row[2], styles["mono"]),
            Paragraph(row[3], styles["body"]),
        ])

    api_table = Table(fmt_api, colWidths=[0.7 * inch, 1.6 * inch, 1.9 * inch, 2.3 * inch])
    api_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), INDIGO),
        ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
        *[("BACKGROUND", (0, i), (-1, i), INDIGO_L if i % 2 == 1 else WHITE)
          for i in range(1, len(fmt_api))],
        ("BOX",           (0, 0), (-1, -1), 0.75, BORDER),
        ("INNERGRID",     (0, 0), (-1, -1), 0.5, BORDER),
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("ROUNDEDCORNERS", [4]),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(api_table)
    story.append(Spacer(1, 16))

    # ── 7. Key Design Decisions ──────────────────────────────────────────────
    story.append(Paragraph("7. Key Design Decisions", styles["section"]))
    story.append(hr(INDIGO, thickness=1.5, space_before=0, space_after=10))

    decisions = [
        ("Content-based IDs",
         "sha256(pdf_bytes)[:16] means the same file always produces the same kb_id. "
         "Re-uploading is idempotent — the Qdrant collection is dropped and rebuilt, "
         "avoiding stale index state without needing version tracking."),
        ("Per-KB Qdrant collections",
         "Isolating each KB in its own collection (kb_{id}) avoids cross-contamination "
         "and makes deletion trivially safe. The tradeoff is that cross-KB search requires "
         "manual aggregation across collections."),
        ("Shared embedding singleton",
         "The all-MiniLM-L6-v2 model is loaded once per process and reused for both "
         "ingestion and queries. This guarantees vector space alignment and avoids paying "
         "the ~80MB model load cost on every request."),
        ("Local Qdrant (file-based)",
         "Using Qdrant in local file mode (no separate server process) keeps deployment "
         "simple. The database lives at data/kb/qdrant/. If the collection count or "
         "volume grows significantly, migrating to a Qdrant server is straightforward."),
        ("Graceful VLM fallback",
         "Figure description via Ollama is optional. If the VLM is unavailable or the "
         "call fails, the raw Docling caption is used instead. This means ingestion "
         "never hard-fails due to a missing local model."),
        ("Overlapping chunks",
         "An 80-word overlap between consecutive 400-word chunks ensures that information "
         "near chunk boundaries is represented in both adjacent chunks, reducing the chance "
         "of a relevant fact being split across a boundary and missed by retrieval."),
    ]

    for title, body in decisions:
        block = Table(
            [[Paragraph(f"<b>{title}</b>", styles["subsection"])],
             [Paragraph(body, styles["body"])]],
            colWidths=[6.5 * inch],
        )
        block.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (0, 0), INDIGO_L),
            ("BACKGROUND",    (0, 1), (0, 1), WHITE),
            ("BOX",           (0, 0), (-1, -1), 0.75, BORDER),
            ("TOPPADDING",    (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("LEFTPADDING",   (0, 0), (-1, -1), 12),
            ("ROUNDEDCORNERS", [5]),
        ]))
        story.append(block)
        story.append(Spacer(1, 7))

    story.append(PageBreak())

    # ── 8. File Map ──────────────────────────────────────────────────────────
    story.append(Paragraph("8. File Map", styles["section"]))
    story.append(hr(INDIGO, thickness=1.5, space_before=0, space_after=10))

    files = [
        ("backend/services/knowledge_base/ingestion.py",
         "Core ingestion: PDF parsing, chunking, embedding, Qdrant upsert"),
        ("backend/services/knowledge_base/embedder.py",
         "Singleton embedder: all-MiniLM-L6-v2 loader + encode()"),
        ("backend/services/knowledge_base/retriever.py",
         "Vector search: search_kb() → ranked top-k results"),
        ("backend/services/knowledge_base/store.py",
         "JSON registry: register_kb(), list_kbs(), remove_kb()"),
        ("backend/app/routes/kb.py",
         "FastAPI router: /api/kb/upload, /list, /{kb_id}"),
        ("backend/app/controllers/kb.py",
         "Request handlers: file validation, thread-executor dispatch"),
        ("backend/services/explainer/drill_context_resolver.py",
         "KB enrichment: _enrich_with_kb() injects context into drill prompt"),
        ("backend/shared/config.py",
         "Settings: KB_DIR, KB_QDRANT_PATH, OLLAMA_BASE, VISION_MODEL"),
        ("data/kb/registry.json",
         "Runtime: JSON array of registered KB metadata records"),
        ("data/kb/qdrant/",
         "Runtime: Local Qdrant database directory (one collection per KB)"),
        ("test_ingestion.py",
         "Smoke test: end-to-end ingestion + query validation"),
    ]

    file_data = [[Paragraph("<b>Path</b>", styles["body"]),
                  Paragraph("<b>Purpose</b>", styles["body"])]]
    for path, purpose in files:
        file_data.append([
            Paragraph(path, styles["mono"]),
            Paragraph(purpose, styles["body"]),
        ])

    file_table = Table(file_data, colWidths=[3.1 * inch, 3.4 * inch])
    file_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), INDIGO),
        ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
        *[("BACKGROUND", (0, i), (-1, i), INDIGO_L if i % 2 == 1 else WHITE)
          for i in range(1, len(file_data))],
        ("BOX",           (0, 0), (-1, -1), 0.75, BORDER),
        ("INNERGRID",     (0, 0), (-1, -1), 0.5, BORDER),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("ROUNDEDCORNERS", [4]),
    ]))
    story.append(file_table)

    # Footer note
    story.append(Spacer(1, 20))
    story.append(hr(BORDER, thickness=0.5, space_before=0, space_after=8))
    story.append(Paragraph(
        f"drilldown-cap-int · RAG Pipeline Report · Generated {today}",
        styles["caption"],
    ))

    return story


def main():
    import os
    os.makedirs("docs", exist_ok=True)

    doc = SimpleDocTemplate(
        OUTPUT,
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        title="RAG Pipeline — Architecture & Implementation Guide",
        author="drilldown-cap-int",
    )

    styles = build_styles()
    story = build_story(styles)
    doc.build(story)
    print(f"PDF written → {OUTPUT}")


if __name__ == "__main__":
    main()
