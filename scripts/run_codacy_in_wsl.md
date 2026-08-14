run_codacy_in_wsl.ps1 — Documentation

Purpose
- Automates downloading and running the Codacy Analysis CLI inside WSL (Ubuntu), executes a selected analysis tool (Bandit by default), and copies the output back to the Windows workspace for inspection.

When to use
- When the Codacy MCP integration is unavailable or fails on Windows.
- When you want a repeatable, local Bandit scan using WSL's Linux environment and installed Java.

Prerequisites
- Windows with WSL2 (e.g., Ubuntu-24.04) available and enabled.
- WSL user able to run apt and sudo (or able to install Java inside WSL).
- PowerShell on Windows to run the script.

High-level behavior
- Ensures a temporary directory in WSL (/tmp/codacy) and downloads the Codacy CLI jar.
- Installs Java (default-jre-headless) if missing (user prompt may be required inside WSL depending on configuration).
- Runs the Codacy CLI against your repository path (mounted under /mnt/<drive>/...) using the selected tool (-Tool, default: bandit).
- Copies the result back to the repo's `scripts/` folder as `codacy_out.json` (or .txt depending on chosen format).

Usage
From the repository root in Windows PowerShell:

```powershell
# default: Bandit, text output
.\scripts\run_codacy_in_wsl.ps1 -Tool bandit -Format text

# JSON output (better for parsing)
.\scripts\run_codacy_in_wsl.ps1 -Tool bandit -Format json

# Run a different tool if supported by Codacy CLI
.\scripts\run_codacy_in_wsl.ps1 -Tool bandit -Format json -ExtraArgs "-s"
```

Flags and parameters
- -Tool: Analysis tool to run (default: bandit).
- -Format: Output format (text or json). When json is used the output file is `scripts/codacy_out.json`.
- -ExtraArgs: Optional extra arguments passed to the Codacy CLI (string).

Outputs
- `scripts/codacy_out.json` or `scripts/codacy_out.txt` in the repository root, containing the Codacy analysis output.

Common use cases
- Quick local Bandit scan when the MCP integration fails.
- CI debugging: run in WSL to verify the Codacy CLI environment and reproduce analysis results locally.
- Generate a machine-readable JSON report to feed other tools or parsers.

Troubleshooting
- If the script fails downloading the CLI: ensure WSL has outbound network access and the download URL is reachable.
- If Java install fails inside WSL: open WSL and run `sudo apt-get update && sudo apt-get install -y default-jre-headless`.
- If the generated output is missing or empty: check the WSL-side temporary output path (/tmp/codacy/out.json) and run the jar command manually inside WSL to inspect errors.
- If Codacy/MCP tools are available and preferred, consider fixing the MCP extension errors instead of using this script.

Security notes
- The script runs commands inside WSL and invokes Java on the downloaded Codacy CLI jar. Inspect the downloaded jar and its source before use in sensitive environments.
- Output files may contain findings about secrets or unsafe code; treat them as sensitive if your policy requires.

Extending / Automation
- You can call this script from a CI job on Windows runners that have WSL enabled.
- For reproducible runs, pin the Codacy CLI version in the script by editing the download URL.

Maintenance
- Keep the Codacy CLI URL up-to-date. If Codacy changes their distribution URL, update the script accordingly.
- Consider adding a `--no-install` flag to skip Java install if your WSL image already contains Java.

Contact
- If you want me to convert this to a POSIX shell script or add JSON parsing helpers, tell me which option you prefer.
