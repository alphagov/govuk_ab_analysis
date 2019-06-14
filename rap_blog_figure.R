library(tidyverse)
library(ggthemes)
library(scales)

# show_col(colorblind_pal()(8))

df <- read_csv("2019-03-22-summary_results_ci_all_experiments - Sheet1.csv")

df <- df %>%
  mutate(name = paste(experiment, iteration, sep = "_")) %>%
  mutate_at(vars(name, metric, loved), as_factor))
  mutate(name = paste(experiment, iteration, sep = "_")) %>%
  mutate(name = as_factor(name)) %>%
  mutate(metric = as_factor(metric)) %>%
  mutate(loved = as_factor(loved))

# we are only interested in unloved and one metric for our blog post
df_unloved <- df %>%
  filter(loved == "unloved", metric %in% c('prop_no_nav')) %>%
  filter(name %in% c("content_similarity_ii", "node2vec_i", "llr_i"))

# nice names and labels
levels(df_unloved$metric) <- c("Proportion of journeys using at least one related link", 
                       "search_nav_count",
                       "Proportion of journeys not using internal search",
                       "journey_length")

levels(df_unloved$name) <- c("content similarity 300 words", 
                               "content similarity",
                               "node2vec",
                               "log likelihood ratio")

p2 <- ggplot(data=df_unloved,
             aes(x = name,y = (100*mean_diff),
                 ymin = (100*lci), ymax = (100*uci) ))+
  geom_pointrange(aes(col=name))+
  ylab("Reduction in journeys \n using internal search (%)")+
# as percentages rather than proportions
  geom_errorbar(aes(ymin=(100*lci), ymax=(100*uci),col=name),
                width = 0.8, size = 0.5) +
  theme_classic()  +
  theme(axis.text.x=element_text(angle=50, size=6, vjust=0.5)) +
  theme(axis.text.x=element_blank()) +
  ggtitle("") + ylim(0, 50) +
  xlab("Algorithms")+
  theme(axis.title.y = element_text(size=10))+
  theme(legend.position= c(0.82, 0.35),
        legend.background = element_blank(),
        legend.key = element_blank(),
        strip.text = element_text(size = 6))+
  scale_colour_colorblind(name = "")

# save
ggsave("rap_blog_ab.png", units="in", width=5, height=3, dpi=300)
