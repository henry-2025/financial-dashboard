# Financial Dashboard
## A pretty basic, but pretty good dashboard for personal finance breakdowns
## How it works

1. Upload a transaction file that you download from your bank account, creadit card, or Venmo
2. Manually tag each transaction and submit your taggings to an on-disk database that you can access in the future
3. See insightful breakdowns of your transaction history on a month-by-month basis

## How to add new parsers
New parsers are stupid easy to add if you know the format that you are parsing. Do the following:

1. Create a new parser class in `transaction_parsers.py` and add the class to the lookup table `_parsers`.
2. In the `start.html` template, add the display name for the transaction sheet type that you want to display in the dropdown. *This name, when lowercased, must be identical to the key in `_parsers` that you created in step 1.
