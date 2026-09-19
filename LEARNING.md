# Learning Notes

## Completed

- PyMuPDF returns structured page data, not plain text alone.
- Page numbers must stay attached to extracted text for citations.
- Blocks provide positional metadata useful for locating source text.
- Normalized page records make parser output easier to use downstream.

## Current Focus

- Extract meaningful lines in reading order.
- Preserve page number, text, and bounding box for each line.
- Do not add chunking or embeddings yet.