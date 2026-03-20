# Snowflake Skills for AI Coding Agents

Skills that teach AI coding agents how to work effectively with Snowflake and related tools — providing patterns, best practices, and code examples.

## Installation

Run in your project root:

```bash
# Install all skills (auto-detects your agent)
curl -sSL https://raw.githubusercontent.com/Snowflake-Labs/snowflake-ai-kit/main/snowflake-skills/install_skills.sh | bash

# Install specific skills
curl -sSL .../snowflake-skills/install_skills.sh | bash -s -- docker-dev-setup snowpipe-streaming-python

# Install for a specific agent
curl -sSL .../snowflake-skills/install_skills.sh | bash -s -- --agent cursor

# List available skills
curl -sSL .../snowflake-skills/install_skills.sh | bash -s -- --list
```

**Manual install:**
```bash
git clone https://github.com/Snowflake-Labs/snowflake-ai-kit.git
mkdir -p .cursor/rules
cp snowflake-ai-kit/snowflake-skills/docker-dev-setup/SKILL.md .cursor/rules/docker-dev-setup.mdc
```

## Available Skills

### 🔧 Development

- **[docker-dev-setup](docker-dev-setup/)** — Containerize apps with production-grade Dockerfiles, Docker Compose for local dev, and Dev Container configuration
- **[drizzle-orm-setup](drizzle-orm-setup/)** — Scaffold Drizzle ORM with TypeScript schema, relations, database client, and migrations
- **[supabase-auth-rls](supabase-auth-rls/)** — Scaffold Supabase with database schema, Row Level Security policies, and auth integration

### ❄️ Data Engineering

- **[snowpipe-streaming-java](snowpipe-streaming-java/)** — Stream data into Snowflake using the Java Snowpipe Streaming SDK with exactly-once delivery
- **[snowpipe-streaming-python](snowpipe-streaming-python/)** — Stream data into Snowflake using the Python Snowpipe Streaming SDK with parallel channels

### 🔄 Migration

- **[ssis-to-dbt-replatform-migration](ssis-to-dbt-replatform-migration/)** — Validate, deploy, and operationalize SnowConvert AI Replatform output — SSIS to dbt and Snowflake TASKs

## Skill Structure

Each skill is a self-contained directory:

```
<skill-name>/
├── SKILL.md          # Agent entry point — YAML metadata + instructions
├── README.md         # Human-facing docs (prerequisites, usage, examples)
├── references/       # Optional guides, schemas, or reference material
├── templates/        # Optional code templates the agent can scaffold
├── scripts/          # Optional helper scripts
└── src/              # Optional bundled source code
```

`SKILL.md` starts with YAML frontmatter for discovery:

```yaml
---
name: my-skill
description: "Brief description. Triggers: keyword1, keyword2."
---
```

The body contains step-by-step instructions, tool usage, and validation steps. Additional files are loaded on demand — only what's needed enters the agent's context window.

## How It Works

```
┌─────────────────────────────────────────────────────────┐
│  Your AI coding agent loads SKILL.md as a rule/skill    │
│                                                         │
│  SKILL.md defines:                                      │
│    • When to activate (triggers)                        │
│    • Step-by-step workflow                               │
│    • Code patterns and templates                        │
│    • Validation checks                                  │
│                                                         │
│  Agent follows the instructions → builds correctly      │
└─────────────────────────────────────────────────────────┘
```

**Example:** User says "Set up Docker for my Python app"
1. Agent loads `docker-dev-setup` skill
2. Reads Dockerfile patterns from `references/`
3. Scaffolds `Dockerfile`, `compose.yaml`, `.devcontainer/`
4. Validates the build works

## Custom Skills

Create your own using the [TEMPLATE](TEMPLATE/):

```bash
cp -r TEMPLATE/ my-new-skill/
# Edit my-new-skill/SKILL.md with your patterns
```

See [CONTRIBUTING.md](../CONTRIBUTING.md) for the full guide.

## Troubleshooting

**Skills not loading?** Make sure the file is in the correct directory for your agent:
- Cursor: `.cursor/rules/` (`.mdc` extension)
- Windsurf: `.windsurf/rules/` (`.md` extension)
- Claude Code: `.claude/rules/` (`.md` extension)
- Cortex Code: `~/.snowflake/cortex/skills.json` with remote source

**Install script fails?** Check write permissions or clone the repo and copy manually.
