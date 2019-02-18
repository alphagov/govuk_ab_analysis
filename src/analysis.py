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


def is_nav_event(event):
    """
    Return the total number of related links clicks for that row.

    Clicks per sequence multiplied by occurrences.
    """
    return any(
        ['breadcrumbClicked' in event, 'homeLinkClicked' in event,
         all(cond in event for cond in [
             'relatedLinkClicked', 'Explore the topic'])])


def count_nav_events(page_event_list):
    """
    Counts the number of nav events from a content page in a Page Event List.

    Helper function dependent on thing_page_paths instantiated in analyse_sampled_processed_journey.

    """
    content_page_nav_events = 0
    for pair in page_event_list:
        if is_nav_event(pair[1]):
            if pair[0] in thing_page_paths:
                content_page_nav_events += 1
    return content_page_nav_events


def count_search_from_content(page_list):
    """
    Counts the number of GOV.UK searches in the given journey.

    Helper function dependent on thing_page_paths instantiated in analyse_sampled_processed_journey.
    """
    search_from_content = 0
    for i, page in enumerate(page_list):
        if i > 0:
            if '/search?q=' in page:
                if page_list[i-1] in thing_page_paths:
                    search_from_content += 1
    return search_from_content


def z_prop(df, col_name):
    """
    Conduct z_prop test and generate confidence interval.

    Using Bernoulli trial terminology where X (or x)
    is number of successes and n is number of trials
    total occurrences, we compare ABVariant A and B.
    p is x/n. We use a z proportion test between variants.
    """
    # A & B
    n = df.Occurrences.sum()
    # prop of journeys with at least one related link, occurrences summed for those rows gives X
    p = df[df[col_name] == 1].Occurrences.sum() / n

    assert (p >= 0), "Prop less than zero!"
    assert (p <= 1), "Prop greater than one!"

    # A
    # number of trials for page A
    n_a = df[df.ABVariant == "A"].Occurrences.sum()
    # number of successes (occurrences), for page A and at least one related link clicked journeys
    x_a = df[(df['ABVariant'] == 'A') & (df[col_name] == 1)].Occurrences.sum()
    # prop of journeys where one related link was clicked, on A
    p_a = x_a / n_a

    # B
    # number of trials for page B
    n_b = df[df.ABVariant == "B"].Occurrences.sum()
    # number of successes for page B, at least one related link clicked
    x_b = df[(df['ABVariant'] == 'B') & (df[col_name] == 1)].Occurrences.sum()
    # prop of journeys where one related link was clicked, on B
    p_b = x_b / n_b

    assert (n == n_a + n_b), "Error in filtering by ABVariant!"

    # validate assumptions
    # The formula of z-statistic is valid only when sample size (n) is large enough.
    # nAp, nAq, nBp and nBq should be ≥ 5.
    # where p is probability of success (we can use current baseline)
    # q = 1 - p

    # tried a helper function here but it didn't work hence not DRY
    assert (n_a * p) >= 5, "Assumptions for z prop test invalid!"
    assert (n_a * (1 - p)) >= 5, "Assumptions for z prop test invalid!"

    assert (n_b * p) >= 5, "Assumptions for z prop test invalid!"
    assert (n_b * (1 - p)) >= 5, "Assumptions for z prop test invalid!"

    # using statsmodels
    # successes
    count = np.array([x_a, x_b])
    # number of trials
    nobs = np.array([n_a, n_b])
    # z prop test
    z, p_value = proportions_ztest(count, nobs, value=0, alternative='two-sided')
    # print(' z-stat = {z} \n p-value = {p_value}'.format(z=z,p_value=p_value))

    statsdict = {'metric_name': col_name, 'stats_method': 'z_prop_test',
                 'x_ab': x_a + x_b, 'n_ab': n, 'p': p,
                 'x_a': x_a, 'n_a': n_a, 'p_a': p_a,
                 'x_b': x_b, 'n_b': n_b, 'p_b': p_b,
                 'test_statistic': z, 'p-value': p_value}

    return statsdict


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

        As this takes some time to run ~ 1 hour, we output an additional dataframe as .csv.gz
        to the rl_sampled_processed dir as a side effect.
        This can allow the user to revisit the metrics
        at a later date without having to rerun the analysis.

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

    logger.info('Related link preparation...')
    logger.debug('Get the number of related links clicks per Sequence')
    df['Related Links Clicks per seq'] = df['Event_cat_act_agg'].progress_map(sum_related_click_events)
    logger.debug('Calculate number of related links per experimental unit.')
    df["Has_Related"] = df["Related Links Clicks per seq"].progress_map(is_related)
    df['Related Links Clicks row total'] = df['Related Links Clicks per seq'] * df['Occurrences']

    # needs finding_thing_df read in from document_types.csv.gz
    logger.info('Navigation events preparation...')
    df['Content_Page_Nav_Event_Count'] = df['Page_Event_List'].progress_map(count_nav_events)
    logger.info('Search events preparation...')
    df['Content_Search_Event_Count'] = df['Page_List'].progress_map(count_search_from_content)
    logger.debug('Calculating the ratio of clicks on navigation elements vs. clicks on related links')
    df['Ratio_Nav_Search_to_Rel'] = (df['Content_Page_Nav_Event_Count'] + df.Content_Search_Event_Count + 1) / (
                df['Related Links Clicks row total'] + 1)

    logger.info('All necessary variables derived for pending statistical tests...')

    logger.debug('Performing z_prop test on prop with at least one related link.')

    rl_stats = z_prop(df, 'Has_Related')
    # as it's one row needs to be a Series
    df_ab = pd.Series(rl_stats).to_frame().T
    logger.debug(df_ab)
    ci_low, ci_upp = zconf_interval_two_samples(rl_stats['x_a'], rl_stats['n_a'],
                                                rl_stats['x_b'], rl_stats['n_b'], alpha=0.01)
    logger.debug(' 95% Confidence Interval = ( {0:.2f}% , {1:.2f}% )'
                 .format(100 * ci_low, 100 * ci_upp))
    df_ab['ci_low'] = ci_low
    df_ab['ci_upp'] = ci_upp

    logger.debug('Performing z_prop test on prop with content page nav event.')

    nav_stats = z_prop(df, 'Content_Page_Nav_Event_Count')
    # concat rows
    df_ab_nav = pd.Series(nav_stats).to_frame().T
    logger.debug(df_ab_nav)
    ci_low, ci_upp = zconf_interval_two_samples(nav_stats['x_a'], nav_stats['n_a'],
                                                nav_stats['x_b'], nav_stats['n_b'], alpha=0.01)
    logger.debug(' 95% Confidence Interval = ( {0:.2f}% , {1:.2f}% )'
                 .format(100 * ci_low, 100 * ci_upp))
    # assign a dict to row of dataframe
    df_ab_nav['ci_low'] = ci_low
    df_ab_nav['ci_upp'] = ci_upp

    logger.debug('Joining dataframes.')

    df_ab = pd.concat([df_ab, df_ab_nav])

    logger.info('Saving df with related links derived variables to rl_sampled_processed_journey dir')
    out_path = os.path.join(DATA_DIR, "rl_sampled_processed_journey", f"{filename}")
    logger.info(f"Saving to {out_path}")
    df_ab.to_csv(out_path, compression="gzip", index=False)

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

    logger.info('Reading in Page metadata...')

    metadata_path = os.path.join(
        DATA_DIR, 'metadata',
        'document_types.csv.gz')

    logger.debug(f'Reading in metadata from {metadata_path}')
    df_finding_thing = pd.read_csv(metadata_path, sep="\t", compression="gzip")
    logger.debug(print('metadata head:', df_finding_thing.head(3)))

    logger.info('Creating thing and finding thing lists...')

    thing_page_paths = df_finding_thing[
        df_finding_thing['is_finding'] == 0]['pagePath'].tolist()

    finding_page_paths = df_finding_thing[
        df_finding_thing['is_finding'] == 1]['pagePath'].tolist()

    print()
    analyse_sampled_processed_journey(DATA_DIR, args.filename)
