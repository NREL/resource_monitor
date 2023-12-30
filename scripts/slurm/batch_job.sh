#!/bin/bash
#SBATCH --account=my_account
#SBATCH --job-name=my_job
#SBATCH --time=4:00:00
#SBATCH --output=output_%j.o
#SBATCH --error=output_%j.e
#SBATCH --nodes=5

# Include these two lines in your script to collect stats on all nodes.
rm -f shutdown
srun collect_stats.sh &

# Run your job here.
bash run_my_job.sh

# Include these three lines in your script to gracefully shut down rmon.
touch shutdown
srun wait_for_stats.sh
rm shutdown
