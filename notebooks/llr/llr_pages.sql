WITH session_pages AS (
  SELECT
    CONCAT(fullVisitorId,"-",CAST(visitId AS STRING)) AS sessionId,
    pagePath,
    pageTitle
  FROM (
    SELECT
      fullVisitorId,
      visitId,
      hits.page.pagePath AS pagePath,
      hits.page.pageTitle AS pageTitle,
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
    WHERE _TABLE_SUFFIX BETWEEN start_date
        AND end_date)
    WHERE pagePath != '/'
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
  GROUP BY
  sessionId,
  pagePath,
  pageTitle)


SELECT
  pagePath_1,
  pagePath_2,
  pageTitle_1,
  pageTitle_2,
  k11,
  k12,
  k21,
  k22,
  N,
  k11_k21,
  k11_k12,
  k21_k22,
  k12_k22,
  H_k,
  H_rowsums_k,
  H_colsums_k,
  2*N*(H_k - H_rowsums_k - H_colsums_k) AS llr_score
FROM (
  SELECT
  pagePath_1,
  pagePath_2,
  pageTitle_1,
  pageTitle_2,
  k11,
  k12,
  k21,
  k22,
  N,
  k11_k21,
  k11_k12,
  k21_k22,
  k12_k22,
  IF(k11>0,k11*log(k11/N),0) + IF(k12>0,k12*log(k12/N),0) + IF(k21>0,k21*log(k21/N),0) + IF(k22>0,k22*log(k22/N),0) AS H_k,
  k11_k12*log(k11_k12/N) + k21_k22*log(k21_k22/N) AS H_rowsums_k,
  k11_k21*log(k11_k21/N) + k12_k22*log(k12_k22/N) AS H_colsums_k
  FROM (
    SELECT
    pagePath_1,
    pagePath_2,
    pageTitle_1,
    pageTitle_2,
    co_occurrences AS k11,
    pagePath_1_occurrences AS  k11_k21,
    pagePath_2_occurrences AS k11_k12,
    pagePath_2_occurrences - co_occurrences AS k12,
    pagePath_1_occurrences - co_occurrences AS k21,
    total_occurrences - pagePath_2_occurrences - pagePath_1_occurrences + co_occurrences AS k22,
    total_occurrences - pagePath_2_occurrences AS k21_k22,
    total_occurrences - pagePath_1_occurrences AS k12_k22,
    total_occurrences AS N
    FROM (
      SELECT
      pagePath_1,
      pagePath_2,
      pageTitle_1,
      pageTitle_2,
      co_occurrences,
      SUM(co_occurrences) OVER (PARTITION BY pagePath_1) as pagePath_1_occurrences,
      SUM(co_occurrences) OVER (PARTITION BY pagePath_2) as pagePath_2_occurrences,
      SUM(co_occurrences) OVER () AS total_occurrences
      FROM
      (
        SELECT
        session_pages_1.pagePath as pagePath_1,
        session_pages_2.pagePath as pagePath_2,
        session_pages_1.pageTitle as pageTitle_1,
        session_pages_2.pageTitle as pageTitle_2,
        COUNT(DISTINCT session_pages_1.sessionId) as co_occurrences
        FROM session_pages session_pages_1
        JOIN session_pages session_pages_2
        ON session_pages_1.sessionId = session_pages_2.sessionId
        WHERE session_pages_1.pagePath != session_pages_2.pagePath
        AND session_pages_1.pageTitle != session_pages_2.pageTitle
        GROUP BY
        pagePath_1,
        pagePath_2,
        pageTitle_1,
        pageTitle_2
      )
      WHERE co_occurrences > 5
      -- BQ was freaking out about the total_occurrences calculation without this for data 20190218 to 20190221
    )
  )
)
ORDER BY llr_score desc


-- query to output a few ranked links per link
SELECT concat('https://www.gov.uk',pagePath_1) as page_1, 
concat('https://www.gov.uk',pagePath_2) as page_2, pageTitle_1, pageTitle_2, k11, llr_score, rank
from

(SELECT pagePath_1, pagePath_2, pageTitle_1, pageTitle_2, k11, llr_score,
RANK() OVER ( PARTITION BY pagePath_1 ORDER BY cast(llr_score as numeric) desc) AS rank
FROM `govuk-bigquery-analytics.87773428.temp_ss_llr`
)
where rank < 7
order by 
pagePath_1, rank