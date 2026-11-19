const path = require("path");
// Strictly load frontend/.env only
require("dotenv").config({ path: path.resolve(__dirname, "../.env") });

const requiredEnvVars = [
  "NEXT_PUBLIC_API_URL",
  "NEXT_PUBLIC_FILM_UI_URL",
  "NODE_ENV",
];

function checkEnvVariables(env = process.env) {
  const missingVars = [...requiredEnvVars];
  const missing = missingVars.filter((envVar) => !env[envVar] || !env[envVar].trim());

  if (missing.length > 0) {
    console.error("Error: The following required environment variables are missing:");
    for (const variable of missing) {
      console.error(`- ${variable}`);
    }
    if (require.main === module) {
      process.exit(1);
    }
    return { valid: false, missing };
  } else {
    console.log("All required environment variables are present.");
    return { valid: true, missing: [] };
  }
}

async function checkBackendHealth(apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000") {
  const healthUrl = `${apiUrl.replace(/\/+$/, "")}/health`;
  try {
    const res = await fetch(healthUrl, { signal: AbortSignal.timeout(3000) });
    if (res.ok) {
      console.log(`[PASS] Backend health check passed (${healthUrl})`);
      return true;
    }
    console.warn(`[WARN] Backend health check returned status: ${res.status}`);
    return false;
  } catch (err) {
    console.warn(`[WARN] Backend is unreachable at ${healthUrl} (${err.message})`);
    return false;
  }
}

async function runPreDeployment() {
  const result = checkEnvVariables();
  if (result.valid) {
    await checkBackendHealth();
  }
}

if (require.main === module) {
  runPreDeployment();
}

module.exports = {
  requiredEnvVars,
  checkEnvVariables,
  checkBackendHealth,
  validateEnvironment: checkEnvVariables,
};
