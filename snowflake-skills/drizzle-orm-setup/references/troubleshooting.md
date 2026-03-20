# Troubleshooting

Common Drizzle ORM errors, their causes, and fixes.

## TypeScript Errors

### Type instantiation is excessively deep and possibly infinite

**Cause:** Too many tables or relations defined in a single file, causing TypeScript to hit the type instantiation limit (~59,000 instantiations).

**Fix:**
1. Split schema into multiple files (one per table or domain area)
2. Use `satisfies` on table definitions to help TS narrow types earlier:
   ```typescript
   export const users = pgTable('users', { ... }) satisfies PgTableWithColumns<any>;
   ```
3. If using the relational query API, ensure `drizzle()` receives `{ schema }` with a barrel export, not a dynamically constructed object
4. Check `tsconfig.json` — set `"strict": true` and `"moduleResolution": "bundler"` (or `"nodenext"`)
5. As a last resort, add `// @ts-expect-error` on the specific relation causing issues and file a Drizzle GitHub issue

### Property 'X' does not exist on type

**Cause:** Column name mismatch between schema and query, or schema not imported correctly.

**Fix:**
- Check that the column name in the query matches the TypeScript property name (first arg to the column function), NOT the database column name
- For `pgTable('users', { firstName: varchar('first_name') })`, use `users.firstName` in queries (not `users.first_name`)

### Cannot find module 'drizzle-orm/...'

**Cause:** Wrong dialect import path.

**Fix:** Use the correct import path for your dialect:
| Dialect | Schema imports | Client import |
|---------|---------------|---------------|
| PostgreSQL | `drizzle-orm/pg-core` | `drizzle-orm/node-postgres` |
| MySQL | `drizzle-orm/mysql-core` | `drizzle-orm/mysql2` |
| SQLite | `drizzle-orm/sqlite-core` | `drizzle-orm/better-sqlite3` |
| Neon | `drizzle-orm/pg-core` | `drizzle-orm/neon-serverless` |
| Turso | `drizzle-orm/sqlite-core` | `drizzle-orm/libsql` |
| PlanetScale | `drizzle-orm/mysql-core` | `drizzle-orm/planetscale-serverless` |
| D1 | `drizzle-orm/sqlite-core` | `drizzle-orm/d1` |

## Relation Errors

### Error: relation "X" not found / Relation not defined

**Cause:** Relation defined on one side but not the other, or `{ schema }` not passed to `drizzle()`.

**Fix:**
1. Define BOTH sides of every relation:
   ```typescript
   // BOTH are required
   export const usersRelations = relations(users, ({ many }) => ({
     posts: many(posts),
   }));

   export const postsRelations = relations(posts, ({ one }) => ({
     author: one(users, {
       fields: [posts.authorId],
       references: [users.id],
     }),
   }));
   ```
2. Pass `{ schema }` to drizzle:
   ```typescript
   import * as schema from './schema';
   const db = drizzle(client, { schema });
   ```
3. Ensure the barrel export (`schema/index.ts`) re-exports ALL tables AND relations

### Circular import errors

**Cause:** Two schema files importing from each other (e.g., `users.ts` imports `posts` for a relation, and `posts.ts` imports `users`).

**Fix:**
- Put tables in one file and all relations in a separate `relations.ts` file
- Or use a barrel export pattern where each file only defines its own table, and `relations.ts` imports all tables:
  ```
  schema/
  ├── tables/
  │   ├── users.ts     # only defines users table
  │   └── posts.ts     # only defines posts table
  ├── relations.ts     # imports all tables, defines all relations
  └── index.ts         # re-exports everything
  ```

## Migration Errors

### drizzle-kit generate produces no output

**Cause:** Schema hasn't changed since last generation, or `drizzle.config.ts` points to wrong schema path.

**Fix:**
1. Verify `schema` path in `drizzle.config.ts` matches actual file location
2. Check that the schema file exports table definitions (not just types)
3. Delete `./drizzle/meta/` and regenerate from scratch (last resort — loses migration history)

### drizzle-kit push drops a column unexpectedly

**Cause:** `push` detects a column rename as a drop + add, losing data.

**Fix:**
- Use `generate` + manually edit the SQL to use `ALTER TABLE ... RENAME COLUMN` instead
- `push` is for prototyping only — never use on data you care about
- For production, always use `generate` and review the SQL before running `migrate`

### Migration fails with "relation already exists"

**Cause:** Migration was partially applied, or the `drizzle` journal is out of sync with the actual database.

**Fix:**
1. Check `./drizzle/meta/_journal.json` to see which migrations Drizzle thinks have been applied
2. Compare with actual database state: `npx drizzle-kit introspect`
3. If the database is ahead of the journal, manually update `_journal.json` to mark the migration as applied
4. If stuck, use `drizzle-kit push` to force-sync (dev only)

### No migration rollback support

**Cause:** Drizzle does not generate down migrations.

**Workarounds:**
1. Create a new migration that reverses the changes:
   ```bash
   # After a bad migration, modify the schema to undo the change, then:
   npx drizzle-kit generate
   npx drizzle-kit migrate
   ```
2. For critical rollbacks, write raw SQL:
   ```sql
   -- manual-rollback.sql
   ALTER TABLE users DROP COLUMN IF EXISTS new_column;
   ```
3. Use database-level snapshots/backups before running migrations

## Runtime Errors

### db.query is undefined

**Cause:** Schema not passed to `drizzle()`.

**Fix:**
```typescript
// Wrong — no relational query API
const db = drizzle(client);

// Right — enables db.query.*
import * as schema from './schema';
const db = drizzle(client, { schema });
```

### prepared statement "X" already exists

**Cause:** Calling `.prepare()` with the same name multiple times.

**Fix:**
- Use unique names for prepared statements
- Or create the prepared statement once at module level, not inside a function

### Pool connection timeout

**Cause:** Database connections exhausted, usually from not closing the pool.

**Fix:**
```typescript
// For PostgreSQL with node-postgres
import { Pool } from 'pg';

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  max: 20,  // adjust based on your needs
});

const db = drizzle(pool, { schema });

// On shutdown
process.on('SIGTERM', () => pool.end());
```

## Performance Tips

1. **Use `select()` with specific columns** instead of selecting everything — reduces data transfer
2. **Use prepared statements** for queries that run frequently with different parameters
3. **Use `db.query` (relational API) for nested data** instead of manual joins — Drizzle optimizes the SQL
4. **Add indexes** for columns used in `where`, `orderBy`, and `join` conditions
5. **Use `.$dynamic()` for conditional queries** instead of string concatenation
6. **Split large schemas** to keep TypeScript type checking fast — the compiler struggles with >30 tables in one file
