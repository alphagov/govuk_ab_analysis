#!/usr/bin/env python3
import sys
# .. other safe imports
try:
    import os
    import pandas as pd
    import random
    from numpy.random import choice
    # other unsafe imports
except ImportError:
    print("Error: missing one of the libraries (pandas, random or numpy)")
    sys.exit()


REQUIRED_COLUMNS = ["Occurrences", "ABVariant", "Sequence", 'Page_Event_List',
                    'Page_List', 'PageSequence', 'Event_List',
                    'num_event_cats', 'Event_cats_agg', 'Event_cat_act_agg']

DATA_DIR = os.getenv("DATA_DIR")


def sample_processed_journey(filename, seed=1337, k=1000, with_replacement=True):
    """
    Samples from processed journey files.

    Samples with replacement from govuk-network-data processed journey files. The probability of a
    user journey Sequence of pages visited and events being sampled is weighted by the number of occurrences of
    that Sequence. This outputs a pandas Dataframe into the sampled_journey directory.

    Parameters:
        filename (str): The filename of the processed journey.
        seed (int): The random seed for reproducibility.
        k (int): The output shape.
        with_replacement (bool): Whether the sample is with or without replacement.

    Returns:
       pandas.core.frame.DataFrame: A sampled data frame.
    """

    path = os.path.join(DATA_DIR, "processed_journey", filename, ".csv.gz")

    print("Reading in file...")

    df = pd.read_csv(path, sep='\t')

    print("Finished reading, now sampling...")

    # create list of row indexes, a bag to draw from
    elements = list(df.index.values)

    # need weights as probabilities, should sum to one, more occurrences more probable
    total_occur = sum(df.Occurrences)
    weights = df.Occurrences / total_occur

    # reproducible
    random.seed(seed)

    # size should be an arg, what is the desired sample size we are after?
    # this will need to consider each day, and what day of the week it is
    # so the user provides N, N is split into the appropriate proportions for each day
    # as an mvp the user could provide a list of proportions for each filename
    # or we could expect to get 7 filenames, and then hard code the sizes
    # to abstract away this complexity
    our_sample = choice(a=elements, size=k, p=weights, replace=with_replacement)

    # select rows and set occurrences to one
    df_sampled = df.iloc[our_sample]

    # set all rows of Occurrences col to one
    # df_sampled.loc[:, "Occurrences"] = 1
    df_sampled.assign(Occurrences=1)

    # return something to show it's worked
    print(df_sampled.info())
    print(df_sampled.shape())

    print("Saving to data/sampled_journey")
    # slow and too big, need to roll up


def main(filename):
    sample_processed_journey(filename)


if __name__ == "main":
    main(sys.argv[1])  # The 0th arg is the module filename
