# Snowpipe Streaming — Python

A [Cortex Code](https://docs.snowflake.com/en/user-guide/cortex-code/cortex-code) skill that streams data into Snowflake using the **Python Snowpipe Streaming SDK**.

## Background

**Snowpipe Streaming** lets you load data into Snowflake tables with sub-second latency — no staging files, no COPY INTO, no pipes. The Python SDK (backed by Snowflake's Rust engine `cyclone_shared`) opens one or more **channels** against a table and inserts rows directly via the `insert_rows()` API.

This skill walks you through the entire setup end-to-end: RSA key-pair auth, Snowflake object creation, SDK configuration, streaming code, and data verification.

## What It Does (7 Steps)

| Step | Description | Snowflake Access |
|------|-------------|------------------|
| **Phase 0** | Briefing — explains what will happen, asks for approval | None |
| **1. Environment** | Creates project directory, virtual environment, installs `snowflake-connector-python` and `snowflake-ingest` | None |
| **2. RSA Auth** | Generates PKCS8 key pair, registers public key with Snowflake user | Writes (ALTER USER) |
| **3. Profile** | Creates `profile.json` and `config.properties` with connection details | None (local files) |
| **4. Snowflake Objects** | Creates database, schema, tables (ORDERS, ORDER_ITEMS) | Writes to Snowflake |
| **5. Stream** | Runs single-instance streaming — generates orders and inserts via SDK | Writes to Snowflake |
| **6. Verify** | Queries row counts, checks order-to-item ratio | Reads Snowflake |
| **7. Parallel** | (Optional) Multi-channel parallel streaming for higher throughput | Writes to Snowflake |

Every step requires explicit user approval before proceeding. All SQL and commands are shown for review before execution.

## What It Will NOT Do

- Drop or alter any existing objects not created by this workflow
- Store credentials in plain text — uses RSA key-pair auth exclusively
- Run anything without showing you the exact command/SQL first
- Continue past any step without your explicit approval

## Prerequisites

- **Python 3.9+**
- **Snowflake account** with a role that can create databases and ALTER USER
- **Cortex Code** CLI installed and configured

## Installation

### Option 1: Remote (auto-synced)

Add to `~/.snowflake/cortex/skills.json`:

```json
{
  "remote": [
    {
      "source": "https://github.com/Snowflake-Labs/snowflake-ai-kit",
      "ref": "main",
      "skills": [{ "name": "snowpipe-streaming-python" }]
    }
  ]
}
```

### Option 2: Manual

```bash
git clone https://github.com/Snowflake-Labs/snowflake-ai-kit.git snowflake-ai-kit
cp -r snowflake-ai-kit/snowflake-skills/snowpipe-streaming-python \
  ~/.snowflake/cortex/skills/snowpipe-streaming-python
```

### Verify

Run `/skill` in Cortex Code to confirm it appears, or invoke directly with `$snowpipe-streaming-python`.

## Usage

This skill is invoked automatically by Cortex Code when you mention Python streaming, Snowpipe Python, or streaming data with Python. You can also invoke it directly:

```
$snowpipe-streaming-python
```

## Project Structure

```
snowpipe-streaming-python/
  SKILL.md                        # Skill definition (loaded by Cortex Code)
  requirements.txt                # Python dependencies
  setup.sh                        # Environment setup script
  profile.template.json           # Connection profile template
  config.template.properties      # SDK configuration template
  src/
    streaming_app.py              # Single-instance streaming entry point
    parallel_streaming_orchestrator.py  # Multi-channel parallel streaming
    snowpipe_streaming_manager.py # SDK client/channel management
    data_generator.py             # Synthetic order data generation
    config_manager.py             # Profile and config loading
    reconciliation_manager.py     # Row count verification
    models.py                     # Order and OrderItem data classes
```
