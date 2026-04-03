import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

sns.set(style="whitegrid")

def explore_data(file_path):
    df = pd.read_csv(file_path)
    
    print("--- Basic Information ---")
    print(df.info())
    
    print("\n--- Summary Statistics ---")
    print(df.describe())
    
    print("\n--- Missing Values ---")
    print(df.isnull().sum())
    
    print("\n--- Duplicates ---")
    print(f"Total duplicate rows: {df.duplicated().sum()}")
    
    plot_dir = "eda_plots"
    if not os.path.exists(plot_dir):
        os.makedirs(plot_dir)
    
    num_cols = df.select_dtypes(include=['float64', 'int64']).columns
    for col in num_cols:
        plt.figure(figsize=(10, 6))
        sns.histplot(df[col].dropna(), kde=True)
        plt.title(f'Distribution of {col}')
        plt.savefig(f'{plot_dir}/{col}_distribution.png')
        plt.close()

    if len(num_cols) > 1:
        plt.figure(figsize=(12, 10))
        sns.heatmap(df[num_cols].corr(), annot=True, cmap='coolwarm', fmt=".2f")
        plt.title('Correlation Matrix')
        plt.savefig(f'{plot_dir}/correlation_matrix.png')
        plt.close()

    cat_cols = df.select_dtypes(include=['object']).columns
    for col in cat_cols:
        if df[col].nunique() < 50:
            plt.figure(figsize=(12, 6))
            sns.countplot(y=df[col], order=df[col].value_counts().index[:20])
            plt.title(f'Top 20 counts for {col}')
            plt.savefig(f'{plot_dir}/{col}_counts.png')
            plt.close()

if __name__ == "__main__":
    explore_data("ais_raw.csv")
