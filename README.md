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

| Component | Description |
|-----------|-------------|
| [`snowflake-skills/`](snowflake-skills/) | Markdown skills teaching Snowflake and development patterns |

---

## Skills

<!-- BEGIN_SKILLS_TABLE -->
| Skill | What it does |
|-------|-------------|
| [docker-dev-setup](snowflake-skills/docker-dev-setup/) | Containerize an application with a production-grade Dockerfile, Docker Compose for local development, and optional Dev Container configuration |
| [drizzle-orm-setup](snowflake-skills/drizzle-orm-setup/) | Scaffold a Drizzle ORM project with TypeScript schema, relations, database client, and migrations |
| [snowpipe-streaming-java](snowflake-skills/snowpipe-streaming-java/) | Stream data into Snowflake using the Java Snowpipe Streaming SDK |
| [snowpipe-streaming-python](snowflake-skills/snowpipe-streaming-python/) | Stream data into Snowflake using the Python Snowpipe Streaming SDK |
| [ssis-to-dbt-replatform-migration](snowflake-skills/ssis-to-dbt-replatform-migration/) | Validates, deploys, and operationalizes SnowConvert AI (SCAI) Replatform output — SSIS to dbt and Snowflake TASKs migrations |
| [supabase-auth-rls](snowflake-skills/supabase-auth-rls/) | Scaffold a Supabase project with database schema, Row Level Security policies, and auth integration |
<!-- END_SKILLS_TABLE -->

See [`snowflake-skills/`](snowflake-skills/) for detailed descriptions, categories, and installation options.

---

## Star History

<a href="https://star-history.com/#Snowflake-Labs/snowflake-ai-kit&Date">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=Snowflake-Labs/snowflake-ai-kit&type=Date&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=Snowflake-Labs/snowflake-ai-kit&type=Date" />
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=Snowflake-Labs/snowflake-ai-kit&type=Date" />
 </picture>
</a>

---

## Contributing

Want to add a skill? See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines, or use the [TEMPLATE](snowflake-skills/TEMPLATE/) to get started.

## License

Apache License 2.0. See [LICENSE](LICENSE) for details.
