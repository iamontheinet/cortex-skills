# drizzle-orm-setup

Agent skill for scaffolding a [Drizzle ORM](https://orm.drizzle.team/) project with TypeScript schema, relations, database client, and migration tooling.

## What It Does

1. Detects your project setup (existing deps, database dialect, TypeScript config)
2. Creates typed table schemas using `pgTable()`, `mysqlTable()`, or `sqliteTable()`
3. Defines relations for the relational query API
4. Sets up the database client with schema-aware `drizzle()` instance
5. Configures `drizzle-kit` for migration generation and execution
6. Runs the initial migration or schema push

## Supported Databases

| Database | Driver | Import |
|----------|--------|--------|
| PostgreSQL | `pg` | `drizzle-orm/pg-core` |
| PostgreSQL (Neon) | `@neondatabase/serverless` | `drizzle-orm/neon-serverless` |
| MySQL | `mysql2` | `drizzle-orm/mysql-core` |
| MySQL (PlanetScale) | `@planetscale/database` | `drizzle-orm/planetscale-serverless` |
| SQLite | `better-sqlite3` | `drizzle-orm/sqlite-core` |
| SQLite (Turso) | `@libsql/client` | `drizzle-orm/libsql` |
| SQLite (Cloudflare D1) | `@cloudflare/workers-types` | `drizzle-orm/d1` |

## Prerequisites

- Node.js 18+
- TypeScript project with `tsconfig.json`
- A database to connect to (local or hosted)

## File Structure

```
drizzle-orm-setup/
├── SKILL.md                          # Agent instructions (guided workflow)
├── README.md                         # This file
├── references/
│   ├── schema-patterns.md            # Table defs, columns, enums, indexes, relations
│   ├── query-patterns.md             # Core API + relational API patterns
│   └── troubleshooting.md            # Common errors and fixes
└── templates/
    ├── schema.ts                     # Multi-table starter schema
    ├── drizzle.config.ts             # drizzle-kit configuration
    └── db.ts                         # Database client setup
```

## Quick Reference

```typescript
// Define a table (PostgreSQL)
import { pgTable, varchar, integer, timestamp } from 'drizzle-orm/pg-core';

export const users = pgTable('users', {
  id: integer('id').primaryKey().generatedAlwaysAsIdentity(),
  email: varchar('email', { length: 320 }).notNull().unique(),
  name: varchar('name', { length: 100 }).notNull(),
  createdAt: timestamp('created_at').defaultNow().notNull(),
});

// Define relations (separate from schema)
import { relations } from 'drizzle-orm';

export const usersRelations = relations(users, ({ many }) => ({
  posts: many(posts),
}));

// Query with the relational API
const result = await db.query.users.findMany({
  with: { posts: true },
});

// Query with the core SQL-like API
import { eq } from 'drizzle-orm';

const admins = await db.select().from(users).where(eq(users.role, 'admin'));
```

## Key Commands

```bash
npx drizzle-kit generate    # Generate SQL migration from schema changes
npx drizzle-kit migrate     # Apply pending migrations
npx drizzle-kit push        # Push schema directly (dev only)
npx drizzle-kit studio      # Open visual database browser
npx drizzle-kit introspect  # Generate schema from existing database
```
