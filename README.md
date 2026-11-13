# B2B Sales Intelligence Dashboard

This is a Streamlit dashboard that takes one year of invoice data from a Turkish book and puzzle distributor and turns it into something you can actually explore: where the money comes from, who the important customers are, which products move and which ones just sit on the shelf, and what the next few weeks might look like.

You can try it here: https://b2b-sales-intelligence.streamlit.app/

## The data

The raw file is `B2B_Transaction_Data_.xlsx` (about 41 MB). It has 664,154 invoice lines covering every day from 2 January to 31 December 2020. Each line tells you which customer bought which product, on which day, how many units, and at what price. Both the list price and the discounted price are included. There are around 1,200 customers (bookshops and resellers), about 43,600 products identified by barcode, 306 detailed categories and 77 provinces.

The data was fairly clean, but not perfect. `prepare_data.py` drops 21 broken rows (missing or zero quantities, zero prices) and 6,213 exact duplicate lines, keeping the first copy of each. It also fills in missing provinces and categories as "UNKNOWN". After cleaning there are 657,920 lines, about 29.4 million lira of net revenue, and an average discount of 39% off list price.

On top of the raw columns I added a few of my own. Revenue, list value and discount are calculated per line. The document series comes from the first three letters of the invoice number. The 306 categories are grouped into 8 main categories using keyword rules, so the charts stay readable. Customers are split into Key account, Large, Medium and Small groups based on how much they bought over the year.

## What's in the dashboard

The sidebar lets you filter everything by date range, main category, province, document series and customer group. Every page updates with the filters, including the short notes under each chart that point out the main takeaway and anything unusual.

The first page is an executive summary: headline numbers compared with the previous period, the weekly revenue trend with a short forecast, and how revenue splits across the main categories.

The sales page shows where customers are on a map of Turkey, the best-selling categories and products, monthly revenue by document series and customer group, how discounts vary, and which weekdays are busiest.

The customer page segments customers with RFM (recency, frequency, monetary value) and with K-Means clustering. It also shows how concentrated revenue is in a small group of customers, which categories tend to be bought together, and how many new customers come back in later months. There's a button to download the at-risk customers as a CSV.

The supply chain page classifies products with ABC × XYZ analysis (how much revenue they bring and how steady their demand is). It also forecasts weekly demand per category, lists slow movers, and has a small safety-stock calculator where you choose a product, a service level and a lead time.

A few terms used on that page, in plain words:

- ABC analysis sorts products by how much revenue they bring. A products are the small group that together make the first 80% of revenue, B products make the next 15%, and C products, usually the long tail, make the last 5%.
- XYZ analysis looks at how predictable a product's demand is. It compares the month-to-month swings in units sold with the average (the coefficient of variation). X products sell steadily (below 0.5), Y products vary (0.5 to 1), and Z products are erratic (above 1).
- ABC × XYZ combines the two into nine groups. AX products are valuable and easy to plan, so they can be restocked almost automatically. CZ products bring little revenue and sell unpredictably, so they're candidates for dropping or ordering only on demand.
- Slow movers are products that sold on just one invoice line, or haven't sold at all in the last 90 days of the selected period.
- Lead time is how many weeks pass between placing an order with a supplier and the books arriving.
- Service level is how often you want to have the product in stock when a customer asks for it, for example 95% of the time.
- Safety stock is the extra stock kept on top of normal demand to cover unexpected spikes during the lead time. The more demand swings and the longer the lead time, the more you need.
- Reorder point is the stock level at which you should place a new order: the demand you expect during the lead time plus the safety stock.

The forecasting page compares four simple models (naive, moving average, Holt and random forest) on the last 8 weeks of data. It also flags unusual trading days.

The last page explains the cleaning steps and the columns, and lets you preview and download the filtered data.

## Things to keep in mind

There's only one year of data, so the forecasts can't learn anything about seasonality. They're short-term trend guesses, nothing more. There's also no stock or delivery information, so the supply chain page only looks at the demand side. Lead times in the calculator are whatever you type in. Nobody explained what the invoice prefixes (BAD, BSR, DPF, DPE, MUH) mean, so I treated them as labels. And in late July there's a 13-day gap with no invoices at all, which shows up as a dip in every weekly chart.

## Running it yourself

You'll need Python (I used 3.14). Then:

```bash
python -m venv venv
venv\Scripts\activate          # on macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
python prepare_data.py         # takes about a minute
streamlit run streamlit_app.py
```

`prepare_data.py` reads the Excel file and writes a much smaller `data/transactions.parquet`, which is what the app loads. If you skip that step, the app builds the file the first time it starts. The first page load takes 15 to 20 seconds while the models are fitted. After that, results are cached and filter changes are quick.

## How the code is organised

`streamlit_app.py` is the entry point. It draws the sidebar and the tabs. Everything else is under `src/`. `prep.py` cleans the data, `data.py` loads and filters it, and `analytics.py` does the calculations and models. Each tab has its own file in `src/views/`. Colours and chart styling live in `theme.py`, chart helpers in `charts.py`, and fixed settings like the category rules in `config.py`. The exploratory analysis I did before building the app is in `EDA_B2B_Transactions.ipynb`.

## Deploying

The live version runs on Streamlit Community Cloud straight from this repository, with `streamlit_app.py` as the main file. Pushing to `main` redeploys it. The Excel file is over GitHub's 25 MB browser upload limit, so push it with git instead.
