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
from .fingerprint_file import Comparison, Fingerprint, compare, fingerprint
from .finalize_file import discard, place
from .verify_pinned import IntegrityError, PinnedFile, verify_pinned

__all__ = [
    "Comparison",
    "Entry",
    "FetchError",
    "Fingerprint",
    "IntegrityError",
    "Manifest",
    "ManifestError",
    "NotInRepoError",
    "compare",
    "discard",
    "entry_for",
    "fetch",
    "fingerprint",
    "manifests",
    "partial_path",
    "place",
    "PinnedFile",
    "require_repo",
    "verify_pinned",
]
