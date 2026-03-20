# Query Patterns

Drizzle ORM has two query APIs. Use whichever fits the query.

- **Core API** (`db.select()`, `db.insert()`, etc.) — SQL-like, explicit joins, full control
- **Relational API** (`db.query.*`) — nested data loading, automatic joins from relations

## Core API

### Select

```typescript
import { eq, ne, gt, gte, lt, lte, like, ilike, between, inArray, isNull, and, or, not, sql, desc, asc, count, sum, avg } from 'drizzle-orm';

// Basic select
const allUsers = await db.select().from(users);

// Select specific columns
const names = await db.select({ name: users.name, email: users.email }).from(users);

// Where clause
const admins = await db.select().from(users).where(eq(users.role, 'admin'));

// Multiple conditions
const activeAdmins = await db.select().from(users).where(
  and(
    eq(users.role, 'admin'),
    eq(users.isActive, true),
  )
);

// OR conditions
const adminOrMember = await db.select().from(users).where(
  or(
    eq(users.role, 'admin'),
    eq(users.role, 'member'),
  )
);

// Pattern matching
const gmailUsers = await db.select().from(users).where(
  like(users.email, '%@gmail.com')
);

// Case-insensitive (PostgreSQL)
const search = await db.select().from(users).where(
  ilike(users.name, `%${query}%`)
);

// IN operator
const specificUsers = await db.select().from(users).where(
  inArray(users.id, [1, 2, 3])
);

// NULL check
const noProfile = await db.select().from(users).where(isNull(users.profileId));

// Between
const recentUsers = await db.select().from(users).where(
  between(users.createdAt, startDate, endDate)
);

// Order by
const sorted = await db.select().from(users).orderBy(desc(users.createdAt));

// Multiple order columns
const multiSort = await db.select().from(users)
  .orderBy(asc(users.role), desc(users.createdAt));

// Limit and offset (pagination)
const page2 = await db.select().from(users).limit(10).offset(10);
```

### Joins

```typescript
// Inner join
const postsWithAuthors = await db.select({
  postTitle: posts.title,
  authorName: users.name,
}).from(posts)
  .innerJoin(users, eq(posts.authorId, users.id));

// Left join
const usersWithPosts = await db.select({
  userName: users.name,
  postTitle: posts.title,
}).from(users)
  .leftJoin(posts, eq(users.id, posts.authorId));

// Multiple joins
const fullData = await db.select({
  userName: users.name,
  postTitle: posts.title,
  teamName: teams.name,
}).from(users)
  .leftJoin(posts, eq(users.id, posts.authorId))
  .innerJoin(teamMembers, eq(users.id, teamMembers.userId))
  .innerJoin(teams, eq(teamMembers.teamId, teams.id));
```

### Aggregations

```typescript
// Count
const userCount = await db.select({ count: count() }).from(users);

// Count with condition
const adminCount = await db.select({ count: count() }).from(users)
  .where(eq(users.role, 'admin'));

// Group by
const roleDistribution = await db.select({
  role: users.role,
  count: count(),
}).from(users).groupBy(users.role);

// Having
const activePowers = await db.select({
  authorId: posts.authorId,
  postCount: count(),
}).from(posts)
  .groupBy(posts.authorId)
  .having(gt(count(), 5));

// Sum, avg
const stats = await db.select({
  totalAmount: sum(orders.amount),
  avgAmount: avg(orders.amount),
}).from(orders);
```

### Insert

```typescript
// Single insert
const newUser = await db.insert(users).values({
  email: 'alice@example.com',
  name: 'Alice',
  role: 'member',
});

// Returning (PostgreSQL / SQLite)
const [inserted] = await db.insert(users).values({
  email: 'alice@example.com',
  name: 'Alice',
}).returning();

// Returning specific fields
const [{ id }] = await db.insert(users).values({
  email: 'alice@example.com',
  name: 'Alice',
}).returning({ id: users.id });

// Bulk insert
await db.insert(users).values([
  { email: 'alice@example.com', name: 'Alice' },
  { email: 'bob@example.com', name: 'Bob' },
]);

// On conflict (upsert) — PostgreSQL
await db.insert(users).values({
  email: 'alice@example.com',
  name: 'Alice Updated',
}).onConflictDoUpdate({
  target: users.email,
  set: { name: 'Alice Updated' },
});

// On conflict do nothing
await db.insert(users).values({
  email: 'alice@example.com',
  name: 'Alice',
}).onConflictDoNothing({ target: users.email });
```

### Update

```typescript
// Update with where
await db.update(users)
  .set({ role: 'admin' })
  .where(eq(users.id, 1));

// Update with returning
const [updated] = await db.update(users)
  .set({ isActive: false })
  .where(eq(users.id, 1))
  .returning();

// Update multiple fields
await db.update(users)
  .set({
    name: 'New Name',
    role: 'admin',
    updatedAt: new Date(),
  })
  .where(eq(users.id, 1));
```

### Delete

```typescript
// Delete with where
await db.delete(users).where(eq(users.id, 1));

// Delete with returning
const [deleted] = await db.delete(users)
  .where(eq(users.id, 1))
  .returning();

// Delete all (careful!)
await db.delete(users);
```

### Raw SQL

```typescript
import { sql } from 'drizzle-orm';

// In a where clause
const recent = await db.select().from(users)
  .where(sql`${users.createdAt} > NOW() - INTERVAL '7 days'`);

// As a column expression
const withAge = await db.select({
  name: users.name,
  daysSinceCreation: sql<number>`EXTRACT(DAY FROM NOW() - ${users.createdAt})`,
}).from(users);

// Full raw query
const result = await db.execute(sql`SELECT * FROM users WHERE id = ${userId}`);
```

## Relational Query API

Requires `{ schema }` passed to `drizzle()` and relations defined in the schema.

### findMany

```typescript
// All users
const allUsers = await db.query.users.findMany();

// With related data (one level)
const usersWithPosts = await db.query.users.findMany({
  with: {
    posts: true,
  },
});

// Nested relations
const usersWithPostsAndComments = await db.query.users.findMany({
  with: {
    posts: {
      with: {
        comments: true,
      },
    },
  },
});

// Select specific columns
const userNames = await db.query.users.findMany({
  columns: {
    id: true,
    name: true,
    email: true,
  },
});

// Exclude columns
const withoutPassword = await db.query.users.findMany({
  columns: {
    passwordHash: false,
  },
});

// Filter related data
const usersWithPublishedPosts = await db.query.users.findMany({
  with: {
    posts: {
      where: eq(posts.status, 'published'),
      orderBy: [desc(posts.publishedAt)],
      limit: 5,
    },
  },
});

// Where + orderBy + limit
const recentActiveUsers = await db.query.users.findMany({
  where: eq(users.isActive, true),
  orderBy: [desc(users.createdAt)],
  limit: 20,
  offset: 0,
});

// Extras (computed fields)
const usersWithExtras = await db.query.users.findMany({
  extras: {
    fullName: sql<string>`${users.name} || ' (' || ${users.email} || ')'`.as('full_name'),
  },
});
```

### findFirst

```typescript
// Single record
const user = await db.query.users.findFirst({
  where: eq(users.id, 1),
  with: { posts: true },
});
// Returns T | undefined (not an array)
```

## Transactions

```typescript
// Basic transaction
const result = await db.transaction(async (tx) => {
  const [newUser] = await tx.insert(users).values({
    email: 'alice@example.com',
    name: 'Alice',
  }).returning();

  await tx.insert(teamMembers).values({
    userId: newUser.id,
    teamId: 1,
  });

  return newUser;
});

// Rollback on error (automatic — just throw)
await db.transaction(async (tx) => {
  await tx.insert(users).values({ email: 'alice@example.com', name: 'Alice' });

  // This will roll back the entire transaction
  if (someCondition) {
    tx.rollback();  // or just throw new Error('...')
  }

  await tx.insert(posts).values({ title: 'Hello', authorId: 1 });
});

// Nested transactions (savepoints)
await db.transaction(async (tx) => {
  await tx.insert(users).values({ email: 'outer@example.com', name: 'Outer' });

  try {
    await tx.transaction(async (tx2) => {
      await tx2.insert(users).values({ email: 'inner@example.com', name: 'Inner' });
      throw new Error('rollback inner only');
    });
  } catch {
    // Inner rolled back, outer continues
  }
});
```

## Prepared Statements

```typescript
import { placeholder } from 'drizzle-orm';

// Prepare once
const getUserByEmail = db.select().from(users)
  .where(eq(users.email, placeholder('email')))
  .prepare('get_user_by_email');

// Execute many times
const alice = await getUserByEmail.execute({ email: 'alice@example.com' });
const bob = await getUserByEmail.execute({ email: 'bob@example.com' });
```

## Dynamic Query Building

```typescript
// Build queries conditionally
function getUsers(filters: { role?: string; isActive?: boolean; search?: string }) {
  let query = db.select().from(users).$dynamic();

  const conditions = [];

  if (filters.role) {
    conditions.push(eq(users.role, filters.role));
  }
  if (filters.isActive !== undefined) {
    conditions.push(eq(users.isActive, filters.isActive));
  }
  if (filters.search) {
    conditions.push(ilike(users.name, `%${filters.search}%`));
  }

  if (conditions.length > 0) {
    query = query.where(and(...conditions));
  }

  return query;
}
```
