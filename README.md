# govuk_ab_analysis
> Statistical tools to help analyse A/B tests of processed BigQuery user journey data.

An analytical pipeline for analysing A/B test data output from this
 [GOV.UK data pipeline](https://github.com/alphagov/govuk-network-data).
  The data should be provided as one `processed_journey.csv.gz` file per day the test was run.
   This pipeline will then be `sample.py`'ed from those days provided to achieve a user defined sample size.
    This outputs a single `sampled_processed_journey.csv.gz` file that is analysed with `analysis.py`. 
    This outputs the knowledge to inform a decision whether there was a difference between page variants A and B.
    
 ## Supported A/B analyses
 * Related links
    * events with category `relatedLinkClicked` and action`Related content`
    * The detailed reasoning behind this can be found
     [here](https://github.com/alphagov/govuk-network-data/pull/88/files#diff-815d8e4ad52e4baf14e58409ed32215f).

An analytical pipeline for analysing A/B test data output from this [GOV.UK data pipeline](https://github.com/alphagov/govuk-network-data).

## Usage
This series of scripts has been built with Python 3.7.

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
#### Using the notebook
You can open the `generate_ab_rl_mvp.ipynb` notebook and adjust the `filename` therein.

#### Running the analysis module programmatically
In the console run the script and pass it the `filename` of the processed sampled dataframe found in the `sampled_journey` directory in DATA_DIR. 
You can also adjust the logging level for extra verbosity and detail as the derivation of metrics can take some time.
`src/analysis.py sampled_processed_journey.csv.gz --debug-level DEBUG`

This analyses and compares the difference of various metrics by page variant. 
 It outputs two `.csv.gz` into the `reports` dir. 
One containing the z proportion tests and the other the Bayesian bootstrap confidence intervals.
