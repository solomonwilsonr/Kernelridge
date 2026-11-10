# Kernelridge

**Project proposal — Version 1.1**
**Project name:** Kernelridge
**Category:** Open-source agentic infrastructure compatibility intelligence
**Short tagline:** *Know what breaks before it breaks.*  
**Date:** 10 November 2026  
**Foundation:** VCM Machines (existing versioning, dependency graph, drift and MCP capabilities)
**Proposed repository name:** `kernelridge` (availability unverified)  
**Research working title:** EAGER — Evidence-Aware Agentic Revalidation for Heterogeneous Infrastructure  
**Tagline:** *Know what may break, discover why, and verify the fix before deployment.*

## 1. Executive Summary

**Naming convention:** Kernelridge is the platform and open-source project. VCM Machines is the underlying existing foundation; EAGER remains the provisional research framework and ECAR the provisional experiment-selection algorithm. The names do not imply trademark or domain availability.


Kernelridge is a proposed open-source, AI-assisted platform for validating hardware–software compatibility **before** infrastructure changes are deployed. It extends VCM Machines' versioned hardware manifests, semantic comparison, dependency analysis, drift detection, audit records, and MCP capabilities with an **evidence-aware, autonomous experimentation workflow**.

The system compares current and proposed states; identifies compatibility claims that may no longer be valid; determines what is unknown; chooses targeted experiments under cost and safety constraints; runs those experiments in isolated environments; and produces scoped, reproducible evidence for a human-reviewed deployment decision.

The first target is **RISC-V Linux**, using QEMU for emulated tests and at least one physical RISC-V device for selected hardware validation. ARM64, x86, AWS, and heterogeneous edge fleets are later targets.

**Research hypothesis:** Version-aware evidence tracking and risk-constrained active experiment selection can reduce compatibility revalidation cost while maintaining specified failure-detection requirements compared with conventional test-selection baselines. This is a hypothesis to test, **not an established result or a verified claim of novelty**.

## 2. Problem Statement

Teams operating mixed hardware and software configurations face five related problems:

1. **Fragmented configuration knowledge.** Processor capabilities, firmware, kernels, drivers, libraries, applications, and deployment policies live in different systems.
2. **Unknown pre-deployment compatibility.** Infrastructure-as-code previews and configuration diffs do not necessarily establish that a native application will run on a specific processor and operating environment.
3. **Expensive regression testing.** Large test matrices repeat work even when changes affect only a subset of assumptions.
4. **Stale evidence.** A passing test on an earlier machine or kernel revision may no longer support the same claim after a relevant change.
5. **Manual investigation.** Engineers must choose experiments, diagnose failures, and validate possible fixes.

### Example

An application built for a RISC-V ISA extension is proposed for a target processor that lacks that extension. Kernelridge should detect the mismatch, explain the evidence, propose an alternative build, test it in QEMU, seek physical-device validation when necessary, and record precisely what has and has not been established. If the processor, kernel, or other relevant dependency changes later, Kernelridge should re-evaluate the validity of the earlier evidence.

## 3. Product Vision and Scope

### Core question

> Given a proposed change and a target environment, which compatibility claims remain supported, which are uncertain or invalidated, and what is the least costly **safe** sequence of experiments that can resolve the important uncertainties?

### Intended users

- Cloud and platform engineers managing mixed compute architectures.
- Embedded Linux and RISC-V developers.
- Edge-device manufacturers and fleet operators.
- CI/CD and release engineers validating native software.
- Researchers studying regression test selection and dependable systems.

### In scope for initial MVP

- Versioned hardware/software manifests.
- RISC-V ISA and ELF/ABI compatibility checks.
- Dependency-based impact analysis.
- Evidence graph with assumptions and provenance.
- Conservative evidence invalidation after changes.
- Cost- and risk-aware experiment planning.
- Isolated QEMU execution and structured test results.
- Preflight report with `PASS`, `FAIL`, `REVIEW`, or `UNKNOWN` decisions.
- Human approval gates and audit trails.

### Out of scope for initial MVP

- Autonomous production deployment or destructive remediation.
- Universal support for all processors, firmware, and operating systems.
- Guaranteed absence of undiscovered compatibility failures.
- Treating QEMU success as proof of physical-hardware compatibility.
- Training a foundation model from scratch.

## 4. Proposed Differentiation

The proposed contribution is **not** merely adding AI agents to a test runner. The distinguishing workflow combines:

1. **Version-aware compatibility evidence:** Claims are linked to the exact hardware, firmware, OS, libraries, build artifacts, and test environment that support them.
2. **Evidence invalidation:** Relevant changes cause earlier claims to be marked for revalidation, while demonstrably unaffected evidence may be retained.
3. **Uncertainty-guided experimentation:** The system identifies unresolved claims and selects informative experiments subject to budgets and mandatory safety coverage.
4. **Causal investigation:** Controlled changes and repeated tests help distinguish causes from correlations.
5. **Portable scoped attestations:** Reports state what was tested, under which assumptions, with what results, and what would invalidate the findings.
6. **Cross-architecture extension:** Later research investigates when evidence can be transferred between emulated RISC-V, physical RISC-V, ARM64, and x86.

These ideas overlap with existing work in regression test selection, active learning, incremental assurance, causal debugging, and software attestations. A literature and prior-art review is required before claiming algorithmic novelty.

## 5. System Architecture

```text
GitHub PR / Kernelridge CLI / Dashboard / API
                  |
                  v
       Change Request + Proposed State
                  |
                  v
        VCM Agentic Orchestrator
                  |
      +-----------+------------+
      |           |            |
      v           v            v
 Discovery     Impact       Hypothesis
 Workflow      Workflow     Workflow
      |           |            |
      +-----------+------------+
                  |
                  v
         VCM Deterministic Core
   (manifests, diffs, dependency graph,
    compatibility rules, policy engine)
                  |
                  v
        Evidence Dependency Graph
                  |
                  v
     Risk-Constrained Experiment Planner
                  |
          +-------+--------+
          |                |
          v                v
    QEMU / EC2 Lab     Physical RISC-V CI
          |                |
          +-------+--------+
                  |
                  v
       Results + Provenance + Logs
                  |
                  v
       Invalidation / Revalidation
                  |
                  v
      Signed, Scoped Preflight Report
                  |
                  v
      Human Review / Deployment Gate
```

**Trust boundary:** The LLM proposes hypotheses, tests, and candidate fixes. Deterministic rules and a separate policy engine validate tool inputs, authorize experiment execution, and control final deployment permissions. The LLM cannot unilaterally approve production changes.

## 6. Core Modules

| ID | Module | Responsibilities | Priority |
|---|---|---|---|
| M1 | Inventory adapter | Capture architecture, ISA extensions, firmware, kernel, drivers, ABI, libraries, build provenance | P0 |
| M2 | Change impact engine | Compare manifests and calculate affected dependency paths | P0 |
| M3 | Evidence graph | Store claims, assumptions, experiments, outcomes, confidence, hashes, provenance | P0 |
| M4 | Compatibility analyzer | Evaluate deterministic ISA, ELF, ABI, package, and known kernel constraints | P0 |
| M5 | Experiment planner | Select tests using relevance, uncertainty, severity, cost, and required coverage | P0 |
| M6 | Autonomous lab | Run isolated QEMU and physical-device experiments with budgets and timeouts | P1 |
| M7 | Diagnosis workflow | Generate and test causal hypotheses about observed incompatibilities | P1 |
| M8 | Remediation workflow | Propose alternative builds/configurations and verify candidates | P1 |
| M9 | Attestation exporter | Sign and export reproducible, scoped evidence records | P1 |

## 7. Evidence Model

A compatibility conclusion is a **claim** supported by one or more **observations** and conditional on explicit **assumptions**.

### Example entities

- `MachineRevision`: CPU/ISA, firmware, kernel, drivers, installed packages.
- `ArtifactRevision`: application binary, build flags, dependencies, checksum.
- `ChangeSet`: before/after state and affected dependency nodes.
- `CompatibilityClaim`: statement such as “artifact A executes correctly on target B under workload W.”
- `Experiment`: test method, executor, environment, parameters, cost, policy scope.
- `Observation`: output, exit code, logs, measurements, pass/fail/inconclusive status.
- `Evidence`: links observations to claims and records assumptions, provenance, and validity.
- `Attestation`: signed representation of scoped findings.

### Evidence lifecycle

`SUPPORTED → POTENTIALLY_INVALIDATED → REVALIDATING → SUPPORTED / REFUTED / UNKNOWN`

A change invalidates evidence **only relative to the claim's recorded assumptions and dependency relationships**. When those relationships are incomplete, the system conservatively requests review or retesting rather than declaring evidence valid.

### Sample conceptual evidence record

```yaml
claim_id: claim-001
statement: "application-v2 runs on riscv-lab-001 for smoke-workload"
target_revision: machine-rev-42
artifact_sha256: "<actual-content-hash>"
assumptions:
  - cpu.isa.extensions
  - os.kernel.version
  - runtime.glibc.version
observations:
  - test-run-204
validation_scope:
  environment: qemu
  workload: smoke-workload
status: supported_in_emulation
physical_hardware_verified: false
revalidate_if:
  - cpu.isa.extensions
  - os.kernel.version
  - runtime.glibc.version
```

## 8. Agentic Workflows

Use **one orchestrator with specialized workflows** initially, rather than multiple unrestricted autonomous agents.

| Workflow | Input | Output | Authority |
|---|---|---|---|
| Discovery | Machine identity and manifest | Missing/conflicting facts | Read-only |
| Impact | Current and proposed states | Affected dependency subgraph | Read-only |
| Hypothesis | Rules, prior evidence, observed failures | Structured failure hypotheses | Advisory |
| Experiment planning | Hypotheses, candidate tests, policy budget | Ranked plan | Proposal only |
| Diagnosis | Experimental outcomes and controlled changes | Root-cause candidates | Advisory |
| Remediation | Verified constraints and build metadata | Candidate fix/PR | Requires approval |
| Evidence packaging | Test records and assumptions | Signed report | No deployment authority |

Agent outputs should be schema-validated and linked to source evidence. All shell execution occurs through allowlisted experiment tools in isolated environments.

## 9. Proposed Research Algorithm: ECAR

**ECAR — Evidence-Constrained Active Revalidation** is the provisional name of the research algorithm.

### Inputs

- Current environment graph `G_current`.
- Proposed environment graph `G_proposed`.
- Compatibility claims `C` and supporting evidence `E`.
- Candidate experiments `T`.
- Cost budget `B`, risk policy `P`, and mandatory test constraints `M`.

### Procedure

1. Compute a semantic difference between current and proposed environment revisions.
2. Traverse dependency and assumption edges to find potentially invalidated claims.
3. Mark unresolved claims and estimate their severity and uncertainty.
4. Generate candidate experiments that can distinguish competing hypotheses.
5. Select experiments to maximize expected information value under cost, mandatory coverage, and policy constraints.
6. Execute approved experiments in isolation; record observations and provenance.
7. Update claim support, refutation, or uncertainty; repeat until stopping criteria are met.
8. Export the decision and evidence without overstating what was verified.

### Initial scoring heuristic

```text
score(test) =
  expected_information_gain(test)
  × risk_severity(test)
  × claim_relevance(test)
  / (estimated_cost(test) + epsilon)
```

This heuristic is a starting point, not a proven optimal algorithm. Mandatory safety tests must not be skipped merely because their scores are low. Later versions can explore Bayesian experimental design, submodular selection, constrained optimization, and causal interventions.

### Research objective

Minimize the total cost of selected experiments **subject to** required evidence coverage, execution constraints, and an empirically evaluated upper bound on missed relevant failures. Guarantees can be claimed only under explicitly proven assumptions.

## 10. MVP Demonstration

**Scenario:** A proposed RISC-V application binary requires an instruction-set extension unavailable on the target machine.

1. Collect a versioned target manifest and binary metadata.
2. Submit the proposed application release to `vcm preflight`.
3. Detect the ISA mismatch using deterministic rules.
4. Record the failed compatibility claim and supporting evidence.
5. Have the agent propose a build that avoids the unsupported extension.
6. Select a minimal relevant test plan under a time budget.
7. Execute the candidate in QEMU and collect reproducible logs.
8. Validate on physical RISC-V hardware where accessible.
9. Change a relevant target property and demonstrate selective evidence invalidation.
10. Generate a signed, scoped preflight report with explicit unknowns.

The demonstration must label emulation-only results as such.

## 11. Proposed Technology Stack

| Layer | Technology | Notes |
|---|---|---|
| Core | Python 3.11+ | Reuse VCM code |
| API | FastAPI | Optional for initial CLI-first MVP |
| Orchestration | Custom state machine or LangGraph | Prefer explicit durable state and tool policies |
| Model inference | Amazon Bedrock or local model | Optional for deterministic baseline |
| Constraint evaluation | VCM rules; optional Z3 | Begin with simple auditable rules |
| Graph and offline records | Existing VCM graph layer and SQLite | Avoid premature database migration |
| Shared metadata | Appwrite TablesDB | Reuse existing system of record where appropriate |
| Experiment workers | QEMU on Linux; optional EC2 | Isolated, ephemeral execution |
| Physical validation | RISC-V development board / hardware CI | Required for hardware-specific claims |
| Artifacts | Local files initially; S3 later | Content-addressed logs and results |
| CI | GitHub Actions | PR checks and benchmark automation |
| Signing | Sigstore or KMS-backed signatures | Verify provenance and report integrity |
| UI | Existing VCM dashboard | Add evidence and experiment views |
| Agent integration | Existing VCM MCP server | Read-only first; privileged actions gated |

### Proposed CLI (not yet implemented)

```bash
vcm discover --target riscv-lab-001
vcm preflight --target riscv-lab-001 --release app-v2
vcm experiment plan --preflight latest --budget-minutes 30
vcm experiment run --plan latest --environment qemu
vcm evidence report --run latest
vcm remediate propose --run latest
```

## 12. Security, Safety, and Trust

- **No direct production write access** for AI agents.
- **Separate identities and permissions** for discovery, experiments, PR generation, and deployment.
- **Allowlisted tool execution**, argument validation, and human review for sensitive actions.
- **Sandbox isolation** with network restrictions, resource quotas, timeouts, and automatic cleanup.
- **Immutable or content-addressed experiment artifacts** with hashes and audit records.
- **Explicit uncertainty**: unsupported or untested conditions produce `UNKNOWN`/`REVIEW`, never inferred `PASS`.
- **Scope-aware evidence**: emulated results do not automatically transfer to physical hardware.
- **Budget guardrails** for cloud spend and model inference.
- **Adversarial testing** of prompts, manifests, experiment specifications, and tool outputs.

## 13. Research Plan and Evaluation

### Research questions

- **RQ1:** Does evidence-aware revalidation reduce experiment cost compared with full-suite testing?
- **RQ2:** Does it preserve detection of relevant incompatibilities compared with baseline selection strategies?
- **RQ3:** How much value comes from modeling hardware and firmware assumptions explicitly?
- **RQ4:** Does agent-guided experiment proposal improve outcomes over a deterministic planner?
- **RQ5:** How accurately can the system identify when evidence is transferable between emulated and physical environments?

### Baselines

1. Full test suite.
2. Random test selection under the same budget.
3. Dependency-based regression test selection.
4. A budget-matched predictive or ML-based test prioritization baseline.
5. ECAR without AI agent proposals.

### Benchmark design

- At least 100 controlled configuration-change scenarios as an initial target.
- Include ISA incompatibilities, ELF/ABI mismatches, library dependency conflicts, kernel interface changes, and selected firmware/driver changes.
- Use full-suite reference executions to determine observed failures where feasible.
- Run QEMU experiments and a physical RISC-V subset; later add ARM64 and x86.
- Publish test fixtures, manifests, selection decisions, scripts, and results.

### Metrics

| Metric | Definition |
|---|---|
| Failure-detection recall | Detected relevant failures / all observed relevant failures |
| Missed critical failures | Count of critical failures not detected by selected tests |
| Test cost | Wall-clock time, compute hours, and estimated spend |
| Revalidation latency | Time from change submission to evidence-backed decision |
| Evidence reuse | Tests safely avoided due to still-valid evidence |
| Invalidation accuracy | Correctly identified affected and unaffected claims |
| Root-cause quality | Accuracy on controlled, injected failure causes |
| Reproducibility | Stability of decisions and outputs for fixed inputs |

### Ablation studies

Remove evidence invalidation, hardware-aware dependencies, agentic planning, and uncertainty scoring individually. Compare each variant against the complete method to identify which components contribute measurable improvements.

### Proposed success criteria (not measured results)

- Aim for at least 30% lower test cost than full-suite execution on the benchmark.
- Maintain comparable failure-detection recall and report all misses.
- Correctly invalidate explicitly modeled evidence dependencies in controlled tests.
- Never perform an unauthorized production modification.
- Clearly distinguish physical validation from emulated validation.

## 14. Delivery Roadmap

| Phase | Weeks | Deliverables |
|---|---|---|
| 1. Foundation | 1–3 | Repo audit, RISC-V inventory schema, ELF/ISA checks, baseline fixtures |
| 2. Evidence core | 4–6 | Claim graph, assumption edges, invalidation and preflight reports |
| 3. Experimentation | 7–9 | QEMU runner, test catalog, deterministic cost-aware planner |
| 4. Agentic workflows | 10–12 | Structured hypotheses, experiment proposals, diagnosis, remediation suggestions |
| 5. Validation | 13–14 | Physical-device subset, signing, security review, approval gates |
| 6. Research release | 15–16 | Baseline comparison, benchmark, reproducibility package, v0.1 release |

**Planning assumption:** Roughly 12–16 weeks for a scoped research MVP with one or two contributors; timelines will depend on the existing codebase, access to hardware, and evaluation scope. A rigorous full paper may take additional months.

### First 10 working days

- [ ] Audit current VCM manifests, dependency graph, CLI, storage, MCP server, and tests.
- [ ] Define `MachineRevision`, `CompatibilityClaim`, `Experiment`, and `Evidence` schemas.
- [ ] Implement RISC-V machine metadata collection.
- [ ] Implement deterministic ELF and ISA checks.
- [ ] Build three reproducible incompatibility fixtures.
- [ ] Persist claim/evidence relationships.
- [ ] Implement conservative evidence invalidation.
- [ ] Create an isolated QEMU runner.
- [ ] Add a simple budget-aware test planner.
- [ ] Record and document the first end-to-end preflight demonstration.

## 15. Cost and Resource Planning

Use a **local-first** MVP to avoid unnecessary infrastructure expenses. A cloud-backed prototype may incur charges for EC2 experiment hours, storage, logs, model inference, networking, and data transfer. Exact prices depend on region, instance family, usage, and service configuration and should be checked before deployment.

Recommended controls:

- Stop or terminate experiment workers immediately after tests.
- Cap runtime, concurrent workers, model calls, and monthly spending.
- Keep a deterministic no-LLM path for baseline experiments.
- Reuse cached artifacts only when their scope and assumptions remain valid.
- Avoid always-on NAT gateways and oversized instances for the prototype.
- Budget separately for a physical RISC-V board and accessories.

## 16. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| LLM invents compatibility facts | Require machine evidence, structured outputs, deterministic verification |
| Incomplete dependency graph | Conservative invalidation and `UNKNOWN` decisions |
| QEMU diverges from real hardware | Explicit environment scope and physical-device subset |
| Tests miss a critical incompatibility | Mandatory coverage, full-suite benchmark comparisons, publish missed cases |
| Unsafe autonomous execution | Sandboxes, allowlists, least privilege, approvals |
| Excessive cost | Hard budgets, worker cleanup, quotas, alerts |
| Research novelty not established | Literature review, prior-art mapping, formal contribution, baselines |
| Project becomes too broad | Start with one RISC-V scenario and three incompatibility classes |

## 17. Research Publication Strategy

**Proposed paper title:** *EAGER: Evidence-Aware Agentic Revalidation for Heterogeneous Infrastructure*

**Potential contributions:**

1. A formal representation of compatibility claims, environmental assumptions, and evidence validity.
2. An evidence-constrained active revalidation algorithm.
3. A reproducible implementation on Kernelridge (built on VCM Machines) with QEMU and physical RISC-V validation.
4. A public benchmark and empirical comparison against regression test selection baselines.

**Potential venues:** Software engineering and testing venues such as ICSE, ASE, and ISSTA; dependable-systems venues such as DSN; and relevant workshops or tool-demonstration tracks. Submission deadlines, policies, and suitability must be checked against official calls for papers.

**Important:** Existing research covers regression test selection, configuration-aware testing, incremental assurance, active experiment design, and attestations. The paper must acknowledge prior art and demonstrate a distinct method or meaningful empirical finding. A proposal or architecture alone is unlikely to support a strong full research-paper claim.

### Paper outline

1. Introduction and motivating scenario.
2. Related work and precise research gap.
3. Compatibility evidence model and formal problem definition.
4. ECAR algorithm and policy constraints.
5. VCM implementation.
6. Benchmark and experimental setup.
7. Results, baselines, and ablation studies.
8. Threats to validity and limitations.
9. Conclusion and future work.

## 18. Definition of Done for v0.1

The first release is complete when a user can:

1. Collect or import a versioned RISC-V target manifest.
2. Submit a proposed native application release.
3. Receive deterministic compatibility findings with supporting evidence.
4. Generate and execute a bounded, isolated experiment plan.
5. Inspect experiment provenance and scoped outcomes.
6. Change a relevant dependency and see affected evidence flagged for revalidation.
7. Export an auditable report with explicit unknowns and approval requirements.

## 19. Long-Term Vision

Kernelridge can evolve into an **evidence-aware compatibility intelligence layer** for heterogeneous infrastructure. Potential extensions include ARM64/x86 support, AWS fleet integrations, causal experiment planning, cross-architecture evidence transfer, portable attestations, and continuously maintained compatibility knowledge across edge-device fleets.

The guiding principle is simple:

> **AI may decide what to investigate next, but compatibility claims must remain grounded in reproducible observations, explicit assumptions, and enforceable safety policies.**

---

**Status:** Project proposal; implementation, evaluation, and research novelty remain to be validated.  
**Immediate next step:** Audit the existing VCM Machines repository and map reusable modules to the proposed MVP.
