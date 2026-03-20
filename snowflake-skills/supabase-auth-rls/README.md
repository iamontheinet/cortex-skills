# Supabase Auth + RLS Setup

Set up a Supabase project with proper database schema, Row Level Security (RLS) policies, and auth integration. Addresses the most common Supabase pain point — getting RLS right so users only see and modify data they're allowed to.

## What It Does

An AI coding agent walks you through:

1. **Requirements gathering** — what kind of app, who can see/edit what
2. **Project setup** — Supabase CLI + local development
3. **Schema design** — tables with `auth.users` foreign keys, timestamps, triggers
4. **RLS policies** — tailored to your app's access patterns (7 common patterns included)
5. **Auth integration** — profile auto-creation, org membership, custom JWT claims
6. **Verification** — test policies with simulated users
7. **Typed client** — generate TypeScript types from your schema

## Supported Patterns

| Pattern | Use Case |
|---------|----------|
| User owns data | Personal apps — todos, notes, bookmarks |
| Team/org membership | SaaS, workspaces, multi-tenant platforms |
| Public read, auth write | Blogs, forums, catalogs |
| Published/draft visibility | CMS, document sharing |
| Admin bypass | Admin dashboards, moderation tools |
| Row-level sharing | Google Docs-style per-resource permissions |
| JWT custom claims | Subscription tiers, feature flags |

## Prerequisites

- **Node.js 18+** — for Supabase CLI
- **Docker** — for Supabase local development
- **Supabase CLI** — installed via `npx supabase` (no global install needed)
- An AI coding agent that supports skills

## File Structure

```
supabase-auth-rls/
├── SKILL.md                          # Agent instructions (entry point)
├── README.md                         # This file
├── references/
│   ├── rls-patterns.md               # 7 RLS policy patterns with full SQL
│   ├── auth-helpers.md               # auth.uid(), auth.jwt(), auth.role() reference
│   └── troubleshooting.md            # Debugging checklist for common RLS issues
└── templates/
    ├── migration-schema.sql          # Starter schema (profiles, orgs, projects, tasks)
    └── migration-rls.sql             # RLS policies for the starter schema
```

## Quick Reference

### Enable RLS on a table

```sql
ALTER TABLE public.my_table ENABLE ROW LEVEL SECURITY;
```

### Most common policy — user owns their data

```sql
CREATE POLICY "Users can view own rows"
  ON public.my_table FOR SELECT
  USING (auth.uid() = user_id);
```

### Check if RLS is enabled

```sql
SELECT tablename, rowsecurity FROM pg_tables WHERE schemaname = 'public';
```

### Common mistake: forgetting WITH CHECK on UPDATE

```sql
-- Bad: user can change user_id to someone else's
CREATE POLICY "update" ON my_table FOR UPDATE
  USING (auth.uid() = user_id);

-- Good: both clauses prevent user_id tampering
CREATE POLICY "update" ON my_table FOR UPDATE
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);
```

See `references/rls-patterns.md` for all 7 patterns and `references/troubleshooting.md` for the full debugging guide.
