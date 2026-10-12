# Operations workspace redesign

This draft replaces the dark promotional UI with a warm, evidence-led workspace
across all 11 existing routes. It retains the prototype's actual backend and
synthetic example boundaries. No hosted worker, live refund, production model
training, deployment, new dependency, or new external connection is introduced.

## Design decisions

- Group navigation by Workspace, Operate, and Studio. Keep every URL.
- Use a 224px dark green-black rail, a quiet location header, warm neutral canvas,
  white working documents, compact metadata, and cobalt actions.
- Make source records, workflow evidence, object traces, draft policy, invoice,
  ticket and incident the center of the page instead of decorative hero panels.
- Keep unknown, loading, empty, failed and confirmed states distinct.
- At tablet widths use named icon navigation; on mobile use a native modal drawer
  with Escape/backdrop/route dismissal and restored focus.
- Use the installed Framer Motion 11 for the active tab marker and real result
  state feedback. Respect reduced motion in both React motion and CSS.

The reference material informed original layout decisions, not copied assets:
[Linear UI redesign](https://linear.app/now/how-we-redesigned-the-linear-ui),
[Linear's calmer interface](https://linear.app/now/behind-the-latest-design-refresh),
[incident.io timeline](https://incident.io/changelog/tell-the-full-story-with-your-incident-timeline),
and [Motion accessibility guidance](https://motion.dev/docs/react-accessibility).
System fonts, existing Lucide icons, React Flow and Recharts remain in use.

## Functional boundaries preserved

Workflow Lab still has all five examples, an explicit connected/local switch,
arrow/Home/End tabs, cancellation/race guards and duplicate-submit locks. The
invoice's built-in document preview is compared to the Python fixture by
`tests/test_invoice_preview.py`. Its discrepancy changes the stated total to
$3,466; the actual validation delta is expected minus stated, or -$10. Approval
and rollback still operate on the same returned ticket/incident and token.

Discovery retains source IDs. Its graph positions are explicitly illustrative;
unfounded inter-workflow edges were removed. Object filters cannot leave an
unrelated object trace selected. Scores now display the API's recommended mode.
Pilot validation, mutations and lifecycle locks remain unchanged. Model Recipes
keeps both attestations, data opt-in, redaction limits and artifact-only outcome.
Social Studio keeps three formats and both clipboard flows; copied examples
carry their synthetic/illustrative disclosure.

## Verification and review

Independent source review covered all routes, shared navigation, lifecycle
preservation, invoice fixture synchronization and test changes. It identified
three fixed accessibility/control issues: dark-rail focus contrast, clipped
scroll-region focus outlines, and a nonfunctional tablet expansion toggle.

Local checks for this draft:
- 253 frontend tests across 19 files pass (including new overview and simulation
  state coverage and strengthened source/mode/selection/copy assertions).
- 396 backend tests and 138 subtests pass; measured backend line coverage 100%.
- The Playwright suite discovers 70 tests. In addition to the existing actual API
  workflows it covers all routes at 1440px, 390px, 320px and 768px widths, short
  viewports, modal focus, and reduced-motion/200% CSS zoom behavior.

Discovery of tests is not execution. The current draft's actual browser result
must be verified from CI for its exact commit. Native browser zoom, screen-reader
compliance, other browser engines and exhaustive accessibility are not certified.
A prior recording's frames were inspected only as a supplied before-reference.
Fresh screenshots/pixel review and a revised recording remain separately gated
by a permitted capture and transfer path. No new media artifact upload is enabled
by this redesign commit. The consumed earlier one-shot workflow gate is unchanged.

No merge, deployment or public hosting is authorized by this draft. In particular,
this UI work does not solve the prototype's public authentication/session security
requirements. Keep the application unexposed until that separate work is reviewed.
