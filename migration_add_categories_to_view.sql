-- unified_forms 뷰에 카테고리·태그 컬럼 추가
-- legal_forms 행은 cat_large/medium/small, tag1/2/3 값을 가짐
-- gov_contracts 행은 NULL

CREATE OR REPLACE VIEW unified_forms AS
SELECT
  'legal_' || id::text   AS uid,
  source                 AS source_name,
  title                  AS form_title,
  file_format            AS doc_format,
  download_url,
  collected_at,
  cat_large,
  cat_medium,
  cat_small,
  tag1,
  tag2,
  tag3
FROM legal_forms

UNION ALL

SELECT
  'gov_' || id::text     AS uid,
  source                 AS source_name,
  file_name              AS form_title,
  file_format            AS doc_format,
  download_url,
  collected_at,
  NULL::text             AS cat_large,
  NULL::text             AS cat_medium,
  NULL::text             AS cat_small,
  NULL::text             AS tag1,
  NULL::text             AS tag2,
  NULL::text             AS tag3
FROM gov_contracts;
