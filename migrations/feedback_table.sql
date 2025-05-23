-- Drop existing table and policies
drop policy if exists "Enable insert for anon" on feedback;
drop policy if exists "Enable select for anon" on feedback;
drop table if exists feedback;

-- Create the feedback table
create table feedback (
    id bigint generated by default as identity primary key,
    feedback_text text not null,
    user_verdict text not null,
    user_id bigint,
    result_id bigint,
    feedback_date timestamptz default now(),
    created_at timestamptz default now()
);

-- Enable RLS
alter table feedback enable row level security;

-- Create policies for anonymous access
create policy "Enable insert for anon"
    on feedback for insert
    to anon
    with check (true);

create policy "Enable select for anon"
    on feedback for select
    to anon
    using (true);

-- Grant permissions
grant usage on schema public to anon;
grant all on feedback to anon;
grant usage, select on sequence feedback_id_seq to anon;
