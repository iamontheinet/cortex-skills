# Supabase Auth Helpers Reference

Functions available in RLS policies and SQL for interacting with Supabase Auth.

## Core Functions

### `auth.uid()`

Returns the current user's UUID from the JWT. This is the most commonly used function in RLS policies.

```sql
-- Returns UUID or NULL if not authenticated
SELECT auth.uid();
-- e.g., 'd0c4e99a-1f3b-4c5d-9e7a-8f2b3c4d5e6f'
```

**Use in policies:**
```sql
USING (auth.uid() = user_id)
```

**Returns NULL when:**
- Request uses the `anon` key without a logged-in user
- JWT has expired
- No authorization header present

### `auth.role()`

Returns the role from the JWT. Two built-in roles:

| Role | Meaning |
|------|---------|
| `authenticated` | Logged-in user (used the `anon` key with a valid session) |
| `anon` | Not logged in (used the `anon` key without a session) |
| `service_role` | Server-side key that **bypasses RLS entirely** |

```sql
-- Only allow authenticated users
USING (auth.role() = 'authenticated')
```

**Note:** `service_role` requests bypass RLS completely — policies are not evaluated at all. You won't see `auth.role() = 'service_role'` in policies because those requests skip policy checks.

### `auth.jwt()`

Returns the full decoded JWT as a JSON object. Use this to access custom claims.

```sql
-- Access standard claims
SELECT auth.jwt() ->> 'email';
SELECT auth.jwt() ->> 'sub';          -- same as auth.uid()
SELECT auth.jwt() ->> 'aud';          -- audience
SELECT (auth.jwt() ->> 'exp')::int;   -- expiration timestamp

-- Access app_metadata (set by server-side code)
SELECT auth.jwt() -> 'app_metadata' ->> 'plan';
SELECT auth.jwt() -> 'app_metadata' ->> 'org_id';

-- Access user_metadata (set by user during sign-up or profile update)
SELECT auth.jwt() -> 'user_metadata' ->> 'full_name';
```

**JWT structure:**
```json
{
  "sub": "d0c4e99a-...",
  "email": "user@example.com",
  "role": "authenticated",
  "aud": "authenticated",
  "exp": 1710000000,
  "app_metadata": {
    "provider": "email",
    "plan": "premium"
  },
  "user_metadata": {
    "full_name": "Jane Dev"
  }
}
```

### `auth.email()`

Shorthand for `auth.jwt() ->> 'email'`. Returns the user's email.

```sql
SELECT auth.email();
```

## The `auth.users` Table

Supabase stores user records in `auth.users` (in the `auth` schema). You can reference it with foreign keys but should **never modify it directly**.

```sql
-- Reference auth.users in your tables
CREATE TABLE public.profiles (
  id UUID REFERENCES auth.users(id) ON DELETE CASCADE PRIMARY KEY,
  display_name TEXT,
  avatar_url TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);
```

**Key columns in `auth.users`:**
| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key — use this for foreign keys |
| `email` | TEXT | User's email |
| `encrypted_password` | TEXT | Hashed password (never read this) |
| `created_at` | TIMESTAMPTZ | Account creation time |
| `updated_at` | TIMESTAMPTZ | Last profile update |
| `last_sign_in_at` | TIMESTAMPTZ | Most recent login |
| `raw_app_meta_data` | JSONB | Server-managed metadata |
| `raw_user_meta_data` | JSONB | User-managed metadata |

**Important:** Don't query `auth.users` in RLS policies if you can avoid it — use `auth.uid()` instead. Querying `auth.users` in a policy adds overhead and can cause issues.

## `app_metadata` vs `user_metadata`

| | `app_metadata` | `user_metadata` |
|--|----|----|
| **Who sets it** | Server-side only (service role) | User can set during sign-up or update |
| **Use for** | Roles, plans, org assignments | Display name, avatar, preferences |
| **Trusted in policies?** | Yes — user can't modify | No — user can modify |
| **Access in JWT** | `auth.jwt() -> 'app_metadata'` | `auth.jwt() -> 'user_metadata'` |

**Setting app_metadata (server-side only):**
```sql
-- Via SQL (in a migration or Edge Function)
UPDATE auth.users
SET raw_app_meta_data = raw_app_meta_data || '{"plan": "premium"}'::jsonb
WHERE id = 'user-uuid-here';
```

```typescript
// Via Supabase Admin SDK
const { data, error } = await supabase.auth.admin.updateUserById(userId, {
  app_metadata: { plan: 'premium' }
});
```

## Auto-Creating Profiles with a Trigger

A common pattern: automatically create a profile row when a user signs up.

```sql
-- Function that runs after user creation
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  INSERT INTO public.profiles (id, display_name, avatar_url)
  VALUES (
    NEW.id,
    COALESCE(NEW.raw_user_meta_data ->> 'full_name', NEW.email),
    NEW.raw_user_meta_data ->> 'avatar_url'
  );
  RETURN NEW;
END;
$$;

-- Trigger on auth.users insert
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();
```

**Why `SECURITY DEFINER`?** The trigger runs in the context of the auth system, which doesn't have INSERT permissions on your public tables by default. `SECURITY DEFINER` runs the function as the owner (usually `postgres`), bypassing RLS.

## Common Gotchas

1. **`auth.uid()` is NULL in migrations**: Auth functions only work in the context of a request with a JWT. In migrations or SQL editor sessions, they return NULL.

2. **JWT claims are cached**: Changes to `app_metadata` take effect after the next token refresh (default: 1 hour). Call `supabase.auth.refreshSession()` to force a refresh.

3. **`auth.users` has RLS disabled by default**: The `auth` schema is managed by Supabase. Don't enable RLS on `auth.users` — it will break authentication.

4. **Foreign key to `auth.users` requires `ON DELETE CASCADE`**: If a user deletes their account, the cascade ensures related rows are cleaned up. Without it, you'll get orphaned data.
