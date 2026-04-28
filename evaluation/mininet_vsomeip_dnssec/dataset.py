from pathlib import Path

from loguru import logger
from tqdm import tqdm
import typer
import os
import polars as pl

from mininet_vsomeip_dnssec.config import PROCESSED_DATA_DIR, RAW_DATA_DIR, INTERIM_DATA_DIR, SCENARIOS, get_config_for_pubsub_count, get_pubsub_count_from_config

app = typer.Typer()

def _find_files_per_service(raw_run_dir: str) -> dict[str, str]:
    # list files per run and parse as map service -> file path
    # 1. list files in raw dir
    files = [f for f in os.listdir(raw_run_dir) if (os.path.isfile(os.path.join(raw_run_dir, f)) and f.endswith('.csv'))]
    # 2. parse file names to extract service name
    service_map = {}
    for f in files:
        # Assuming file name format is "A-SERVICEID-#0.csv"
        service_name = f.split('-')[1]  # Extract SERVICEID
        service_map[service_name] = os.path.join(raw_run_dir, f)
    # 3. return map service -> file path sorted by service name
    return dict(sorted(service_map.items()))

def _find_files_per_run(raw_config_dir: str) -> dict[str, dict[str, str]]:
    # list files and parse as map run -> map service -> file path
    # 1. list runs in raw/run-{RUN}
    run_folders = [d for d in os.listdir(raw_config_dir) if (os.path.isdir(os.path.join(raw_config_dir, d)) and d.startswith('run-'))]
    run_map = {}
    for run in run_folders:
        run_num = run.split('-')[1]  # Extract RUN
        run_map[run_num] = _find_files_per_service(os.path.join(raw_config_dir, run))
    return dict(sorted(run_map.items(), key=lambda item: int(item[0])))

def _find_files_per_config(raw_series_dir: str) -> dict[str, dict[str, dict[str, str]]]:
    # list files and parse as map config -> map run -> map service -> file path
    # 1. list configs in raw/{SCENARIO}
    config_folders = [d for d in os.listdir(raw_series_dir) if (os.path.isdir(os.path.join(raw_series_dir, d)) and d.startswith('p'))]
    config_map = {}
    for config in config_folders:
        config_map[config] = _find_files_per_run(os.path.join(raw_series_dir, config))
    return dict(sorted(config_map.items()))

def _find_files_per_series(raw_scenario_dir: str) -> dict[str, dict[str, dict[str, dict[str, str]]]]:
    # list files and parse as map series -> map config -> map run -> map service -> file path
    # 1. list series in raw
    series_folders = [d for d in os.listdir(raw_scenario_dir) if (os.path.isdir(os.path.join(raw_scenario_dir, d)) and d.endswith('-series'))]
    series_map = {}
    for series in series_folders:
        series_name = series.split('-')[0]  # Extract SERIES
        series_map[series_name] = _find_files_per_config(os.path.join(raw_scenario_dir, series))
    return dict(sorted(series_map.items()))

def _find_files_per_scenario(raw_dir: str) -> dict[str, dict[str, dict[str, dict[str, dict[str, str]]]]]:
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
    ("SUBSCRIBER_APP_INITIALIZATION_START", "SUBSCRIBER_APP_INITIALIZATION_END"): "subscriber_app_init_dur",
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

def preprocess_stat_file(raw_file: str) -> pl.DataFrame:
    duration_exprs = [
        (pl.col(end_col) - pl.col(start_col)).alias(duration_col)
        for (start_col, end_col), duration_col in column_duration_pairs.items()
    ]
    # host_ip_expr = pl.col("HOST").map_elements(lambda x: str(ipaddress.IPv4Address(x)), return_dtype=pl.Utf8).alias("host_ip")
    return (
        pl.scan_csv(raw_file)
        .drop(columns_to_drop, strict=False)
        .with_columns(pl.selectors.numeric().replace(0, None)) # replace 0 with null for numeric columns to avoid skewing aggregates
        .with_columns(duration_exprs)
        .with_columns(
            [
                pl.max_horizontal(
                    "offer_receive_to_subscribeack_dur",
                    "offer_receive_to_verify_service_dur",
                ).alias("subscription_dur"),
                pl.max_horizontal(
                    "validate_offer_to_subscribeack_dur",
                    "validate_offer_to_verify_service_dur",
                ).alias("valid_offer_to_subscription_dur"),
                pl.min_horizontal(
                    "svcb_service_dur",
                    "tlsa_client_dur",
                    "tlsa_service_dur",
                ).alias("dns_resolution_min_dur"),
                pl.mean_horizontal(
                    "svcb_service_dur",
                    "tlsa_client_dur",
                    "tlsa_service_dur",
                ).alias("dns_resolution_mean_dur"),
                pl.max_horizontal(
                    "svcb_service_dur",
                    "tlsa_client_dur",
                    "tlsa_service_dur",
                ).alias("dns_resolution_max_dur"),
            ]
        )
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
    dns_exprs = [
        pl.col("dns_resolution_min_dur").drop_nulls().min().alias("dns_resolution_dur_min"),
        pl.col("dns_resolution_mean_dur").drop_nulls().mean().alias("dns_resolution_dur_mean"),
        pl.col("dns_resolution_max_dur").drop_nulls().max().alias("dns_resolution_dur_max"),
    ]
    # expression to drop everything except the columns that contain "dur"
    drop_non_duration_expr = pl.all().exclude("^.*dur.*$")
    # compute all base aggregates in one pass, then derive total durations
    return (
        all_services_df
        .select(first_last_exprs + duration_exprs + dns_exprs)
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
            (pl.col("verify_service_signature_end_last") - pl.col("validate_offer_end_first")).alias(
                "total_validate_offer_to_verify_service_dur"
            ),
        ).drop(drop_non_duration_expr)
    )

def load_or_create_interim_for_service(service_file: str, interim_path: Path) -> pl.DataFrame:
    if interim_path.exists():
        return pl.read_parquet(interim_path)
    else:
        df_stat = preprocess_stat_file(service_file)
        interim_path.parent.mkdir(parents=True, exist_ok=True)
        df_stat.write_parquet(interim_path)
        return df_stat

def load_or_create_interim_for_run(all_services_df: pl.DataFrame, interim_path: Path) -> pl.DataFrame:
    if interim_path.exists():
        return pl.read_parquet(interim_path)
    else:
        df_run = preprocess_run_data(all_services_df)
        interim_path.parent.mkdir(parents=True, exist_ok=True)
        df_run.write_parquet(interim_path)
        return df_run

def load_or_create_interim_for_files(run_files: dict[str, dict[str, str]], config_interim_dir: str, config_info_msg: str) -> pl.DataFrame:
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
            df_stat = load_or_create_interim_for_service(file_path, config_interim_dir / f"run-{run}" / f"{service}.parquet")
            stat_dfs.append(df_stat)
        df_config = load_or_create_interim_for_run(pl.concat(stat_dfs, how="vertical_relaxed", rechunk=True), config_interim_dir / f"run-{run}.parquet")
        config_dfs.append(df_config)
    df_config_all_runs = pl.concat(config_dfs, how="vertical_relaxed", rechunk=True)
    df_config_all_runs.write_parquet(interim_path)
    return df_config_all_runs
            


@app.command()
def main(
):
    logger.info("Processing dataset...")

    files = _find_files_per_scenario(RAW_DATA_DIR)

    # parse interim data 
    # create a map scenario -> map series -> map config -> df of all runs for that config
    print("Loading or creating interim datasets for all configs...")
    all_sceario_dfs = dict()
    for scenario, series_map in files.items():
        all_sceario_dfs[scenario] = dict()
        for series, config_map in series_map.items():
            all_sceario_dfs[scenario][series] = dict()
            for config, run_map in config_map.items():
                all_sceario_dfs[scenario][series][config] = load_or_create_interim_for_files(run_map, INTERIM_DATA_DIR / scenario / series / config, f"Processing runs of config {config} for {series}-series in {scenario}") 
                
    # process all runs for each config to create final processed dataset with aggregates, and save as parquet

    logger.success("Processing dataset complete.")

    
if __name__ == "__main__":
    app()
