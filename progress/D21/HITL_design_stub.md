# Human-In-The-Loop (HITL) Design Document (Stub)

## Overview
This document outlines the planned architecture for introducing Human-In-The-Loop capabilities into InsightSwarm. The goal is to allow human moderators to override, guide, and inject nuance into LLM-driven debates before final verdicts are stored or presented.

## Core Mechanics
1. **Interactive Checkpoints:** The debate graph will pause execution at critical decision nodes (e.g., after `fact_checker` but before `moderator`) to allow a human to review the presented evidence and flags.
2. **Override Controls:** A specialized UI panel where humans can edit the FactChecker's source ratings or manually re-route claims the system flagged as "uncertain."
3. **Auditable Trails:** Every human intervention will be logged alongside the debate state to distinguish synthetic reasoning from human bias in the historical record.

## Technical Requirements
- LangGraph state modifications to support `interrupt_before=["moderator"]`.
- WebSocket or specialized SSE channels to signal frontend "Awaiting User Input" states.
- Re-entry endpoints (`/resume`) in FastAPI to continue graph execution with the patched state.

*To be expanded in D22/D23 sprints.*
