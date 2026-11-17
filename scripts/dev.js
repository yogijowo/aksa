const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");

const rootDir = path.resolve(__dirname, "..");
const isWin = process.platform === "win32";

// Priority 1: Project's own virtual environment python
const venvPy = isWin
  ? path.join(rootDir, "services", "engine", ".venv", "Scripts", "python.exe")
  : path.join(rootDir, "services", "engine", ".venv", "bin", "python");

let pythonExecutable = fs.existsSync(venvPy) ? venvPy : (isWin ? "py" : "python3");

const args = process.argv.slice(2);

if (args.includes("--test")) {
  const testArgs = ["-m", "pytest", "services/engine/tests", "-v"];
  const child = spawn(pythonExecutable, testArgs, {
    cwd: rootDir,
    stdio: "inherit",
    env: { ...process.env, AKSA_DEV_MODE: "1", AKSA_AUTH_TOKEN: "dev-aksa-local-token" },
  });
  child.on("exit", (code) => process.exit(code || 0));
} else {
  const scriptPath = path.join(__dirname, "dev.py");
  const child = spawn(pythonExecutable, [scriptPath, ...args], {
    cwd: rootDir,
    stdio: "inherit",
    env: { ...process.env, AKSA_DEV_MODE: "1", AKSA_AUTH_TOKEN: "dev-aksa-local-token" },
  });
  child.on("exit", (code) => process.exit(code || 0));
}
