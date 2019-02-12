import sys
import os
import argparse
# import random
import logging
# .. other safe imports
try:
    import pandas as pd
    import numpy as np
    from numpy.random import choice
    # other unsafe imports
except ImportError:
    print("Error: missing one of the libraries (pandas or numpy)")
    sys.exit()

print("other modules loaded")

REQUIRED_COLUMNS = ["Occurrences", "ABVariant", 'Page_Event_List',
                    "Page_List",  "Event_cat_act_agg"
                    # ,"Sequence", 'PageSequence', 'Event_List',
                    # 'num_event_cats', "Event_cats_agg"
                    ]


def is_a_b(variant):
    """
    Is the value of the variant either 'A' or 'B'? Filters out junk data
    :param variant:
    :return: True or False
    """
    return any([variant == x for x in ['A', 'B']])


def sample_processed_journey(data_dir, filename, seed=1337, k=1000,
                             with_replacement=True):
    """
    Samples from processed journey files.

    Samples with replacement from govuk-network-data processed journey files. The probability of a
    user journey Sequence of pages visited and events being sampled is weighted by the number of occurrences of
    that Sequence. This outputs a pandas Dataframe into the sampled_journey directory.

    Parameters:
        data_dir: The directory processed_journey and sampled_journey can be
            found in
        filename (str): The filename of the processed journey.
        seed (int): The random seed for reproducibility.
        k (int): The output size.
        with_replacement (bool): Whether the sample is with or without replacement.

    Returns:
       pandas.core.frame.DataFrame: A sampled data frame.
    """

    # having issue with global env, $PWD not recognised in pycharm, so can't use DATA_DIR
    # assume current work dir is project dir
    in_path = os.path.join(data_dir, "processed_journey", filename)
    # the above adds slashes, need separate for file type
    in_path = in_path + ".csv.gz"

    print("Reading in file...")

    df = pd.read_csv(in_path, sep='\t', usecols=REQUIRED_COLUMNS)

    print(df.info())

    print("Finished reading, now removing any non A or B variants")

    # filter out any values like Object object
    df['is_a_b'] = df['ABVariant'].map(is_a_b)
    df = df[df['is_a_b']][REQUIRED_COLUMNS]

    print(df.info())

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

    # return something to show it's worked
    print(df_sampled.info())

    print("rolling up data")
    cols_without_occurrences = REQUIRED_COLUMNS.copy()
    cols_without_occurrences.remove('Occurrences')
    df_sampled_grouped = df_sampled.groupby(
        cols_without_occurrences).count().reset_index()

    print(df_sampled_grouped.info())

    print("Saving to data/sampled_journey")

    out_path = os.path.join(data_dir, "sampled_journey", filename)
    out_path = out_path + ".csv.gz"
    df_sampled_grouped.to_csv(out_path, sep='\t', compression='gzip',
                              index=False)
    # slow and too big, need to roll up

    return None


print("function defined")


# def main(filename):
#     sample_processed_journey(filename)


if __name__ == "__main__":  # our module is being executed as a program
    parser = argparse.ArgumentParser(
        description='Sampling processed data module')
    parser.add_argument(
        'filename', help='''
        name of the file we want to sample, we add .csv.gz at the end so
        don\'t worry about that. We will read from the processed_journey
        directory in data, and write to the sampled_journey directory
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
    args = parser.parse_args()

    DATA_DIR = os.getenv("DATA_DIR")
    print(DATA_DIR)

    print(args.seed)
    print(args.k)
    sample_processed_journey(DATA_DIR, args.filename, seed=args.seed,
                             k=args.k, with_replacement=args.with_replacement)
    # main(sys.argv[1])  # The 0th arg is the module filename
