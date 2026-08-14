# Review Checklist — <JIRA-KEY>
<!-- Every item requires explicit PASS / FAIL(detail) / N-A(why) -->

## Spec compliance
- [ ] Every acceptance criterion is actually satisfied by the code (verify each)
- [ ] Nothing outside spec scope was added
- [ ] Out-of-scope items were NOT implemented

## Design conformance
<!-- Skip this section (mark N-A) only if no docs/design/<KEY>.md exists for this ticket. -->
- [ ] Implementation matches the design doc's declared interface/API
      contract (endpoints, function signatures, request/response shapes)
- [ ] Data model matches the design doc (or deviation is explicitly
      justified in the PR/ticket)
- [ ] Key technical decisions in the design doc were actually followed
      (or deviation is explicitly justified — not silently different)
- [ ] Anything the design doc promised a downstream story would depend on
      (a shared function, a naming convention, a config key) actually
      exists as specified

## Correctness
- [ ] Logic errors / off-by-one / boundary conditions
- [ ] Error paths handled (not just happy path)
- [ ] No race conditions / unsafe shared state introduced

## Security
- [ ] No secrets/credentials in code or config
- [ ] External input validated/escaped where applicable
- [ ] No obviously unsafe patterns (injection, path traversal, eval)

## Tests
- [ ] AC->test mapping table exists and is accurate
- [ ] Tests assert behavior, not implementation details
- [ ] No existing tests weakened or deleted

## Maintainability
- [ ] Follows existing codebase patterns and profile conventions
- [ ] No unjustified duplication
- [ ] Naming communicates intent

## Verdict
APPROVE / REQUEST_CHANGES:
1. <actionable item>
