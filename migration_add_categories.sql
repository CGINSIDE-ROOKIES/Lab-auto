-- legal_forms 테이블에 통합 분류·태그 컬럼 추가
ALTER TABLE legal_forms
  ADD COLUMN IF NOT EXISTS cat_large  TEXT,
  ADD COLUMN IF NOT EXISTS cat_medium TEXT,
  ADD COLUMN IF NOT EXISTS cat_small  TEXT,
  ADD COLUMN IF NOT EXISTS tag1       TEXT,
  ADD COLUMN IF NOT EXISTS tag2       TEXT,
  ADD COLUMN IF NOT EXISTS tag3       TEXT;
