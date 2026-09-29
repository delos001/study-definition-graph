"""
Script:      vocabulary.py
Description: Holds the values a check's labels may take: the categories, the
             aspects of quality with the objectives each holds, and the cases.
             src/sdgval/build_inventory.py refuses a check whose label is not
             one of them, src/sdgval/select_checks.py refuses a selection option
             that names none of them, and src/sdgval/labels.py reads a check's
             aspect from its objective here.

             The values live in a file of their own so that every file that needs
             them can import them without importing another that imports it back.
             validation/README.md and validation/validation_inventory_dictionary.md
             say what each value means.

Inputs:      It reads nothing.

Outputs:     Nothing on disk. Other code imports the values.

Usage:       This file is not run directly; other code imports it.
             from sdgval.vocabulary import ASPECT_OF, CATEGORIES
                ASPECT_OF["correctness"]   -> "integrity"

Exit codes:  There are none. This file is not run on its own.

Date:        2026-09-29
Owner:       Jason Delosh
"""

from __future__ import annotations

#######################################################################################
### The values a label may take ###

# What kind of thing a check confirms. validation/validation_inventory_dictionary.md
# defines each one.
CATEGORIES = ("repository", "sources", "processing", "products")

# The objectives each aspect of quality holds. A check carries only its objective,
# and the generator looks the aspect up here, so an objective can never be filed
# under an aspect it does not belong to. Adding an objective means adding it here,
# which is what keeps the two in step. The dictionary defines every one of them.
OBJECTIVES_BY_ASPECT = {
    "conformance": ("conformance",),
    "integrity": ("correctness", "completeness", "stability", "consistency"),
    "technical": (
        "functionality",
        "performance",
        "reliability",
        "security",
        "compatibility",
        "maintainability",
        "portability",
    ),
}

# Every objective, and the aspect each one belongs to. Both are worked out from the
# table above rather than typed a second time, so neither can drift from it.
ASPECT_OF = {
    objective: aspect
    for aspect, objectives in OBJECTIVES_BY_ASPECT.items()
    for objective in objectives
}
OBJECTIVES = tuple(ASPECT_OF)

# The aspects, in the order the vocabulary lists them. A check file's name ends with
# one of them, so the names come from the vocabulary rather than a list of their own.
ASPECTS = tuple(OBJECTIVES_BY_ASPECT)

# A check that staged its own situation carries one of these, saying whether the
# situation was a working one or a broken one. A check that looked at something real
# carries neither. The case says how the check was set up, which is a separate thing
# from the question it asks, so any objective may carry one.
CASES = ("positive", "negative")
