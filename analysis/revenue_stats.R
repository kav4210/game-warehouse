# Statistical layer on the warehouse marts. Base R only (no packages to install).
# Run from repo root: Rscript analysis/revenue_stats.R
args <- commandArgs(trailingOnly = FALSE)
q  <- read.csv("data/mart_game_quarterly.csv", stringsAsFactors = FALSE)
rc <- read.csv("data/mart_region_channel.csv", stringsAsFactors = FALSE, na.strings = character(0))
cat("== 1. Does revenue per unit differ by channel? (Welch t-test on per-row price) ==\n")
sales <- read.csv("data/raw_sales.csv", stringsAsFactors = FALSE, na.strings = character(0))
sales <- sales[!duplicated(sales$sale_id) & sales$revenue >= 0 & sales$units > 0, ]
sales$ppu <- sales$revenue / sales$units
tt <- t.test(ppu ~ channel, data = sales)
print(tt)
cat("\n== 2. Does genre explain quarterly revenue? (one-way ANOVA + Tukey HSD) ==\n")
fit <- aov(revenue ~ genre, data = q)
print(summary(fit))
print(TukeyHSD(fit))
cat("\n== 3. Revenue trend by quarter (linear model, game fixed effects) ==\n")
m <- lm(revenue ~ quarter + factor(title), data = q)
co <- summary(m)$coefficients["quarter", ]
cat(sprintf("quarter slope = %.2f per quarter (SE %.2f, p = %.4f)\n", co[1], co[2], co[4]))
cat(sprintf("adj R-squared = %.3f\n", summary(m)$adj.r.squared))
cat("\n== 4. Is channel mix independent of region? (chi-square on TRANSACTION COUNTS) ==\n")
cat("Counts, not dollars: a chi-square on revenue would treat each dollar as an observation and inflate significance.\n")
tab <- table(sales$region, sales$channel)
print(round(prop.table(tab, 1), 3))
cs <- chisq.test(tab)
print(cs)
res <- list(ttest_p = tt$p.value, anova_p = summary(fit)[[1]][["Pr(>F)"]][1],
            quarter_slope = unname(co[1]), quarter_slope_p = unname(co[4]), adj_r2 = summary(m)$adj.r.squared, chisq_p = cs$p.value)
dir.create("analysis/out", showWarnings = FALSE)
writeLines(paste0("{", paste(sprintf('"%s": %.6g', names(res), unlist(res)), collapse = ", "), "}"), "analysis/out/stats.json")
cat("\nwrote analysis/out/stats.json\n")
