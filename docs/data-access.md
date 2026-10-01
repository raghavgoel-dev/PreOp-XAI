# PreOp-XAI Data Access

Status: access was not evidenced in this session. This page records the official
sources, the researcher checklist, and the handling rules. Last updated:
2026-10-01.

## Official sources

- Release page (INSPIRE 1.4.2): https://physionet.org/content/inspire/1.4.2/
- DOI: https://doi.org/10.13026/1eay-yc85
- Data Use Agreement: https://physionet.org/content/inspire/view-dua/1.4.2/
- Profile and credentialing: https://physionet.org/settings/profile/
- CITI training guidance: https://physionet.org/about/citi-course/
- PhysioNet FAQs: https://physionet.org/about/faqs/
- Responsible-use guidance for large language models:
  https://physionet.org/news/post/llm-responsible-use/
- Dataset publication (manuscript): https://pmc.ncbi.nlm.nih.gov/articles/PMC11192876/

Only these sources are authoritative. Mirrors, reposts, and third-party copies
are not used (see `docs/decisions.md`, D-005).

## Researcher checklist

Each person who accesses the data must qualify individually; access is per
person, not per project. The steps, in order:

1. Create or confirm a PhysioNet account and sign in.
2. Complete identity credentialing via the profile page
   (https://physionet.org/settings/profile/).
3. Complete the CITI "Data or Specimens Only Research" course and submit the
   completion report through PhysioNet (see
   https://physionet.org/about/citi-course/).
4. Accept the dataset's credentialed health data agreement, listed for this
   release as the Korea Credentialed Health Data Agreement
   (https://physionet.org/content/inspire/view-dua/1.4.2/).
5. Verify restricted access: the Files section of the release page must become
   visible and list downloadable content for the signed-in account.
6. Determine institutional ethics requirements with the researcher's own
   institution before any analysis and record the outcome locally. No ethics
   determination has been made for this project yet, and none is claimed.

## Handling rules

- The authenticated inventory and download are performed by the researcher in a
  separate local terminal, outside captured or shared tooling. The researcher
  runs `uv run preop-risk download-data ...` interactively; no captured session
  initiates or observes the authenticated transfer.
- Credentials are entered only through an interactive prompt, or through the
  official Wget `--ask-password` flow on systems where GNU Wget is available.
  Credentials never appear in chat, command arguments, configuration files,
  environment dumps, logs, or committed files.
- No bypassing or weakening access controls, no sharing of the researcher's
  authenticated session, and no mirrors.
- Automated tooling must not inspect credentials, the authenticated session, or
  any authenticated URL. Authenticated-only metadata stays under the external
  raw root (`INSPIRE_DATA_DIR`), is never committed, and is not pasted into
  chat.
- No cloud-based inference or processing on patient-level data. All computation
  is local (see `docs/decisions.md`, D-018).

## Public logical roles versus authenticated-only physical metadata

Public documentation describes the dataset's logical roles. The physical
filenames, download URLs, sizes, checksums, table schemas, and data dictionaries
are visible only after authenticated access and are therefore unknown to this
repository until the researcher's inventory exists.

| Public logical role (known now) | Physical filenames, URLs, sizes, checksums, schema, dictionaries |
| Operations | Authenticated-only; unknown until inventory |
| Laboratory results | Authenticated-only; unknown until inventory |
| Ward and device observations | Authenticated-only; unknown until inventory |
| Diagnosis codes | Authenticated-only; unknown until inventory |
| Medications | Authenticated-only; unknown until inventory |
| Intraoperative vitals | Authenticated-only; unknown until inventory |
| Dictionaries and metadata (public documentation names supporting files such as `schema.csv`, `parameters.csv`, and applicable excluded-code files) | Exact set, sizes, and checksums authenticated-only; unknown until inventory |

Rules that follow from this split:

- Code and docs may name logical roles freely.
- Code and docs must not hardcode physical file names (beyond the publicly
  documented supporting files above), sizes, counts, checksums, column lists, or
  URLs. All of these come from the inventory artifact at runtime.
- Any document that states a physical fact before the inventory exists is wrong
  and must be corrected.

## Data Use Agreement obligations

The DUA at the link above governs use, sharing, and publication. Key operational
consequences for this project, to be re-read against the live DUA text at access
time:

- Do not redistribute the data or derived patient-level content.
- Do not attempt re-identification.
- Publish only aggregate, non-identifiable outputs.
- Cite the dataset through its DOI in any report.
