import os
from pathlib import Path

from loguru import logger
import polars as pl
from tqdm import tqdm
import typer

from mininet_vsomeip_dnssec.config import (
    INTERIM_DATA_DIR,
    PROCESSED_DATA_DIR,
    RAW_DATA_DIR,
    SCENARIOS,
    get_pubsub_count_from_config,
    get_config_for_pubsub_count
)

app = typer.Typer()


def _find_files_per_service(raw_run_dir: str) -> dict[str, str]:
    # list files per run and parse as map service -> file path
    # 1. list files in raw dir
    files = [
        f
        for f in os.listdir(raw_run_dir)
        if (os.path.isfile(os.path.join(raw_run_dir, f)) and f.endswith(".csv"))
    ]
    # 2. parse file names to extract service name
    service_map = {}
    for f in files:
        # Assuming file name format is "A-SERVICEID-#0.csv"
        service_name = f.split("-")[1]  # Extract SERVICEID
        service_map[service_name] = os.path.join(raw_run_dir, f)
    # 3. return map service -> file path sorted by service name
    return dict(sorted(service_map.items()))


def _find_files_per_run(raw_config_dir: str) -> dict[str, dict[str, str]]:
    # list files and parse as map run -> map service -> file path
    # 1. list runs in raw/run-{RUN}
    run_folders = [
        d
        for d in os.listdir(raw_config_dir)
        if (os.path.isdir(os.path.join(raw_config_dir, d)) and d.startswith("run-"))
    ]
    run_map = {}
    for run in run_folders:
        run_num = run.split("-")[1]  # Extract RUN
        run_map[run_num] = _find_files_per_service(os.path.join(raw_config_dir, run))
    return dict(sorted(run_map.items(), key=lambda item: int(item[0])))


def _find_files_per_config(raw_series_dir: str) -> dict[str, dict[str, dict[str, str]]]:
    # list files and parse as map config -> map run -> map service -> file path
    # 1. list configs in raw/{SCENARIO}
    config_folders = [
        d
        for d in os.listdir(raw_series_dir)
        if (os.path.isdir(os.path.join(raw_series_dir, d)) and d.startswith("p"))
    ]
    config_map = {}
    for config in config_folders:
        config_map[config] = _find_files_per_run(os.path.join(raw_series_dir, config))
    return dict(sorted(config_map.items()))


def _find_files_per_series(
    raw_scenario_dir: str,
) -> dict[str, dict[str, dict[str, dict[str, str]]]]:
    # list files and parse as map series -> map config -> map run -> map service -> file path
    # 1. list series in raw
    series_folders = [
        d
        for d in os.listdir(raw_scenario_dir)
        if (os.path.isdir(os.path.join(raw_scenario_dir, d)) and d.endswith("-series"))
    ]
    series_map = {}
    for series in series_folders:
        series_name = series.split("-")[0]  # Extract SERIES
        series_map[series_name] = _find_files_per_config(os.path.join(raw_scenario_dir, series))
    return dict(sorted(series_map.items()))


def _find_files_per_scenario(
    raw_dir: str,
) -> dict[str, dict[str, dict[str, dict[str, dict[str, str]]]]]:
    # list files and parse as map scenario -> map series -> map config -> map run -> map service -> file path
    scenario_map = {}
    for scenario in SCENARIOS:
        scenario_map[scenario] = _find_files_per_series(os.path.join(raw_dir, scenario))
    return scenario_map


columns_to_drop = [
    "PUBLISHER_APP_INITIALIZATION",
    "GENERATE_OFFER_NONCE_START",
    "GENERATE_OFFER_NONCE_END",
    "FIND_RECEIVE",
    "OFFER_SEND",
    "SVCB_SERVICE_REQUEST_RECEIVE",
    "SVCB_SERVICE_RESPONSE_SEND",
    "SVCB_CLIENT_REQUEST_SEND",
    "SVCB_CLIENT_REQUEST_RECEIVE",
    "SVCB_CLIENT_RESPONSE_SEND",
    "SVCB_CLIENT_RESPONSE_RECEIVE",
    "TLSA_CLIENT_REQUEST_RECEIVE",
    "TLSA_CLIENT_RESPONSE_SEND",
    "TLSA_SERVICE_REQUEST_RECEIVE",
    "TLSA_SERVICE_RESPONSE_SEND",
]
column_duration_pairs = {
    (
        "SUBSCRIBER_APP_INITIALIZATION_START",
        "SUBSCRIBER_APP_INITIALIZATION_END",
    ): "subscriber_app_init_dur",
    ("FIND_SEND", "OFFER_RECEIVE"): "find_offer_dur",
    ("SVCB_SERVICE_REQUEST_SEND", "SVCB_SERVICE_RESPONSE_RECEIVE"): "svcb_service_dur",
    ("VALIDATE_OFFER_START", "VALIDATE_OFFER_END"): "validate_offer_dur",
    ("CLIENT_SIGN_START", "CLIENT_SIGN_END"): "client_sign_dur",
    ("OFFER_RECEIVE", "SUBSCRIBE_SEND"): "offer_to_subscribe_dur",
    ("SUBSCRIBE_SEND", "SUBSCRIBE_RECEIVE"): "subscribe_transmission_dur",
    ("TLSA_CLIENT_REQUEST_SEND", "TLSA_CLIENT_RESPONSE_RECEIVE"): "tlsa_client_dur",
    ("VERIFY_CLIENT_SIGNATURE_START", "VERIFY_CLIENT_SIGNATURE_END"): "verify_client_dur",
    ("SERVICE_SIGN_START", "SERVICE_SIGN_END"): "service_sign_dur",
    ("SUBSCRIBE_ACK_SEND", "SUBSCRIBE_ACK_RECEIVE"): "subscribeack_transmission_dur",
    ("SUBSCRIBE_SEND", "SUBSCRIBE_ACK_RECEIVE"): "subscribe_to_subscribeack_client_dur",
    ("SUBSCRIBE_RECEIVE", "SUBSCRIBE_ACK_SEND"): "subscribe_to_subscribeack_service_dur",
    ("TLSA_SERVICE_REQUEST_SEND", "TLSA_SERVICE_RESPONSE_RECEIVE"): "tlsa_service_dur",
    ("VERIFY_SERVICE_SIGNATURE_START", "VERIFY_SERVICE_SIGNATURE_END"): "verify_service_dur",
    ("OFFER_RECEIVE", "SUBSCRIBE_ACK_RECEIVE"): "offer_receive_to_subscribeack_dur",
    ("VALIDATE_OFFER_END", "SUBSCRIBE_ACK_RECEIVE"): "validate_offer_to_subscribeack_dur",
    ("OFFER_RECEIVE", "VERIFY_SERVICE_SIGNATURE_END"): "offer_receive_to_verify_service_dur",
    ("VALIDATE_OFFER_END", "VERIFY_SERVICE_SIGNATURE_END"): "validate_offer_to_verify_service_dur",
}
cols_duration = list(column_duration_pairs.values()) + [
    "subscription_dur",
    "valid_offer_to_subscription_dur",
]
cols_first_last = [
    ("SUBSCRIBER_APP_INITIALIZATION_START", "subscriber_app_initialization_start"),
    ("OFFER_RECEIVE", "offer_receive"),
    ("VALIDATE_OFFER_END", "validate_offer_end"),
    ("FIND_SEND", "find_send"),
    ("SUBSCRIBE_SEND", "subscribe_send"),
    ("SUBSCRIBE_ACK_RECEIVE", "subscribe_ack_receive"),
    ("VERIFY_SERVICE_SIGNATURE_END", "verify_service_signature_end"),
    ("SVCB_SERVICE_REQUEST_SEND", "svcb_service_request_send"),
    ("TLSA_CLIENT_REQUEST_SEND", "tlsa_client_request_send"),
    ("TLSA_SERVICE_REQUEST_SEND", "tlsa_service_request_send"),
    ("SUBSCRIBER_APP_INITIALIZATION_END", "subscriber_app_initialization_end"),
]
sum_stats = {
    "dns_resolution": ["svcb_service_dur", "tlsa_client_dur", "tlsa_service_dur"],
    "sign": ["client_sign_dur", "service_sign_dur"],
    "verify": ["verify_client_dur", "verify_service_dur"],
    "crypto": ["client_sign_dur", "service_sign_dur", "verify_client_dur", "verify_service_dur"],
}


def preprocess_stat_file(raw_file: str) -> pl.DataFrame:
    duration_exprs = [
        (
            pl.when(pl.col(start_col).is_null() | pl.col(end_col).is_null())
            .then(None)
            .otherwise(pl.col(end_col) - pl.col(start_col))
        ).alias(duration_col)
        for (start_col, end_col), duration_col in column_duration_pairs.items()
    ]
    # host_ip_expr = pl.col("HOST").map_elements(lambda x: str(ipaddress.IPv4Address(x)), return_dtype=pl.Utf8).alias("host_ip")
    add_exprs = [
        pl.sum_horizontal([pl.col(stat) for stat in stat_set]).alias(f"{stat_name}_dur_sum")
        for stat_name, stat_set in sum_stats.items()
    ]
    return (
        pl.scan_csv(raw_file)
        .drop(columns_to_drop, strict=False)
        .with_columns(
            pl.selectors.numeric().replace(0, None)
        )  # replace 0 with null for numeric columns to avoid skewing aggregates
        .with_columns(duration_exprs)
        .with_columns(add_exprs)
        .with_columns(
            pl.max_horizontal(
                "offer_receive_to_subscribeack_dur", "offer_receive_to_verify_service_dur"
            ).alias("subscription_dur"),
            pl.max_horizontal(
                "validate_offer_to_subscribeack_dur", "validate_offer_to_verify_service_dur"
            ).alias("valid_offer_to_subscription_dur"),
        )
        .with_columns(
            pl.selectors.numeric().clip(0, None)
        )  # ensure no negative values--> set to none
        .with_columns(
            pl.selectors.numeric().replace(0, None)
        )  # replace 0 with null for numeric columns to avoid skewing aggregates
        .collect()
    )


def preprocess_run_data(all_services_df: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    # build aggregate expressions once
    first_last_exprs = [
        expr
        for col_name, alias_base in cols_first_last
        for expr in (
            pl.col(col_name).drop_nulls().min().alias(f"{alias_base}_first"),
            pl.col(col_name).drop_nulls().max().alias(f"{alias_base}_last"),
        )
    ]
    duration_exprs = [
        expr
        for col_name in cols_duration
        for expr in (
            pl.col(col_name).drop_nulls().min().alias(f"{col_name}_min"),
            pl.col(col_name).drop_nulls().mean().alias(f"{col_name}_mean"),
            pl.col(col_name).drop_nulls().std().alias(f"{col_name}_stddev"),
            pl.col(col_name).drop_nulls().max().alias(f"{col_name}_max"),
        )
    ]
    add_exprs = [
        expr
        for stat_name in sum_stats.keys()
        for expr in (
            pl.col(f"{stat_name}_dur_sum").drop_nulls().min().alias(f"{stat_name}_dur_sum_min"),
            pl.col(f"{stat_name}_dur_sum").drop_nulls().mean().alias(f"{stat_name}_dur_sum_mean"),
            pl.col(f"{stat_name}_dur_sum").drop_nulls().max().alias(f"{stat_name}_dur_sum_max"),
        )
    ]
    # expression to drop everything except the columns that contain "dur"
    drop_non_duration_expr = pl.all().exclude("^.*dur.*$")
    # compute all base aggregates in one pass, then derive total durations
    return (
        all_services_df.select(first_last_exprs + duration_exprs + add_exprs)
        .with_columns(
            (pl.col("subscribe_ack_receive_last") - pl.col("offer_receive_first")).alias(
                "total_offer_receive_to_subscribeack_dur"
            ),
            (pl.col("verify_service_signature_end_last") - pl.col("offer_receive_first")).alias(
                "total_offer_receive_to_verify_service_dur"
            ),
            (pl.col("subscribe_ack_receive_last") - pl.col("validate_offer_end_first")).alias(
                "total_validate_offer_to_subscribeack_dur"
            ),
            (
                pl.col("verify_service_signature_end_last") - pl.col("validate_offer_end_first")
            ).alias("total_validate_offer_to_verify_service_dur"),
        )
        .with_columns(
            pl.selectors.numeric().clip(0, None)
        )  # ensure no negative values--> set to none
        .with_columns(
            pl.selectors.numeric().replace(0, None)
        )  # replace 0 with null for numeric columns to avoid skewing
        .with_columns(
            pl.max_horizontal(
                "total_offer_receive_to_subscribeack_dur",
                "total_offer_receive_to_verify_service_dur",
            ).alias("total_dur")
        )
        .drop(drop_non_duration_expr)
    )


def load_or_create_interim_for_service(service_file: str, interim_path: Path) -> pl.DataFrame:
    if interim_path.exists():
        return pl.read_parquet(interim_path)
    else:
        df_stat = preprocess_stat_file(service_file)
        interim_path.parent.mkdir(parents=True, exist_ok=True)
        df_stat.write_parquet(interim_path)
        return df_stat


def load_or_create_interim_for_run(
    all_services_df: pl.DataFrame, interim_path: Path
) -> pl.DataFrame:
    if interim_path.exists():
        return pl.read_parquet(interim_path)
    else:
        df_run = preprocess_run_data(all_services_df)
        interim_path.parent.mkdir(parents=True, exist_ok=True)
        df_run.write_parquet(interim_path)
        return df_run


def load_or_create_interim_for_files(
    run_files: dict[str, dict[str, str]], config_interim_dir: Path, config_info_msg: str
) -> pl.DataFrame:
    # check if interim file already exists for config with all runs, if so load and return
    interim_path = config_interim_dir / "all_runs.parquet"
    if interim_path.exists():
        return pl.read_parquet(interim_path)

    # no interim file for config, so start preprocessing
    config_dfs = []
    for run, service_map in tqdm(
        sorted(run_files.items(), key=lambda item: int(item[0])),
        total=len(run_files),
        desc=f"{config_info_msg} runs",
        leave=True,
    ):
        stat_dfs = []
        for service, file_path in service_map.items():
            df_stat = load_or_create_interim_for_service(
                file_path, config_interim_dir / f"run-{run}" / f"{service}.parquet"
            )
            stat_dfs.append(df_stat)
        df_config = load_or_create_interim_for_run(
            pl.concat(stat_dfs, how="vertical_relaxed", rechunk=True),
            config_interim_dir / f"run-{run}.parquet",
        )
        config_dfs.append(df_config.with_columns(pl.lit(int(run)).alias("run_num")))
    df_config_all_runs = pl.concat(config_dfs, how="vertical_relaxed", rechunk=True)
    interim_path.parent.mkdir(parents=True, exist_ok=True)
    df_config_all_runs.write_parquet(interim_path)
    return df_config_all_runs


def preprocess_log_file(log_file: str) -> dict[str, dict[str, pl.DataFrame]]:
    # read log file as dataframe and extract relevant metrics for config, then return as new df
    # this is a placeholder function, the actual implementation will depend on the format of the log files and the metrics we want to extract
    indicators = {
        # "series": "Evaluation runs for option",
        "initialization": "Total initialization time",
        # "failed": "failed with return code",
        "success": "RUN (",
        "pub_count": "services: [",
        "sub_count": "member_counts: [",
    }
    dfs = dict()
    # read log file and look for indicators to track progress and extract metrics
    pub_count = None
    sub_count = None
    initialization_times = None
    with open(log_file, "r") as f:
        for line in f:
            if indicators["pub_count"] in line:
                # count length of the list that looks like this:
                # services: [1, 2,..., X]
                pub_count = len(line.split(indicators["pub_count"])[1].split("]")[0].strip().split(","))
            elif indicators["sub_count"] in line:
                # add up numbers in the list that indicate the subs per service, looks like this:
                # member_counts: [1,2,2,1,...,1]
                sub_count = sum(int(x) for x in line.split(indicators["sub_count"])[1].split("]")[0].strip().split(","))
            elif indicators["initialization"] in line:
                # looks like this:
                # Total initialization time: 0.8188607692718506s (managers: 0.024270057678222656s, publishers: 0.2712595462799072s, subscribers: 0.5233304500579834s)
                init_total = float(line.split("time:")[1].split("s")[0].strip())
                manager_time = float(line.split("managers:")[1].split("s")[0].strip())
                publisher_time = float(line.split("publishers:")[1].split("s")[0].strip())
                subscriber_time = float(line.split("subscribers:")[1].split("s")[0].strip().split(")")[0].strip())
                initialization_times = {
                    "total": init_total,
                    "manager": manager_time,
                    "publisher": publisher_time,
                    "subscriber": subscriber_time,
                }
            elif indicators["success"] in line:
                # looks like this:
                # RUN (A): 13/25 (1.4339499473571777s)
                series = line.split("RUN (")[1].split("):")[0].strip()
                run = int(line.split("):")[1].split("/")[0].strip())
                run_time = float(line.split("/")[1].split("(")[1].strip().split("s")[0])
                if not pub_count or not sub_count:
                    logger.warning(f"Could not extract pub_count or sub_count from log file {log_file} for run {run}. Skipping this run.")
                    continue
                config = get_config_for_pubsub_count(pub_count, sub_count)
                if series not in dfs:
                    dfs[series] = dict()
                if config not in dfs[series]:
                    dfs[series][config] = pl.DataFrame()
                dfs[series][config] = dfs[series][config].vstack(
                    pl.DataFrame([
                        {
                            "run": run,
                            "run_time": run_time,
                            "initialization_total": initialization_times["total"] if initialization_times else None,
                            "initialization_manager": initialization_times["manager"] if initialization_times else None,
                            "initialization_publishers": initialization_times["publisher"] if initialization_times else None,
                            "initialization_subscribers": initialization_times["subscriber"] if initialization_times else None,
                        }
                    ])
                )
    return dfs

def create_processed_log_data(log_file: str, interim_dir: Path) -> dict[str, dict[str, pl.DataFrame]]:
    dfs = preprocess_log_file(log_file)
    # save processed log data as parquet in interim dir, with one file per series and config, e.g., p1_s1.parquet
    for series, config_map in dfs.items():
        for config, df in config_map.items():
            df.write_parquet(interim_dir / series / config / f"{config}_logs.parquet")
    return dfs

log_columns = [
    "run_time",
    "initialization_total",
    "initialization_manager",
    "initialization_publishers",
    "initialization_subscribers",
]

processed_columns = {
    "crypto_sum": "crypto_dur_sum",
    "create_signatures_sum": "sign_dur_sum",
    "verify_signatures_sum": "verify_dur_sum",
    "resolve_dns_sum": "dns_resolution_dur_sum",
    "resolve_pub_svcb": "svcb_service_dur",
    "resolve_pub_tlsa": "tlsa_service_dur",
    "resolve_sub_tlsa": "tlsa_client_dur",
}
processed_non_aggregates = {
    "network_initialization": "total_dur",
    "service_setup": "subscription_dur_max",
}
processed_results_cols = list(processed_columns.keys()) + list(processed_non_aggregates.keys())
processed_results_cols = [
    col + suffix
    for col in processed_results_cols
    for suffix in ["_min", "_mean", "_stddev", "_max"]
]


def load_or_create_processed_config_data(
    df_config: pl.DataFrame, df_log: pl.DataFrame, config_processed_file: Path
) -> pl.DataFrame:
    # check if processed file already exists for config, if so load and return
    if config_processed_file.exists():
        return pl.read_parquet(config_processed_file)
    # we need to process this config
    process_exprs = [
        expr
        for col_name, stat_name in processed_columns.items()
        for expr in [
            pl.min(f"{stat_name}_min").alias(f"{col_name}_min"),
            pl.mean(f"{stat_name}_mean").alias(f"{col_name}_mean"),
            pl.max(f"{stat_name}_max").alias(f"{col_name}_max"),
        ]
    ]
    process_exprs.extend(
        [
            expr
            for col_name, stat_name in processed_non_aggregates.items()
            for expr in [
                pl.min(f"{stat_name}").alias(f"{col_name}_min"),
                pl.mean(f"{stat_name}").alias(f"{col_name}_mean"),
                pl.max(f"{stat_name}").alias(f"{col_name}_max"),
            ]
        ]
    )
    processed_df = df_config.select(process_exprs).select(
        [
            col
            for col in df_config.select(process_exprs).columns
            if df_config.select(process_exprs)[col].null_count()
            < df_config.select(process_exprs).height
        ]
    )
    log_exprs = [ expr
        for col_name in log_columns
        for expr in [
            pl.min(f"{col_name}").alias(f"{col_name}_min"),
            pl.mean(f"{col_name}").alias(f"{col_name}_mean"),
            pl.max(f"{col_name}").alias(f"{col_name}_max"),
        ]
    ]
    processed_df = processed_df.hstack(df_log.select(log_exprs))
    # save aggregated data for config as parquet in processed dir
    config_processed_file.parent.mkdir(parents=True, exist_ok=True)
    processed_df.write_parquet(config_processed_file)
    return processed_df

def load_processed_data() -> dict[str, dict[str, pl.DataFrame]]:
    processed_data = {}
    for scenario in SCENARIOS:
        scenario_dir = PROCESSED_DATA_DIR / scenario
        if not scenario_dir.exists():
            logger.warning(f"Processed data for scenario {scenario} not found in {PROCESSED_DATA_DIR}. Skipping.")
            continue
        processed_data[scenario] = {}
        for config_file in scenario_dir.glob("*.parquet"):
            config_name = config_file.stem  # get file name without extension
            processed_data[scenario][config_name] = pl.read_parquet(config_file)
    return processed_data


@app.command()
def main():
    logger.info("Processing dataset...")

    files = _find_files_per_scenario(RAW_DATA_DIR)

    if not files or any(len(series_map) == 0 for series_map in files.values()):
        logger.error(
            f"No raw data files found in {RAW_DATA_DIR} or directory structure not recognized. Please check the directory and try again."
        )
        logger.info(
            f"Expected directory structure: {RAW_DATA_DIR}/{{SCENARIO}}/{{SERIES}}/{{CONFIG}}/run-{{RUN}}/{{SERVICE}}.csv"
        )
        return

    # parse interim data
    # create a map scenario -> map series -> map config -> df of all runs for that config
    logger.info("Loading or creating interim datasets for all configs...")
    all_sceario_dfs = dict()
    for scenario, series_map in files.items():
        all_sceario_dfs[scenario] = dict()
        for series, config_map in series_map.items():
            all_sceario_dfs[scenario][series] = dict()
            for config, run_map in config_map.items():
                all_sceario_dfs[scenario][series][config] = load_or_create_interim_for_files(
                    run_map,
                    INTERIM_DATA_DIR / scenario / series / config,
                    f"Preprocessing runs of config {config} for {series}-series in {scenario}",
                )

    logger.info("Preprocessing log data for all configs...")
    processed_logs = dict()
    for scenario in tqdm(SCENARIOS, desc="Processing log files for scenarios", leave=True):
        # list log file in RAW_DATA_DIR / scenario / *.log and take the one with the most recent timestamp 
        log_files = list(Path(RAW_DATA_DIR / scenario).glob("*.log"))
        log_file = None
        current_date = 0
        current_time = 0
        for log_file in log_files: # e.g., carnet_study_20260418-000722.log 
            timestamp_str = log_file.stem.split("_")[-1]  # get timestamp part of file name
            date = int(timestamp_str.split("-")[0])
            time = int(timestamp_str.split("-")[1])
            if date > current_date or (date == current_date and time > current_time):
                current_date = date
                current_time = time
                log_file = log_file
        if log_file:
            logger.info(f"Processing log file {log_file} for config {config} in {series}-series of {scenario}...")
            processed_logs[scenario] = create_processed_log_data(str(log_file), INTERIM_DATA_DIR / scenario)
        else:
            logger.warning(f"Log file {log_file} not found for config {config} in {series}-series of {scenario}. Skipping log data processing for this config.")

    logger.success("Interim datasets for all configs complete.")

    # process all runs for each config to create final processed dataset with aggregates, and save as parquet
    logger.info("Creating processed datasets for all configs...")
    for scenario, series_map in all_sceario_dfs.items():
        for series, config_map in series_map.items():
            for config, df_config in tqdm(
                config_map.items(),
                desc=f"Processing configs for {series}-series in {scenario}",
                leave=True,
            ):
                df_log = None
                if scenario in processed_logs and series in processed_logs[scenario] and config in processed_logs[scenario][series]:
                    df_log = processed_logs[scenario][series][config]
                _ = load_or_create_processed_config_data(
                    df_config, df_log, PROCESSED_DATA_DIR / scenario / f"{series}_{config}.parquet"
                )

    logger.success("Processing dataset complete.")


if __name__ == "__main__":
    app()
