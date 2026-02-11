# Agent Instructions
Engineer an Agentic AI System-an autonomous First Responder capable of diagnosing complex system failures in real-time. 
This system must demonstrate sophisticated Multi-Agent Reasoning, moving beyond simple automation into the realm of independent investigation and decision-making.

## Agent Roles
1. **Commander Agent**: The Orchestrator. Evaluates initial alerts, develops an investigation plan, and coordinates the specialized investigators.
2. **Logs Agent**: The Forensic Expert. Deep-scans distributed application logs to find specific stack traces and error correlations.
3. **Metrics Agent**: The Telemetry Analyst. Monitors performance counters (CPU, p99 Latency, Memory Leak patterns) to spot anomalies.
4. **Deploy Intelligence**: The Historian. Maps real-time errors against the timeline of CI/CD deployments and services configuration changes.

## Resoning Loop
Detect --> Plan --> Investigate --> Decide --> Act --> Report

## Roadmap
1. Architecture: Establish Agent communication protocols & State Management. Design Reasoning Graph flow(Nodes & Transitions). Prepare Mock Data Infrastructure(Logs/Metrics JSON).
2. Foundation: Build Commander Logic & Tool-use integration. Develop Mock Retrieval APIs for sub-agents. Implementation detection trigger based on simulated failure.
3. The Intelligence: Enable specialized tools for Log parsing & Metric analysis. Bridge data correlations(e.g. Linking Log errors to Metric spikes). Refine autonomous decision-making and fallback logic.
4. Deliverables: Generate Automated RCA Markdown Artifact. Finalize Visualization of Agent “Chain of Thought”. Ready the demo: “From Detection to Resolution”. Deploy it on AWS

## Final Demo Scenario
1. Objective: Prove the agent can solve a “Latent Configuration Bug”.
2.  Trigger: Checkout Service latency spikes to 2000ms.
3. Investigation: Agents find DB Connection timeouts correlated with a configuration deployment that happened 15minutes prior.
4. Outcome: System outputs a full investigation report and recommends an immediate rollback.

