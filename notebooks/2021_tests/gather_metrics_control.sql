-- create time-series to use as control 

-- for each day queried, returns counts of:
-- visitors
-- visitors_that_clicked related links on pages that didn't have manually curated related links
-- visitors_2_or_more related links that day
-- visitors_that_clicked_navigation elements - home link, breadcrumbs, and "Explore this topic" links
-- visitors_that_used_search

-- uses data created by notebooks/2021_tests/get pages with manually curated links.ipynb 
-- that returns all the content items that have manually curated related links, this snapshot was
-- uplaoded to BigQuery as `govuk-bigquery-analytics.datascience.manual_related_links_pages`
-- removed "finder" as otherwise we wouldn't have internal page results

DECLARE NO_N2V_DOCS ARRAY <STRING>;
SET NO_N2V_DOCS = ["html_publication","homepage","organisation","mainstream_browse_page","coronavirus_landing_page","travel_advice_index","service_sign_in","step_by_step_nav","topic"];

CREATE OR REPLACE TABLE `govuk-bigquery-analytics.datascience.control_manual_links_20211011_20211215_data` AS

WITH relevant_fields AS (
    SELECT
    date,
    fullVisitorId,
    visitNumber,
    hits.hitNumber AS hitNumber,
    hits.type AS hit_type,
    hits.page.pagePath AS pagePath,
    hits.eventInfo.eventCategory AS eventCategory,
    hits.eventInfo.eventAction AS eventAction,
    (SELECT
      value
    FROM
      hits.customDimensions
    WHERE
      index=4) AS content_id,
    (SELECT
      value
    FROM
      hits.customDimensions
    WHERE
      index=2) AS doc_type
    FROM `govuk-bigquery-analytics.87773428.ga_sessions_*` AS sessions
    CROSS JOIN
    UNNEST(sessions.hits) AS hits
    WHERE
     _TABLE_SUFFIX BETWEEN '20211011'
     AND '20211215'
    ),

-- flag hits
flagged_hits AS (
    SELECT 
        *,
        CASE WHEN content_id IN (SELECT content_id FROM `govuk-bigquery-analytics.datascience.manual_related_links_pages`) 
            OR doc_type IN UNNEST(NO_N2V_DOCS) THEN 1
        ELSE 0 
        END AS no_n2v_rl_pages 
    FROM relevant_fields 
),

-- count sessions length and number of non n2v (vs n2v pages)
counts_hits AS (
    SELECT 
        date,
        fullVisitorId,
        COUNT(*) as number_of_hits,
        SUM(no_n2v_rl_pages) AS number_of_non_n2v_hits
    FROM flagged_hits
    GROUP BY fullVisitorId, date
),

purely_non_n2v_visitors AS (
    SELECT DISTINCT date, fullVisitorId
    FROM counts_hits
    WHERE number_of_non_n2v_hits = number_of_hits
),

per_visitor_table AS (
    SELECT
    date,
    fullVisitorId,
    COUNT(DISTINCT 
        CASE WHEN eventCategory = 'relatedLinkClicked'
        AND CONTAINS_SUBSTR(eventAction, 'Related content') 
        THEN CONCAT(visitNumber,'-',hitNumber) END) AS number_rl_clicked,

    MAX(CASE WHEN (eventCategory IN ('breadcrumbClicked', 'homeLinkClicked')
        OR (eventCategory = 'relatedLinkClicked' 
            AND CONTAINS_SUBSTR(eventAction, 'Explore the topic')))
        THEN 1 ELSE 0 END) AS navigation_clicked,

    MAX(CASE WHEN hit_type = 'PAGE' AND STARTS_WITH(pagePath, '/search?q=')
        THEN 1 ELSE 0 END) AS search_used,
    FROM
        relevant_fields
    INNER JOIN purely_non_n2v_visitors USING (date, fullVisitorId)
    GROUP BY
    date,
    fullVisitorId
),

counts AS (
    SELECT 
    date,
    COUNT(DISTINCT fullVisitorId) AS visitors,
    -- shall we also look at proportion of visitors that clicked related links more than once?
    -- indicates the first link was good enough quality for them to not lose confidence in recommendations
    COUNT(DISTINCT CASE WHEN number_rl_clicked > 0 THEN fullVisitorId END) AS visitors_that_clicked_rl,
    COUNT(DISTINCT CASE WHEN number_rl_clicked > 1 THEN fullVisitorId END) AS visitors_2_or_more_rl,
    -- clicking breadcrumbs, a link to the homepage, or "Explore the topic" links 
    -- indicate a user may not be finding what they are looking for and related links aren't helpful to them
    SUM(navigation_clicked) AS visitors_that_clicked_navigation,
    COUNT(DISTINCT CASE WHEN number_rl_clicked > 0 AND navigation_clicked = 0 THEN fullVisitorId END) AS visitors_that_clicked_rl_and_no_nav,
    -- an increase in users searching may indicate that more users are lost and related links aren't helping
    SUM(search_used) AS visitors_that_used_search
    FROM per_visitor_table
    GROUP BY 
    date
)

SELECT
date,
visitors,
visitors_that_clicked_rl,
visitors_2_or_more_rl,
visitors_that_clicked_navigation,
visitors_that_clicked_rl_and_no_nav,
visitors_that_used_search,
-- proportions
ROUND(visitors_that_clicked_rl / visitors, 5) AS pc_visitors_used_rl,
ROUND(visitors_2_or_more_rl / visitors, 5)  AS pc_visitors_2_or_more_rl,
ROUND(visitors_2_or_more_rl / visitors_that_clicked_rl, 5) AS pc_visitors_returning_to_rl,
ROUND(visitors_that_clicked_navigation / visitors, 5)  AS pc_visitors_that_clicked_navigation,
ROUND(visitors_that_used_search / visitors, 5)  AS pc_visitors_that_used_search
FROM
counts
