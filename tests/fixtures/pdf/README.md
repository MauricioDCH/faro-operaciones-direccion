# Synthetic PDF fixtures

Tests build deterministic PDF fixtures at runtime with Python's standard library
and the same local Poppler tools required by the production extraction path:

- native-text invoice;
- scanned invoice or quotation;
- mixed PDF with one native page and one scanned page.

The fixture builders contain only synthetic business content. Generated files are
written to temporary directories and are not committed as binary artifacts.
