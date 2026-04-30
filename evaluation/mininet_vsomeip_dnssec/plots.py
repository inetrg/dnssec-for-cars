from loguru import logger
import typer
from tqdm import tqdm
import polars as pl

from mininet_vsomeip_dnssec.config import PROCESSED_DATA_DIR, SCENARIOS, REPORTS_DIR, FIGURES_DIR, get_pubsub_count_from_config
from mininet_vsomeip_dnssec.dataset import load_processed_data

app = typer.Typer()


def check_data_exists():
    base_error_msg = (
        "Please run the data processing step first. See 'make data' and dataset.py for details."
    )
    if not PROCESSED_DATA_DIR.exists():
        logger.error(
            f"Processed data directory {PROCESSED_DATA_DIR} does not exist. {base_error_msg}"
        )
        return False
    if not all((PROCESSED_DATA_DIR / scenario).exists() for scenario in SCENARIOS):
        logger.error(
            f"Processed data for one or more scenarios not found in {PROCESSED_DATA_DIR}. {base_error_msg}"
        )
        return False
    if not any(PROCESSED_DATA_DIR.glob("**/*.parquet")):
        logger.error(f"No processed data files found in {PROCESSED_DATA_DIR}. {base_error_msg}")
        return False
    return True


def print_report_table_config_stats(df, path):
    table_data = [["Metric", "min[ms]", "mean[ms]", "max[ms]"]]
    # extract metric names from df remove ["_min", "_mean", "_max"]:
    # Use a fixed, ordered list for suffixes to ensure columns match header order
    suffixes = ["_min", "_mean", "_max"]
    metric_set = {
        col[: -len(suffix)]
        for col in df.columns
        for suffix in suffixes
        if col.endswith(suffix)
    }
    for metric in metric_set:
        row = [metric]
        for suffix in suffixes:
            value = df.select(f"{metric}{suffix}").item()
            if value is None:
                row.append("n/a")
            else:
                row.append(f"{float(value) / 1_000_000:.2f}")
        table_data.append(row)
    with open(path, "w") as f:
        for row in table_data:
            f.write(", ".join(row) + "\n")

def create_latex_table_config_stats(config_map, path):
    section_order = ["A", "F", "H"]
    section_titles = {
        "A": "Vanilla vsomeip",
        "F": "Pre-deployed certificates",
        "H": "DNSSEC, DANE, and DANCE",
    }
    metric_labels = {
        "network_initialization": "Full network startup",
        "service_setup": "Setup-time per subscription",
        "create_signatures_sum": "% Create signature",
        "verify_signatures_sum": "% Verify signature",
        "resolve_pub_svcb": "% Resolve Pub SVCB",
        "resolve_sub_tlsa": "% Resolve Sub TLSA",
        "resolve_pub_tlsa": "% Resolve Pub TLSA",
        "resolve_dns_sum": "DNS resolution per subscription",
        "crypto_sum": "Crypto ops. per subscription",
        "run_time": "% Total experiment runtime",
        "initialization_total": "% Total initialization time",
        "initialization_manager": "% Initialization time (manager)",
        "initialization_publishers": "% Initialization time (publishers)",
        "initialization_subscribers": "% Initialization time (subscribers)",
    }
    metric_scaling = {
        # data in ns --> convert to ms
        "network_initialization": 1_000_000,
        "service_setup": 1_000_000,
        "create_signatures_sum": 1_000_000,
        "verify_signatures_sum": 1_000_000,
        "resolve_pub_svcb": 1_000_000,
        "resolve_sub_tlsa": 1_000_000,
        "resolve_pub_tlsa": 1_000_000,
        "resolve_dns_sum": 1_000_000,
        "crypto_sum": 1_000_000,
        # data in s --> convert to ms
        "run_time": 0.001,
        "initialization_total": 0.001,
        "initialization_manager": 0.001,
        "initialization_publishers": 0.001,
        "initialization_subscribers": 0.001,
    }
    metrics_per_section = {
        "A": ["network_initialization", "service_setup", "run_time", "initialization_total", "initialization_manager", "initialization_publishers", "initialization_subscribers"],
        "F": [
            "network_initialization",
            "service_setup",
            "create_signatures_sum",
            "verify_signatures_sum",
            "crypto_sum",
            "run_time", "initialization_total", "initialization_manager", "initialization_publishers", "initialization_subscribers"
        ],
        "H": [
            "network_initialization",
            "service_setup",
            "create_signatures_sum",
            "verify_signatures_sum",
            "resolve_pub_svcb",
            "resolve_sub_tlsa",
            "resolve_pub_tlsa",
            "crypto_sum",
            "resolve_dns_sum",
            "run_time", "initialization_total", "initialization_manager", "initialization_publishers", "initialization_subscribers"
        ],
    }

    def _format_metric(df: pl.DataFrame, metric: str) -> str | None:
        cols = [f"{metric}_min", f"{metric}_mean", f"{metric}_max"]
        if any(col not in df.columns for col in cols):
            return None
        values = [df.select(col).item() for col in cols]
        if any(value is None for value in values):
            return None
        values_ms = [float(value) / metric_scaling[metric] for value in values]
        return (
            f"        {metric_labels[metric]} & \\SI{{{values_ms[0]:.2f}}}{{}} & "
            f"\\SI{{{values_ms[1]:.2f}}}{{}} & \\SI{{{values_ms[2]:.2f}}}{{}} \\\\"
        )

    config_by_section = {}
    for config, df in config_map.items():
        section = config.split("_")[0]
        if section in section_order:
            config_by_section[section] = df

    lines = [
        r"    \begin{tabularx}{\linewidth}{L r r r}",
        r"        \toprule",
        r"        \textbf{Metric} & \textbf{Min [\si{\milli\second}]} & \textbf{Mean [\si{\milli\second}]} & \textbf{Max [\si{\milli\second}]} \\",
    ]

    first_section = True
    for section in section_order:
        if section not in config_by_section:
            continue
        if first_section:
            lines.append(r"        \toprule")
            first_section = False
        else:
            lines.append(r"        \toprule")

        lines.append(
            f"        \\multicolumn{{4}}{{c}}{{\\textit{{{section_titles[section]}}}}} \\\\"
        )
        lines.append(r"        \midrule")

        df = config_by_section[section]
        for metric in metrics_per_section[section]:
            latex_row = _format_metric(df, metric)
            if latex_row is not None:
                lines.append(latex_row)

    lines.extend([r"        \bottomrule", r"    \end{tabularx}"])

    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")

def print_report_table_scalability_mean_service_setup(config_map, path):
    # creates a table per series (A, F, H) with the service_setup[_min, _mean, _max] values for each sub_count in the config
    # example for 5 sub count series
    # pub_count, sub_count,setup_delay_min,setup_delay_max,setup_delay_mean
    # 1,1,3.275682,3.465888,3.35806715
    # 1,2,3.2203,3.584216,3.3255767000000005
    # 1,3,3.18605,3.828147,3.291612783333333
    # 1,4,3.187712,3.533842,3.303841525
    # 1,5,3.17876,4.351194,3.2786193
    heading = ["pub_count", "sub_count", "setup_delay_min", "setup_delay_max", "setup_delay_mean"]
    data_rows = []
    for config, df in config_map.items():
        pub_count, sub_count = get_pubsub_count_from_config(config)
        if "service_setup_mean" not in df.columns:
            logger.warning(f"service_setup_mean column not found in df for config {config}, skipping")
            continue
        row = [str(pub_count), str(sub_count)]
        for suffix in ["_min", "_max", "_mean"]:
            value = df.select(f"service_setup{suffix}").item()
            if value is None:
                row.append("n/a")
            else:
                row.append(f"{float(value) / 1_000_000:.6f}")
        data_rows.append(row)

    # ensure rows are sorted by pub_count and sub_count
    data_rows.sort(key=lambda x: (int(x[0]), int(x[1])))
    with open(path, "w") as f:
        f.write(", ".join(heading) + "\n")
        for row in data_rows:
            f.write(", ".join(row) + "\n")
            

def split_data_set_for_series(config_map) -> dict[str, dict[str, pl.DataFrame]]:
    # the config name is in format "{series}_p{pub_count}_s{sub_count}", e.g., "A_p1_s1"
    # create separate dataframes for each series prefix in the config names, e.g., "A", "F", "H"
    series_map = {}
    for config, df in config_map.items():
        series = config.split("_")[0]
        pubs_subs_part = config.replace(f"{series}_", "")
        if series not in series_map:
            series_map[series] = dict()
        series_map[series][pubs_subs_part] = df    
    return series_map



@app.command()
def main():
    logger.info("Generating plots, tables and latex input from data...")
    if not check_data_exists():
        return

    # import processed data as scenario -> config -> df structure
    logger.info("Loading processed data...")
    data = load_processed_data()

    logger.info("Printing reports as csv for every config...")
    for scenario, config_map in data.items():
        # check if dir exists in reports for scenario, if not create it
        scenario_report_dir = REPORTS_DIR / scenario
        scenario_report_dir.mkdir(parents=True, exist_ok=True)
        for config, df in tqdm(
            config_map.items(),
            desc=f"Processing configs for {scenario}",
            leave=True,
        ):
            print_report_table_config_stats(df, scenario_report_dir / f"{config}.csv")
        if scenario == "carnet":
            create_latex_table_config_stats(
                config_map, scenario_report_dir / "table-carnet-statistics.tex"
            )

    # print scalability report tables
    for scenario, config_map in data.items():
        if "scalability" not in scenario:
            continue
        split_configs = split_data_set_for_series(config_map)
        for series, series_config_map in split_configs.items():
            print_report_table_scalability_mean_service_setup(
                series_config_map, REPORTS_DIR / scenario / f"scalability-{series}-statistics.csv"
            )
    

    logger.success("Data plotting complete.")


if __name__ == "__main__":
    app()
