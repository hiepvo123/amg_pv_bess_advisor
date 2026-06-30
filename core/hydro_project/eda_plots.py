from pathlib import Path
import matplotlib.pyplot as plt


def _require_columns(df, columns, plot_name):
    missing = [col for col in columns if col not in df.columns]
    if missing:
        print(f"Skip {plot_name}: missing columns {missing}. Current columns: {list(df.columns)}")
        return False
    return True


def plot_water_level_trend(df, output_dir):
    if not _require_columns(df, ["date", "h_mean_m"], "water level trend"):
        return

    plot_df = df.dropna(subset=["date", "h_mean_m"])

    plt.figure(figsize=(12, 5))
    plt.plot(plot_df["date"], plot_df["h_mean_m"], marker="o")
    plt.xlabel("Date")
    plt.ylabel("Mean reservoir level (m)")
    plt.title("Reservoir Water Level Trend")
    plt.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(Path(output_dir) / "eda_water_level_trend.png", dpi=300)
    plt.close()


def plot_flow_trend(df, output_dir):
    if "date" not in df.columns:
        print("Skip flow trend: missing date column.")
        return

    plt.figure(figsize=(12, 5))

    if "q_turbine_m3s" in df.columns:
        plot_df = df.dropna(subset=["date", "q_turbine_m3s"])
        plt.plot(plot_df["date"], plot_df["q_turbine_m3s"], marker="o", label="Q turbine")

    if "q_inflow_m3s" in df.columns:
        plot_df = df.dropna(subset=["date", "q_inflow_m3s"])
        plt.plot(plot_df["date"], plot_df["q_inflow_m3s"], marker="o", label="Q inflow")

    plt.xlabel("Date")
    plt.ylabel("Flow (m3/s)")
    plt.title("Flow Trend")
    plt.legend()
    plt.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(Path(output_dir) / "eda_flow_trend.png", dpi=300)
    plt.close()


def plot_q_vs_power(df, output_dir):
    if not _require_columns(df, ["q_turbine_m3s", "p_theoretical_mw"], "Q vs power"):
        return

    plot_df = df.dropna(subset=["q_turbine_m3s", "p_theoretical_mw"])
    if plot_df.empty:
        print("Skip Q vs power: no valid rows after dropping missing values.")
        return

    plt.figure(figsize=(7, 5))
    plt.scatter(plot_df["q_turbine_m3s"], plot_df["p_theoretical_mw"])
    plt.xlabel("Q turbine (m3/s)")
    plt.ylabel("Theoretical power (MW)")
    plt.title("Q Turbine vs Theoretical Power")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(Path(output_dir) / "eda_q_vs_power.png", dpi=300)
    plt.close()


def plot_water_balance_residual(df, output_dir):
    if not _require_columns(df, ["date", "water_balance_residual_m3s"], "water balance residual"):
        return

    plot_df = df.dropna(subset=["date", "water_balance_residual_m3s"])
    if plot_df.empty:
        print("Skip water balance residual: no valid rows.")
        return

    plt.figure(figsize=(12, 5))
    plt.bar(plot_df["date"].astype(str), plot_df["water_balance_residual_m3s"])
    plt.xlabel("Date")
    plt.ylabel("Residual (m3/s equivalent)")
    plt.title("Water Balance Residual")
    plt.grid(True)
    plt.xticks(rotation=90, fontsize=7)
    plt.tight_layout()
    plt.savefig(Path(output_dir) / "eda_water_balance_residual.png", dpi=300)
    plt.close()


def create_all_eda_plots(df, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Columns available for EDA:", list(df.columns))

    plot_water_level_trend(df, output_dir)
    plot_flow_trend(df, output_dir)
    plot_q_vs_power(df, output_dir)
    plot_water_balance_residual(df, output_dir)
