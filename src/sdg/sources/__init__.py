"""
The sdg.sources folder gets and keeps the pipeline's inputs.
See README.md.
"""

# Each function that other code is meant to use is listed here, so a caller
# writes `from sdg.sources import manifests` and never names the file it is
# in. A function not listed can still be imported from its own file. Only the
# short form is missing. The list grows as each file's code is written.

from .fetch_file import FetchError, fetch, partial_path
from .finalize_file import discard, place
from .fingerprint_file import Comparison, Fingerprint, compare, fingerprint
from .read_manifests import (
    Entry,
    Manifest,
    ManifestError,
    NotInRepoError,
    entry_for,
    entry_named,
    manifests,
    require_repo,
)
from .verify_pinned import (
    IntegrityError,
    PinnedFile,
    UnrecordedFileError,
    verify_pinned,
)

__all__ = [
    "Comparison",
    "Entry",
    "FetchError",
    "Fingerprint",
    "IntegrityError",
    "Manifest",
    "ManifestError",
    "NotInRepoError",
    "UnrecordedFileError",
    "compare",
    "discard",
    "entry_for",
    "entry_named",
    "fetch",
    "fingerprint",
    "manifests",
    "partial_path",
    "place",
    "PinnedFile",
    "require_repo",
    "verify_pinned",
]
