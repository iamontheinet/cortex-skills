# Agent Skills

Community-contributed skills for AI coding agents. Each skill teaches an agent how to handle a specific task — streaming data, migrating pipelines, deploying infrastructure, and more.

## Skills

<!-- BEGIN_SKILLS_TABLE -->
| Skill | What it does |
|-------|-------------|
| [docker-dev-setup](docker-dev-setup/) | Containerize an application with a production-grade Dockerfile, Docker Compose for local development, and optional Dev Container configuration |
| [drizzle-orm-setup](drizzle-orm-setup/) | Scaffold a Drizzle ORM project with TypeScript schema, relations, database client, and migrations |
| [supabase-auth-rls](supabase-auth-rls/) | Scaffold a Supabase project with database schema, Row Level Security policies, and auth integration |
| [snowpipe-streaming-java](snowpipe-streaming-java/) | Stream data into Snowflake using the Java Snowpipe Streaming SDK |
| [snowpipe-streaming-python](snowpipe-streaming-python/) | Stream data into Snowflake using the Python Snowpipe Streaming SDK |
| [ssis-to-dbt-replatform-migration](ssis-to-dbt-replatform-migration/) | Validates, deploys, and operationalizes SnowConvert AI (SCAI) Replatform output — SSIS to dbt and Snowflake TASKs migrations |
<!-- END_SKILLS_TABLE -->

## Skill Structure

Each skill is a self-contained directory:

```
<skill-name>/
├── SKILL.md          # Agent entry point — YAML metadata + instructions
├── README.md         # Human-facing docs (prerequisites, usage, examples)
├── scripts/          # Optional helper scripts the agent can execute
├── references/       # Optional guides, schemas, or reference material
└── src/              # Optional bundled source code
```

`SKILL.md` is what the agent reads. It starts with YAML frontmatter for discovery:

```yaml
---
name: my-skill
description: "Brief description. Triggers: keyword1, keyword2."
---
```

The body contains step-by-step instructions, tool usage, and validation steps. Additional files (scripts, references, templates) are loaded on demand — only what's needed enters the agent's context.

## Getting Started

Clone the repo and copy any skill into your project or agent's skill directory:

```bash
git clone https://github.com/Snowflake-Labs/snowflake-ai-kit.git

# Copy a skill into your project
cp -r snowflake-ai-kit/docker-dev-setup ./my-project/.agent-skills/docker-dev-setup
```

These skills are **agent-agnostic** — they work with any AI coding agent that can read files. Each skill is just markdown + code templates, no proprietary format.

### Cursor

Add a skill's `SKILL.md` as a [project rule](https://docs.cursor.com/context/rules) (`.mdc` format):

```bash
cp snowflake-ai-kit/docker-dev-setup/SKILL.md .cursor/rules/docker-dev-setup.mdc
```

### Windsurf

Add to Windsurf's [rules directory](https://docs.windsurf.com/windsurf/cascade/memories):

```bash
cp snowflake-ai-kit/docker-dev-setup/SKILL.md .windsurf/rules/docker-dev-setup.md
```

### Claude Code

Add as a [project rule](https://code.claude.com/docs/en/memory):

```bash
cp snowflake-ai-kit/docker-dev-setup/SKILL.md .claude/rules/docker-dev-setup.md
```

### Other Agents (Cline, Aider, etc.)

Point the agent at the `SKILL.md` file directly, or paste its contents into the agent's system prompt / context window. The `references/` and `templates/` directories provide additional material the agent can load as needed.

### Cortex Code

Add skills to `~/.snowflake/cortex/skills.json` for auto-sync:

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

Run `/skill` in a session to confirm installation, or invoke directly with `$docker-dev-setup`.

## Prerequisites

Each skill documents its own requirements in `SKILL.md`. An AI coding agent that supports skills is all you need to get started.

## Contributing

Want to add a skill? Each skill is a self-contained directory with a `SKILL.md` that defines triggers, instructions, and validation steps. See any existing skill for the pattern. PRs welcome.
