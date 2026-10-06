"""
The sdg.sources folder gets and keeps the pipeline's inputs.
See README.md.
"""

# Each function that other code is meant to use is listed here, so a caller
# writes `from sdg.sources import manifests` and never names the file it is
# in. A function not listed can still be imported from its own file. Only the
# short form is missing. The list grows as each file's code is written.

from .fetch_ctgov_study_records import (
    CtgovBadAnswerError,
    CtgovError,
    CtgovNoAnswerError,
    CtgovReplyUnparseableError,
    fetch_ctgov_study_records,
)
from .fetch_file import (
    FetchBadUrlError,
    FetchError,
    FetchErrorAnswerError,
    FetchNoAnswerError,
    FetchNotWrittenError,
    FetchRefusedError,
    fetch,
    partial_path,
)
from .finalize_file import discard, place
from .fingerprint_file import Comparison, Fingerprint, compare, fingerprint
from .narrow_ctgov_study_records import (
    FiltersError,
    FiltersInvalidError,
    FiltersMissingError,
    FiltersUnparseableError,
    FiltersUnreadableError,
    narrow_ctgov_study_records,
    read_filters,
)
from .parse_ctgov_study_records import (
    describe_candidate,
    list_study_countries,
    list_study_documents,
)
from .read_manifests import (
    AmbiguousNameError,
    Entry,
    Manifest,
    ManifestError,
    ManifestMissingError,
    ManifestNameError,
    ManifestUnparseableError,
    ManifestUnreadableError,
    NotInRepoError,
    OutsideInputsError,
    entry_for,
    entry_named,
    manifests,
    require_repo,
)
from .save_ctgov_search_records import RecordNotWrittenError, save_ctgov_search_records
from .verify_pinned import (
    IntegrityError,
    PinnedFile,
    UnrecordedFileError,
    verify_pinned,
)
from .write_manifests import (
    ManifestEntryExistsError,
    ManifestNotWrittenError,
    write_manifests,
)

__all__ = [
    "AmbiguousNameError",
    "Comparison",
    "CtgovBadAnswerError",
    "CtgovError",
    "CtgovNoAnswerError",
    "CtgovReplyUnparseableError",
    "Entry",
    "FetchBadUrlError",
    "FetchError",
    "FetchErrorAnswerError",
    "FetchNoAnswerError",
    "FetchNotWrittenError",
    "FetchRefusedError",
    "FiltersError",
    "FiltersInvalidError",
    "FiltersMissingError",
    "FiltersUnparseableError",
    "FiltersUnreadableError",
    "Fingerprint",
    "IntegrityError",
    "Manifest",
    "ManifestEntryExistsError",
    "ManifestError",
    "ManifestMissingError",
    "ManifestNameError",
    "ManifestNotWrittenError",
    "ManifestUnparseableError",
    "ManifestUnreadableError",
    "NotInRepoError",
    "OutsideInputsError",
    "RecordNotWrittenError",
    "UnrecordedFileError",
    "compare",
    "describe_candidate",
    "discard",
    "entry_for",
    "entry_named",
    "fetch",
    "fetch_ctgov_study_records",
    "fingerprint",
    "list_study_countries",
    "list_study_documents",
    "manifests",
    "narrow_ctgov_study_records",
    "partial_path",
    "place",
    "PinnedFile",
    "read_filters",
    "require_repo",
    "save_ctgov_search_records",
    "verify_pinned",
    "write_manifests",
]
