# Cortex Skills

A collection of [Cortex Code](https://docs.snowflake.com/en/user-guide/cortex-code/cortex-code) skills for Snowflake migrations, data engineering, and operations.

## Skills

| Skill | Description |
|-------|-------------|
| [ssis-to-dbt-replatform-migration](ssis-to-dbt-replatform-migration/) | Validates, deploys, and operationalizes SnowConvert AI Replatform output — SSIS packages converted to dbt projects and Snowflake TASKs |
| [snowpipe-streaming-python](snowpipe-streaming-python/) | Stream data into Snowflake using the Python Snowpipe Streaming SDK — RSA auth setup, single and parallel streaming, staging vs production, reconciliation |
| [snowpipe-streaming-java](snowpipe-streaming-java/) | Stream data into Snowflake using the Java Snowpipe Streaming SDK — RSA auth setup, Maven build, single and parallel streaming, JVM Arrow flags |

## Installation

### Option 1: Remote (auto-synced)

Add this repo to your Cortex Code skills config at `~/.snowflake/cortex/skills.json`:

```json
{
  "remote": [
    {
      "source": "https://github.com/iamontheinet/cortex-skills",
      "ref": "main",
      "skills": [
        { "name": "ssis-to-dbt-replatform-migration" },
        { "name": "snowpipe-streaming-python" },
        { "name": "snowpipe-streaming-java" }
      ]
    }
  ]
}
```

Skills are cached locally and updated on next Cortex Code session.

### Option 2: Manual (local copy)

```bash
git clone https://github.com/iamontheinet/cortex-skills.git /tmp/cortex-skills

# Install one or more skills
cp -r /tmp/cortex-skills/ssis-to-dbt-replatform-migration \
  ~/.snowflake/cortex/skills/ssis-to-dbt-replatform-migration

cp -r /tmp/cortex-skills/snowpipe-streaming-python \
  ~/.snowflake/cortex/skills/snowpipe-streaming-python

cp -r /tmp/cortex-skills/snowpipe-streaming-java \
  ~/.snowflake/cortex/skills/snowpipe-streaming-java
```

### Verify

In a Cortex Code session, run `/skill` to open the skill manager — skills should appear under **Global** or **Remote** skills. You can also invoke them directly:

```
$ssis-to-dbt-replatform-migration
$snowpipe-streaming-python
$snowpipe-streaming-java
```

## Prerequisites

Each skill has its own requirements documented in its `SKILL.md`. Common prerequisites:

- **Cortex Code** CLI installed and configured
- **Snowflake account** with appropriate permissions
- **RSA key-pair auth** (for streaming skills) — the skills will guide you through setup