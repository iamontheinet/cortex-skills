# Snowflake AI Kit

Skills and tools for AI coding agents working with Snowflake. Give your agent (Cortex Code, Cursor, Windsurf, Claude Code, etc.) the patterns and best practices it needs to build on Snowflake correctly.

---

## What Can I Build?

- **Docker Dev Environments** — Dockerfiles, Compose, Dev Containers for any stack
- **ORM Scaffolding** — Drizzle ORM with TypeScript schemas, migrations, and queries
- **Auth & Row-Level Security** — Supabase projects with RLS policies and auth integration
- **Streaming Pipelines** — Snowpipe Streaming in Java or Python with exactly-once delivery
- **ETL Migrations** — SSIS-to-dbt replatforming on Snowflake
- ...and more as the community contributes

---

## Pick Your Path

| Adventure | Best For | Start Here |
|-----------|----------|------------|
| **Install AI Kit** | Add all Snowflake skills to your AI agent | [Quick Start](#quick-start) |
| **Browse Skills** | Explore patterns and best practices | [`snowflake-skills/`](snowflake-skills/) |
| **Builder App** | Chat with Claude + Snowflake tools in one UI | [`snowflake-builder-app/`](snowflake-builder-app/) |
| **MCP Server** | Give your agent executable Snowflake tools | Coming soon |
| **Tools Library** | Use Snowflake helpers in your Python code | Coming soon |
| **Contribute** | Share your expertise with the community | [CONTRIBUTING.md](CONTRIBUTING.md) |

---

## Quick Start

### One-line install (Mac / Linux)

```bash
bash <(curl -sSL https://raw.githubusercontent.com/Snowflake-Labs/snowflake-ai-kit/main/snowflake-skills/install_skills.sh)
```

This auto-detects your agent (Cursor, Windsurf, Claude Code) and installs all skills.

<details>
<summary><strong>Advanced options</strong></summary>

```bash
# Install for a specific agent
bash <(curl -sSL .../snowflake-skills/install_skills.sh) --agent cursor

# Install specific skills only
bash <(curl -sSL .../snowflake-skills/install_skills.sh) docker-dev-setup drizzle-orm-setup

# List available skills
bash <(curl -sSL .../snowflake-skills/install_skills.sh) --list
```

</details>

### Manual install

Clone the repo and copy skills into your agent's rules directory:

```bash
git clone https://github.com/Snowflake-Labs/snowflake-ai-kit.git
```

#### Cursor

```bash
cp snowflake-ai-kit/snowflake-skills/docker-dev-setup/SKILL.md .cursor/rules/docker-dev-setup.mdc
```

#### Windsurf

```bash
cp snowflake-ai-kit/snowflake-skills/docker-dev-setup/SKILL.md .windsurf/rules/docker-dev-setup.md
```

#### Claude Code

```bash
cp snowflake-ai-kit/snowflake-skills/docker-dev-setup/SKILL.md .claude/rules/docker-dev-setup.md
```

#### Other Agents (Cline, Aider, etc.)

Point the agent at the `SKILL.md` file directly, or paste its contents into the agent's system prompt.

#### Cortex Code

Add to `~/.snowflake/cortex/skills.json`:

```json
{
  "remote": [
    {
      "source": "https://github.com/Snowflake-Labs/snowflake-ai-kit",
      "ref": "main",
      "skills": [
        { "name": "docker-dev-setup" },
        { "name": "drizzle-orm-setup" },
        { "name": "supabase-auth-rls" }
      ]
    }
  ]
}
```

---

## What's Included

| Component | Description | Status |
|-----------|-------------|--------|
| [`snowflake-skills/`](snowflake-skills/) | Snowflake-specific skills (Snowpipe Streaming, ETL migration) | 3 skills |
| [`general-skills/`](general-skills/) | General-purpose skills (Docker, Drizzle ORM, Supabase) | 3 skills |
| [`snowflake-builder-app/`](snowflake-builder-app/) | Claude Code agent UI with Snowflake MCP tools | Beta |
| `snowflake-mcp/` | Standalone MCP server for Snowflake operations | Planned |
| `snowflake-tools/` | Python library for common Snowflake tasks | Planned |

---

## Contributing

Want to add a skill? See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines, or use the [TEMPLATE](snowflake-skills/TEMPLATE/) to get started.

## License

Apache License 2.0. See [LICENSE](LICENSE) for details.
