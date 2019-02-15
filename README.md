# govuk_ab_analysis
Statistical tools to help analyse A/B tests of processed BigQuery user journey data.

An analytical pipeline for analysing A/B test data output from this
 [GOV.UK data pipeline](https://github.com/alphagov/govuk-network-data).
  The data should be provided as one `processed_journey.csv.gz` file per day the test was run.
   This pipeline will then be `sample.py`'ed from those days provided to achieve a user defined sample size.
    This outputs a single `sampled_journey.csv.gz` file that is analysed with `analysis.py`. 
    This outputs the knowledge to inform a decision whether there was a difference between page variants A and B.
    
 ## Supported A/B analyses
 * Related links
    * events with category `relatedLinkClicked` and action`Related content`
    * The detailed reasoning behind this can be found
     [here](https://github.com/alphagov/govuk-network-data/pull/88/files#diff-815d8e4ad52e4baf14e58409ed32215f).
