-- Lulia Database Initialization
-- Runs on first startup via Docker entrypoint

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- TEACHERS & CLASSES
-- ============================================
CREATE TABLE teachers (
    teacher_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR NOT NULL UNIQUE,
    name VARCHAR NOT NULL,
    auth_provider VARCHAR DEFAULT 'email',  -- 'email' or 'google'
    google_credentials_encrypted TEXT,
    subjects JSONB DEFAULT '[]',
    grade_levels JSONB DEFAULT '[]',
    state_code VARCHAR(2),
    dashboard_layout VARCHAR DEFAULT 'subject_grid',  -- 'subject_grid' or 'period_list'
    design_theme VARCHAR DEFAULT 'modern_clean',
    notification_prefs JSONB DEFAULT '{"email": true, "push": false, "badge": true}',
    auto_plan_enabled BOOLEAN DEFAULT false,
    auto_plan_days JSONB DEFAULT '["mon","tue","wed","thu","fri"]',
    freshness_window_months INT DEFAULT 6,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE classes (
    class_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    teacher_id UUID REFERENCES teachers ON DELETE CASCADE,
    name VARCHAR NOT NULL,
    subject VARCHAR NOT NULL,
    grade_level VARCHAR NOT NULL,
    school_year VARCHAR NOT NULL,
    period VARCHAR,
    google_classroom_course_id VARCHAR,
    class_code VARCHAR UNIQUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================
-- THREE-TIER STANDARDS
-- ============================================
CREATE TABLE standards_frameworks (
    framework_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR NOT NULL,
    tier VARCHAR NOT NULL,  -- 'custom', 'state', 'national'
    state_code VARCHAR,
    authority VARCHAR,
    subjects_covered JSONB,
    grade_range VARCHAR,
    is_active BOOLEAN DEFAULT true,
    priority INT NOT NULL,  -- 1=custom, 2=state, 3=national
    uploaded_by UUID REFERENCES teachers,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE standards (
    standard_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    framework_id UUID REFERENCES standards_frameworks ON DELETE CASCADE,
    parent_id UUID REFERENCES standards,
    code VARCHAR NOT NULL,
    description TEXT NOT NULL,
    grade_level VARCHAR,
    subject VARCHAR,
    domain VARCHAR,
    cluster VARCHAR,
    cognitive_level VARCHAR
);

CREATE TABLE standards_crosswalks (
    crosswalk_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_standard_id UUID REFERENCES standards,
    target_standard_id UUID REFERENCES standards,
    confidence FLOAT,
    mapping_type VARCHAR,
    auto_suggested BOOLEAN DEFAULT true,
    educator_approved BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================
-- RAG KNOWLEDGE BASE
-- ============================================
CREATE TABLE knowledge_sources (
    source_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    teacher_id UUID REFERENCES teachers ON DELETE CASCADE,
    name VARCHAR NOT NULL,
    file_type VARCHAR NOT NULL,
    original_path VARCHAR NOT NULL,
    subject VARCHAR,
    grade_level VARCHAR,
    unit VARCHAR,
    standards_covered JSONB DEFAULT '[]',
    upload_lane VARCHAR NOT NULL,  -- 'materials' or 'curriculum'
    chunk_count INT DEFAULT 0,
    processing_status VARCHAR DEFAULT 'pending',
    uploaded_at TIMESTAMP DEFAULT NOW(),
    processed_at TIMESTAMP
);

CREATE TABLE knowledge_chunks (
    chunk_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id UUID REFERENCES knowledge_sources ON DELETE CASCADE,
    chunk_number INT NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR(1024),  -- Bedrock Titan V2 = 1024 dimensions
    standards_tags JSONB DEFAULT '[]',
    topic VARCHAR,
    page_number INT,
    section_heading VARCHAR
);

-- HNSW index works on empty tables (ivfflat requires rows to build)
CREATE INDEX ON knowledge_chunks USING hnsw (embedding vector_cosine_ops);

-- ============================================
-- CURRICULUM CALENDAR
-- ============================================
CREATE TABLE curriculum_calendar (
    calendar_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    class_id UUID REFERENCES classes ON DELETE CASCADE,
    week_number INT,
    week_start_date DATE,
    unit_name VARCHAR,
    topic VARCHAR,
    standards_scheduled JSONB,
    pacing_notes TEXT,
    is_assessment_week BOOLEAN DEFAULT false,
    source_upload_id UUID
);

-- ============================================
-- LESSON PLANS
-- ============================================
CREATE TABLE lesson_plan_templates (
    template_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    teacher_id UUID REFERENCES teachers,
    name VARCHAR NOT NULL,
    preset VARCHAR DEFAULT 'standard',
    enabled_fields JSONB NOT NULL,
    standard_citation_style VARCHAR DEFAULT 'per_procedure',
    document_scope VARCHAR DEFAULT 'both',
    output_formats JSONB DEFAULT '["pdf"]',
    custom_template_path VARCHAR,
    field_mappings JSONB,
    school_name VARCHAR,
    school_logo_path VARCHAR,
    admin_drive_folder_id VARCHAR,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE lesson_plans (
    plan_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    class_id UUID REFERENCES classes,
    teacher_id UUID REFERENCES teachers,
    duration_type VARCHAR NOT NULL,  -- 'day', 'custom', 'week', 'unit', 'semester', 'year'
    selected_days JSONB,  -- ['mon','tue','thu'] or null for full week
    week_number INT,
    week_start_date DATE,
    status VARCHAR DEFAULT 'draft',  -- draft, suggested, approved, generating, complete
    plan_data JSONB NOT NULL,
    template_id UUID REFERENCES lesson_plan_templates,
    approved_at TIMESTAMP,
    pdf_path VARCHAR,
    docx_path VARCHAR,
    gdoc_id VARCHAR,
    gdoc_url VARCHAR,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================
-- ASSIGNMENTS
-- ============================================
CREATE TABLE assignments (
    assignment_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    class_id UUID REFERENCES classes,
    teacher_id UUID REFERENCES teachers,
    plan_id UUID REFERENCES lesson_plans,
    work_order_id VARCHAR,
    title VARCHAR NOT NULL,
    output_template_id VARCHAR NOT NULL,
    output_format VARCHAR NOT NULL,
    design_theme VARCHAR,
    standards_ids JSONB,
    standards_tier VARCHAR,
    questions JSONB,
    answer_key JSONB,
    rubric JSONB,
    qa_report JSONB,
    status VARCHAR DEFAULT 'generating',
    file_paths JSONB,
    google_classroom_id VARCHAR,
    day_of_week VARCHAR,
    assigned_date DATE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================
-- GENERATION HISTORY (NO REPEATS)
-- ============================================
CREATE TABLE generation_history (
    history_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    teacher_id UUID REFERENCES teachers ON DELETE CASCADE,
    assignment_id UUID REFERENCES assignments,
    standard_codes JSONB,
    output_template_id VARCHAR,
    content_fingerprint VARCHAR,
    content_summary TEXT,
    question_texts JSONB,
    scenario_context VARCHAR,
    vocabulary_used JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================
-- INTERACTIVE ACTIVITIES & GAMES
-- ============================================
CREATE TABLE interactive_activities (
    activity_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    teacher_id UUID REFERENCES teachers,
    assignment_id UUID REFERENCES assignments,
    activity_type VARCHAR NOT NULL,  -- 'assessment' or 'live_game'
    interaction_types JSONB,
    game_shell_id VARCHAR,
    questions JSONB,
    randomization_seed INT,
    access_method VARCHAR,
    s3_path VARCHAR,
    cloudfront_url VARCHAR,
    game_pin VARCHAR,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE student_responses (
    response_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    activity_id UUID REFERENCES interactive_activities,
    student_identifier VARCHAR NOT NULL,
    question_responses JSONB,
    total_score FLOAT,
    started_at TIMESTAMP,
    submitted_at TIMESTAMP
);

CREATE TABLE game_sessions (
    session_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    activity_id UUID REFERENCES interactive_activities,
    game_pin VARCHAR NOT NULL,
    host_teacher_id UUID REFERENCES teachers,
    status VARCHAR DEFAULT 'waiting',
    connected_players JSONB DEFAULT '[]',
    question_index INT DEFAULT 0,
    scores JSONB DEFAULT '{}',
    started_at TIMESTAMP,
    ended_at TIMESTAMP
);

-- ============================================
-- GRADING
-- ============================================
CREATE TABLE grading_results (
    result_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    assignment_id UUID REFERENCES assignments,
    student_identifier VARCHAR NOT NULL,
    grading_method VARCHAR NOT NULL,  -- 'auto', 'phone_scan', 'upload_scan', 'manual', 'interactive'
    scan_image_path VARCHAR,
    ocr_text JSONB,
    ocr_confidence FLOAT,
    per_question_scores JSONB,
    total_score FLOAT,
    total_possible FLOAT,
    standards_scores JSONB,  -- per-standard breakdown for analytics
    needs_review BOOLEAN DEFAULT false,
    review_notes TEXT,
    graded_at TIMESTAMP DEFAULT NOW()
);

-- ============================================
-- CREDITS
-- ============================================
CREATE TABLE credit_accounts (
    account_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    teacher_id UUID REFERENCES teachers ON DELETE CASCADE UNIQUE,
    tier VARCHAR NOT NULL DEFAULT 'basic',
    credits_remaining INT NOT NULL DEFAULT 50,
    credits_total INT NOT NULL DEFAULT 50,
    billing_cycle_start DATE,
    billing_cycle_end DATE
);

CREATE TABLE credit_transactions (
    transaction_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id UUID REFERENCES credit_accounts,
    action VARCHAR NOT NULL,
    credits_spent INT NOT NULL,
    assignment_id UUID,
    refunded BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================
-- ACCOMMODATIONS
-- ============================================
CREATE TABLE accommodation_profiles (
    profile_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    teacher_id UUID REFERENCES teachers ON DELETE CASCADE,
    name VARCHAR NOT NULL,
    type VARCHAR NOT NULL,  -- 'iep', '504', 'ell', 'gifted', 'custom'
    modifications JSONB NOT NULL,
    is_default BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE student_accommodations (
    record_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    teacher_id UUID REFERENCES teachers ON DELETE CASCADE,
    class_id UUID REFERENCES classes,
    student_code VARCHAR NOT NULL,
    profile_id UUID REFERENCES accommodation_profiles,
    custom_overrides JSONB,
    notes TEXT
);

-- ============================================
-- EVENTS (Dev event bus — replaced by SQS in prod)
-- ============================================
CREATE TABLE events (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type VARCHAR NOT NULL,
    payload JSONB,
    status VARCHAR DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW(),
    processed_at TIMESTAMP
);

-- ============================================
-- SHARING
-- ============================================
CREATE TABLE share_links (
    share_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    teacher_id UUID REFERENCES teachers,
    assignment_id UUID REFERENCES assignments,
    token VARCHAR NOT NULL UNIQUE,
    remix_count INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================
-- ADMIN AUDIT LOG
-- ============================================
CREATE TABLE admin_audit_log (
    log_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    admin_email VARCHAR NOT NULL,
    action VARCHAR NOT NULL,
    target_type VARCHAR,
    target_id VARCHAR,
    metadata JSONB,
    ip_address VARCHAR,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================
-- SYSTEM ERRORS LOG
-- ============================================
CREATE TABLE system_errors (
    error_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    error_type VARCHAR NOT NULL,
    message TEXT NOT NULL,
    stack_trace TEXT,
    teacher_id UUID,
    context JSONB,
    severity VARCHAR DEFAULT 'error',
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================
-- SUBMISSIONS & GRADING
-- ============================================
CREATE TABLE submissions (
    submission_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    assignment_id UUID REFERENCES assignments(assignment_id),
    student_id UUID,
    student_name VARCHAR,
    submission_method VARCHAR,
    raw_file_url VARCHAR,
    ocr_responses JSONB,
    confidence_scores JSONB,
    flagged_questions JSONB,
    status VARCHAR DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE grades (
    grade_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    submission_id UUID REFERENCES submissions(submission_id),
    question_number INTEGER,
    student_response TEXT,
    correct_answer TEXT,
    points_earned DECIMAL,
    points_possible DECIMAL,
    feedback TEXT,
    needs_review BOOLEAN DEFAULT false,
    teacher_override BOOLEAN DEFAULT false
);

-- ============================================
-- STUDENT MASTERY TRACKING
-- ============================================
CREATE TABLE student_mastery (
    mastery_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id UUID,
    standard_id VARCHAR,
    total_questions INTEGER,
    correct_questions INTEGER,
    mastery_percentage DECIMAL,
    last_assessed TIMESTAMP DEFAULT NOW(),
    trend VARCHAR
);

-- ============================================
-- ANALYTICS
-- ============================================
CREATE TABLE analytics_snapshots (
    snapshot_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    class_id UUID,
    snapshot_date DATE,
    period_type VARCHAR DEFAULT 'daily',
    aggregated_data JSONB,
    insights JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE standard_mastery_history (
    history_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    class_id UUID,
    standard_code VARCHAR,
    date DATE,
    mastery_percent DECIMAL
);
