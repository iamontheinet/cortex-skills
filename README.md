# Agent Skills

Community-contributed skills for AI coding agents. Each skill teaches an agent how to handle a specific task — streaming data, migrating pipelines, deploying infrastructure, and more.

## Skills

<!-- BEGIN_SKILLS_TABLE -->
| Skill | What it does |
|-------|-------------|
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

### Install via remote sync (recommended)

Add skills to `~/.snowflake/cortex/skills.json`:

```json
{
  "remote": [
    {
      "source": "https://github.com/Snowflake-Labs/agent-skills",
      "ref": "main",
      "skills": [{ "name": "<skill-name>" }]
    }
  ]
}
```

Skills auto-sync at session start.

### Install manually

```bash
git clone https://github.com/Snowflake-Labs/agent-skills.git
cp -r agent-skills/<skill-name> ~/.snowflake/cortex/skills/<skill-name>
```

### Verify

Run `/skill` in a session — installed skills appear under **Global** or **Remote**. Or invoke directly:

```
$<skill-name>
```

## Prerequisites

Each skill documents its own requirements in `SKILL.md`. An AI coding agent that supports skills is all you need to get started.

## Contributing

Want to add a skill? Each skill is a self-contained directory with a `SKILL.md` that defines triggers, instructions, and validation steps. See any existing skill for the pattern. PRs welcome.
