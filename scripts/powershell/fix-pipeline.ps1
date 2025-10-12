# Fix syntax errors in pipeline.py
$filePath = "src/core/pipeline.py"
$content = Get-Content $filePath -Raw -Encoding UTF8

Write-Host "Fixing syntax errors in pipeline.py..." -ForegroundColor Yellow

# Fix 1: Line 234 - Remove orphaned TreeNode parameters after A4
$content = $content -replace '(\s+\)\s+\)\s+)\s+key="A3",\s+title="News & Narrative Signals",\s+description="Aggregate news feeds for sentiment context",\s+action=self\._action_fetch_news,\s+\)\s+\)', '$1'

# Fix 2: Line 389 - Remove orphaned TreeNode parameters after D3_summary  
$content = $content -replace '(\s+action=self\._action_record_safety_heuristics,\s+\)\s+\)\s+)\s+key="D1",\s+title="Penalty Application",\s+description="Apply safety penalties to the feature vector",\s+action=self\._action_apply_penalties,\s+\)\s+\)', '$1'

# Fix 3: Line 962 - Add missing closing parenthesis
$content = $content -replace '(data=\{"penalties": penalties\},)\s+(def _action_compute_composite_metrics)', '$1' + "`n        )`n`n    $2"

# Fix 4: Line 1033 - Remove orphaned parameters after artifact_markdown
$content = $content -replace '(context\.artifact_markdown = markdown)\s+context\.news_items,\s+context\.sentiment_metrics,\s+context\.technical_metrics,\s+context\.security_metrics,\s+context\.final_score,\s+\)', '$1'

# Save fixed content
$content | Out-File $filePath -Encoding UTF8 -NoNewline

Write-Host "Fixed! Testing syntax..." -ForegroundColor Green
python -m py_compile $filePath

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n[SUCCESS] All syntax errors fixed!" -ForegroundColor Green
} else {
    Write-Host "`n[WARNING] Some errors remain, but trying to continue..." -ForegroundColor Yellow
}
