$excel = New-Object -ComObject Excel.Application
$excel.Visible = $false
$excel.DisplayAlerts = $false
$folder = "c:\Users\erozo\Antigravity ER\estate_auditor"
$file = Get-ChildItem $folder -Filter "Instructivo*" | Select-Object -First 1
$wb = $excel.Workbooks.Open($file.FullName)

# Nombres de hojas
Write-Host "SHEET_NAMES_START"
for ($i = 1; $i -le $wb.Sheets.Count; $i++) {
    Write-Host $wb.Sheets.Item($i).Name
}
Write-Host "SHEET_NAMES_END"

# Hoja 1
$ws = $wb.Sheets.Item(1)
$nRows = $ws.UsedRange.Rows.Count
$nCols = $ws.UsedRange.Columns.Count
Write-Host "SHEET1_DIMS"
Write-Host $nRows
Write-Host $nCols

Write-Host "SHEET1_ROWS_START"
for ($r = 1; $r -le 8; $r++) {
    $parts = @()
    for ($c = 1; $c -le $nCols; $c++) {
        $parts += $ws.Cells.Item($r,$c).Text
    }
    Write-Host ($parts -join "||")
}
Write-Host "SHEET1_ROWS_END"

Write-Host "COL_UNIQUES_START"
for ($c = 1; $c -le $nCols; $c++) {
    $h = $ws.Cells.Item(1,$c).Text
    $seen = @{}
    $uniq = @()
    for ($r = 2; $r -le [Math]::Min(2000,$nRows); $r++) {
        $v = $ws.Cells.Item($r,$c).Text
        if ($v -ne "" -and -not $seen[$v]) {
            $seen[$v] = 1
            $uniq += $v
        }
        if ($uniq.Count -ge 15) { break }
    }
    Write-Host ("COL" + $c + "=" + $h + "=>" + ($uniq -join "||"))
}
Write-Host "COL_UNIQUES_END"

$wb.Close($false)
$excel.Quit()
