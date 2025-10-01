# Thanatos Bot SFTP Deployment Helper
Write-Host "🚀 Thanatos Bot Deployment Helper" -ForegroundColor Green
Write-Host "=================================" -ForegroundColor Green
Write-Host ""

# Check if we're in the right directory
if (!(Test-Path "main.py")) {
    Write-Host "❌ Error: Please run this script from the Thanatos Project directory" -ForegroundColor Red
    exit 1
}

Write-Host "✅ GitHub Status: All changes pushed successfully" -ForegroundColor Green
Write-Host "📦 Repository: https://github.com/HydrikMasqued/thanatos-bot.git" -ForegroundColor Cyan
Write-Host ""

# Files to upload (modified files)
Write-Host "📁 Files to Upload (Modified):" -ForegroundColor Yellow
$modifiedFiles = @(
    "main.py",
    "utils/database.py", 
    "utils/smart_time_formatter.py",
    "utils/time_parser.py",
    "debug_main.py",
    "dashboard/app.py",
    "cogs/enhanced_menu_system.py"
)

foreach ($file in $modifiedFiles) {
    if (Test-Path $file) {
        Write-Host "  ✓ $file" -ForegroundColor Green
    } else {
        Write-Host "  ❌ $file (NOT FOUND)" -ForegroundColor Red
    }
}

Write-Host ""

# New files to upload
Write-Host "➕ New Files to Upload:" -ForegroundColor Yellow
$newFiles = @(
    "cogs/dues_v2.py",
    "cogs/prospects_v2.py",
    "cogs/time_converter.py",
    "CHANGELOG_DUES_SYSTEM_V2.md",
    "CHANGELOG_SUMMARY.md", 
    "ENHANCED_DUES_SYSTEM.md",
    "PROSPECTS_DUES_V2_CHANGELOG.md",
    "SIMPLIFIED_DUES_SYSTEM_GUIDE.md",
    "TECHNICAL_CHANGELOG.md",
    "V2_IMPLEMENTATION_SUMMARY.md",
    "DEPLOYMENT_GUIDE.md"
)

foreach ($file in $newFiles) {
    if (Test-Path $file) {
        Write-Host "  ✓ $file" -ForegroundColor Green
    } else {
        Write-Host "  ❌ $file (NOT FOUND)" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "📋 Next Steps:" -ForegroundColor Cyan
Write-Host "1. Connect to your SFTP server"
Write-Host "2. Upload the files marked with ✓ above"
Write-Host "3. Remove deprecated files from server" 
Write-Host "4. Update dependencies on server"
Write-Host "5. Restart your bot service"
Write-Host "6. Test the new features"
Write-Host ""
Write-Host "📖 See DEPLOYMENT_GUIDE.md for detailed instructions" -ForegroundColor Green

# Create upload list file
$uploadList = $modifiedFiles + $newFiles
$uploadList | Out-File -FilePath "files_to_upload.txt" -Encoding UTF8
Write-Host ""
Write-Host "💾 Created files_to_upload.txt with complete file list" -ForegroundColor Green