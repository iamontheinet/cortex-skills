# Snowpipe Streaming — Java

A [Cortex Code](https://docs.snowflake.com/en/user-guide/cortex-code/cortex-code) skill that streams data into Snowflake using the **Java Snowpipe Streaming SDK**.

## Background

**Snowpipe Streaming** lets you load data into Snowflake tables with sub-second latency — no staging files, no COPY INTO, no pipes. The Java SDK (`snowflake-ingest-sdk`) opens one or more **channels** against a table and inserts rows directly via the `insertRow()` API.

This skill walks you through the entire setup end-to-end: RSA key-pair auth, Maven project setup, Snowflake object creation, SDK configuration, streaming code, and data verification. It requires Java 21+ and handles the `--add-opens` JVM flags needed for Arrow memory access.

## What It Does (8 Steps)

| Step | Description | Snowflake Access |
|------|-------------|------------------|
| **Phase 0** | Briefing — explains what will happen, asks for approval | None |
| **1. Environment** | Creates Maven project with `snowflake-ingest-sdk` dependency, configures shade plugin | None |
| **2. RSA Auth** | Generates PKCS8 key pair, registers public key with Snowflake user | Writes (ALTER USER) |
| **3. Profile** | Creates `profile.json` and `config.properties` with connection details | None (local files) |
| **4. Java Source** | Generates Java source files — streaming manager, data generator, models, config loader | None (local files) |
| **5. Snowflake Objects** | Creates database, schema, tables (ORDERS, ORDER_ITEMS) | Writes to Snowflake |
| **6. Build & Stream** | Builds uber-JAR with Maven, runs single-instance streaming | Writes to Snowflake |
| **7. Verify** | Queries row counts, checks order-to-item ratio | Reads Snowflake |
| **8. Parallel** | (Optional) Multi-channel parallel streaming for higher throughput | Writes to Snowflake |

Every step requires explicit user approval before proceeding. All SQL and commands are shown for review before execution.

## What It Will NOT Do

- Drop or alter any existing objects not created by this workflow
- Store credentials in plain text — uses RSA key-pair auth exclusively
- Run anything without showing you the exact command/SQL first
- Continue past any step without your explicit approval

## Prerequisites

- **Java 21+** (JDK, not just JRE)
- **Maven 3.8+**
- **Snowflake account** with a role that can create databases and ALTER USER
- **Cortex Code** CLI installed and configured

## Installation

### Option 1: Remote (auto-synced)

Add to `~/.snowflake/cortex/skills.json`:

```json
{
  "remote": [
    {
      "source": "https://github.com/Snowflake-Labs/agent-skills",
      "ref": "main",
      "skills": [{ "name": "snowpipe-streaming-java" }]
    }
  ]
}
```

### Option 2: Manual

```bash
git clone https://github.com/Snowflake-Labs/agent-skills.git agent-skills
cp -r agent-skills/snowpipe-streaming-java \
  ~/.snowflake/cortex/skills/snowpipe-streaming-java
```

### Verify

Run `/skill` in Cortex Code to confirm it appears, or invoke directly with `$snowpipe-streaming-java`.

## Usage

This skill is invoked automatically by Cortex Code when you mention Java streaming, Snowpipe Java, or streaming data with Java. You can also invoke it directly:

```
$snowpipe-streaming-java
```

## Project Structure

```
snowpipe-streaming-java/
  SKILL.md                        # Skill definition (loaded by Cortex Code)
  java/
    pom.xml                       # Maven build with shade plugin (uber-JAR)
    .mvn/jvm.config               # --add-opens flags for Arrow memory access
    profile.template.json         # Connection profile template
    config.template.properties    # SDK configuration template
    src/main/java/com/snowflake/demo/
      StreamingApp.java           # Single-instance streaming entry point
      ParallelStreamingOrchestrator.java  # Multi-channel parallel streaming
      SnowpipeStreamingManager.java       # SDK client/channel management
      DataGenerator.java          # Synthetic order data generation
      ConfigManager.java          # Profile and config loading
      Order.java                  # Order model
      OrderItem.java              # OrderItem model
```
