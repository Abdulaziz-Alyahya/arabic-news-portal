import subprocess
import sys
import logging
import os


# Create logs folder if it does not exist
os.makedirs("logs", exist_ok=True)


# Configure logging
logging.basicConfig(
    filename="logs/pipeline.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


STEPS = [
    ("Database setup", "data/database.py"),
    ("Article collection", "collection/rss_collector.py"),
    ("Text preprocessing", "processing/prepare_text.py"),
    ("Story clustering", "analysis/create_clusters.py"),
]


def run_step(name, script):

    print(f"\nRunning: {name}")

    try:
        subprocess.run(
            [sys.executable, script],
            check=True
        )

        logging.info("%s completed successfully", name)
        print(f"Completed: {name}")

    except subprocess.CalledProcessError as error:

        logging.error(
            "%s failed with return code %s",
            name,
            error.returncode
        )

        print(f"ERROR: {name} failed.")
        sys.exit(1)


def main():

    print("\nArabic News Backend Pipeline")
    print("============================")

    logging.info("Pipeline started")

    for name, script in STEPS:
        run_step(name, script)

    logging.info("Pipeline completed successfully")

    print("\nPipeline completed successfully.")


if __name__ == "__main__":
    main()
    