# src/sdg/view/

This folder shows a person what is inside a pinned document, a PDF section or a workbook sheet, from the terminal. Both commands open their files read-only and write nothing.

| File | What it does |
| --- | --- |
| `read_pdf.py` | Prints part of a pinned PDF as plain text, by section number, section title, page range or search term, so a session can consult a standard without loading the whole document. The documents it can open come from `lookup_documents.yml`, and each one's location comes from the manifest that records it. Installed as the command `read_pdf`. |
| `read_xlsx.py` | Prints a sheet out of any pinned workbook under `inputs/`, as an aligned table or one field per line for sheets too wide to align, and searches one workbook or all of them. A workbook is named by a path or by any fragment of its filename that matches exactly one. Installed as the command `read_xlsx`. |
| `lookup_documents.yml` | The documents `read_pdf` can open. Each row carries the key a person types, the label used when citing the document, the file name a manifest records, and the patterns for the page headers and footers to strip. The file opens with the rule for which documents belong in it. |
