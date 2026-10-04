"""
The generator of the invoice extraction benchmark corpus.

A spec-driven synthetic corpus: every vendor, customer, number and amount is
invented. Each document is a DocSpec, the single source of truth for both
what is drawn and what a correct extraction returns.

    python -m generator.generate            # writes corpus/v1 (seed 42)

    spec.py        DocSpec: one document and its answer key
    names.py       invented vendors, customers, places and goods
    us_specs.py    the 20 US invoices of the clean category
    corpus_v1.py   the v1 set: 181 specs across 10 categories, from a seed
    layout.py      DocSpec -> pages of drawing operations (one layout engine)
    render.py      pages -> PDF (reportlab, real text layer) or image (Pillow)
    handwriting.py handwriting-style text with graded legibility
    degrade.py     photo / scan / fax degradations with graded severity
    generate.py    writes the documents, answer keys and manifest
"""
