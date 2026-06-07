# Prophet Forecasting for Portfolio Optimisation

I built this to explore whether time series forecasting could meaningfully 
improve portfolio allocation decisions. It uses Facebook's Prophet model to 
forecast next-day asset prices, feeds those forecasts into Markowitz 
optimisation to calculate optimal portfolio weights, and saves results to 
Supabase for a live Streamlit dashboard.

> For illustrative purposes only — not financial advice.

**Live:** [portfolio-optimisation.com](http://portfolio-optimisation.com) — 
runs every morning at 09:00 UTC

**Slides:** [View presentation](#)

---

## Architecture

<!-- Add architecture diagram here -->

---

## How it works

Prophet fits to historical price data for each asset and generates a 
one-step-ahead forecast. Those forecasted returns feed into Markowitz 
optimisation — solving for the portfolio weights that maximise risk-adjusted 
return given a historical covariance matrix. Results are written to Supabase 
and surfaced through a Streamlit dashboard where you can inspect weights, 
compare predicted vs actual prices, and track accuracy over time.

---

## Stack

| Layer | Tool |
|---|---|
| Forecasting | Facebook Prophet |
| Optimisation | SciPy SLSQP solver |
| Storage | Supabase |
| Dashboard | Streamlit |
| Scheduler | CircleCI |
| Hosting | Hostinger VPS |
| Dependency management | Poetry |

---

## Setup

```bash
make install-dev
```

Configure your tickers, risk aversion, and date range in `src/settings.py`, 
then run:

```bash
make run          # run optimisation
make dashboard    # launch Streamlit
```

Requires a Supabase project and CircleCI account — see 
[setup guide](#) for environment configuration.
