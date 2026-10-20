# references/

Rulebook and case material the committee consults (methodology §0.1).

## Committed
- `APPENDIX_M_principles.md` — a distilled, paraphrased summary of RRS Appendix M
  (Recommendations for Protest Committees), mapped to how this toolkit should
  behave. Authoritative text:
  https://www.racingrulesofsailing.org/rules?part_id=159

## Not committed (World Sailing copyright) — build locally
The World Sailing Case Book and its derived files are **not** redistributed in
this repo. Generate them yourself:

```
pip install  # nothing extra needed; requires poppler-utils for `pdftotext`
python references/build_casebook.py                 # downloads the public PDF
# or, if you already have the PDF (e.g. on your machine):
python references/build_casebook.py /path/to/WS-Case-Book-2025-2028.pdf
```

This produces (all gitignored):
- `WS-Case-Book-2025-2028.pdf` — the source
- `casebook_parsed.json` — every case: cited rules, principle, full
  Facts/Question/Answer, plus a `by_rule_top` index
- `CASEBOOK_REFERENCE.md` — rule → cases index with one-line principles

## Rule text
The rules themselves are not bundled; browse at
https://www.racingrulesofsailing.org/rules and fetch the specific rule when
exact wording matters.
