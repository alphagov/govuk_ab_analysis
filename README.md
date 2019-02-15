# govuk_ab_analysis
Statistical tools to help analyse A/B tests of processed BigQuery user journey data.

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
                        full_sample_<<filename_prefix>>.csv.gz
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
and a combined file with the overall sample, saved as `full_sample_taxon_ab_2019.csv.gz` in `sampled_journey`.
                           