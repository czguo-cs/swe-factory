# Data Versioning

This directory provides a hybrid strategy to accurately version task instances. It combines two methods for robust results, prioritizing accuracy while maintaining automation.

***

### Our Approach

Our pipeline intelligently combines two methods:

1.  **Pattern-Based Method (Primary)**
    Inspired by SWE-bench, this method uses a predefined map of repository paths (e.g., `__init__.py`, `package.json`) and regex patterns to find the exact version string. It is extremely fast and accurate for supported projects.

2.  **Git-Based Method (Fallback)**
    This fully automated method infers the version by finding the nearest tag to a commit using git describe --tags. It requires no manual setup but is more time-consuming due to the need for repository cloning and checkout operations.

If a pattern is not defined for a repository, the system will automatically use the Git-Based Method for that task. However, for the best overall performance and accuracy, we still recommend using both methods together. This hybrid approach ensures we can efficiently retrieve version information for the vast majority of task instances.
***

### How to Use

Run the provided shell script to execute the entire versioning pipeline. The script runs both methods and merges the results into a final versioned file.

**Command:**
```bash
bash run_versioning.sh <instance_file> <output_dir> [testbed_dir]
````

**Arguments:**

  * `<instance_file>`: **(Required)** Path to your input task instances file.
  * `<output_dir>`: **(Required)** Directory to store the results.
  * `[testbed_dir]`: **(Optional)** Temporary directory for cloning repos. Defaults to `./testbed`.

The final, merged output will be saved in the `<output_dir>`.


