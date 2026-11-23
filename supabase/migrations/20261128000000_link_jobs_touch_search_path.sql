-- Pin search_path on the link_jobs updated_at trigger (Supabase advisor 0011). Body only uses now() and NEW, so an empty path is safe.
alter function public.link_jobs_touch() set search_path = '';
