paperstand/
├── paperstand/              # main package
│   ├── __init__.py
│   ├── fetch.py             # download HTML from PMCID via PubMed Central
│   ├── parse.py             # BeautifulSoup parsing → nested dict
│   ├── extract.py           # pull specific fields (title, date, methods, etc.)
│   ├── export.py            # dict → spreadsheet (CSV/Excel)
│   └── nlp.py               # stretch goal: NLP for metadata (age, disease, accession)
├── cli.py                   # command-line interface entry point
├── tests/
│   ├── test_fetch.py
│   ├── test_parse.py
│   └── test_extract.py
├── data/
│   └── sample_papers/       # store downloaded HTMLs for testing
├── output/                  # generated spreadsheets go here
├── requirements.txt
└── README.md