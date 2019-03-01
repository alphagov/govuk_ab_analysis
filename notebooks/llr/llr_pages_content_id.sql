 WITH
  session_pages AS (
  SELECT
    CONCAT(fullVisitorId,"-",CAST(visitId AS STRING)) AS sessionId,
    content_id
  FROM (
    SELECT
      fullVisitorId,
      visitId,
      hits.page.pagePath AS pagePath,
      (
      SELECT
        value
      FROM
        hits.customDimensions
      WHERE
        index=4) AS content_id,
      (
      SELECT
        value
      FROM
        hits.customDimensions
      WHERE
        index=2) AS document_type
    FROM
      `govuk-bigquery-analytics.87773428.ga_sessions_*` AS sessions
    CROSS JOIN
      UNNEST(sessions.hits) AS hits
    WHERE
      _TABLE_SUFFIX BETWEEN '{START_DATE}'
      AND '{END_DATE}')
  WHERE
    pagePath != '/'
    AND document_type NOT IN ('document_collection',
      'finder',
      'homepage',
      'license_finder',
      'mainstream_browse_page',
      'organisation',
      'search',
      'service_manual_homepage',
      'service_manual_topic',
      'services_and_information',
      'taxon',
      'topic',
      'topical_event')
    AND content_id NOT IN ('00000000-0000-0000-0000-000000000000', '[object Object]')
  GROUP BY
    sessionId,
    content_id),
  occurrence_counts AS (
  SELECT
    page_1,
    page_2,
    co_occurrences,
    SUM(co_occurrences) OVER (PARTITION BY page_1) AS page_1_occurrences,
    SUM(co_occurrences) OVER (PARTITION BY page_2) AS page_2_occurrences,
    SUM(co_occurrences) OVER () AS total_occurrences
  FROM (
    SELECT
      session_pages_1.content_id AS page_1,
      session_pages_2.content_id AS page_2,
      COUNT(DISTINCT session_pages_1.sessionId) AS co_occurrences
    FROM
      session_pages session_pages_1
    JOIN
      session_pages session_pages_2
    ON
      session_pages_1.sessionId = session_pages_2.sessionId
    WHERE
      session_pages_1.content_id != session_pages_2.content_id
    GROUP BY
      page_1,
      page_2 )
--  WHERE co_occurrences > 1 
    ),
  llr_scores AS (
  SELECT
    page_1,
    page_2,
    k11,
    -- k12,
    -- k21,
    -- k22,
    -- N,
    -- k11_k21,
    -- k11_k12,
    -- k21_k22,
    -- k12_k22,
    -- H_k,
    -- H_rowsums_k,
    -- H_colsums_k,
    2*N*(H_k - H_rowsums_k - H_colsums_k) AS llr_score
  FROM (
    SELECT
      page_1,
      page_2,
      k11,
      -- k12,
      -- k21,
      -- k22,
      N,
      -- k11_k21,
      -- k11_k12,
      -- k21_k22,
      -- k12_k22,
      IF(k11>0,
        k11*LOG(k11/N),
        0) + IF(k12>0,
        k12*LOG(k12/N),
        0) + IF(k21>0,
        k21*LOG(k21/N),
        0) + IF(k22>0,
        k22*LOG(k22/N),
        0) AS H_k,
      k11_k12*LOG(k11_k12/N) + k21_k22*LOG(k21_k22/N) AS H_rowsums_k,
      k11_k21*LOG(k11_k21/N) + k12_k22*LOG(k12_k22/N) AS H_colsums_k
    FROM (
      SELECT
        page_1,
        page_2,
        co_occurrences AS k11,
        page_1_occurrences AS k11_k21,
        page_2_occurrences AS k11_k12,
        page_2_occurrences - co_occurrences AS k12,
        page_1_occurrences - co_occurrences AS k21,
        total_occurrences - page_2_occurrences - page_1_occurrences + co_occurrences AS k22,
        total_occurrences - page_2_occurrences AS k21_k22,
        total_occurrences - page_1_occurrences AS k12_k22,
        total_occurrences AS N
      FROM
        occurrence_counts ) ) )

  -- query to output a few ranked links per link
SELECT
  page_1,
  page_2,
  co_occurrences,
  llr_score,
  rank
FROM (
  SELECT
    page_1,
    page_2,
    k11 AS co_occurrences,
    llr_score,
    RANK() OVER (PARTITION BY page_1 ORDER BY CAST(llr_score AS numeric) DESC) AS rank
  FROM
    llr_scores )
WHERE
  rank < 11
ORDER BY
  page_1,
  rank
