---
name: multi-agent-patterns
description: Implementation guide and templates for core multi-agent orchestration patterns (Supervisor, Router, Hierarchical, Pipeline). Standardized architecture for complex AI coordination.
risk: unknown
source: community
---
# Multi-Agent Orchestration Patterns

Framework for designing and implementing reliable multi-agent systems using Antigravity and Claude.

## Core Patterns

### 1. The Supervisor (Planning)
A lead agent manages a pool of workers, delegating tasks and reviewing output before finalizing.
- **Best for:** Complex tasks requiring multi-step reasoning.

### 2. The Router (Classification)
An entry-point agent classifies the request and directs it to the most qualified specialist.
- **Best for:** Systems with many distinct capabilities.

### 3. The Pipeline (Sequential)
Tasks are processed in a fixed sequence, where the output of one agent is the input for the next.
- **Best for:** Data processing, code generation -> audit -> test workflows.

### 4. Hierarchical (Modular)
Agents are organized in a nested tree structure. Supervisors manage sub-supervisors.
- **Best for:** Large enterprise-scale projects.

## Implementation Guide

### Defining Agent Roles
Each agent should have a specific `persona` and `toolset`.

```yaml
agents:
  - id: tech_lead
    role: Architect & Auditor
    instructions: "Oversee workers, ensure code standards..."
  - id: developer
    role: Implementation Specialist
    instructions: "Write clean, tested code based on specs..."
```

## Best Practices
- **Small Context Windows**: Keep worker prompts focused to reduce noise.
- **State Management**: Use a shared "Blackboard" or "State" object the supervisor can read.
- **Human-in-the-loop**: Include explicit triggers for human review at critical junctions.
