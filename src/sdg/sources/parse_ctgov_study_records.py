"""
Script:      parse_ctgov_study_records.py
Description: Pulls single pieces of information out of a ClinicalTrials.gov study
             record, such as the study's documents or the countries where it has sites.

             Each study from ClinicalTrials.gov is one large block of details, as
             fetch_ctgov_study_records.py collects it. Each function here takes one
             record and hands back one piece of it, and a caller runs it over every
             record it holds.

             This module reads nothing on disk, writes nothing and never asks the API.

Inputs:      one study record at a time, as ClinicalTrials.gov sent it

Outputs:     Nothing on disk.
             Hands back the piece asked for: the study's documents, its countries
             with sites, or the details a person needs to pick between studies.

Usage:       This file is not run directly; other code imports it.
             from sdg.sources.parse_ctgov_study_records import list_study_documents
                list_study_documents(study)    -> one entry per posted document
                list_study_countries(study)    -> the countries with sites, each once
                describe_candidate(study)      -> the details a person picks a study by

Exit codes:  There are none, because this file is not run on its own, and nothing in
             it raises an error. A piece missing from a record comes back empty.

Date:        2026-10-06
Owner:       Jason Delosh
"""

from typing import Any

#######################################################################################
### Reading a study record ###

# Each study from ClinicalTrials.gov is one large block of details.  The functions
# in this section parse needed information from that block.


def list_study_documents(study: dict[str, Any]) -> list[dict[str, Any]]:
    """List the documents associated with a study.

    Args:
        study: One study as ClinicalTrials.gov sent it.

    Returns:
        One entry per document, or an empty list when the study has none.
    """
    module = study.get("documentSection", {}).get("largeDocumentModule", {})
    return module.get("largeDocs", [])


def list_study_countries(study: dict[str, Any]) -> set[str]:
    """List the countries where the study has sites, each country once.

    Args:
        study: One study from ClinicalTrials.gov.

    Returns:
        The names of the countries, or an empty set when the study lists no sites.
    """
    module = study.get("protocolSection", {}).get("contactsLocationsModule", {})
    return {
        site["country"] for site in module.get("locations", []) if site.get("country")
    }


def describe_candidate(study: dict[str, Any]) -> dict[str, Any]:
    """Gather details a person needs to choose between candidate studies.

    Args:
        study: One study that passed every filter.

    Returns:
        The study's ID, title, lead sponsor, conditions, countries with sites,
        enrollment, and whether it posted an informed consent form (ICF).
    """

    protocol = study.get("protocolSection", {})
    identification = protocol.get("identificationModule", {})
    sponsors = protocol.get("sponsorCollaboratorsModule", {})
    return {
        "nct_id": identification.get("nctId"),
        "title": identification.get("briefTitle"),
        "sponsor": sponsors.get("leadSponsor", {}).get("name"),
        "conditions": protocol.get("conditionsModule", {}).get("conditions", []),
        "countries": sorted(list_study_countries(study)),
        "enrollment": protocol.get("designModule", {})
        .get("enrollmentInfo", {})
        .get("count"),
        "icf_posted": any(d.get("hasIcf") for d in list_study_documents(study)),
    }
