"""
S&P 500 Historical Dataset Pipeline Orchestrator.
This script runs the entire ETL pipeline sequentially, managing memory efficiently
by executing each module as a separate subprocess.
"""

import subprocess
import time
import sys

def run_step(step_name: str, script_path: str) -> None:
    """
    Executes a Python script as a subprocess and tracks its execution time.
    """
    print(f"\n{'='*80}")
    print(f"STARTING STEP: {step_name}")
    print(f"{'='*80}")
    
    start_time = time.time()
    
    try:
        result = subprocess.run(
            ["uv", "run", "python", script_path], 
            check=True, 
            text=True
        )
        
        elapsed_time = time.time() - start_time
        print(f"\nSTEP COMPLETED: {step_name} (Took {elapsed_time:.2f} seconds)")
        
    except subprocess.CalledProcessError as e:
        print(f"\nSTEP FAILED: {step_name}")
        print(f"Error returned code: {e.returncode}")
        sys.exit(1)
    except KeyboardInterrupt:
        print(f"\nPIPELINE ABORTED BY USER DURING: {step_name}")
        sys.exit(1)

def main():
    print("INITIALIZING S&P 500 DATASET GENERATION PIPELINE\n")
    pipeline_start = time.time()

    pipeline_steps = [
        (
            "1. Generate Daily Composition", 
            "src/s_and_p_500_picker/generate_s_and_p_500_daily_composition.py"
        ),
        (
            "2. Generate Corporate Events Ledger", 
            "src/s_and_p_500_picker/generate_corporate_events.py"
        ),
        (
            "3. Download Historical Prices (Yahoo Finance)", 
            "src/s_and_p_500_picker/download_historical_prices.py"
        ),
        (
            "4. Backfill Missing Prices (Tiingo API)", 
            "src/s_and_p_500_picker/backfill_missing_prices.py"
        ),
        (
            "5. Fetch SEC EDGAR Fundamentals", 
            "src/s_and_p_500_picker/fetch_sec_fundamentals.py"
            
            # 6: Feature Engineering
            # src/..................................
        )
        
    ]

    for step_name, script_path in pipeline_steps:
        run_step(step_name, script_path)

    total_time = time.time() - pipeline_start
    print(f"\n{'='*80}")
    print(f"PIPELINE FINISHED SUCCESSFULLY! Total execution time: {total_time:.2f} seconds.")
    print(f"{'='*80}\n")

if __name__ == "__main__":
    main()