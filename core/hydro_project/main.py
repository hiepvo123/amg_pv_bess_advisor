from config import INPUT_FILES, OUTPUT_DIR
from data_loader import load_all_excel_files
from data_cleaning import clean_hydro_data
from quality_checks import run_quality_checks
from hydro_model import calculate_hydropower
from eda_plots import create_all_eda_plots
from export_results import export_outputs


def main():
    raw_df = load_all_excel_files(INPUT_FILES)
    print("Raw columns:", list(raw_df.columns))
    print("Raw shape:", raw_df.shape)

    clean_df = clean_hydro_data(raw_df)
    print("Clean columns:", list(clean_df.columns))
    print("Clean shape:", clean_df.shape)

    qc_df = run_quality_checks(clean_df)
    model_df = calculate_hydropower(qc_df)

    create_all_eda_plots(model_df, OUTPUT_DIR)
    export_outputs(model_df, qc_df, OUTPUT_DIR)

    print(f"Done. Outputs saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
