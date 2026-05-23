Write-Host "====================================="
Write-Host " SakhiSafe Network Setup Script"
Write-Host "====================================="

# -----------------------------
# STEP 1 - Detect WSL IP
# -----------------------------
Write-Host "`n[1] Detecting WSL IP Address..."

$wslIp = (wsl hostname -I).Trim().Split(" ")[0]

if (-not $wslIp) {
    Write-Host "ERROR: Unable to detect WSL IP."
    exit
}

Write-Host "WSL IP Detected: $wslIp"

# -----------------------------
# STEP 2 - Remove Old Port Proxy
# -----------------------------
Write-Host "`n[2] Removing Existing Port Proxy Rules..."

netsh interface portproxy delete v4tov4 `
listenport=8554 `
listenaddress=0.0.0.0

# -----------------------------
# STEP 3 - Add New Port Proxy
# -----------------------------
Write-Host "`n[3] Configuring Port Forwarding..."

netsh interface portproxy add v4tov4 `
listenport=8554 `
listenaddress=0.0.0.0 `
connectport=8554 `
connectaddress=$wslIp

Write-Host "Port forwarding configured successfully."

# -----------------------------
# STEP 4 - Configure Firewall
# -----------------------------
Write-Host "`n[4] Configuring Firewall Rule..."

$ruleName = "SakhiSafe_RTSP_8554"

# Remove old rule if exists
Remove-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue

# Create new rule
New-NetFirewallRule `
-DisplayName $ruleName `
-Direction Inbound `
-Protocol TCP `
-LocalPort 8554 `
-Action Allow

Write-Host "Firewall rule added."

# -----------------------------
# STEP 5 - Verify Port Proxy
# -----------------------------
Write-Host "`n[5] Verifying Port Proxy..."

netsh interface portproxy show all

# -----------------------------
# STEP 6 - Test Docker
# -----------------------------
Write-Host "`n[6] Checking Docker Status..."

docker --version

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker is not installed or running."
    exit
}

Write-Host "Docker is running successfully."

# -----------------------------
# STEP 7 - Optional Docker Compose Start
# -----------------------------
Write-Host "`n[7] Starting Docker Services..."

docker compose up -d

# -----------------------------
# COMPLETE
# -----------------------------
Write-Host "`n====================================="
Write-Host " SakhiSafe Setup Completed Successfully"
Write-Host "====================================="

Write-Host "`nRTSP Stream should now be accessible at:"
Write-Host "rtsp://localhost:8554/cam1"