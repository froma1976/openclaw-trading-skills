---
name: agent-memory-mcp
description: "Model Context Protocol (MCP) server that provides AI agents with persistent multi-level memory capabilities (Episodic, Semantic, Procedural). Enables agents to remember facts, past experiences, and procedural knowledge across sessions."
risk: low
source: community
---
# Agent Memory MCP Server

This MCP server implements a high-performance memory system for AI agents, allowing them to store and retrieve long-term context beyond the current session.

## Core Memory Types

1.  **Episodic Memory**: Fast storage of specific events, conversations, and interactions.
2.  **Semantic Memory**: Learning and recalling general facts, concepts, and relationships.
3.  **Procedural Memory**: Storing "how-to" knowledge and successful patterns for completing tasks.

## Setup

### 1. Prerequisites
- [Node.js](https://nodejs.org/) v18+
- Git

### 2. Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/webzler/agentMemory.git
cd agentMemory
npm install
npm run build
```

### 3. MCP Configuration

Add the server to your Antigravity or Claude Desktop configuration:

```json
{
  "mcpServers": {
    "agent-memory": {
      "command": "node",
      "args": ["C:/path/to/agentMemory/build/index.js"]
    }
  }
}
```

## Tools Provided

- `store_episodic`: Save a new experience or event.
- `retrieve_episodic`: Search for past experiences using semantic similarity.
- `store_semantic`: Record a factual piece of information.
- `query_semantic`: Search the knowledge base for specific facts.
- `store_procedure`: Save a successful workflow or logic pattern.
- `get_procedure`: Retrieve instructions for a specific task type.

## Best Practices

- **Explicit Tagging**: Use descriptive tags when storing memory to improve retrieval accuracy.
- **Deduplication**: The server automatically handles some deduplication, but providing clean, unique summaries is better.
- **Context Consolidation**: Periodically review stored memories to consolidate overlapping facts.

## When to Use

Use this skill whenever an agent needs to maintain continuity across multiple tasks or remember user preferences, project details, and previous debugging outcomes that aren't present in the current file context.
