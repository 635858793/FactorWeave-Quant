$docsPath = 'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\.trae\documents'
$files = Get-ChildItem -Path $docsPath -File -Filter '*.md' -ErrorAction SilentlyContinue |
    Sort-Object Name

# 输出文件清单
$files | ForEach-Object {
    $sizeKB = [math]::Round($_.Length / 1KB, 2)
    Write-Output ("FILE| " + $_.Name + " | " + $sizeKB.ToString() + " KB | " + $_.LastWriteTime.ToString("yyyy-MM-dd"))
}

Write-Output ""
Write-Output ("TOTAL: " + $files.Count + " files")
$totalSize = ($files | Measure-Object -Property Length -Sum).Sum
Write-Output ("TOTAL SIZE: " + [math]::Round($totalSize/1KB, 2) + " KB")
