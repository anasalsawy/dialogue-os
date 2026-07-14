# Dialogue OS Conformance

A runtime may claim Dialogue OS compatibility only after running the canonical tests and preserving evidence.

## Required result fields

- Dialogue OS version
- runtime identifier
- compatibility level attempted
- test identifier
- method
- expected behavior
- observed behavior
- evidence references
- PASS/FAIL
- remediation owner
- timestamp

## Rules

- Prompt inspection alone is not a test.
- Simulated logs are not proof of runtime behavior.
- Repeated timestamps or duplicated evidence do not prove separate executions.
- A test that cannot observe the relevant state is `NOT PROVEN`, not `PASS`.
- Every failure remains visible until remediated and retested.
- Compatibility claims expire when a breaking runtime, policy, or Codex change occurs.
