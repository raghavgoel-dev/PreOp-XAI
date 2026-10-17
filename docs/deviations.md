# Decisions and deviations

## 17 October 2026 - initial implementation

- The plan and synopsis are aligned; no methodological expansion is needed.
- The respiratory endpoint is disabled pending qualified review. The shipped
  study title is mortality-only until its gates pass. This is the specified
  fallback, not evidence that respiratory ascertainment has failed.
- A synthetic demonstration exercises the implementation without substituting
  invented results for clinical experiments. Demo settings are visibly labeled.
- Actual cohort eligibility, endpoint semantics, ASA/age interpretation and
  predictor provenance remain unapproved until documented review occurs.
- VitalDB is optional and deliberately not merged into the core study.
- Generic skill defaults disagree with the explicit plan's pandas/scientific
  stack; the supplied study stack takes precedence.
- The staged root `.gitignore` belongs to the user. Nested output exclusions
  protect restricted artifacts without changing or committing that staged work.
