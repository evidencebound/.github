# EvidenceBound

**Human Control Plane for Verifiable AI Agents**

EvidenceBound is early-stage open-source AI safety infrastructure for binding agent actions to evidence, provenance and executable policy, with deterministic verification, bounded blast radius and recoverable human control.

The core design principle is simple: an AI system should not be able to grant itself trust. EvidenceBound keeps verification, policy enforcement and human authority outside model-generated claims and makes unavailable, stale or mismatched evidence visible rather than silently promoting it to certainty.

## Core public implementations

| Repository | Purpose |
|---|---|
| [evidencebound-core](https://github.com/evidencebound/evidencebound-core) | Framework-agnostic runtime for evidence/provenance binding, deterministic verification, policy enforcement and fail-closed selective recovery. |
| [evidencebound-recovery-mesh](https://github.com/evidencebound/evidencebound-recovery-mesh) | Trust-aware selective recovery for autonomous agent fleets after a trust break. |
| [evidencebound-authority-cut](https://github.com/evidencebound/evidencebound-authority-cut) | Reversible autonomy with human authority kept outside the model-callable surface and correction propagated through affected descendants. |
| [evidencebound-releaseproof-dws](https://github.com/evidencebound/evidencebound-releaseproof-dws) | Differential reverification for changed document evidence under a frozen historical review-equivalence policy. |

## What EvidenceBound is designed to preserve

- **Evidence visibility** - missing, stale, blocked or mismatched evidence remains explicit.
- **Provenance** - claims are bound to inspectable inputs and transformations.
- **Executable policy** - trust decisions are enforced outside natural-language model output.
- **Deterministic verification** - machine-checkable gates decide whether evidence and state remain acceptable.
- **Bounded blast radius** - trust breaks invalidate only work that depends on the broken evidence or authority.
- **Recoverable human control** - human grants, revocations and corrections remain outside model self-authorization.

## Public identity

- Website: [evidencebound.org](https://evidencebound.org)
- Maintainer: [Ruslan Vrublevskyi](https://github.com/moneyparking)
- Contact: `ruslan@evidencebound.org`
- LinkedIn: [Ruslan Vrublevskyi](https://www.linkedin.com/in/ruslan-vrublevskyi)

EvidenceBound does not claim that cryptographically authenticated provenance makes source data true, that an LLM can certify its own behavior, or that a working prototype is equivalent to a security-reviewed production system.
