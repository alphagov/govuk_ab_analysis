import os
import sys
import argparse
import pandas as pd
import numpy as np
import ast
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


def is_a_b(variant, variant_dict):
    """
    Is the value of the variant either 'A' or 'B'? Filters out junk data
    :param variant:
    :return: True or False
    """

    return any([variant == x for x in list(variant_dict.values())])


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
    Determine whether an event is navigation related.

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
    Counts the number of GOV.UK searches from a content page,
     as specified by the list of content pages, `thing_page_paths`.

    Helper function dependent on thing_page_paths instantiated in analyse_sampled_processed_journey.
    """
    search_from_content = 0
    for i, page in enumerate(page_list):
        if i > 0:
            if '/search?q=' in page:
                if page_list[i-1] in thing_page_paths:
                    search_from_content += 1
    return search_from_content

def count_total_searches(df, group):
    searches = df[df.ABVariant == group].groupby(
            'Content_Nav_or_Search_Count').sum().iloc[:, 0].reset_index(0)
    total_searches = searches['Content_Nav_or_Search_Count']*searches['Occurrences']
    return sum(total_searches)


def compare_total_searches(df, variant_dict):
    control = count_total_searches(df, variant_dict['CONTROL_GROUP'])
    intervention = count_total_searches(df, variant_dict['INTERVENTION_GROUP'])
    print("total searches in control group = {}".format(control))
    print("total searches in intervention group = {}".format(intervention))
    percent_diff = abs((intervention - control)/(control + intervention))*100
    
    if control>intervention:
        print("intervention has {} fewer navigation or searches than control;".format(control-intervention))
        
    if intervention>control:
        print("intervention has {} more navigation or searches than control;".format(intervention-control))
    
    print("a {0:.2f}% overall difference".format(percent_diff))
    print("The relative change was {0:.2f}% from control to intervention".format(
        ((intervention - control)/control)*100
    ))


def z_prop(df, col_name, variant_dict):
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
    n_a = df[df.ABVariant == variant_dict['CONTROL_GROUP']].Occurrences.sum()
    # number of successes (oc currences), for page A and at least one related link clicked journeys
    x_a = df[(df['ABVariant'] == variant_dict['CONTROL_GROUP']) & (df[col_name] == 1)].Occurrences.sum()
    # prop of journeys where one related link was clicked, on A
    p_a = x_a / n_a

    # B
    # number of trials for page B
    n_b = df[df.ABVariant == variant_dict['INTERVENTION_GROUP']].Occurrences.sum()
    # number of successes for page B, at least one related link clicked
    x_b = df[(df['ABVariant'] ==  variant_dict['INTERVENTION_GROUP']) & (df[col_name] == 1)].Occurrences.sum()
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
    The standard error of the difference between two proportions
     is given by the square root of the sum of the variances.

     The variance of the difference between two independent proportions is
      equal to the sum of the variances of the proportions of each sample,
       because each sample contributes to sampling error in the distribution of differences.
        var(A-B) = var(A) + ((-1)^2)*var(B)

    """

    p1 = x_a / n_a
    p2 = x_b / n_b
    se = p1 * (1 - p1) / n_a + p2 * (1 - p2) / n_b
    return np.sqrt(se)


def zconf_interval_two_samples(x_a, n_a, x_b, n_b, alpha=0.05):
    """
    Gives two points, the lower and upper bound of a (1-alpha)% confidence interval.

    To calculate the confidence interval we need to know the standard error of the difference between two proportions.
    The standard error of the difference between two proportions is the combination of the standard error
     of two independent distributions, ES (p_a) and (p_b).

    If the CI includes one then we accept the null hypothesis at the defined alpha.
    """
    p1 = x_a / n_a
    p2 = x_b / n_b
    se = compute_standard_error_prop_two_samples(x_a, n_a, x_b, n_b)
    z_critical = stats.norm.ppf(1 - 0.5 * alpha)
    return p2 - p1 - z_critical * se, p2 - p1 + z_critical * se


def mean_bb(counter_X_keys, counter_X_vals, n_replications):
    """Simulate the posterior distribution of the mean.
    Parameter X: The observed data (array like)
    Parameter n_replications: The number of bootstrap replications to perform (positive integer)
    Returns: Samples from the posterior
    """
    samples = []
    weights = np.random.dirichlet(counter_X_vals, n_replications)
    for w in weights:
        samples.append(np.dot(counter_X_keys, w))
    return samples


def bayesian_bootstrap_analysis(df, col_name=None, boot_reps=10000, seed=1337, variant_dict=None):
    """Run bayesian bootstrap on the mean of a variable of interest between Page Variants.

    Args:
        df: A rl_sampled_processed pandas Datframe.
        col_name: A string of the column of interest.
        boot_reps: An int of number of resamples with replacement.
        seed: A int random seed for reproducibility.
        variant_dict:dictionary containing letter codes for CONTROL_GROUP and INTERVENTION_GROUP

    Returns:
        a_bootstrap: a vector of boot_reps n resampled means from A.
        b_bootstrap: a vector of boot_reps n resampled means from B.
        """
    if variant_dict is None:
        variant_dict = {
            'CONTROL_GROUP':'B',
            'INTERVENTION_GROUP':'C'
        }
        logging.info('assigning defaults for variants: control group = "A" and intervention = "B"')

    with NumpyRNGContext(seed):
        A_grouped_by_length = df[df.ABVariant == variant_dict['CONTROL_GROUP']].groupby(
            col_name).sum().reset_index()
        B_grouped_by_length = df[df.ABVariant == variant_dict['INTERVENTION_GROUP']].groupby(
            col_name).sum().reset_index()
        a_bootstrap = mean_bb(A_grouped_by_length[col_name],
                              A_grouped_by_length['Occurrences'],
                              boot_reps)
        b_bootstrap = mean_bb(B_grouped_by_length[col_name],
                              B_grouped_by_length['Occurrences'],
                              boot_reps)

    return a_bootstrap, b_bootstrap


def bb_hdi(a_bootstrap, b_bootstrap, alpha=0.05):
    """Calculate a 1-alpha high density interval

    Args:
        a_bootstrap: a list of resampled means from page A journeys.
        b_bootstrap: a list of resampled means from page B journeys.
        alpha: false positive rate.

    Returns:
        a_ci_low: the lower point of the 1-alpha% highest density interval for A.
        a_ci_hi: the higher point of the 1-alpha% highest density interval for A.
        b_ci_low: the lower point of the 1-alpha% highest density interval for B.
        b_ci_hi: the higher point of the 1-alpha% highest density interval for B.
        ypa_diff_mean: the mean difference for the posterior between A's and B's distributions.
        ypa_diff_ci_low: lower hdi for posterior of the difference.
        ypa_diff_ci_hi: upper hdi for posterior of the difference.
        prob_b_>_a: number of values greater than 0 divided by num of obs for mean diff posterior. Or
        the probability that B's mean metric was greater than A's mean metric.
        """
    # Calculate a 95% HDI
    a_ci_low, a_ci_hi = bb.highest_density_interval(a_bootstrap, alpha=alpha)
    # Calculate a 95% HDI
    b_ci_low, b_ci_hi = bb.highest_density_interval(b_bootstrap, alpha=alpha)

    # calculate the posterior for the difference between A's and B's mean of resampled means
    # ypa prefix is vestigial from blog post
    ypa_diff = np.array(b_bootstrap) - np.array(a_bootstrap)
    ypa_diff_mean = ypa_diff.mean()
    # get the hdi
    ypa_diff_ci_low, ypa_diff_ci_hi = bb.highest_density_interval(ypa_diff, alpha=alpha)
    # We count the number of values greater than 0 and divide by the total number
    # of observations
    # which returns us the the proportion of values in the distribution that are
    # greater than 0
    p_value = (ypa_diff > 0).sum() / ypa_diff.shape[0]

    return {'a_ci_low': a_ci_low, 'a_ci_hi': a_ci_hi,
            'b_ci_low': b_ci_low, 'b_ci_hi': b_ci_hi,
            'diff_mean': ypa_diff_mean,
            'diff_ci_low': ypa_diff_ci_low, 'diff_ci_hi': ypa_diff_ci_hi,
            'prob_b_>_a': p_value}


# main
def analyse_sampled_processed_journey(data_dir, filename, alpha, boot_reps, variants):
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
            alpha: The corrected false positive rate.
            boot_reps: int of number of statistics generated from resampling to create distribution.
            variants: list containing two str elements defining the control and intervention group labels
        Returns:
           pandas.core.frame.DataFrame: A data frame containing statistics of the A/B tests on various metrics.
        """
    variant_dict = {
        'CONTROL_GROUP': variants[0],
        'INTERVENTION_GROUP': variants[1]
    }

    logger.info(f"Analysing {filename} - calculating A/B test statistics...")

    in_path = os.path.join(data_dir, "sampled_journey", filename)

    logger.info("Reading in file...")

    df = pd.read_csv(in_path, sep='\t', usecols=REQUIRED_COLUMNS)

    logger.debug(f'{filename} DataFrame shape {df.shape}')

    logger.info("Finished reading, defensively removing any non A or B variants,"
                " in-case the user did not sample...")

    # filter out any weird values like Object object
    df.query("ABVariant in @variants", inplace=True)

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
    logger.debug('Summing Nav and Search Events')
    df['Content_Nav_or_Search_Count'] = df['Content_Page_Nav_Event_Count'] + df['Content_Search_Event_Count']

    logger.debug('Sum content page nav event and search events, then multiply by occurrences for row total.')
    df['Content_Nav_Search_Event_Sum_row_total'] = df['Content_Nav_or_Search_Count'] * df['Occurrences']
    logger.debug('Calculating the ratio of clicks on navigation elements vs. clicks on related links')
    # avoid NaN with +1
    df['Ratio_Nav_Search_to_Rel'] = (df['Content_Nav_Search_Event_Sum_row_total'] + 1) / \
                                    (df['Related Links Clicks row total'] + 1)

    # if (Content_Nav_Search_Event_Sum == 0) that's our success
    # Has_No_Nav_Or_Search will equal 1, that's our success, works with z_prop function
    df['Has_No_Nav_Or_Search'] = df['Content_Nav_Search_Event_Sum_row_total'] == 0

    logger.info('All necessary variables derived for pending statistical tests...')

    logger.debug('Performing z_prop test on prop with at least one related link.')

    rl_stats = z_prop(df, 'Has_Related', variant_dict)
    # as it's one row needs to be a Series
    df_ab = pd.Series(rl_stats).to_frame().T
    logger.debug(df_ab)
    ci_low, ci_upp = zconf_interval_two_samples(rl_stats['x_a'], rl_stats['n_a'],
                                                rl_stats['x_b'], rl_stats['n_b'], alpha=alpha)
    logger.debug(' 95% Confidence Interval = ( {0:.2f}% , {1:.2f}% )'
                 .format(100 * ci_low, 100 * ci_upp))
    df_ab['ci_low'] = ci_low
    df_ab['ci_upp'] = ci_upp

    logger.debug('Performing z_prop test on prop with content page nav event.')

    nav_stats = z_prop(df, 'Has_No_Nav_Or_Search', variant_dict)
    # concat rows
    df_ab_nav = pd.Series(nav_stats).to_frame().T
    logger.debug(df_ab_nav)
    ci_low, ci_upp = zconf_interval_two_samples(nav_stats['x_a'], nav_stats['n_a'],
                                                nav_stats['x_b'], nav_stats['n_b'], alpha=alpha)
    logger.debug(' 1-alpha % Confidence Interval = ( {0:.2f}% , {1:.2f}% )'
                 .format(100 * ci_low, 100 * ci_upp))
    # assign a dict to row of dataframe
    df_ab_nav['ci_low'] = ci_low
    df_ab_nav['ci_upp'] = ci_upp

    logger.debug('Joining z_prop dataframes.')

    df_ab = pd.concat([df_ab, df_ab_nav])

    logger.info('Saving df with related links derived variables to rl_sampled_processed_journey dir')
    out_path = os.path.join(DATA_DIR, "rl_sampled_processed_journey", ("zprop_" + f"{filename}"))
    logger.info(f"Saving to {out_path}")
    df_ab.to_csv(out_path, compression="gzip", index=False)

    logger.info('Performing Bayesian bootstrap on count of nav or search.')

    a_bootstrap, b_bootstrap = bayesian_bootstrap_analysis(df, col_name='Content_Nav_or_Search_Count',
                                                           boot_reps=boot_reps,
                                                           variant_dict=variant_dict)
    # high density interval of page variants and difference posteriors
    # ratio is vestigial name
    ratio_nav_stats = bb_hdi(a_bootstrap, b_bootstrap, alpha=alpha)

    df_ab_ratio = pd.Series(ratio_nav_stats).to_frame().T
    logger.debug(df_ab_ratio)

    logger.info('Performing Bayesian bootstrap on Page_List_Length')

    a_bootstrap, b_bootstrap = bayesian_bootstrap_analysis(df, col_name='Page_List_Length', boot_reps=boot_reps)
    # high density interval of page variants and difference posteriors
    length_stats = bb_hdi(a_bootstrap, b_bootstrap, alpha=alpha)

    df_ab_length = pd.Series(length_stats).to_frame().T
    logger.debug(df_ab_length)

    logger.debug('Joining bayesian boot dataframes.')

    df_bayes = pd.concat([df_ab_ratio, df_ab_length])
    # modifies in place
    df_bayes.insert(0, 'Metric', ['Content_Nav_or_Search_Count', 'Page_List_Length'])

    logger.info('Saving df with related links derived variables to rl_sampled_processed_journey dir')
    out_path = os.path.join(DATA_DIR, "rl_sampled_processed_journey", ("bayesbootstrap_" + f"{filename}"))
    logger.info(f"Saving to {out_path}")
    df_bayes.to_csv(out_path, compression="gzip", index=False)

    return


if __name__ == "__main__":  # our module is being executed as a program
    parser = argparse.ArgumentParser(
        description='Analysing sampled processed data module')
    parser.add_argument(
        'filename', help='''
        Prefix of files we want to analyse without csv.gz ending. We will read from
                        the sampled_journey directory from the DATA_DIR
                        specified in your .envrc, and write to the
                        rl_sampled_processed_journey directory in DATA_DIR, the two dataframes with analyses outputs, 
                        will be saved as
                        bayesbootstrap_<<filename_prefix>>.csv.gz and
                         zprop_<<filename_prefix>>.csv.gz
        ''')
    parser.add_argument(
        'document_types_filename', default='document_types', help='''
        Filename of the lookup table in `./data/metadata` for page document type including .csv.gz.
        
        Users need a contemporary lookup table to determine the type of content a page is; whether it's a 
        "finding" or a "thing" page. See README for details of getting this data.
        ''')
    parser.add_argument(
        '--alpha', default=0.05, help='''
           The false positive rate.
           
           With respect to hypothesis tests , alpha refers to significance level, 
           the probability of making a Type I error.
            ''')
    parser.add_argument(
        '--m', default=4, help='''
               The number of hypotheses tested.
               
               Given we are testing 4 null hypotheses we should control for multiple comparisons, 
               the simplest and most conservative approach is to use the Bonferroni correction, 
               alpha / m. So 0.05 / 4 = 0.0125 = alpha_corrected 
               
               The Bonferroni correction can be used to adjust confidence intervals. 
               If one establishes m confidence intervals, and wishes to have an overall confidence level of 1-alpha, 
               each individual confidence interval can be adjusted to the level of 1-(alpha/m).
 
                ''')
    parser.add_argument(
        '--boot_reps', default=10000, help='''
               The number of bootstrap replicates.
               
               The number of times we draw n-1 times with replacement from a sample and estimate a statistic. 
               
               Monte Carlo sampling builds an estimate of the sampling distribution by randomly 
               drawing a large number of samples of size boot_reps from a population, and calculating for 
               each one the associated value of the statistic. In this module we calculate the mean.

                ''')
    parser.add_argument(
        '--control_group', default="B", help='''
                   Capital letter that defines the control variant (e.g., "B")
                    ''')
    parser.add_argument(
        '--intervention_group', default="C", help='''
                   Capital letter that defines the intervention variant (e.g., "C")
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
        args.document_types_filename)

    logger.debug(f'Reading in metadata from {metadata_path}')
    df_finding_thing = pd.read_csv(metadata_path, sep="\t", compression="gzip")
    logger.debug(print('metadata head:', df_finding_thing.head(3)))

    logger.info('Creating thing and finding thing lists...')

    thing_page_paths = df_finding_thing[
        df_finding_thing['is_finding'] == 0]['pagePath'].tolist()

    finding_page_paths = df_finding_thing[
        df_finding_thing['is_finding'] == 1]['pagePath'].tolist()

    analyse_sampled_processed_journey(DATA_DIR, args.filename, alpha=args.alpha / args.m, boot_reps=args.boot_reps,
                                      variants=list(args.control_group, args.intervention_group))
