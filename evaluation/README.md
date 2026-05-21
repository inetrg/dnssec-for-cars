# mininet_vsomeip_dnssec

<a target="_blank" href="https://cookiecutter-data-science.drivendata.org/">
    <img src="https://img.shields.io/badge/CCDS-Project%20template-328F97?logo=cookiecutter" />
</a>

Evaluation components and data for mininet experiments of SOME/IP using DNSSEC for service authentication.

## Project Organization

```
├── Makefile           <- Makefile with convenience commands like `make data` or `make plots`
├── README.md          <- The top-level README for developers using this project.
├── data
│   ├── interim        <- Intermediate data that has been transformed.
│   ├── processed      <- The final, canonical data sets for analysis.
│   └── raw            <- The original, immutable statistics recording from experiments.
│
├── notebooks          <- Jupyter notebooks for prototype development.
│
├── pyproject.toml     <- Project configuration file with package metadata for 
│                         mininet_vsomeip_dnssec and configuration for tools like black
│
├── reports            <- Generated analysis as HTML, PDF, LaTeX, etc.
│   └── figures        <- Generated graphics and figures to be used in reporting
│
├── requirements.txt   <- The requirements file for reproducing the analysis environment, e.g.
│                         generated with `pip freeze > requirements.txt`
│
├── setup.cfg          <- Configuration file for flake8
│
└── mininet_vsomeip_dnssec   <- Source code for use in this project.
    │
    ├── __init__.py             <- Makes mininet_vsomeip_dnssec a Python module
    │
    ├── config.py               <- Store useful variables and configuration
    │
    ├── dataset.py              <- Scripts to process data from the raw format to the interim and processed data sets
    │
    └── plots.py                <- Code to create visualizations, and tables
```

--------

## Reproducing the Analysis
Make sure the data is in place. 
Either run the series as described in the main project README, or use the ```make extract``` command to extract the data set from the tar.gz file in the raw data directory.
If you run the series yourself, move the data from the data collection directory to the raw data directory, as each run will create a directory with the time and date of the run. Move the scenario folders, i.e., carnet or scalability up one level.

The run ```make data``` to preprocess the data, and ```make plots``` to reproduce the tables and reports.
