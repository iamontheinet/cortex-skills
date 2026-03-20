/**
 * Drizzle ORM — Starter Schema (PostgreSQL)
 *
 * A multi-table SaaS starter with users, teams, team memberships, and posts.
 * Includes: enums, relations, indexes, timestamps, typed JSON columns.
 *
 * To adapt for MySQL or SQLite, swap the imports:
 *   PostgreSQL: 'drizzle-orm/pg-core'    → pgTable, pgEnum
 *   MySQL:      'drizzle-orm/mysql-core'  → mysqlTable, mysqlEnum
 *   SQLite:     'drizzle-orm/sqlite-core' → sqliteTable (text enums only)
 */

import { relations, sql } from 'drizzle-orm';
import {
  pgTable,
  pgEnum,
  integer,
  varchar,
  text,
  boolean,
  timestamp,
  jsonb,
  uniqueIndex,
  index,
  primaryKey,
} from 'drizzle-orm/pg-core';

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------

/** Reusable timestamp columns. Spread into any table: `...timestamps` */
const timestamps = {
  createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
  updatedAt: timestamp('updated_at', { withTimezone: true })
    .defaultNow()
    .notNull()
    .$onUpdateFn(() => new Date()),
};

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export const userRoleEnum = pgEnum('user_role', ['admin', 'member', 'guest']);
export const postStatusEnum = pgEnum('post_status', ['draft', 'published', 'archived']);

// ---------------------------------------------------------------------------
// Tables
// ---------------------------------------------------------------------------

export const users = pgTable('users', {
  id: integer('id').primaryKey().generatedAlwaysAsIdentity(),
  email: varchar('email', { length: 320 }).notNull(),
  name: varchar('name', { length: 100 }).notNull(),
  role: userRoleEnum('role').default('member').notNull(),
  isActive: boolean('is_active').default(true).notNull(),
  avatarUrl: varchar('avatar_url', { length: 512 }),
  metadata: jsonb('metadata').$type<{ onboarded?: boolean; theme?: string }>(),
  ...timestamps,
}, (table) => [
  uniqueIndex('users_email_idx').on(table.email),
]);

export const teams = pgTable('teams', {
  id: integer('id').primaryKey().generatedAlwaysAsIdentity(),
  name: varchar('name', { length: 100 }).notNull(),
  slug: varchar('slug', { length: 100 }).notNull(),
  ...timestamps,
}, (table) => [
  uniqueIndex('teams_slug_idx').on(table.slug),
]);

export const teamMembers = pgTable('team_members', {
  userId: integer('user_id').notNull().references(() => users.id, { onDelete: 'cascade' }),
  teamId: integer('team_id').notNull().references(() => teams.id, { onDelete: 'cascade' }),
  role: varchar('role', { length: 20 }).default('member').notNull(),
  joinedAt: timestamp('joined_at', { withTimezone: true }).defaultNow().notNull(),
}, (table) => [
  primaryKey({ columns: [table.userId, table.teamId] }),
]);

export const posts = pgTable('posts', {
  id: integer('id').primaryKey().generatedAlwaysAsIdentity(),
  title: varchar('title', { length: 255 }).notNull(),
  slug: varchar('slug', { length: 255 }).notNull(),
  content: text('content'),
  status: postStatusEnum('status').default('draft').notNull(),
  authorId: integer('author_id').notNull().references(() => users.id),
  teamId: integer('team_id').references(() => teams.id),
  publishedAt: timestamp('published_at', { withTimezone: true }),
  ...timestamps,
}, (table) => [
  uniqueIndex('posts_slug_idx').on(table.slug),
  index('posts_author_idx').on(table.authorId),
  index('posts_team_status_idx').on(table.teamId, table.status),
]);

// ---------------------------------------------------------------------------
// Relations
// ---------------------------------------------------------------------------

export const usersRelations = relations(users, ({ many }) => ({
  posts: many(posts),
  teamMembers: many(teamMembers),
}));

export const teamsRelations = relations(teams, ({ many }) => ({
  teamMembers: many(teamMembers),
  posts: many(posts),
}));

export const teamMembersRelations = relations(teamMembers, ({ one }) => ({
  user: one(users, {
    fields: [teamMembers.userId],
    references: [users.id],
  }),
  team: one(teams, {
    fields: [teamMembers.teamId],
    references: [teams.id],
  }),
}));

export const postsRelations = relations(posts, ({ one }) => ({
  author: one(users, {
    fields: [posts.authorId],
    references: [users.id],
  }),
  team: one(teams, {
    fields: [posts.teamId],
    references: [teams.id],
  }),
}));
