# Git Setup Script for Banking_Copilot
# Run this script from the Banking_Copilot folder

Write-Host "Setting up git repository..." -ForegroundColor Green

# Remove any .git in home directory if it exists
if (Test-Path "C:\Users\acer\.git") {
    Remove-Item -Recurse -Force "C:\Users\acer\.git"
    Write-Host "Removed .git from home directory" -ForegroundColor Yellow
}

# Initialize git in current directory
Write-Host "Initializing git repository..." -ForegroundColor Cyan
git init

# Add remote
Write-Host "Adding remote origin..." -ForegroundColor Cyan
git remote add origin https://github.com/darrendariustan/Banking-CoPilot.git

# Fetch from remote
Write-Host "Fetching from remote..." -ForegroundColor Cyan
git fetch origin

# Checkout main branch
Write-Host "Checking out main branch..." -ForegroundColor Cyan
git checkout -b main origin/main --force

# Verify setup
Write-Host "`nRepository setup complete!" -ForegroundColor Green
Write-Host "Repository location: $(git rev-parse --show-toplevel)" -ForegroundColor Cyan
Write-Host "Remote: $(git remote get-url origin)" -ForegroundColor Cyan
Write-Host "`nNext steps:" -ForegroundColor Yellow
Write-Host "1. git add ." -ForegroundColor White
Write-Host "2. git commit -m 'Your commit message'" -ForegroundColor White
Write-Host "3. git push origin main" -ForegroundColor White

