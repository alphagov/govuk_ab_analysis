-- for each day queried, returns counts of:
-- visitors
-- visitors_that_clicked related links on pages that didn't have manually curated related links
-- visitors_2_or_more related links that day
-- visitors_that_clicked_navigation elements - home link, breadcrumbs, and "Explore this topic" links
-- visitors_that_used_search

-- uses data created by notebooks/2021_tests/get pages with manually curated links.ipynb 
-- that returns all the content items that have manually curated related links, this snapshot was
-- uplaoded to BigQuery as `govuk-bigquery-analytics.datascience.manual_related_links_pages`

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
      index=4) AS content_id
    FROM `govuk-bigquery-analytics.87773428.ga_sessions_*` AS sessions
    CROSS JOIN
    UNNEST(sessions.hits) AS hits
    WHERE
     _TABLE_SUFFIX BETWEEN '20211124'
     AND '20211125'
    ),

per_visitor_table AS (
    SELECT
    date,
    fullVisitorId,
    COUNT(DISTINCT 
        CASE WHEN eventCategory = 'relatedLinkClicked'
        AND CONTAINS_SUBSTR(eventAction, 'Related content') 
        AND content_id NOT IN (
            SELECT content_id 
            -- list of content IDs with manually curated related links, generated using notebooks/2021_tests/get pages with manually curated links.ipynb
            FROM `govuk-bigquery-analytics.datascience.manual_related_links_pages`)
        THEN CONCAT(visitNumber,'-',hitNumber) END) AS number_rl_clicked,

    MAX(CASE WHEN (eventCategory IN ('breadcrumbClicked', 'homeLinkClicked')
        OR (eventCategory = 'relatedLinkClicked' 
            AND CONTAINS_SUBSTR(eventAction, 'Explore the topic')))
        AND content_id NOT IN (
            SELECT content_id 
            -- list of content IDs with manually curated related links, generated using notebooks/2021_tests/get pages with manually curated links.ipynb
            FROM `govuk-bigquery-analytics.datascience.manual_related_links_pages`)
        THEN 1 ELSE 0 END) AS navigation_clicked,

    MAX(CASE WHEN hit_type = 'PAGE' AND STARTS_WITH(pagePath, '/search?q=')
        THEN 1 ELSE 0 END) AS search_used,
    FROM
        relevant_fields
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
visitors_that_clicked_rl / visitors * 100 AS pc_visitors_used_rl,
visitors_2_or_more_rl / visitors * 100 AS pc_visitors_2_or_more_rl,
visitors_2_or_more_rl / visitors_that_clicked_rl * 100 AS pc_visitors_returning_to_rl,
visitors_that_clicked_navigation / visitors * 100 AS pc_visitors_that_clicked_navigation,
visitors_that_used_search / visitors * 100 AS pc_visitors_that_used_search
FROM
counts