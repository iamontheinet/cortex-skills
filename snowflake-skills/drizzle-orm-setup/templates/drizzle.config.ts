/**
 * Drizzle Kit Configuration
 *
 * Docs: https://orm.drizzle.team/kit-docs/config-reference
 *
 * Uncomment the dialect section that matches your database.
 * Set DATABASE_URL in your .env file or environment.
 */

import { defineConfig } from 'drizzle-kit';

export default defineConfig({
  // --- Schema location ---
  // Single file:
  schema: './src/db/schema.ts',
  // Multi-file:
  // schema: './src/db/schema/index.ts',
  // Glob:
  // schema: './src/db/schema/*.ts',

  // --- Output directory for generated migrations ---
  out: './drizzle',

  // --- PostgreSQL (default) ---
  dialect: 'postgresql',
  dbCredentials: {
    url: process.env.DATABASE_URL!,
  },

  // --- MySQL ---
  // dialect: 'mysql',
  // dbCredentials: {
  //   url: process.env.DATABASE_URL!,
  // },

  // --- SQLite ---
  // dialect: 'sqlite',
  // dbCredentials: {
  //   url: process.env.DATABASE_URL!,  // file path, e.g. './sqlite.db'
  // },

  // --- Turso / libSQL ---
  // dialect: 'turso',
  // dbCredentials: {
  //   url: process.env.TURSO_DATABASE_URL!,
  //   authToken: process.env.TURSO_AUTH_TOKEN,
  // },

  // --- Options ---
  // verbose: true,   // Log all SQL statements during generate/push
  // strict: true,    // Prompt for confirmation on destructive changes
});
