import sys
import os
import argparse
import glob
# import random
import logging.config
# .. other safe imports
try:
    import pandas as pd
    # import numpy as np
    # from numpy.random import choice
    # other unsafe imports
except ImportError:
    logging.error("Missing pandas library")
    # raise ImportError("Missing pandas library")
    sys.exit()

logging.debug("other modules loaded")


# other cols we might want are:"Sequence", 'PageSequence', 'Event_List',
# 'num_event_cats', "Event_cats_agg"
REQUIRED_COLUMNS = ["Occurrences", "ABVariant", "Page_Event_List",
                    "Page_List",  "Event_cat_act_agg"
                    ]


def get_df_total_occurrences(filepath):
    df = pd.read_csv(filepath, sep="\t", usecols=["Occurrences"])
    total_occurrences = df.Occurrences.sum()
    return total_occurrences


def is_a_b(variant):
    """
    Is the value of the variant either 'A' or 'B'? Filters out junk data
    :param variant:
    :return: True or False
    """
    return any([variant == x for x in ['A', 'B']])


def sample_one_day_processed_journey(
        data_dir, filename, seed=1337, k=1000, with_replacement=True):
    """
    Samples from processed journey file.

    Samples with replacement from govuk-network-data processed journey files. The probability of a
    user journey Sequence of pages visited and events being sampled is weighted by the number of occurrences of
    that Sequence. This outputs a pandas Dataframe into the sampled_journey directory.

    Parameters:
        data_dir: The directory processed_journey and sampled_journey can be
            found in
        filename (str): The filename of the processed journey, please include
            any .csv.gz etc extensions.
        seed (int): The random seed for reproducibility.
        k (int): The output size.
        with_replacement (bool): Whether the sample is with or without replacement.

    Returns:
       pandas.core.frame.DataFrame: A sampled data frame.
    """

    # having issue with global env, $PWD not recognised in pycharm, so can't use DATA_DIR
    # assume current work dir is project dir
    in_path = os.path.join(data_dir, "processed_journey", filename)

    logger.info("Reading in file...")

    df = pd.read_csv(in_path, sep='\t', usecols=REQUIRED_COLUMNS)
    logger.debug(f'{filename} DataFrame shape {df.shape}')

    logger.info("Finished reading, now removing any non A or B variants")

    # filter out any weird values like Object object
    df["is_a_b"] = df["ABVariant"].map(is_a_b)
    df = df[df["is_a_b"]][REQUIRED_COLUMNS]
    logger.debug(f'Cleaned DataFrame shape {df.shape}')

    logger.info("Finished removing any non A or B variants, now sampling")

    # size should be an arg, what is the desired sample size we are after?
    # this will need to consider each day, and what day of the week it is
    # so the user provides N, N is split into the appropriate proportions for each day
    # as an mvp the user could provide a list of proportions for each filename
    # or we could expect to get 7 filenames, and then hard code the sizes
    # to abstract away this complexity
    # select rows at random
    df_sampled = df.sample(n=k, replace=with_replacement,
                           weights=df.Occurrences, random_state=seed)

    # instead of setting all rows of Occurrences col to one, we can just group
    # by the other things and count the rows instead of summing
    # occurrences, to roll up data
    # df_sampled.loc[:, "Occurrences"] = 1
    # df_sampled = df_sampled.assign(Occurrences=1)
    # df_sampled['Occurrences'] = 1

    logger.debug(f'Sampled DataFrame shape {df_sampled.shape}')

    logger.info("rolling up data")
    cols_without_occurrences = REQUIRED_COLUMNS.copy()
    cols_without_occurrences.remove("Occurrences")
    df_sampled_grouped = df_sampled.groupby(
        cols_without_occurrences).count().reset_index()

    logger.debug(f'Sampled and rolled up DataFrame shape '
                 f'{df_sampled_grouped.shape}')

    logger.debug("Saving to data/sampled_journey")

    out_path = os.path.join(data_dir, "sampled_journey", f"{filename}.csv.gz")
    df_sampled_grouped.to_csv(out_path, sep="\t", compression="gzip",
                              index=False)

    return None


def sample_multiple_days_processed_journey(
        data_dir, filename_prefix, seed=1337, k=1000, with_replacement=True):
    """
    Samples from multiple processed journey files, to get one proportional
    sample of k journeys, saved in one file in the sampled_journey directory.

    Parameters:
        data_dir: The directory processed_journey and sampled_journey can be
            found in
        filename_prefix (str): The filename of the processed journey.
        seed (int): The random seed for reproducibility.
        k (int): The number of journeys in the overall sample.
        with_replacement (bool): Whether the sample is with or without replacement.

    Returns:
       pandas.core.frame.DataFrame: A sampled data frame.
    """

    filepath_list = glob.glob(
        f'{data_dir}/processed_journey/{filename_prefix}*.csv.gz')
    total_occurrences_list = [
        get_df_total_occurrences(filepath) for filepath in filepath_list]
    total_occurrences = sum(total_occurrences_list)
    k_list = np.array(total_occurrences_list) * k / total_occurrences

    for filepath, k in zip(filepath_list, k_list):
        sample_one_day_processed_journey(
            data_dir, filepath, seed=seed, k=int(round(k)),
            with_replacement=with_replacement)

    return


# for each DF get total occurrences
# sum total occurrences
# for each DF, sample according to total occurrences, then save
# read all saved samples, create one sample file and save

# def main(filename):
#     sample_processed_journey(filename)


if __name__ == "__main__":  # our module is being executed as a program
    parser = argparse.ArgumentParser(
        description='Sampling processed data module')
    parser.add_argument(
        'filename', help='''
        Name of the file we want to sample. We will read from the 
        processed_journey directory in data, and write to the sampled_journey 
        directory
        ''')
    parser.add_argument(
        '--seed', help='seed for choosing sample', default=1337, type=int)
    parser.add_argument(
        '--k', help='number of journeys you want in your sampled dataframe',
        default=1000, type=int)

    # should we give people the opportunity to sample without replacement?
    parser.add_argument(
        '--with_replacement', default=True,
        help='do you want to sample with or without replacement?', type=bool)
    parser.add_argument('--debug-level', default="INFO",
                        help='debug level of messages (DEBUG, INFO, WARNING'
                             ' etc...)')
    args = parser.parse_args()

    # Logger setup
    LOGGING_CONFIG = os.getenv("LOGGING_CONFIG")
    logging.config.fileConfig(LOGGING_CONFIG)
    logger = logging.getLogger('sample_processed_journey')
    logger.setLevel(getattr(logging, args.debug_level))

    DATA_DIR = os.getenv("DATA_DIR")
    logger.debug("data directory" + DATA_DIR)

    print()
    logger.debug(f"Args: seed={args.seed}, k={args.k}, "
                 f"with_replacement={args.with_replacement}")
    sample_one_day_processed_journey(DATA_DIR, args.filename, seed=args.seed,
                             k=args.k, with_replacement=args.with_replacement)
    # main(sys.argv[1])  # The 0th arg is the module filename
