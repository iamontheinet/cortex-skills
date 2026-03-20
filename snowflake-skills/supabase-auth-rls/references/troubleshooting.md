# RLS Troubleshooting Guide

Debugging checklist for when Row Level Security "doesn't work" in Supabase.

## Quick Diagnostic Queries

### Check if RLS is enabled on a table

```sql
SELECT tablename, rowsecurity
FROM pg_tables
WHERE schemaname = 'public';
```

If `rowsecurity` is `false`, no policies are enforced — all rows are visible.

### List all policies on a table

```sql
SELECT policyname, permissive, roles, cmd, qual, with_check
FROM pg_policies
WHERE tablename = 'your_table_name';
```

### Check what auth.uid() returns in current context

```sql
SELECT auth.uid(), auth.role(), auth.email();
```

If all return NULL, you're not in an authenticated context (e.g., running from SQL editor or migration).

## Problem: "I can see all rows even with RLS enabled"

**Checklist:**

1. **RLS is not actually enabled.** Run the diagnostic query above. You need both:
   ```sql
   ALTER TABLE public.your_table ENABLE ROW LEVEL SECURITY;
   ```
   AND at least one policy created.

2. **You're using the `service_role` key.** Service role bypasses ALL RLS. Switch to the `anon` key in your client:
   ```typescript
   // Wrong — bypasses RLS
   const supabase = createClient(url, SERVICE_ROLE_KEY);
   
   // Right — respects RLS
   const supabase = createClient(url, ANON_KEY);
   ```

3. **You're the table owner.** By default, the table owner (`postgres` role) bypasses RLS. Fix with:
   ```sql
   ALTER TABLE public.your_table FORCE ROW LEVEL SECURITY;
   ```
   This forces RLS even for the table owner. Only needed in development/testing.

4. **Your policy is too permissive.** Check if you have a `USING (true)` policy that's granting access to everyone.

## Problem: "I can't see any rows"

**Checklist:**

1. **No SELECT policy exists.** Having INSERT/UPDATE/DELETE policies without a SELECT policy means no rows are visible. Every operation needs its own policy (or use `FOR ALL`).

2. **`auth.uid()` is NULL.** The user isn't authenticated. Check that your client is passing the auth header:
   ```typescript
   const { data: { session } } = await supabase.auth.getSession();
   console.log('User ID:', session?.user?.id);  // Should not be null
   ```

3. **`user_id` column doesn't match `auth.uid()`.** Common causes:
   - Column stores a string but `auth.uid()` returns UUID — cast with `user_id::uuid`
   - Column was populated with a different value than the auth user's ID
   - Column is named differently than what the policy references

4. **Policy uses wrong column.** Double-check the column name in your policy matches your actual schema.

## Problem: "INSERT works but the row disappears"

This happens when your INSERT policy allows the write but your SELECT policy filters it out.

```sql
-- INSERT succeeds because WITH CHECK passes
CREATE POLICY "insert" ON posts FOR INSERT WITH CHECK (true);

-- But SELECT filters it because user_id doesn't match
CREATE POLICY "select" ON posts FOR SELECT USING (auth.uid() = user_id);
```

**Fix:** Make sure the INSERT `WITH CHECK` is consistent with the SELECT `USING`:
```sql
CREATE POLICY "insert" ON posts FOR INSERT
  WITH CHECK (auth.uid() = user_id);
```

## Problem: "Infinite recursion detected in policy"

This happens when policy on table A references table B, and table B's policy references table A.

**Example of the problem:**
```sql
-- Policy on profiles references teams
CREATE POLICY "..." ON profiles USING (
  EXISTS (SELECT 1 FROM teams WHERE teams.owner_id = profiles.id)
);

-- Policy on teams references profiles
CREATE POLICY "..." ON teams USING (
  EXISTS (SELECT 1 FROM profiles WHERE profiles.team_id = teams.id)
);
```

**Fixes:**

1. **Use a SECURITY DEFINER function** to break the cycle:
   ```sql
   CREATE FUNCTION public.get_user_team_id(uid UUID)
   RETURNS UUID
   LANGUAGE sql
   SECURITY DEFINER
   SET search_path = public
   STABLE
   AS $$
     SELECT team_id FROM profiles WHERE id = uid;
   $$;
   
   CREATE POLICY "..." ON teams USING (
     id = public.get_user_team_id(auth.uid())
   );
   ```

2. **Restructure to avoid circular references.** Use a dedicated join table instead of cross-referencing.

## Problem: "RLS works in SQL editor but not from the client"

1. **SQL editor uses `postgres` role** which bypasses RLS by default. Test with:
   ```sql
   SET ROLE authenticated;
   SET request.jwt.claims = '{"sub": "your-user-uuid", "role": "authenticated"}';
   SELECT * FROM your_table;
   RESET ROLE;
   ```

2. **Client might be using the wrong key.** Verify in your app:
   ```typescript
   // Check which key you're using
   console.log('URL:', process.env.NEXT_PUBLIC_SUPABASE_URL);
   // Should be the anon key, NOT service_role
   ```

## Problem: "UPDATE policy not working"

UPDATE policies need BOTH `USING` and `WITH CHECK`:
- `USING` = which existing rows can be selected for update
- `WITH CHECK` = what the row must look like after the update

```sql
-- Common mistake: only USING, no WITH CHECK
CREATE POLICY "bad" ON posts FOR UPDATE
  USING (auth.uid() = user_id);
-- This lets users change user_id to someone else's ID!

-- Correct: both clauses
CREATE POLICY "good" ON posts FOR UPDATE
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);
```

## Problem: "Policy works for some users but not others"

1. **Check the user's JWT claims.** Different users may have different `app_metadata`:
   ```typescript
   const { data: { user } } = await supabase.auth.getUser();
   console.log('App metadata:', user?.app_metadata);
   console.log('User metadata:', user?.user_metadata);
   ```

2. **Check if the membership/role record exists.** For team-based policies, verify the user has a row in the membership table.

3. **JWT might be stale.** If you recently changed a user's `app_metadata`, the change won't take effect until the JWT refreshes:
   ```typescript
   await supabase.auth.refreshSession();
   ```

## Performance Issues

### Slow queries with RLS

1. **Add indexes on columns used in policies:**
   ```sql
   CREATE INDEX idx_todos_user_id ON public.todos(user_id);
   CREATE INDEX idx_org_members_lookup ON public.org_members(org_id, user_id);
   ```

2. **Check policy evaluation with EXPLAIN:**
   ```sql
   SET ROLE authenticated;
   SET request.jwt.claims = '{"sub": "user-uuid", "role": "authenticated"}';
   EXPLAIN ANALYZE SELECT * FROM your_table;
   RESET ROLE;
   ```

3. **Simplify complex policies** by moving logic into `SECURITY DEFINER` functions (they're evaluated once, not per-row).

## Testing RLS Policies

### Using Supabase CLI

```bash
# Start local dev
supabase start

# Run tests
supabase db test
```

### Manual testing with role switching

```sql
-- Simulate an authenticated user
BEGIN;
SET LOCAL ROLE authenticated;
SET LOCAL request.jwt.claims = '{
  "sub": "d0c4e99a-1f3b-4c5d-9e7a-8f2b3c4d5e6f",
  "role": "authenticated",
  "email": "test@example.com"
}';

-- Test your queries here
SELECT * FROM public.todos;
INSERT INTO public.todos (user_id, title) VALUES (auth.uid(), 'Test');

ROLLBACK;  -- Clean up
```

### pgTAP test example

```sql
BEGIN;
SELECT plan(3);

-- Test: user can see own todos
SET LOCAL ROLE authenticated;
SET LOCAL request.jwt.claims = '{"sub": "user-1-uuid", "role": "authenticated"}';

SELECT is(
  (SELECT count(*)::int FROM public.todos),
  2,
  'User 1 should see exactly 2 todos'
);

-- Test: user cannot see other's todos
SELECT is(
  (SELECT count(*)::int FROM public.todos WHERE user_id != auth.uid()),
  0,
  'User should not see other users todos'
);

-- Test: user can insert own todo
SELECT lives_ok(
  $$INSERT INTO public.todos (user_id, title) VALUES (auth.uid(), 'New')$$,
  'User can insert their own todo'
);

SELECT * FROM finish();
ROLLBACK;
```
