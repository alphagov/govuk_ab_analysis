import os
import sys
import argparse
import glob
import pandas as pd
import numpy as np
import ast
import re
import logging.config
# .. other safe imports
try:
    # z test
    from statsmodels.stats.proportion import proportions_ztest

    # bayesian bootstrap and vis
    import matplotlib.pyplot as plt
    import seaborn as sns
    import bayesian_bootstrap.bootstrap as bb
    from astropy.utils import NumpyRNGContext

    # progress bar
    from tqdm import tqdm

    # are these needed?
    from scipy import stats
    from collections import Counter
except ImportError:
    logging.error("Missing niche library")
    sys.exit()

logging.debug("other modules loaded")

# instantiate progress bar goodness
tqdm.pandas()

# cols for related links A/B tests
REQUIRED_COLUMNS = ["Occurrences", "ABVariant", "Page_Event_List",
                    "Page_List",  "Event_cat_act_agg"
                    ]


def is_a_b(variant):
    """
    Is the value of the variant either 'A' or 'B'? Filters out junk data
    :param variant:
    :return: True or False
    """
    return any([variant == x for x in ['A', 'B']])


def get_number_of_events_rl(event):
    """Counts events with category 'relatedLinkClicked' and action'Related content'."""
    if event[0][0] == 'relatedLinkClicked' and 'Related content' in event[0][1]:
        return event[1]
    return 0


def sum_related_click_events(event_list):
    return sum([get_number_of_events_rl(event) for event in event_list])


def is_related(x):
    """Compute whether a journey includes at least one related link click."""
    return x > 0


def compute_standard_error_prop_two_samples(x_a, n_a, x_b, n_b):
    """
    The standard error of the difference between two proportions is given by the square root of the variances.

    The square of the standard error of a proportion is known as the variance of proportion.
    The variance of the difference between two independent proportions is equal to the sum of the variances of the proportions of each sample.
    The variances are summed because each sample contributes to sampling error in the distribution of differences.

    """
    p1 = x_a / n_a
    p2 = x_b / n_b
    se = p1 * (1 - p1) / n_a + p2 * (1 - p2) / n_b
    return np.sqrt(se)


def zconf_interval_two_samples(x_a, n_a, x_b, n_b, alpha=0.05):
    """
    Gives two points, the lower and upper bound of a (1-alpha)% confidence interval.

    To calculate the confidence interval we need to know the standard error of the difference between two proportions.
    The standard error of the difference between two proportions is the combination of the standard error of two independent distributions, ES (p_a) and (p_b).

    If the CI includes one then we accept the null hypothesis at the defined alpha.
    """
    p1 = x_a / n_a
    p2 = x_b / n_b
    se = compute_standard_error_prop_two_samples(x_a, n_a, x_b, n_b)
    z_critical = stats.norm.ppf(1 - 0.5 * alpha)
    return p2 - p1 - z_critical * se, p2 - p1 + z_critical * se


# main
def analyse_sampled_processed_journey(data_dir, filename):
    """
        Conducts various A/B tests on one sampled processed journey file.

        This function is dependent on document_types.csv.gz existing in data/metadata dir.

        Parameters:
            data_dir: The directory processed_journey and sampled_journey can be
                found in.
            filename (str): The filename of the sampled processed journey, please include
            any .csv.gz etc extensions.
        Returns:
           pandas.core.frame.DataFrame: A data frame containing statistics of the A/B tests on various metrics.
        """
    logger.info(f"Analysing {filename} - calculating A/B test statistics...")

    in_path = os.path.join(data_dir, "sampled_journey", filename)

    logger.info("Reading in file...")

    df = pd.read_csv(in_path, sep='\t', usecols=REQUIRED_COLUMNS)

    logger.debug(f'{filename} DataFrame shape {df.shape}')

    logger.info("Finished reading, defensively removing any non A or B variants,"
                " in-case the user did not sample...")

    # filter out any weird values like Object object
    df["is_a_b"] = df["ABVariant"].map(is_a_b)
    # drop helper column
    df = df[df["is_a_b"]][REQUIRED_COLUMNS]
    logger.debug(f'Cleaned DataFrame shape {df.shape}')

    logger.info('Preparing variables / cols for analysis...')

    logger.debug('Convert three variables from str to list...')

    df['Event_cat_act_agg'] = df['Event_cat_act_agg'].progress_apply(ast.literal_eval)
    df['Page_Event_List'] = df['Page_Event_List'].progress_apply(ast.literal_eval)
    df['Page_List'] = df['Page_List'].progress_apply(ast.literal_eval)

    logger.debug('Create Page_Length_List col...')

    df['Page_List_Length'] = df['Page_List'].progress_apply(len)

    logger.info('Reading in Page metadata...')

    metadata_path = os.path.join(
        data_dir, 'metadata',
        'document_types.csv.gz')

    df_finding_thing = pd.read_csv(metadata_path, sep="\t", compression="gzip")

    logger.info('Creating thing and finding thing lists...')

    thing_page_paths = df_finding_thing[
        df_finding_thing['is_finding'] == 0]['pagePath'].tolist()

    finding_page_paths = df_finding_thing[
        df_finding_thing['is_finding'] == 1]['pagePath'].tolist()

    logger.info('Related link preparation...')
    logger.debug('Get the number of related links clicks per Sequence')
    df['Related Links Clicks per seq'] = df['Event_cat_act_agg'].progress_map(sum_related_click_events)
    df["Has_Related"] = df["Related Links Clicks per seq"].map(is_related)
    df['Related Links Clicks row total'] = df['Related Links Clicks per seq'] * df['Occurrences']

    out_path = os.path.join(REPORTS_DIR, f"{filename}")
    logger.info(f"Saving to {out_path}")
    # df_ab.to_csv(out_path, sep="\t", compression="gzip", index=False)

    return None


if __name__ == "__main__":  # our module is being executed as a program
    parser = argparse.ArgumentParser(
        description='Analysing sampled processed data module')
    parser.add_argument(
        'filename', help='''
        Name of the sampled file we want to analyse 
        without .csv.gz suffix. We will read from the 
        sampled_journey directory in data, and write to the reports 
        directory.
        ''')
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
    REPORTS_DIR = os.getenv("REPORTS_DIR")
    logger.debug("data directory" + DATA_DIR)

    print()
    analyse_sampled_processed_journey(DATA_DIR, args.filename)
