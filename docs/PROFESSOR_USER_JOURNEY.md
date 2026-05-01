# Professor User Journey

## Product Goal

Reduce professor effort while increasing confidence.

## Stage 1: Before Using The System

Professor mindset:

- Busy
- Limited time
- Skeptical of plagiarism tools
- Wants fairness
- Wants quick answers
- Does not want false accusations

System mission:

- Reduce anxiety
- Look professional
- Feel simple
- Promise efficiency without overclaiming

## Stage 2: Upload Assignment

Professor action:

- Upload ZIP
- Upload LMS export
- Upload repository bundle

Expected experience:

```text
+------------------------------+
| Drag files here              |
| or Import from LMS           |
+------------------------------+
```

System response:

- Detect language automatically
- Detect assignment type automatically
- Estimate processing time
- Confirm files received

Professor feeling:

> Good. I do not need to configure anything.

## Stage 3: Analysis Running

Progress should show serious work:

- Removing starter code
- Building similarity candidates
- Comparing prior semesters
- Ranking cases worth review

Professor feeling:

> This system is doing serious work.

## Stage 4: Results Summary

The first results screen must answer:

- How many cases need attention?
- How severe are they?
- Where should I start?

Example:

```text
412 submissions analyzed
9 cases may need instructor review
Top case confidence: High
Estimated review time: 12 minutes total
```

Professor feeling:

> Excellent. I only need to inspect 9 cases.

## Stage 5: Case List

The queue should prioritize professor time:

```text
Rank | Students | Risk   | Reason
1    | A vs B   | HIGH   | same rare logic
2    | C vs D   | HIGH   | prior term reuse
3    | E vs F   | MEDIUM | renamed structure
```

Professor feeling:

> It prioritized for me.

## Stage 6: Open A Case

Top of page:

```text
CASE: Student A vs Student B
Risk: HIGH
Confidence: HIGH
Review Time: ~2 min
```

Why flagged:

- Same recursive decomposition
- Same unusual edge-case handling
- Variables renamed
- Similar helper functions

Professor feeling:

> Now I understand why.

## Stage 7: Evidence Review

Evidence layout:

```text
+----------------------+  +----------------------+
| Student A Code       |  | Student B Code       |
| synchronized scroll  |  | synchronized scroll  |
| matched areas marked |  | matched areas marked |
+----------------------+  +----------------------+
```

Extra evidence:

- Starter code removed
- Compared only student-written logic
- Similar to prior semester shown only as context

Professor feeling:

> This is fair and credible.

## Stage 8: Decision Moment

Allowed actions:

- Mark for Review
- Needs More Evidence
- Dismiss
- Add Note
- Export PDF

Professor feeling:

> I remain in control.

## Stage 9: After Review

Progress summary:

```text
1 case resolved
8 remaining
Avg review time: 2.3 min
```

Professor feeling:

> This saves real time.

## Stage 10: Long-Term Trust

Trust comes from:

- Low false positives
- Clear explanations
- Faster review than old workflows
- Fair language and human final decision

Final professor thought:

> I trust this platform.

## Design Principles

- Simplicity first
- Show only what matters
- Explain before showing raw code
- Human makes final decision
- Save time visibly
- Use calm academic tone
- Keep evidence available

## Failure Signals

If the product fails, professors think:

- Too many cases
- I do not understand scores
- Too much clicking
- Looks aggressive
- Not worth my time

## Success Signals

If the product wins, professors think:

- Smart
- Fair
- Fast
- Clear
- Better than old tools
