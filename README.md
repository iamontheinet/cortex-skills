# Cortex Skills

A collection of [Cortex Code](https://docs.snowflake.com/en/user-guide/cortex-code/cortex-code) skills for Snowflake migrations, data engineering, and operations.

## Skills

| Skill | Description |
|-------|-------------|
| [ssis-to-dbt-replatform-migration](ssis-to-dbt-replatform-migration/) | Validate, deploy, and operationalize SnowConvert AI Replatform output — SSIS to dbt + Snowflake TASKs |
| [snowpipe-streaming-python](snowpipe-streaming-python/) | Stream data into Snowflake using the Python Snowpipe Streaming SDK |
| [snowpipe-streaming-java](snowpipe-streaming-java/) | Stream data into Snowflake using the Java Snowpipe Streaming SDK |

## Installation

### Option 1: Remote (auto-synced)

Add this repo to your Cortex Code skills config at `~/.snowflake/cortex/skills.json`, listing the skills you want:

```json
{
  "remote": [
    {
      "source": "https://github.com/iamontheinet/cortex-skills",
      "ref": "main",
      "skills": [{ "name": "<skill-name>" }]
    }
  ]
}
```

Skills are cached locally and updated on next Cortex Code session.

### Option 2: Manual (local copy)

```bash
git clone https://github.com/iamontheinet/cortex-skills.git /tmp/cortex-skills

# Copy the skill(s) you need
cp -r /tmp/cortex-skills/<skill-name> ~/.snowflake/cortex/skills/<skill-name>
```

### Verify

In a Cortex Code session, run `/skill` to open the skill manager — installed skills should appear under **Global** or **Remote** skills. You can also invoke a skill directly:

```
$<skill-name>
```

## Prerequisites

Each skill has its own requirements documented in its `SKILL.md`. Common prerequisites:

- **Cortex Code** CLI installed and configured
- **Snowflake account** with appropriate permissions