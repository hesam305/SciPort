# SciPort — New-listing short backtest

A study of the pattern where **new perpetual-futures listings** pump right after listing and then dump. The strategy tested is a short with 2x leverage.

Both scripts use only the Python 3 standard library, so there is nothing to install.

## 1. Collect data (on your own computer)

```bash
python collect_new_listings.py --exchange binance      # needs a VPN
python collect_new_listings.py --exchange gate         # no VPN needed from Iran
python collect_new_listings.py --exchange bybit
```

- Covers the last 18 months of listings. For each coin it downloads 14 days of 5m candles, 60 days of 1h candles and the funding rates.
- If the run is interrupted, run it again and it picks up where it stopped.
- The output is `new_listings_<exchange>.zip`.
- `binance-archive` reads the public Binance archive (`data.binance.vision`). It has no geo-block and it includes delisted coins, so there is no survivorship bias.

### Or on GitHub, without your own computer

The workflow `.github/workflows/collect.yml` collects the data on GitHub's servers and runs the backtest there. It starts on every push to this branch, or you can start it by hand from the **Actions** tab. The results go to the `data-<exchange>` branch: `backtest_report.txt`, `grid_results.csv`, and the data zip split into parts. To rebuild the zip, run `cat new_listings_*.zip.part* > new_listings.zip`.

## 2. Run the backtest

```bash
python backtest.py new_listings_binance.zip --leverage 2
```

The report has four parts:

0. **Pump anatomy:** how far listings pump and how many hours until the peak.
1. **Entry timing:** a fixed delay after listing (0.5h to 48h) compared with an entry after an X% drop from the peak.
2. **Funding:** how much a short pays or receives while holding.
3. **Stop loss:** how often a secondary pump of 25–30% or more happens, plus the full SL/TP/hold grid.

For a focused look at the first 10 days, where every trade must close by day 10 and results are split by the size of the first-24h pump, run:

```bash
python analyze_10d.py new_listings_binance-archive.zip --days 10
```

Parameters are ranked on the older listings (train) and checked on the newer ones (test). This guards against overfitting. The full grid is saved to `grid_results.csv`.
