"""
sdg.sources: get and keep the pipeline's inputs.
See README.md.
"""

# Each function that other code is meant to use is listed here, so a caller
# writes `from sdg.sources import manifests` and never names the file it is
# in. A function not listed is still importable by its file, only the short
# form is missing. The list grows as each file's code is written.

from .read_manifests import Entry, Manifest, ManifestError, NotInRepoError, entry_for, manifests, require_repo
from .fetch_file import FetchError, fetch, partial_path

__all__ = [
    "Entry",
    "FetchError",
    "Manifest",
    "ManifestError",
    "NotInRepoError",
    "entry_for",
    "fetch",
    "manifests",
    "partial_path",
    "require_repo",
]
