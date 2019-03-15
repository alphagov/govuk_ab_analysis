WITH
  -- for all sessions between START_DATE and END_DATE, for each content ID viewed, get the
  -- lowest hitNumber in that session when it was viewed (because we want to see what pages
    -- were viewed after what other pages)
  -- we could try getting all hitNumbers each piece of content was viewed at, e.g. a session
  -- includes page X -> page Y -> page X, does that mean we should recommmend page Y on page X, and vice versa?
  session_pages AS (
  SELECT
    CONCAT(fullVisitorId,"-",CAST(visitId AS STRING)) AS sessionId,
    content_id,
    MIN(hitNumber) AS hitNumber,
    -- is_news_item based on news_and_communications supergroup here https://docs.publishing.service.gov.uk/document-types/content_purpose_supergroup.html
    -- we only want to recommend news items on news item pages, not on any other pages
    MAX(IF(document_type IN ('medical_safety_alert',
          'drug_safety_update',
          'news_article',
          'news_story',
          'press_release',
          'world_location_news_article',
          'world_news_story',
          'fatality_notice',
          'tax_tribunal_decision',
          'utaac_decision',
          'asylum_support_decision',
          'employment_appeal_tribunal_decision',
          'employment_tribunal_decision',
          'service_standard_report',
          'cma_case',
          'decision',
          'oral_statement',
          'written_statement',
          'authored_article',
          'correspondence',
          'speech',
          'government_response'),
        1,
        0)) AS is_news_item,
    -- we don't want to recommend consultations for any pages
    MAX(IF(document_type IN ('consultation_outcome',
          'closed_consultation',
          'open_consultation'),
        1,
        0)) AS is_consultation_item
  FROM (
    SELECT
      fullVisitorId,
      visitId,
      hits.hitNumber AS hitNumber,
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
    -- document types we don't want to generate related links for, or recommend as related links
    AND document_type NOT IN (
      -- "finding" pages https://docs.publishing.service.gov.uk/document-types/user_journey_document_supertype.html
      'document_collection',
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
      'topical_event',
      -- filter out fatality notices here
      'fatality_notice',
      -- filter out contact pages e.g. https://www.gov.uk/government/organisations/hm-revenue-customs/contact/creative-industry-tax-reliefs
      'contact',
      -- filter out service sign in pages e.g. https://www.gov.uk/personal-tax-account/sign-in/prove-identity
      'service_sign_in',
      -- filter out html publications? instead of recommending https://www.gov.uk/government/publications/rates-and-allowances-national-insurance-contributions/rates-and-allowances-national-insurance-contributions
      -- should we be recommending https://www.gov.uk/government/publications/rates-and-allowances-national-insurance-contributions ?
      'html_publication',
      -- exclude calculator pages like https://www.gov.uk/child-benefit-tax-calculator/main ?
      'calculator',
      -- exclude completed transactions like https://www.gov.uk/done/vehicle-tax
      'completed_transaction' )
    -- pages we don't want to generate related links for, or recommend as related links
    AND content_id NOT IN (
      -- null content IDs
      '00000000-0000-0000-0000-000000000000',
      '[object Object]',
      -- manual exclusions
      -- /apply-for-bankruptcy
      '92ac7166-6cb3-426e-b72a-c8d12236abdf',
      -- view-driving-license
      'bee455d5-5a4f-440a-88be-eb65ae8fde7d',
      -- /being-taken-to-employment-tribunal-by-employee
      '0d12a2da-7c52-4cd9-82ef-0cca0b51b880',
      -- /employment-tribunals
      '2ccfd2a9-5220-48c4-8fdc-166c390ccfac',
      -- /staying-uk-eu-citizen
      'b51139f9-8da7-4e97-ad5d-d91c73d5b5b2',
      -- /report-driving-medical-condition
      'eee83e1d-c3c5-45a7-8717-31394d3e4a1c',
      -- /check-flood-risk
      '2b3617a4-3230-46bd-b7a9-9dbea78508b4')
  GROUP BY
    sessionId,
    content_id),
  -- join session_pages to itself, to get pairs of pages page_1 and page_2, and a count of how
  -- many session included page_2 being viewed in the same session (but after, as the hitNumber is greater) as page_1
  co_occurrences_table AS (
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
    -- page 2 should first be viewed after page 1 is first viewed
    AND session_pages_1.hitNumber < session_pages_2.hitNumber
    -- either the page and the related link are both news items, or the related link is not a news item (we can recommend non news items on news pages, but not vice versa)
    AND (session_pages_2.is_news_item = 0
      OR (session_pages_2.is_news_item = 1
        AND session_pages_1.is_news_item = 1))
    -- don't recommend consultatio pages
    AND session_pages_2.is_consultation_item = 0
  GROUP BY
    page_1,
    page_2 ),
  -- get the total co_occurrences for each page_1 across all page_2s
  occurrences_per_page_1 AS (
  SELECT
    page_1,
    SUM(co_occurrences) AS page_1_occurrences
  FROM
    co_occurrences_table
  GROUP BY
    page_1 ),
  -- get the total co_occurrences for each page_2 across all page_1s
  occurrences_per_page_2 AS (
  SELECT
    page_2,
    SUM(co_occurrences) AS page_2_occurrences
  FROM
    co_occurrences_table
  GROUP BY
    page_2 ),
  -- bring together co_occurrences, page_1_occurrences, page_2_occurrences, and the total of
  -- all co_occurrences in the table, all for each page_1 page_2 pair, as we'll need these for our LLR calculations
  occurrence_counts AS (
  SELECT
    co_occ.page_1,
    co_occ.page_2,
    co_occ.co_occurrences,
    occ_per_page_1.page_1_occurrences page_1_occurrences,
    occ_per_page_2.page_2_occurrences AS page_2_occurrences,
    (
    SELECT
      SUM(co_occurrences)
    FROM
      co_occurrences_table ) AS total_occurrences
  FROM
    co_occurrences_table AS co_occ
  JOIN
    occurrences_per_page_1 occ_per_page_1
  ON
    co_occ.page_1 = occ_per_page_1.page_1
  JOIN
    occurrences_per_page_2 occ_per_page_2
  ON
    co_occ.page_2 = occ_per_page_2.page_2 ),
  -- calculate LLR scores for each page_1 page_2 pair, using the descripton and
  -- notation from this blog http://tdunning.blogspot.com/2008/03/surprise-and-coincidence.html
  llr_scores AS (
  SELECT
    page_1,
    page_2,
    k11,
    page_1_occurrences,
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
    2*(H_k - H_rowsums_k - H_colsums_k) AS llr_score
  FROM (
    SELECT
      page_1,
      page_2,
      k11,
      -- k12,
      -- k21,
      -- k22,
      N,
      k11_k21 AS page_1_occurrences,
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
  -- output up to 100 links per page_1, ranked in order of llr_score - we want to recommend the highest scoring page_2s
SELECT
  page_1,
  page_2,
  page_1_occurrences,
  co_occurrences,
  llr_score,
  rank
FROM (
  SELECT
    page_1,
    page_2,
    page_1_occurrences,
    k11 AS co_occurrences,
    llr_score,
    RANK() OVER (PARTITION BY page_1 ORDER BY CAST(llr_score AS numeric) DESC) AS rank
  FROM
    llr_scores )
WHERE
  rank < 101
ORDER BY
  page_1,
  rank