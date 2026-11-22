# Specs

Each piece of work starts as a short spec before any code is written. A spec folder holds:

| File | Answers |
| --- | --- |
| `requirements.md` | What must be true when the work is done, as numbered, testable acceptance criteria |
| `design.md` | How it will be built, and which alternatives were rejected and why |
| `tasks.md` | The ordered list of small changes that deliver it, each tied to the criteria it satisfies |

Requirements use ids such as `R1.2`. Tasks and tests refer back to those ids, so every criterion can be traced to the code and the test that proves it.

| Spec | Status |
| --- | --- |
| [001 Research brief](001-research-brief/requirements.md) | Done (PRs #1 to #8) |
| [002 Release v1.0.0](002-release-v1/requirements.md) | Done except the tag |
| [003 AWS deployment](003-aws-deployment/requirements.md) | Proposed |
| [004 Deeper evidence and a complete app](004-evidence-and-app/requirements.md) | Done |
| [005 Market focus and evidence hygiene](005-market-focus/requirements.md) | In progress |

A spec changes when the plan changes. Update it in the same pull request as the code, so the spec and the code never disagree.
