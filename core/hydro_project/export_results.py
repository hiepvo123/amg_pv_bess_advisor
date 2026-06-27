from pathlib import Path
from quality_checks import make_qc_summary


def export_outputs(model_df, qc_df, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    model_df.to_csv(output_dir / "ham_thuan_cleaned_daily.csv", index=False, encoding="utf-8-sig")
    qc_df.to_csv(output_dir / "ham_thuan_qc_rows.csv", index=False, encoding="utf-8-sig")

    qc_summary = make_qc_summary(qc_df)
    qc_summary.to_csv(output_dir / "ham_thuan_qc_summary.csv", index=False, encoding="utf-8-sig")
