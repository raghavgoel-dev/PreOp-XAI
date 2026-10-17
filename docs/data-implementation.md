# Data implementation

## Scope and completion record

Implemented the MOVER EPIC data lane against the supplied 17 October 2026
contract: raw audit, canonical adapters, reviewed cohort indexing, nullable
labels, laboratory extraction/provenance, leakage checks and patient splits.

This entry records implementation, not clinical approval. The local raw audit
and synthetic regression execution are recorded in `verification.md`; external
age verification and qualified clinical review remain required.
VitalDB is not included. Model-lane imputation and SHAP tests remain owned by
their respective lanes.

## Canonical boundary

Compact products are pandas tables. Identifiers remain source strings.
`patient_id`, `operation_id`, `t0` identify an indexed operation.
Datetime inputs must use one consistent, externally verified timezone convention;
mixed timezone sources must be normalized before these functions are called.

`load_information(raw_dir)` reads `patient_information.csv`, projecting the
specified source headers. Numeric-looking `BIRTH_DATE` is retained as source
text until external review: it is never parsed as a birth date.

Before `build_cohort`, externally verify and set:

    information.attrs["review"] = {
        "age_numeric_years": True,
        "asa_mapping": True,
        "hospitalization_linkage": True,
        "anesthesia_boundary": True,
        "static_provenance": True,
    }

These flags are attestations, not automated validation. Translate ASA into
canonical integer classes 1–6 before setting its gate. Verify sex categories,
age capping and static availability externally. Persist review evidence outside
DataFrame attributes, which storage formats may discard. Synthetic flags cannot
approve real records.

Exact duplicates across every supplied field collapse. Any remaining repeated
operation ID is quarantined in full, including disagreements in patient identity.
Missing identifiers, non-adults, invalid known ASA, ASA VI and invalid anesthesia
intervals are excluded. Missing ASA and missing discharge are retained. Hospital
containment is checked in labeling, not used to select a later operation.
The earliest eligible operation is indexed without inspecting outcomes.
Ambiguous first-operation timestamp ties quarantine the patient rather than
inventing chronology from identifier sorting. Exclusions are in `cohort.attrs["exclusions"]` and
must be persisted privately by integration code.

## Outcome configuration

Example shape; descriptions and rules below are illustrative, not approvals:

    version: reviewed-map-version
    mortality:
      reviewed: false
      positive_descriptions: ["Expired"]
      negative_descriptions: ["Home"]
      unknown_descriptions: ["Transfer", "Hospice"]
    respiratory:
      enabled: false
      reviewed: false
      rules:
        - element: exact source element
          abbreviation: exact source abbreviation
          context: exact reviewed postoperative context
          value: exact affirmative value
          label: 1
        - element: exact source element
          abbreviation: exact source abbreviation
          context: exact reviewed postoperative context
          value: exact explicit negative value
          label: 0

Populate the complete observed disposition inventory. Transfer and hospice must
remain unknown unless a separately approved protocol explicitly changes their
handling. Unmapped descriptions remain unknown. Mortality requires all linked
information evidence to agree and have consistent cutoff/hospitalization timing.
Information contradictions yield unknown, not majority voting.

Respiratory rules match all four strings exactly. Both positive and explicit
negative mappings are required when enabled. Contradictory matched assessments
yield unknown; absence and unmapped observations do not imply negative.
Review must establish postoperative meaning and assessability. Labels are
nullable `Int64`, with reason and mapping-version columns.

## Laboratory configuration

Required shape:

    reviewed: false
    availability: collection_proxy
    proxy_lag_hours: 24
    file: patient_labs.csv
    columns:
      patient_id: MRN
      operation_id: LOG_ID
      collection_time: Collection Datetime
      lab_name: Lab Name
      value: Observation Value
      unit: Measurement Units
    labs:
      hemoglobin:
        names: [exact reviewed name]
        units: {exact source unit: 1.0}
        min: 1.0
        max: 30.0

Provide all seven concepts: hemoglobin, platelets, creatinine, bun, sodium,
potassium and glucose. Bounds above are illustrative only. Each requires
reviewed names, multiplicative source-to-standard unit factors and finite
plausibility bounds. No implicit unit conversion or text-threshold conversion
is performed. Unit targets are g/dL, 10^9/L, mg/dL, mg/dL, mmol/L, mmol/L and
mg/dL respectively. Review specimen compatibility and BUN versus urea explicitly.

Inspect actual lab headers with `audit_raw`; override the column map rather
than guessing. `RESULT_TIME` is the default collection-time proxy only.
Strict mode requires `availability: strict` and an additional explicit
`columns.result_time` mapping to a verified result-release timestamp.

The 3.56 GB source is scanned lazily as strings, projected, filtered to mapped
names and joined to indexed keys before collection. The temporal window is
filtered lazily before collection, with raw rejection counts stored separately.
Compact candidates include value/unit/release rejections for provenance; exceptionally large retained
candidate sets still require sufficient memory. No whole-source pandas read
occurs.

Proxy eligibility is inclusive from t0 minus 30 days through t0 minus 24 hours.
Strict eligibility requires collection at or after t0 minus 30 days, collection
at or before release, and release at or before t0. Availability is evaluated
before latest-result selection. Invalid strings, nonfinite values, unknown
units and implausible values are rejected. Conflicting normalized values at
the latest eligible collection time make that concept missing; the algorithm
does not fall back to an older observation. Equivalent latest ties select a
deterministic source representation.

`build_features` returns identity plus the ten ordered predictors, and long
candidate provenance including raw values, collection/release times, normalized
values, selection status and reasons. Cohort members without eligible labs
remain present. Provenance is restricted patient-level data.

The model matrix is explicitly:

    X = features.loc[:, [
        "age", "sex", "asa", "hemoglobin", "platelets", "creatinine",
        "bun", "sodium", "potassium", "glucose"
    ]]

Never pass identity columns to a model. Seven explicit laboratory missingness
indicators belong to training-only preprocessing, including entirely absent
training concepts. This data lane does not impute or create learned transforms.

`audit_leakage` checks identity alignment, allowed columns, temporal bounds,
reviewed conversions, selected provenance and static-feature preservation.
It cannot independently verify timestamp semantics, clinical review or the
truth of a collection-proxy availability assumption.

## Audit and split artifacts

`audit_raw` discovers CSV headers dynamically, scans strings with only empty
fields treated as null, computes SHA-256 in chunks, counts rows/keys and
inventories available mapping fields and respiratory tuples. Literal `None`
survives import. Audit files may contain restricted source values and must
remain in authorized storage. Counts/checksums do not establish clinical validity.

Splits sort identities before seeded sklearn stratified train/test splitting:
70% training, then half the 30% holdout to validation and test. Known mortality
must contain both classes in every partition; otherwise an actionable error
requires a prespecified design amendment, not seed searching. Unknown mortality
patients are shuffled once with the same seed and assigned by largest-remainder
70/15/15 allocation independently of respiratory labels. Nullable labels are
preserved. Root must audit endpoint counts before freezing.

## Verification ownership

Included tests cover review gates, exact duplicates/conflict quarantine,
outcome-independent indexing, label containment, nullable outcomes, literal `None`,
respiratory contradictions, proxy boundaries, strict release availability,
conversion, text/unit rejection, provenance consistency, lazy adapter linkage,
dynamic raw auditing and deterministic patient-independent splitting.

Root must execute the tests, add release-specific fixtures, persist exclusions
and review records, and perform clinical/sample-adequacy review before modeling.
No clinical approval is implied by automated execution.
