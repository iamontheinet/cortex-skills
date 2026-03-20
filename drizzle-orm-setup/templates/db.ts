/**
 * Database Client Setup
 *
 * Creates a Drizzle ORM instance connected to your database.
 * Uncomment the section that matches your database driver.
 *
 * IMPORTANT: Pass `{ schema }` to enable the relational query API (db.query.*).
 * Without it, only the core SQL-like API (db.select, db.insert, etc.) works.
 */

import * as schema from './schema';

// ---------------------------------------------------------------------------
// PostgreSQL — node-postgres (pg)
// ---------------------------------------------------------------------------

import { drizzle } from 'drizzle-orm/node-postgres';

export const db = drizzle(process.env.DATABASE_URL!, { schema });

// ---------------------------------------------------------------------------
// PostgreSQL — Neon Serverless
// ---------------------------------------------------------------------------

// import { drizzle } from 'drizzle-orm/neon-serverless';
//
// export const db = drizzle(process.env.DATABASE_URL!, { schema });

// ---------------------------------------------------------------------------
// MySQL — mysql2
// ---------------------------------------------------------------------------

// import { drizzle } from 'drizzle-orm/mysql2';
//
// export const db = drizzle(process.env.DATABASE_URL!, { schema });

// ---------------------------------------------------------------------------
// SQLite — better-sqlite3
// ---------------------------------------------------------------------------

// import { drizzle } from 'drizzle-orm/better-sqlite3';
//
// export const db = drizzle(process.env.DATABASE_URL!, { schema });

// ---------------------------------------------------------------------------
// SQLite — Turso / libSQL
// ---------------------------------------------------------------------------

// import { drizzle } from 'drizzle-orm/libsql';
//
// export const db = drizzle({
//   connection: {
//     url: process.env.TURSO_DATABASE_URL!,
//     authToken: process.env.TURSO_AUTH_TOKEN,
//   },
//   schema,
// });

// ---------------------------------------------------------------------------
// SQLite — Cloudflare D1
// ---------------------------------------------------------------------------

// import { drizzle } from 'drizzle-orm/d1';
//
// // In a Cloudflare Worker, `env.DB` is the D1 binding
// export function createDb(d1: D1Database) {
//   return drizzle(d1, { schema });
// }
