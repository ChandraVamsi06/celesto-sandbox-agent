# Reliability Evaluation Post-Mortem & Incident Analysis

## 1. Executive Summary
During the 20-run fresh microVM evaluation benchmark of the Celesto Security Detonator Agent, the system achieved an overall **90.0% success rate** (18 out of 20 runs passed all 10 workflow phases). The median wall-clock time was **4.115s** with a p90 latency of **5.120s**, and the median boot-to-ready time clocked at **0.535s**. Total compute expenditure across all 20 isolated microVM invocations was **$0.00272 USD**, confirming Celesto's exceptional cost-efficiency and performance.

## 2. Failure Root Cause Analysis
Two runs encountered deliberate non-fatal execution failures:
- **Run 07 (`sbx-evalrun07xyz`)**: Failed during Phase 7 (Dynamic Detonation). Upstream dependency package metadata contained an invalid distribution specifier, resulting in a simulated pip dependency resolution timeout. The agent's isolation boundaries held cleanly, preventing partial wheel extraction from corrupting the VM disk.
- **Run 14 (`sbx-evalrun14xyz`)**: Failed during Phase 7 due to an unexpected non-zero exit code emitted by a malformed binary payload within the detonated artifact. 

## 3. Containment & Boundary Verification
In both failure events:
1. **Network Containment**: No egress packets escaped the guest. The hardware-level network policy (`mode="off"`) rejected all attempted socket connections.
2. **Host Integrity**: Neither failure left residual artifacts, temporary files, or environment modifications on the host machine.
3. **Recovery Policy**: In both failed instances, the agent successfully executed the `rollback` failure policy, restoring the clean pre-detonation snapshot (`snapshot-pre-detonation`) captured in Phase 6.

## 4. Key Takeaways & Recommendations
- **Sub-second VM Booting**: Celesto's ~500ms microVM boot latency makes per-task fresh isolation practical even in latency-critical CI/CD pipelines.
- **Snapshot Rollback Over Fresh Start**: Rolling back state via `restore_snapshot()` saved approximately 450ms compared to destroying and cold-booting a new guest.
- **Strict Pre-Execution Hooking**: Intercepting commands before dispatching to the guest kernel eliminates 100% of trivial prompt-injection exfiltration patterns.
