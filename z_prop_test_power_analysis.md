Power analysis for related links proportion z test
--------------------------------------------------

[GOV.UK](https://www.gov.uk/) is a popular website. According to Google
Analytics, it gets several million [active
users](https://support.google.com/analytics/answer/6171863?hl=en)
everyday.

For our analytical purposes our experimental unit is at the level of the
active user journey
[session](https://support.google.com/analytics/answer/6086069?hl=en). We
need a given number of user sessions to achieve our desired statistical
power.

This doc walks us through the thinking and calculations prior to
initiating the experiment. It gives us our stopping distance (when can
we look at the data and conduct the analysis as part of a valid
experiment).

Assumptions
-----------

We assume independent observations; each session is independent. This
basically means that the journey of a user session must be independent
of the journey of any other user session. We also assume randomised
assignment to page variant type. Once assigned a cookie, a user will
only see page variants of one type (A or B), thus completing a journey
exposed to just one treatment.

Metric of interest
------------------

Null hypothesis - There is no difference in the proportion of user
journey sessions that click on at least one related link between page A
and page B.

journey\_click\_rate = total number of journeys including at least one
click on a related link / total number of journeys  
H0: journey\_click\_rateA = journey\_click\_rateB  
H1: journey\_click\_rateA ≠ journey\_click\_rateB

### Baseline

A power analysis needs to be flexible, exploratory, and well thought
out. We [inspect historical
data](https://github.com/alphagov/govuk-network-data/tree/master/notebooks/eda)
to estimate a ball-park figure for what we expect the
journey\_click\_rate to be for our experiment. This gives us an expected
baseline for the control, or page A variant. The value varied from 1-5%
given different data samples. We use the (statistically) worse-case
scenario of 1% journey\_click\_rate, to be conservative in our power
analysis, ensuring we get enough data.

### More generally

See the appendix for more detail on A/B testing with proportion data
(where we know how many times an event did and didn’t happen).

Effect size
-----------

5% relative increase is our “go-to” effect size we are interested in
detecting (a rule of thumb industry standard). This is in part, due to
the novelty of some of these metrics and their derived nature which
makes it difficult to have any preconceived expectations.

How many sessions do we need to be able to test our null hypothesis?
--------------------------------------------------------------------

To estimate sample size we need these parameters:

-   Current Rate or baseline Related Link Click rate  
-   Effect size or Minimum Detectable Change (the minimum change you
    want to be able to detect)  
-   Statistical Significance: the probability of mistakenly rejecting
    the null hypothesis (H<sub>0</sub>) if it were true  
-   Statistical Power: probability of correctly rejecting the null
    hypothesis (H<sub>0</sub>) when the alternative (H<sub>1</sub>) is
    true. In other words, the ability of a test to detect an effect if
    the effect actually exists.

We can do this in R easily enough:

How many user journey sessions (n) do we need per page variant to be
able to detect a 5% relative difference in related link click through
rate (p<sub>A</sub>)? Let’s take the most extreme example to ensure we
have sufficient power.

(We use standard alpha and beta values, although our alpha value was set
at the industry standard of 0.05, we had to control for multiple
comparisons thus bringing it down to ~ 0.01. At this level we would
expect a false positive 5% of the time; not 1%.)

``` r
# The baseline rate varies on assumptions in the data pipeline
# and the data sample, we use the most conservative (nearest to zero)

# sample size required for each group (so times n by 2)
# to detect 5% relative change in 
# note how p1 - p2 gives a 5% relative change, the effect size

m1 <- power.prop.test(p1 = .01, p2 = .0105,
                      power = 0.8, sig.level = 0.01)
m1
```

    ## 
    ##      Two-sample comparison of proportions power calculation 
    ## 
    ##               n = 947857.8
    ##              p1 = 0.01
    ##              p2 = 0.0105
    ##       sig.level = 0.01
    ##           power = 0.8
    ##     alternative = two.sided
    ## 
    ## NOTE: n is number in *each* group

### Validate assumptions

As proportion data is bounded at zero and one, we can use a normal
approximation to model the difference between the means if they are
relatively far from the bounds given the sample size. We assess this
now.

The formula of z-statistic is valid only when sample size (n) is large
enough. nAp, nAq, nBp and nBq should be ≥ 5.

``` r
# in the same order
# where p is probability of success (we can use current baseline)
# q = 1 - p

# page A
p <- m1$p1
q <- 1 - m1$p1
(m1$n * c(p, q)) >= 5
```

    ## [1] TRUE TRUE

``` r
# page B
p <- m1$p2
q <- 1 - m1$p2
(m1$n * c(p, q)) >= 5
```

    ## [1] TRUE TRUE

The large samples collapses the distribution such that we are not in
danger of breaching zero or one.

Controlling for big data
------------------------

GOV.UK gets alot of visitors, how can we avoid drowning in data (RAM and
compute limitations) but still capture the different user journey
sessions that might occurr during the week (control for weekday /
weekend affects by including the data).

We also want to mitigate getting too large a sample size (not strictly a
bad thing if we communicate correctly), as n tends to infinite, the
p-value of a statistical test between two proportions will tend to zero
(this is because the measurement becomes more and more precise; it
doesn’t necessarily mean the difference is practically significant or
meaningful).

How to sample a week’s worth of data to get N
---------------------------------------------

Our power analysis described n, the sample size per variant required as
9.4785810^{5}. We are interested in getting twice that, what we call N,
1.89571610^{6}.

``` r
N <- round(m1$n, 0)*2
N
```

    ## [1] 1895716

If we consider a typical week (2019-01-25-2019-01-31), we can work
backwards to ascertain how to sample from each day to get sufficient
data for our z proportion test comparing the means of page A and page B
variants. We are interested in drawing from a week’s worth of data as it
captures the putatively different types of journeys seen on weekdays and
weekends which might be affected differently by changes to the related
links served.

Given N, we would need approximately 1.0 million users to make journeys
on both page variants A and B. So how long does it take to get 2.0
million users to visit GOV.UK? A quick look at Google Analytics suggests
we get over 3 million sessions for weekdays and over 2 million for
weekends.

``` r
# a mix of base R and tidyverse code

# skip and nrows combined to take a slice of rows
df <- read.csv("data/20190125-20190131_active_users.csv",
               header = TRUE, skip = 6, nrows=7,
               colClasses = "character",
               stringsAsFactors = FALSE)

replaceCommas<-function(x){
  x<-as.numeric(gsub("\\,", "", x))
}

df$X1.Day.Active.Users <- replaceCommas(df$X1.Day.Active.Users) %>%
  as.numeric() 

df <- dplyr::rename(df, date = Day.Index, 
                    users = X1.Day.Active.Users) %>%
  mutate(date = readr::parse_date(date, format = "%d/%m/%Y")) %>%
  mutate(the_day = weekdays(date))

df
```

    ##         date   users   the_day
    ## 1 2019-01-25 3198439    Friday
    ## 2 2019-01-26 2110783  Saturday
    ## 3 2019-01-27 2275540    Sunday
    ## 4 2019-01-28 3902942    Monday
    ## 5 2019-01-29 3867336   Tuesday
    ## 6 2019-01-30 3946546 Wednesday
    ## 7 2019-01-31 3998355  Thursday

Our first question should be whether we can get N with one weeks data?
This is obvious from the table, where one day provides sufficient active
users. Even if we are conservative that one active user only has one
session we have sufficient sessions to meet N (assuming random
assignment to page variant for each active user).

``` r
# can we get that within a weeks data?
print(paste("It is ", sum(df$users) > (m1$n) * 2, " that one week provides sufficient sample size."))
```

    ## [1] "It is  TRUE  that one week provides sufficient sample size."

Considering how much data we can hold in RAM on a local machine and how
to sample user journey sessions from each day, followed by aggregation
of all days data: how best to go about sampling from the week?

``` r
# a week's worth
week_total <- sum(df$users)
week_total
```

    ## [1] 23299941

``` r
# ratio of what is required to what is available
(N/week_total)*100
```

    ## [1] 8.136141

So if we need 1.89571610^{6} from a weeks worth of data 2.329994110^{7},
that means we can reduce our sampling effort by a factor of 12 from each
day and still have sufficient data.

``` r
# we need to sum the week's worth then sample a prop of each day
# to contribute to the total n*2 required

df <- df %>%
  mutate(prop_of_week_total = round(users / sum(users), 2))
# looks like people start to clock off from work on Friday already!

# let' call n*2, N
df <- mutate(df,
             n_req_by_sampling =
               (users*prop_of_week_total))

df
```

    ##         date   users   the_day prop_of_week_total n_req_by_sampling
    ## 1 2019-01-25 3198439    Friday               0.14          447781.5
    ## 2 2019-01-26 2110783  Saturday               0.09          189970.5
    ## 3 2019-01-27 2275540    Sunday               0.10          227554.0
    ## 4 2019-01-28 3902942    Monday               0.17          663500.1
    ## 5 2019-01-29 3867336   Tuesday               0.17          657447.1
    ## 6 2019-01-30 3946546 Wednesday               0.17          670912.8
    ## 7 2019-01-31 3998355  Thursday               0.17          679720.4

``` r
# let's double check that if we did sample from these days
# at these rates, we would have sufficinet N

sum(df$n_req_by_sampling) > N
```

    ## [1] TRUE

This works out as essentially we are saying one day meets our data
needs, but lets instead sample from the whole week so we end up with the
same amount of data as one would get in a day.

``` r
# sanity check
sum(df$n_req_by_sampling)
```

    ## [1] 3536886

Want more data?
---------------

By sampling we are losing information. We should get the data we need to
perform our statistical test, but let’s say we wanted to add some
complexity to the model. We would then need additional data to provide
the information for a more complex model. This could be simply achieved
by increasing the `prop_of_week_total` by a factor (i.e. 2 or 3) to get
more data.

This sampling step should be done in the Big Query pipeline when
retrieving your data if possible.

``` r
df <- df %>%
  mutate(prop_of_week_total_doubled = prop_of_week_total*2,
         n_req_by_sampling_doubled = n_req_by_sampling*2)

df
```

    ##         date   users   the_day prop_of_week_total n_req_by_sampling
    ## 1 2019-01-25 3198439    Friday               0.14          447781.5
    ## 2 2019-01-26 2110783  Saturday               0.09          189970.5
    ## 3 2019-01-27 2275540    Sunday               0.10          227554.0
    ## 4 2019-01-28 3902942    Monday               0.17          663500.1
    ## 5 2019-01-29 3867336   Tuesday               0.17          657447.1
    ## 6 2019-01-30 3946546 Wednesday               0.17          670912.8
    ## 7 2019-01-31 3998355  Thursday               0.17          679720.4
    ##   prop_of_week_total_doubled n_req_by_sampling_doubled
    ## 1                       0.28                  895562.9
    ## 2                       0.18                  379940.9
    ## 3                       0.20                  455108.0
    ## 4                       0.34                 1327000.3
    ## 5                       0.34                 1314894.2
    ## 6                       0.34                 1341825.6
    ## 7                       0.34                 1359440.7

``` r
# sanity check
sum(df$n_req_by_sampling_doubled)
```

    ## [1] 7073773

This doesn’t necessarily reflect the number of rows in the dataframe, as
this captures the number of occurrences of Sequences. The experimental
unit is at the level of a user session with a specific Sequence (user
journey of page views and events), however for storage efficiency these
are roled up.

Some consideration as how to sample your data should be applied.

Conclusion
----------

The z proportion test is a valid method to compare the proportion of
journeys using at least one related link (journey\_click\_rate) between
page variant A and page variant B, given the historic data.

With a sample size of 9.4785810^{5} per page variant, the z prop test
will meet our statistical power needs.

``` r
# remember sig.level is actually around 0.05
# as we have controlled for multiple comparisons with
# the Bon ferroni correction
m1$method
```

    ## [1] "Two-sample comparison of proportions power calculation"

``` r
broom::tidy(m1)
```

    ## # A tibble: 1 x 5
    ##         n sig.level power    p1     p2
    ##     <dbl>     <dbl> <dbl> <dbl>  <dbl>
    ## 1 947858.      0.01   0.8  0.01 0.0105

``` r
print(paste0("With a minimum detectable relative difference of ",
             # the difference, as a relative percentage of baseline
            (m1$p2-m1$p1) / m1$p1*100, "%."))
```

    ## [1] "With a minimum detectable relative difference of 5%."

References
----------

Wilson, E.B. (1927). Probable inference, the law of succession, and
statistical inference. Journal of the American Statistical Association,
22, 209–212. doi: 10.2307/2276774.

Newcombe R.G. (1998). Two-Sided Confidence Intervals for the Single
Proportion: Comparison of Seven Methods. Statistics in Medicine, 17,
857–872. doi:
10.1002/(SICI)1097-0258(19980430)17:8&lt;857::AID-SIM777&gt;3.0.CO;2-E.

Newcombe R.G. (1998). Interval Estimation for the Difference Between
Independent Proportions: Comparison of Eleven Methods. Statistics in
Medicine, 17, 873–890. doi:
10.1002/(SICI)1097-0258(19980430)17:8&lt;873::AID-SIM779&gt;3.0.CO;2-I.

Appendix
--------

With proportions we are dealing with a numerator and a denominator. We
know the number of times an event did happen and did not happen (this
contrasts with count data where we know how often an event did happen
but don’t know how often it didn’t happen) across each journey (unique
Sequence).

If X is the number of successes and n is the number of trials then, then
p is the probability of success. The probability of failure, is q or 1 -
p. So for metric 2a, a success would be a journey (‘Sequence’ in the
data pipeline language) with at least one related link clicked during
it, multiplied by the number of occurrences of that journey. The number
of trials would be the sum of journeys multiplied by their respective
occurrences.

pA = XA / nA  
pB = XB / nB

The simplest and most frequently used modelling approach is to aggregate
all the data together by page variant (as above). For comparison of
these two observed proportions we can use the two-proportions z-test .
We want to know, whether the proportions of clickers are the same in the
two groups of user journeys.

The test statistic can be calculated as follows:

$$z = \\frac{(p\_A - p\_B) - 0} {\\sqrt{(pq) (\\frac{1}{n\_A} + \\frac{1}{n\_B})}}$$

where,

p<sub>A</sub> is the proportion observed in group A with size nA  
p<sub>B</sub> is the proportion observed in group B with size nB  
p and q are the overall proportions

Note that, the formula of z-statistic is valid only when sample size (n)
is large enough. n<sub>A</sub>p, n<sub>A</sub>q, n<sub>B</sub>p and
n<sub>B</sub>q should be ≥ 5. Thus we should check this in turn with
each metric in our exploration of some baseline data prior to the
experiment.

``` r
devtools::session_info()
```

    ## Session info -------------------------------------------------------------

    ##  setting  value                       
    ##  version  R version 3.5.1 (2018-07-02)
    ##  system   x86_64, darwin15.6.0        
    ##  ui       X11                         
    ##  language (EN)                        
    ##  collate  en_GB.UTF-8                 
    ##  tz       Europe/London               
    ##  date     2019-02-04

    ## Packages -----------------------------------------------------------------

    ##  package    * version date       source         
    ##  assertthat   0.2.0   2017-04-11 CRAN (R 3.5.0) 
    ##  backports    1.1.2   2017-12-13 CRAN (R 3.5.0) 
    ##  base       * 3.5.1   2018-07-05 local          
    ##  bindr        0.1.1   2018-03-13 CRAN (R 3.5.0) 
    ##  bindrcpp   * 0.2.2   2018-03-29 CRAN (R 3.5.0) 
    ##  broom        0.5.0   2018-07-17 CRAN (R 3.5.0) 
    ##  cellranger   1.1.0   2016-07-27 CRAN (R 3.5.0) 
    ##  cli          1.0.0   2017-11-05 CRAN (R 3.5.0) 
    ##  colorspace   1.3-2   2016-12-14 CRAN (R 3.5.0) 
    ##  compiler     3.5.1   2018-07-05 local          
    ##  crayon       1.3.4   2017-09-16 CRAN (R 3.5.0) 
    ##  datasets   * 3.5.1   2018-07-05 local          
    ##  devtools     1.13.6  2018-06-27 CRAN (R 3.5.0) 
    ##  digest       0.6.18  2018-10-10 cran (@0.6.18) 
    ##  dplyr      * 0.7.7   2018-10-16 cran (@0.7.7)  
    ##  evaluate     0.11    2018-07-17 CRAN (R 3.5.0) 
    ##  fansi        0.3.0   2018-08-13 CRAN (R 3.5.0) 
    ##  forcats    * 0.3.0   2018-02-19 CRAN (R 3.5.0) 
    ##  ggplot2    * 3.1.0   2018-10-25 cran (@3.1.0)  
    ##  glue         1.3.0   2018-07-17 CRAN (R 3.5.0) 
    ##  graphics   * 3.5.1   2018-07-05 local          
    ##  grDevices  * 3.5.1   2018-07-05 local          
    ##  grid         3.5.1   2018-07-05 local          
    ##  gtable       0.2.0   2016-02-26 CRAN (R 3.5.0) 
    ##  haven        1.1.2   2018-06-27 CRAN (R 3.5.0) 
    ##  hms          0.4.2   2018-03-10 CRAN (R 3.5.0) 
    ##  htmltools    0.3.6   2017-04-28 CRAN (R 3.5.0) 
    ##  httr         1.3.1   2017-08-20 CRAN (R 3.5.0) 
    ##  jsonlite     1.5     2017-06-01 CRAN (R 3.5.0) 
    ##  knitr        1.20    2018-02-20 CRAN (R 3.5.0) 
    ##  lattice      0.20-35 2017-03-25 CRAN (R 3.5.1) 
    ##  lazyeval     0.2.1   2017-10-29 CRAN (R 3.5.0) 
    ##  lubridate    1.7.4   2018-04-11 CRAN (R 3.5.0) 
    ##  magrittr     1.5     2014-11-22 CRAN (R 3.5.0) 
    ##  memoise      1.1.0   2017-04-21 CRAN (R 3.5.0) 
    ##  methods    * 3.5.1   2018-07-05 local          
    ##  modelr       0.1.2   2018-05-11 CRAN (R 3.5.0) 
    ##  munsell      0.5.0   2018-06-12 CRAN (R 3.5.0) 
    ##  nlme         3.1-137 2018-04-07 CRAN (R 3.5.1) 
    ##  pillar       1.3.0   2018-07-14 CRAN (R 3.5.0) 
    ##  pkgconfig    2.0.2   2018-08-16 CRAN (R 3.5.1) 
    ##  plyr         1.8.4   2016-06-08 CRAN (R 3.5.0) 
    ##  purrr      * 0.2.5   2018-05-29 CRAN (R 3.5.0) 
    ##  R6           2.3.0   2018-10-04 cran (@2.3.0)  
    ##  Rcpp         1.0.0   2018-11-07 cran (@1.0.0)  
    ##  readr      * 1.1.1   2017-05-16 CRAN (R 3.5.0) 
    ##  readxl       1.1.0   2018-04-20 CRAN (R 3.5.0) 
    ##  rlang        0.3.0.1 2018-10-25 cran (@0.3.0.1)
    ##  rmarkdown    1.10    2018-06-11 CRAN (R 3.5.0) 
    ##  rprojroot    1.3-2   2018-01-03 CRAN (R 3.5.0) 
    ##  rstudioapi   0.7     2017-09-07 CRAN (R 3.5.0) 
    ##  rvest        0.3.2   2016-06-17 CRAN (R 3.5.0) 
    ##  scales       1.0.0   2018-08-09 CRAN (R 3.5.0) 
    ##  stats      * 3.5.1   2018-07-05 local          
    ##  stringi      1.2.4   2018-07-20 CRAN (R 3.5.0) 
    ##  stringr    * 1.3.1   2018-05-10 CRAN (R 3.5.0) 
    ##  tibble     * 1.4.2   2018-01-22 CRAN (R 3.5.0) 
    ##  tidyr      * 0.8.2   2018-10-28 cran (@0.8.2)  
    ##  tidyselect   0.2.5   2018-10-11 cran (@0.2.5)  
    ##  tidyverse  * 1.2.1   2017-11-14 CRAN (R 3.5.0) 
    ##  tools        3.5.1   2018-07-05 local          
    ##  utf8         1.1.4   2018-05-24 CRAN (R 3.5.0) 
    ##  utils      * 3.5.1   2018-07-05 local          
    ##  withr        2.1.2   2018-03-15 CRAN (R 3.5.0) 
    ##  xml2         1.2.0   2018-01-24 CRAN (R 3.5.0) 
    ##  yaml         2.2.0   2018-07-25 CRAN (R 3.5.0)
