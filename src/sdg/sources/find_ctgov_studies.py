"""
Script:      find_ctgov_studies.py
Description: Finds the studies on ClinicalTrials.gov that pass the filters in
             src/sdg/sources/ctgov_study_filters.yml, so a person can choose from
             them which studies to download and review.

             This file is a draft. Its sections are laid out, and the code is
             written one piece at a time under issue #57.

             What is settled now:
             - the API answers the query in the filters file, and the script then
               applies the rules listed there under after_fetch, which the API
               cannot apply itself,
             - each run saves a record of the query as sent, the date it ran, how
               many studies were left after the query and after each rule, and
               the studies that passed. The registry changes daily, so a later run
               cannot reproduce an earlier one, and the record is the only proof
               of what a run found.

Inputs:      src/sdg/sources/ctgov_study_filters.yml (read-only)
             the ClinicalTrials.gov API (read-only)

Outputs:     One run record per run. Where the records are kept is settled under
             issue #57.

Usage:       Settled as the pieces are written.

Exit codes:  Settled as the pieces are written.

Date:        2026-10-02
Owner:       Jason Delosh
"""

#######################################################################################
### Settings ###

# Where the filters file is, and how many studies to ask the API for in one page.

#######################################################################################
### Reading the filters ###

# Loads ctgov_study_filters.yml, which holds the query and the after-fetch rules.

#######################################################################################
### Asking the API ###

# Sends the query and collects every page of the reply. When the download script of
# issue #58 needs the same piece, it moves into a file of its own that both use.

#######################################################################################
### Applying the after-fetch rules ###

# Applies each rule in turn, and counts how many studies each one removes.

#######################################################################################
### Saving the run record ###

# Writes the query as sent, the date, the counts and the studies that passed.

#######################################################################################
### Finding the studies ###

# The main() that runs the sections above in order.
