# govuk_ab_analysis
> Statistical tools to help analyse A/B tests of processed BigQuery user journey data.

An analytical pipeline for analysing A/B test data output from this
 [GOV.UK data pipeline](https://github.com/alphagov/govuk-network-data).
  The data should be provided as one `processed_journey.csv.gz` file per day the test was run.
   This pipeline will then be `sample.py`'ed from those days provided to achieve a user defined sample size.
    This outputs a single `sampled_processed_journey.csv.gz` file that is analysed with `analysis.py`. 
    The analysis will check statistical assumptions for you and alert you if there is a problem.
    The script or notebook options outputs the information for a statistician to interpret. 
     This knowledge can inform a decision as to whether there was a difference between page variants A and B.

## Requirements
* Python 3.7
* See [base-requirements.txt](base-requirements.txt) for python dependencies.
* `document_types.csv.gz` in the `DATA_DIR/metadata` dir - essentially a lookup table, 
to work out from page document types whether those pages are "finding" pages or "thing" pages. 
See `notebooks/document_type_query.ipynb` for details.

## Preparing your python environment
Run `pip install -r requirements.txt` to install package dependencies. 

## Setting environment variables
A number of environment variables need to be set before running the modules on your system:

|ENV VAR|Description|Nominal value|
|---|---|---|
|DATA_DIR|Path to the directory storing the data|`./data` (relative to the root of the repository -- you may need to set an absolute path)|
|LOGGING_CONFIG|Path to the logging configuration file|`./logging.conf` (relative to the root of the repository -- you may need to set an absolute path)|
|REPORTS_DIR|Path to the reports dir where reports and outputs are stored| `./reports` (relative to the root of the repository -- you may need to set an absolute path)|
|BQ_KEY_DIR|Path to where your private key (.json) is. There should only be one key.|Not defined, you could point to the dir used in the data pipeline repo|
 
 ## Metadata required for analysis
Some of the metrics used in our analysis are derived from the types of pages that users visit;
 is a page a "finding" or a "thing"? Users need a contemporary lookup table to determine this.
`notebooks/document_type_query.ipynb` is a notebook with a query to work out from page document types whether those
pages are "finding" pages or "thing" pages,
 as detailed [here](https://docs.publishing.service.gov.uk/document-types/user_journey_document_supertype.html).
Rerun this query for the period you want to analyse an A/B test for to get information for all pages visited in that
period. The output file is then used to calculate our metrics. This file should be placed into `./data/metadata`.
 
 ## Supported A/B analyses
 * Related links
    * events with category `relatedLinkClicked` and action`Related content`
    * The detailed reasoning behind this can be found
     [here](https://github.com/alphagov/govuk-network-data/pull/88/files#diff-815d8e4ad52e4baf14e58409ed32215f),
      with derived metrics used to pose hypotheses given below:
        - Prop of journeys containing at least one related link
        - Average journey length
        - Proportion of journeys containing no navigation events

An analytical pipeline for analysing A/B test data output from this [GOV.UK data pipeline](https://github.com/alphagov/govuk-network-data).

### stratify journeys into loved/unloved
Loved journeys are those which include at least one loved page.
Unloved journeys do not contain any loved pages.

Loved pages are defined as any of:
- pages with related links present:
    - related_mainstream_content, 
    - ordered_related_items,  
    - part_of_step_navs or quick_links
- foreign-travel-advice pages
- hmrc_contact_pages  
- help pages
- premises-licence
- find-local-council
- smart answer

To produce the files for loved and unloved journeys, from all taxon_ab*.csv.gz files in processed_journey, run the
notebook: "get_unloved_and_loved_journeys.ipynb"

### sample_processed.py
```
usage: sample_processed.py [-h] [--seed SEED] [--k K]
                           [--with_replacement WITH_REPLACEMENT]
                           [--debug-level DEBUG_LEVEL]
                           filename_prefix
Module for sampling processed data for an A/B test

positional arguments:
  filename_prefix       Prefix of files we want to sample. We will read from
                        the processed_journey directory from the DATA_DIR
                        specified in you .envrc, and write to the
                        sampled_journey directory in DATA_DIR, the overall
                        sample will be saved as
                        full_sample_<<filename_prefix>>_<<k>>.csv.gz
optional arguments:
  -h, --help            show this help message and exit
  --seed SEED           Seed for the random number generator for
                        pandas.DataFrame.sample (default: 1337)
  --k K                 number of journeys per variant you want in your
                        sampled DataFrame (default: 1000)
  --with_replacement WITH_REPLACEMENT
                        do you want to sample with or without replacement?
                        (default: True)
  --debug-level DEBUG_LEVEL
                        debug level of messages (DEBUG, INFO, WARNING, etc...)
                        (default: INFO)
```

The columns from the original files that are included in the samples are: ["Occurrences", "ABVariant", 
"Page_Event_List", "Page_List",  "Event_cat_act_agg"] 

#### Example

```
python src/sample_processed.py taxon_ab_2019 --k 947858 --debug-level DEBUG
```

Our processed journey data from the [GOV.UK data pipeline](https://github.com/alphagov/govuk-network-data) 
is in the `processed_journey` directory in our DATA_DIR (as specified in our `.envrc` file). We want to sample from all
the files whose names begin with `taxon_ab_2019` and end with `.csv.gz`.

For this example we specify that we want 947858 journeys in each variant, a number we have come to after doing a 
power analysis (see `z_prop_test_power_analysis.Rmd`). And we've set the debug level to DEBUG to be extra verbose, so 
we can see what's going in more detail.

The output will be: samples for each file, saved under their names but in the `sampled_journey` directory in DATA_DIR, 
and a combined file with the overall sample, saved as `full_sample_taxon_ab_2019_947858.csv.gz` in `sampled_journey`.

Some rounding may result in a very small amount more or less than the k value being included in the final sample, so 
ideally specify a k a few journeys higher than the k you require.
                           
### analysis.py

```
usage: analysis.py [-h] [--alpha ALPHA] [--m M] [--boot_reps BOOT_REPS]
                   [--debug-level DEBUG_LEVEL]
                   filename

Analysing sampled processed data module

positional arguments:
  filename              Prefix of files we want to analyse without csv.gz
                        ending. We will read from the sampled_journey
                        directory from the DATA_DIR specified in your .envrc,
                        and write to the rl_sampled_processed_journey
                        directory in DATA_DIR, the two dataframes with
                        analyses outputs, will be saved as
                        bayesbootstrap_<<filename_prefix>>.csv.gz and
                        zprop_<<filename_prefix>>.csv.gz

optional arguments:
  -h, --help            show this help message and exit
  --alpha ALPHA         The false positive rate. With respect to hypothesis
                        tests , alpha refers to significance level, the
                        probability of making a Type I error.
  --m M                 The number of hypotheses tested. Given we are testing
                        4 null hypotheses we should control for multiple
                        comparisons, the simplest and most conservative
                        approach is to use the Bonferroni correction, alpha /
                        m. So 0.05 / 4 = 0.0125 = alpha_corrected The
                        Bonferroni correction can be used to adjust confidence
                        intervals. If one establishes m confidence intervals,
                        and wishes to have an overall confidence level of
                        1-alpha, each individual confidence interval can be
                        adjusted to the level of 1-(alpha/m).
  --boot_reps BOOT_REPS
                        The number of bootstrap replicates. The number of
                        times we draw n-1 times with replacement from a sample
                        and estimate a statistic. Monte Carlo sampling builds
                        an estimate of the sampling distribution by randomly
                        drawing a large number of samples of size boot_reps
                        from a population, and calculating for each one the
                        associated value of the statistic. In this module we
                        calculate the mean.
  --debug-level DEBUG_LEVEL
                        debug level of messages (DEBUG, INFO, WARNING etc...)
```

Our processed and sampled journey data from `sample_processed.py`, following the above example is
 `full_sample_taxon_ab_2019_947858.csv.gz` in `sampled_journey` in `DATA_DIR`.
 
When implementation this analysis for the first time it is recommended to use the notebook to take yourself through the 
thinking and analysis.  We deliberately leave in the function definitions to this end.
 The script contains the most up to date code. 
#### Using the notebook
You can open the `generate_ab_rl_mvp.ipynb` notebook and adjust the `filename` therein,
 to `full_sample_taxon_ab_2019_947858.csv.gz`. The bootstrap reps is set to a standard 10,000 and alpha  
 of 0.05 is automatically corrected to ~0.0125 after the Bon Ferroni correction of alpha / number of tests. 
 Prior to running the code you may want to uncomment the cell in section 6.1 Save, in case your kernel 
 crashes during bootstrapping.

#### Running the analysis module programmatically
In the console run the script and pass it the `filename` of the processed sampled dataframe found in the `sampled_journey` directory in DATA_DIR. 
The lookup table for page content document type also needs to be passed. See earlier in the README for getting this data. 
You can also adjust the logging level for extra verbosity and detail as the derivation of metrics can take some time. 
We suggest you leave the default settings for alpha, m and boot_reps.  

```
src/analysis.py sampled_processed_journey.csv.gz document_types.csv.gz --debug-level DEBUG
```

This analyses and compares the difference of various metrics by page variant. 
 It outputs two `.csv.gz`, one containing the z proportion tests and the other
  the Bayesian bootstrap confidence intervals.
