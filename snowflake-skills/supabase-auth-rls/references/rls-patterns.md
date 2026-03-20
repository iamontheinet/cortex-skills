# RLS Policy Patterns

Common Row Level Security patterns for Supabase. Each pattern includes the policy SQL and when to use it.

## Pattern 1: User Owns Their Data

The most common pattern. Users can only access rows where `user_id` matches their auth ID.

```sql
-- Enable RLS (required before any policies take effect)
ALTER TABLE public.todos ENABLE ROW LEVEL SECURITY;

-- Users see only their own rows
CREATE POLICY "Users can view own todos"
  ON public.todos FOR SELECT
  USING (auth.uid() = user_id);

-- Users can insert rows for themselves only
CREATE POLICY "Users can insert own todos"
  ON public.todos FOR INSERT
  WITH CHECK (auth.uid() = user_id);

-- Users can update their own rows
CREATE POLICY "Users can update own todos"
  ON public.todos FOR UPDATE
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

-- Users can delete their own rows
CREATE POLICY "Users can delete own todos"
  ON public.todos FOR DELETE
  USING (auth.uid() = user_id);
```

**When to use:** Personal data — profiles, settings, notes, todos, bookmarks.

**Common mistake:** Forgetting `WITH CHECK` on UPDATE. `USING` controls which rows are visible; `WITH CHECK` controls what values can be written. Without both, a user could update their row to change `user_id` to someone else's.

## Pattern 2: Team/Org Membership

Users access data through a membership table. This is the standard multi-tenant pattern.

```sql
-- Membership table links users to organizations
CREATE TABLE public.org_members (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  org_id UUID REFERENCES public.organizations(id) ON DELETE CASCADE,
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  role TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('owner', 'admin', 'member', 'viewer')),
  UNIQUE(org_id, user_id)
);

ALTER TABLE public.projects ENABLE ROW LEVEL SECURITY;

-- Members can view projects in their org
CREATE POLICY "Org members can view projects"
  ON public.projects FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.org_members
      WHERE org_members.org_id = projects.org_id
        AND org_members.user_id = auth.uid()
    )
  );

-- Only admins and owners can insert projects
CREATE POLICY "Org admins can insert projects"
  ON public.projects FOR INSERT
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.org_members
      WHERE org_members.org_id = projects.org_id
        AND org_members.user_id = auth.uid()
        AND org_members.role IN ('owner', 'admin')
    )
  );
```

**When to use:** SaaS apps, team workspaces, multi-tenant platforms.

**Performance note:** Add an index on `org_members(org_id, user_id)` — this subquery runs on every row access. The UNIQUE constraint above already creates this index.

## Pattern 3: Public Read, Authenticated Write

Content is visible to everyone but only authenticated users can create/modify.

```sql
ALTER TABLE public.posts ENABLE ROW LEVEL SECURITY;

-- Anyone can read (including anonymous/unauthenticated)
CREATE POLICY "Posts are publicly readable"
  ON public.posts FOR SELECT
  USING (true);

-- Only authenticated users can insert
CREATE POLICY "Authenticated users can create posts"
  ON public.posts FOR INSERT
  WITH CHECK (auth.role() = 'authenticated');

-- Only the author can update their post
CREATE POLICY "Authors can update own posts"
  ON public.posts FOR UPDATE
  USING (auth.uid() = author_id)
  WITH CHECK (auth.uid() = author_id);
```

**When to use:** Blogs, forums, product catalogs, public feeds.

**Note:** `auth.role()` returns `'authenticated'` for logged-in users and `'anon'` for unauthenticated requests. This only works if you've enabled anonymous access in your Supabase project settings.

## Pattern 4: Published/Draft Visibility

Rows have a status that controls visibility. Authors see everything; others see only published content.

```sql
ALTER TABLE public.articles ENABLE ROW LEVEL SECURITY;

-- Authors see all their articles; others see only published
CREATE POLICY "View published or own articles"
  ON public.articles FOR SELECT
  USING (
    status = 'published'
    OR auth.uid() = author_id
  );

-- Only authors can update their own articles
CREATE POLICY "Authors can update own articles"
  ON public.articles FOR UPDATE
  USING (auth.uid() = author_id)
  WITH CHECK (auth.uid() = author_id);
```

**When to use:** CMS, blog platforms, document sharing with draft states.

## Pattern 5: Service Role Bypass

The `service_role` key bypasses RLS entirely. For server-side operations that need full access, use the service role client. But you can also create explicit admin policies.

```sql
-- Admin users (stored in a custom claim or admin table) can do anything
CREATE POLICY "Admins have full access"
  ON public.todos FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM public.user_roles
      WHERE user_roles.user_id = auth.uid()
        AND user_roles.role = 'admin'
    )
  );
```

**When to use:** Admin dashboards, moderation tools, support interfaces.

**Important:** Never expose the `service_role` key in client-side code. It bypasses all RLS. Use it only in server-side functions (Edge Functions, server routes).

## Pattern 6: Row-Level Sharing (Granular Access)

Individual rows can be shared with specific users, like Google Docs sharing.

```sql
CREATE TABLE public.document_shares (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  document_id UUID REFERENCES public.documents(id) ON DELETE CASCADE,
  shared_with UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  permission TEXT NOT NULL DEFAULT 'view' CHECK (permission IN ('view', 'edit')),
  UNIQUE(document_id, shared_with)
);

ALTER TABLE public.documents ENABLE ROW LEVEL SECURITY;

-- Owner or shared users can view
CREATE POLICY "Owner and shared users can view"
  ON public.documents FOR SELECT
  USING (
    auth.uid() = owner_id
    OR EXISTS (
      SELECT 1 FROM public.document_shares
      WHERE document_shares.document_id = documents.id
        AND document_shares.shared_with = auth.uid()
    )
  );

-- Only owner and users with 'edit' permission can update
CREATE POLICY "Owner and editors can update"
  ON public.documents FOR UPDATE
  USING (
    auth.uid() = owner_id
    OR EXISTS (
      SELECT 1 FROM public.document_shares
      WHERE document_shares.document_id = documents.id
        AND document_shares.shared_with = auth.uid()
        AND document_shares.permission = 'edit'
    )
  )
  WITH CHECK (
    auth.uid() = owner_id
    OR EXISTS (
      SELECT 1 FROM public.document_shares
      WHERE document_shares.document_id = documents.id
        AND document_shares.shared_with = auth.uid()
        AND document_shares.permission = 'edit'
    )
  );
```

**When to use:** Document sharing, collaborative tools, permission-per-resource systems.

## Pattern 7: JWT Custom Claims

Use custom claims in the JWT for role-based access without extra database queries.

```sql
-- Check a custom claim set during sign-up or by an admin function
CREATE POLICY "Premium users can access premium content"
  ON public.premium_content FOR SELECT
  USING (
    (auth.jwt() -> 'app_metadata' ->> 'plan') = 'premium'
  );
```

**When to use:** Subscription tiers, feature flags stored in JWT, reducing policy query overhead.

**Trade-off:** JWT claims are set at token issuance. Changes don't take effect until the token refreshes (default: 1 hour). For real-time permission changes, use a database lookup instead.

## Anti-Patterns to Avoid

1. **Forgetting to enable RLS**: Creating policies without `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` does nothing. Policies are ignored until RLS is enabled.

2. **Using `FOR ALL` when you mean specific operations**: `FOR ALL` creates one policy for SELECT, INSERT, UPDATE, and DELETE. Usually you want different rules per operation.

3. **Infinite recursion**: If a policy on table A queries table B, and table B has a policy that queries table A, you get infinite recursion. Fix by using `SECURITY DEFINER` functions or restructuring policies.

4. **Not indexing policy columns**: Every `auth.uid() = user_id` check is a filter. Make sure `user_id` columns are indexed.

5. **Overly complex policies**: If a policy requires 3+ JOINs, consider a `SECURITY DEFINER` function that encapsulates the logic:

```sql
CREATE OR REPLACE FUNCTION public.user_has_access(resource_id UUID)
RETURNS BOOLEAN
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1 FROM access_grants
    WHERE access_grants.resource_id = $1
      AND access_grants.user_id = auth.uid()
      AND access_grants.expires_at > now()
  );
$$;

CREATE POLICY "Users with access grant"
  ON public.resources FOR SELECT
  USING (public.user_has_access(id));
```
