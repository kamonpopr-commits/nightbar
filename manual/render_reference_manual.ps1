$referenceWord=New-Object -ComObject Word.Application
$referenceWord.Visible=$false
$referenceWord.DisplayAlerts=0
try {
 $referenceDoc=$referenceWord.Documents.Open((Resolve-Path 'output/docx/JUPITER_User_Manual.docx').Path,$false,$false)
 $referenceDoc.EmbedTrueTypeFonts=$true
 $referenceDoc.SaveSubsetFonts=$false
 $referenceDoc.Content.Font.Name='TH Sarabun PSK'
 $referenceDoc.Content.Font.NameBi='TH Sarabun PSK'
 for ($coverIndex=1;$coverIndex -le 2;$coverIndex++) {
  $coverHeader=$referenceDoc.Sections.Item($coverIndex).Headers.Item(1)
  foreach ($art in ,@('tmp/manual/reference-assets/faculty-crest.png',245,108,122,122)) {
   $shape=$coverHeader.Shapes.AddPicture((Resolve-Path $art[0]).Path,$false,$true,[single]$art[1],[single]$art[2],[single]$art[3],[single]$art[4],$coverHeader.Range)
   $shape.RelativeHorizontalPosition=1
   $shape.RelativeVerticalPosition=1
   $shape.Left=[single]$art[1]
   $shape.Top=[single]$art[2]
   $shape.WrapFormat.Type=5
  }
 }
 $referenceDoc.Repaginate()
 $referenceDoc.Fields.Update() | Out-Null
 $referenceDoc.Repaginate()
 $referenceDoc.Fields.Update() | Out-Null
 Write-Output ('Pages: '+$referenceDoc.ComputeStatistics(2))
 $referenceDoc.Save()
 $referenceDoc.ExportAsFixedFormat((Join-Path (Get-Location) 'output\pdf\JUPITER_User_Manual.pdf'),17)
 $referenceDoc.Close(0)
 [void][Runtime.InteropServices.Marshal]::ReleaseComObject($referenceDoc)
} finally { $referenceWord.Quit(); [void][Runtime.InteropServices.Marshal]::ReleaseComObject($referenceWord) }
& 'C:\Users\TUF GAMING\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin\pdftoppm.exe' -r 95 -png output/pdf/JUPITER_User_Manual.pdf tmp/manual/revised
