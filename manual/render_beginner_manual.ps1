$manualWord = $null
$manualDoc = $null
try {
 $manualWord = New-Object -ComObject Word.Application
 $manualWord.Visible = $false
 $manualWord.DisplayAlerts = 0
 $manualDoc = $manualWord.Documents.Open((Resolve-Path 'output/docx/JUPITER_User_Manual.docx').Path,$false,$false)
 $manualDoc.Repaginate()
 $manualDoc.Fields.Update() | Out-Null
 $manualDoc.Repaginate()
 $manualDoc.Fields.Update() | Out-Null
 Write-Output ('Pages: ' + $manualDoc.ComputeStatistics(2))
 $manualDoc.Save()
 $manualDoc.ExportAsFixedFormat((Join-Path (Get-Location) 'output/pdf/JUPITER_User_Manual.pdf'),17)
 Write-Output 'Word and PDF saved'
} finally {
 if ($manualDoc) { $manualDoc.Close(0); [void][Runtime.InteropServices.Marshal]::ReleaseComObject($manualDoc) }
 if ($manualWord) { $manualWord.Quit(); [void][Runtime.InteropServices.Marshal]::ReleaseComObject($manualWord) }
}
