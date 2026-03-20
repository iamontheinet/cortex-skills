-- Supabase RLS Policy Migration Template
-- Apply AFTER the schema migration. Adapt policies to your access patterns.
--
-- This template covers:
-- 1. User-owns-data (profiles)
-- 2. Team/org membership (organizations, projects)
-- 3. Inherited access (tasks inherit from project's org)
-- 4. Role-based write permissions (admin vs member vs viewer)

-- ============================================================
-- Profiles: users own their own profile
-- ============================================================
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

-- Anyone can view profiles (common for displaying names/avatars)
CREATE POLICY "Profiles are viewable by everyone"
  ON public.profiles FOR SELECT
  USING (true);

-- Users can update only their own profile
CREATE POLICY "Users can update own profile"
  ON public.profiles FOR UPDATE
  USING (auth.uid() = id)
  WITH CHECK (auth.uid() = id);

-- Insert handled by trigger (handle_new_user), but allow explicit insert for own ID
CREATE POLICY "Users can insert own profile"
  ON public.profiles FOR INSERT
  WITH CHECK (auth.uid() = id);

-- ============================================================
-- Organizations: visible to members
-- ============================================================
ALTER TABLE public.organizations ENABLE ROW LEVEL SECURITY;

-- Members can view their organizations
CREATE POLICY "Members can view their organizations"
  ON public.organizations FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.org_members
      WHERE org_members.org_id = organizations.id
        AND org_members.user_id = auth.uid()
    )
  );

-- Any authenticated user can create an organization
CREATE POLICY "Authenticated users can create organizations"
  ON public.organizations FOR INSERT
  WITH CHECK (auth.role() = 'authenticated');

-- Only owners can update organization details
CREATE POLICY "Org owners can update organization"
  ON public.organizations FOR UPDATE
  USING (
    EXISTS (
      SELECT 1 FROM public.org_members
      WHERE org_members.org_id = organizations.id
        AND org_members.user_id = auth.uid()
        AND org_members.role = 'owner'
    )
  );

-- Only owners can delete organizations
CREATE POLICY "Org owners can delete organization"
  ON public.organizations FOR DELETE
  USING (
    EXISTS (
      SELECT 1 FROM public.org_members
      WHERE org_members.org_id = organizations.id
        AND org_members.user_id = auth.uid()
        AND org_members.role = 'owner'
    )
  );

-- ============================================================
-- Org Members: members can view co-members, admins+ can manage
-- ============================================================
ALTER TABLE public.org_members ENABLE ROW LEVEL SECURITY;

-- Members can see other members in their org
CREATE POLICY "Members can view org members"
  ON public.org_members FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.org_members AS self
      WHERE self.org_id = org_members.org_id
        AND self.user_id = auth.uid()
    )
  );

-- Owners and admins can add members
CREATE POLICY "Admins can add org members"
  ON public.org_members FOR INSERT
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.org_members AS self
      WHERE self.org_id = org_members.org_id
        AND self.user_id = auth.uid()
        AND self.role IN ('owner', 'admin')
    )
  );

-- Owners and admins can update member roles
CREATE POLICY "Admins can update org members"
  ON public.org_members FOR UPDATE
  USING (
    EXISTS (
      SELECT 1 FROM public.org_members AS self
      WHERE self.org_id = org_members.org_id
        AND self.user_id = auth.uid()
        AND self.role IN ('owner', 'admin')
    )
  );

-- Owners and admins can remove members; members can remove themselves
CREATE POLICY "Admins can remove org members or self-remove"
  ON public.org_members FOR DELETE
  USING (
    auth.uid() = user_id  -- self-remove
    OR EXISTS (
      SELECT 1 FROM public.org_members AS self
      WHERE self.org_id = org_members.org_id
        AND self.user_id = auth.uid()
        AND self.role IN ('owner', 'admin')
    )
  );

-- ============================================================
-- Projects: access through org membership
-- ============================================================
ALTER TABLE public.projects ENABLE ROW LEVEL SECURITY;

-- Org members can view projects
CREATE POLICY "Org members can view projects"
  ON public.projects FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.org_members
      WHERE org_members.org_id = projects.org_id
        AND org_members.user_id = auth.uid()
    )
  );

-- Admins and owners can create projects
CREATE POLICY "Org admins can create projects"
  ON public.projects FOR INSERT
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.org_members
      WHERE org_members.org_id = projects.org_id
        AND org_members.user_id = auth.uid()
        AND org_members.role IN ('owner', 'admin', 'member')
    )
  );

-- Admins and owners can update projects
CREATE POLICY "Org admins can update projects"
  ON public.projects FOR UPDATE
  USING (
    EXISTS (
      SELECT 1 FROM public.org_members
      WHERE org_members.org_id = projects.org_id
        AND org_members.user_id = auth.uid()
        AND org_members.role IN ('owner', 'admin')
    )
  );

-- Only owners can delete projects
CREATE POLICY "Org owners can delete projects"
  ON public.projects FOR DELETE
  USING (
    EXISTS (
      SELECT 1 FROM public.org_members
      WHERE org_members.org_id = projects.org_id
        AND org_members.user_id = auth.uid()
        AND org_members.role = 'owner'
    )
  );

-- ============================================================
-- Tasks: inherit access from project's org
-- ============================================================
ALTER TABLE public.tasks ENABLE ROW LEVEL SECURITY;

-- Helper function to check org membership through project
-- Uses SECURITY DEFINER to avoid policy recursion
CREATE OR REPLACE FUNCTION public.user_is_org_member_via_project(project_uuid UUID)
RETURNS BOOLEAN
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
STABLE
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM public.projects p
    JOIN public.org_members om ON om.org_id = p.org_id
    WHERE p.id = project_uuid
      AND om.user_id = auth.uid()
  );
$$;

CREATE OR REPLACE FUNCTION public.user_is_org_admin_via_project(project_uuid UUID)
RETURNS BOOLEAN
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
STABLE
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM public.projects p
    JOIN public.org_members om ON om.org_id = p.org_id
    WHERE p.id = project_uuid
      AND om.user_id = auth.uid()
      AND om.role IN ('owner', 'admin', 'member')
  );
$$;

-- Org members can view tasks in their projects
CREATE POLICY "Org members can view tasks"
  ON public.tasks FOR SELECT
  USING (public.user_is_org_member_via_project(project_id));

-- Members+ can create tasks
CREATE POLICY "Org members can create tasks"
  ON public.tasks FOR INSERT
  WITH CHECK (public.user_is_org_admin_via_project(project_id));

-- Task creator or assignee can update; admins+ can also update
CREATE POLICY "Task participants can update tasks"
  ON public.tasks FOR UPDATE
  USING (
    auth.uid() = created_by
    OR auth.uid() = assigned_to
    OR public.user_is_org_admin_via_project(project_id)
  )
  WITH CHECK (
    public.user_is_org_member_via_project(project_id)
  );

-- Admins+ can delete tasks
CREATE POLICY "Org admins can delete tasks"
  ON public.tasks FOR DELETE
  USING (public.user_is_org_admin_via_project(project_id));
