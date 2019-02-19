import sys
import os
import argparse
import glob
# import random
import logging.config
# .. other safe imports
try:
    import pandas as pd
    import numpy as np
    # from numpy.random import choice
    # other unsafe imports
except ImportError:
    logging.error("Missing pandas and/or numpy library")
    # raise ImportError("Missing pandas library")
    sys.exit()

logging.debug("other modules loaded")


# other cols we might want are:"Sequence", 'PageSequence', 'Event_List',
# 'num_event_cats', "Event_cats_agg"
REQUIRED_COLUMNS = ["Occurrences", "ABVariant", "Page_Event_List",
                    "Page_List",  "Event_cat_act_agg"]
# use this when you want to group by everything that isn't Occurrences
REQUIRED_COLUMNS_WITHOUT_OCC = [
    "ABVariant", "Page_Event_List", "Page_List",  "Event_cat_act_agg"]


def get_df_total_occurrences_per_variant(filepath):
    logger.info(f"reading in occurrences from {filepath}")
    df = pd.read_csv(filepath, sep="\t", usecols=["Occurrences", "ABVariant"])
    logger.info("getting total occurrences per variant for this file")
    total_occurrences = df.groupby('ABVariant').sum()
    return total_occurrences


def sample_one_file_processed_journey(
        data_dir, filepath, seed=1337, a_k=500, b_k=500,
        with_replacement=True):
    """
    Samples from processed journey file.

    Samples with replacement from govuk-network-data processed journey files. The probability of a
    user journey Sequence of pages visited and events being sampled is weighted by the number of occurrences of
    that Sequence. This outputs a pandas Dataframe into the sampled_journey directory.

    Parameters:
        data_dir: The directory processed_journey and sampled_journey can be
            found in
        filepath (str): The filepath of the processed journey, please include
            any .csv.gz etc extensions.
        seed (int): The random seed for reproducibility.
        a_k (int): The number of journeys in the sample for variant A.
        b_k (int): The number of journeys in the sample for variant B.
        with_replacement (bool): Whether the sample is with or without replacement.

    Returns:
       pandas.core.frame.DataFrame: A sampled data frame.
    """

    # having issue with global env, $PWD not recognised in pycharm, so can't use DATA_DIR
    # assume current work dir is project dir
    filename = os.path.basename(filepath)
    logger.info(f"Reading in file {filename}")
    df = pd.read_csv(filepath, sep='\t', usecols=REQUIRED_COLUMNS)
    logger.debug(f'{filename} DataFrame shape {df.shape}')

    logger.info("Finished reading, now removing any non A or B variants")
    # filter out any weird values like Object object, select useful cols
    clean_thin_df = df.query("ABVariant in ['A', 'B']")[REQUIRED_COLUMNS]
    logger.debug(f'Cleaned DataFrame shape {clean_thin_df.shape}')

    logger.info("Finished removing any non A or B variants, now sampling")
    # select rows at random
    a_df_sampled = clean_thin_df[clean_thin_df["ABVariant"] == 'A'].sample(
        n=a_k, replace=with_replacement, weights=clean_thin_df.Occurrences,
        random_state=seed)
    logger.debug(f'Sampled A variant DataFrame shape {a_df_sampled.shape}')

    b_df_sampled = clean_thin_df[clean_thin_df["ABVariant"] == 'B'].sample(
        n=b_k, replace=with_replacement, weights=clean_thin_df.Occurrences,
        random_state=seed)
    logger.debug(f'Sampled B variant DataFrame shape {b_df_sampled.shape}')

    # instead of setting all rows of Occurrences col to one, we can just group
    # by the other things and count the rows instead of summing
    # occurrences, to roll up data

    df_sampled = pd.concat([a_df_sampled, b_df_sampled])
    logger.debug(f'Overall sampled DataFrame shape {df_sampled.shape}')

    logger.info("rolling up data")

    df_sampled_grouped = df_sampled.groupby(
        REQUIRED_COLUMNS_WITHOUT_OCC).count().reset_index()

    logger.debug(f'Sampled and rolled up DataFrame shape '
                 f'{df_sampled_grouped.shape}')

    logger.info(f"Saving to data/sampled_journey/{filename}")
    out_path = os.path.join(data_dir, "sampled_journey", filename)
    df_sampled_grouped.to_csv(out_path, sep="\t", compression="gzip",
                              index=False)


def get_k_list_for_variant(k, variant, occurrences_df_list):
    """
    Get a list of floats, how many journeys we should take from each
        file to get a proportional sample for this variant
    :param int k: total number of occurrences we want for the variant
    :param str variant: the variant we want to look at, e.g. 'A', 'B'
    :param list occurrences_df_list: list of pandas DataFrames
    :return: (k_list, total_occurrences_list) -
        k_list is a list of floats, how many journeys we should take from each
        file to get a proportional sample for this variant
        total_occurrences_list is a list of the total number of occurrences
        for this variant per file
    """
    logger.info(f"get k_list for variant {variant}")
    total_occurrences_list = [
        df.at[variant, 'Occurrences'] for df in occurrences_df_list]
    total_occurrences_list = np.array(total_occurrences_list)
    total_occurrences = sum(total_occurrences_list)
    logger.info(f"{total_occurrences} total occurrences in these files")
    if k > total_occurrences:
        # raise a specific error as the required sample size is larger than the
        # total occurrences, and will the maths and rounding work
        # if k = total occurrences?
        raise ValueError('sample size is greater than total occurrences')

    k_list = total_occurrences_list * k / total_occurrences
    logger.debug(f"sample size from each file {k_list}")
    return k_list, total_occurrences_list


def sample_multiple_days_processed_journey(
        data_dir, filename_prefix, seed=1337, k=1000, with_replacement=True):
    """
    Samples from multiple processed journey files, to get one proportional
    sample of k journeys, saved in one file in the sampled_journey directory.
    First it samples each file beginning with filename_prefix in
    data_dir/processed_journey, then saves that file's sample in
    data_dir/sampled_journey, then takes all the files beginning with
    filename_prefix in data_dir/sampled_journey and combines them to get one
    sample file. Make sure there aren't any rogue files in
    data_dir/sampled_journey when you start!

    Parameters:
        data_dir: The directory processed_journey and sampled_journey can be
            found in
        filename_prefix (str): The filename prefix of the processed journeys,
            we will sample from all the days that start with this file prefix
            and end with .csv.gz that are found in data_dir/processed_journey.
        seed (int): The random seed for reproducibility.
        k (int): The number of journeys in the sample for each variant.
        with_replacement (bool): Whether the sample is with or without replacement.

    Returns:
       None
    """

    filepath_list = sorted(glob.glob(
        f'{data_dir}/processed_journey/{filename_prefix}*.csv.gz'))

    logger.info(f"work with files {filepath_list}")

    occurrences_df_list = [
        get_df_total_occurrences_per_variant(filepath) for filepath in
        filepath_list]

    a_k_list, a_occ_list = get_k_list_for_variant(k, 'A', occurrences_df_list)
    b_k_list, b_occ_list = get_k_list_for_variant(k, 'B', occurrences_df_list)

    a_b_occ_list = a_occ_list + b_occ_list
    logger.debug(f"A and B occurrences per file: {a_b_occ_list}")

    for filepath, a_k, b_k in zip(filepath_list, a_k_list, b_k_list):
        sample_one_file_processed_journey(
            data_dir, filepath, seed=seed, a_k=int(round(a_k)),
            b_k=int(round(b_k)), with_replacement=with_replacement)

    sampled_filepath_list = glob.glob(
        f'{data_dir}/sampled_journey/{filename_prefix}*.csv.gz')

    logger.info(f"Reading in all sampled journeys {sampled_filepath_list}")
    all_sample_df = pd.concat(
        [pd.read_csv(f, sep="\t") for f in sampled_filepath_list])

    logger.info("rolling up all sample DataFrame")
    grouped_all_sample_df = all_sample_df.groupby(
        REQUIRED_COLUMNS_WITHOUT_OCC).sum().reset_index()

    out_path = os.path.join(data_dir, "sampled_journey",
                            f"full_sample_{filename_prefix}_{k}.csv.gz")
    logger.info(f"Saving overall sample to {out_path}")
    grouped_all_sample_df.to_csv(
        out_path, sep="\t", compression="gzip", index=False)


# for each DF get total occurrences
# sum total occurrences
# for each DF, sample according to total occurrences, then save
# read all saved samples, create one sample file and save

# def main(filename):
#     sample_processed_journey(filename)


if __name__ == "__main__":  # our module is being executed as a program
    parser = argparse.ArgumentParser(
        description='Module for sampling processed data for an A/B test',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        'filename_prefix', help='''
        Prefix of files we want to sample. We will read from the 
        processed_journey directory from the DATA_DIR specified in you .envrc, 
        and write to the sampled_journey directory in DATA_DIR, the overall 
        sample will be saved as full_sample_<<filename_prefix>>_<<k>>.csv.gz
        ''')
    parser.add_argument(
        '--seed', help='''
        Seed for the random number generator for pandas.DataFrame.sample
        ''', default=1337, type=int)
    parser.add_argument(
        '--k', help='''
        number of journeys per variant you want in your sampled DataFrame
        ''', default=1000, type=int)

    # should we give people the opportunity to sample without replacement?
    parser.add_argument(
        '--with_replacement',
        help='do you want to sample with or without replacement?',
        default=True, type=bool)
    parser.add_argument(
        '--debug-level',
        help='debug level of messages (DEBUG, INFO, WARNING, etc...)',
        default="INFO")
    args = parser.parse_args()

    # Logger setup
    LOGGING_CONFIG = os.getenv("LOGGING_CONFIG")
    logging.config.fileConfig(LOGGING_CONFIG)
    logger = logging.getLogger('sample_processed_journey')
    logger.setLevel(getattr(logging, args.debug_level))

    DATA_DIR = os.getenv("DATA_DIR")
    logger.debug(f"data directory {DATA_DIR}")
    logger.debug(f"Args: seed={args.seed}, k={args.k}, "
                 f"with_replacement={args.with_replacement}")
    sample_multiple_days_processed_journey(
        DATA_DIR, args.filename_prefix, seed=args.seed, k=args.k,
        with_replacement=args.with_replacement)
