# validation/reports/

This folder holds the filed validation reports, the formal records that the code was validated.

- Each aspect of quality has its own folder here, created when its first report is filed, such as `technical/`.
- Each filed run writes two CSV files in that folder. The report has one row per check, and the run's own file has one row with the run's details.
- What each column holds is in [validation_report_dictionary.md](validation_report_dictionary.md).
- When and how a report is filed is in [../running_validation.md](../running_validation.md).
