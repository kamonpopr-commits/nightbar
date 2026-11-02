$arrowWord=New-Object -ComObject Word.Application
$arrowWord.Visible=$false
$arrowWord.DisplayAlerts=0
$arrowDoc=$null
try {
 $arrowDoc=$arrowWord.Documents.Open((Resolve-Path 'output/docx/JUPITER_User_Manual.docx').Path,$false,$false)
 $manifest=Get-Content 'tmp/manual/callouts.json' -Raw -Encoding UTF8 | ConvertFrom-Json
 $red=210+35*256+35*65536
 $total=0
 foreach($figure in $manifest) {
  $picture=$null
  foreach($candidate in $arrowDoc.InlineShapes) {
   if($candidate.AlternativeText -eq ('ภาพหน้าจอระบบสาธิต '+$figure.screen)) { $picture=$candidate;break }
  }
  if($null -eq $picture) { throw ('Missing image '+$figure.screen) }
  $anchor=$picture.Range
  $n=0
  foreach($point in $figure.points) {
   $n++
   $tx=[single]($figure.x+$point[1]*$figure.width)
   $ty=[single]($figure.y+$point[2]*$figure.height)
   $cx=[single]($figure.x+$point[3]*$figure.width)
   $cy=[single]($figure.y+$point[4]*$figure.height)
   $dx=$tx-$cx;$dy=$ty-$cy;$length=[Math]::Sqrt($dx*$dx+$dy*$dy)
   $sx=[single]($cx+7*$dx/$length);$sy=[single]($cy+7*$dy/$length)
   $arrow=$arrowDoc.Shapes.AddLine($sx,$sy,$tx,$ty,$anchor)
   $arrow.Name='JUPITER_Arrow_'+$figure.screen+'_'+$n
   $arrow.RelativeHorizontalPosition=1;$arrow.RelativeVerticalPosition=1
   $arrow.Left=[single][Math]::Min($sx,$tx);$arrow.Top=[single][Math]::Min($sy,$ty)
   $arrow.WrapFormat.Type=3
   $arrow.Line.ForeColor.RGB=$red;$arrow.Line.Weight=1.5;$arrow.Line.EndArrowheadStyle=3
   $circle=$arrowDoc.Shapes.AddShape(9,[single]($cx-7),[single]($cy-7),14,14,$anchor)
   $circle.Name='JUPITER_Number_'+$figure.screen+'_'+$n
   $circle.RelativeHorizontalPosition=1;$circle.RelativeVerticalPosition=1
   $circle.Left=[single]($cx-7);$circle.Top=[single]($cy-7);$circle.WrapFormat.Type=3
   $circle.Fill.ForeColor.RGB=16777215;$circle.Line.ForeColor.RGB=$red;$circle.Line.Weight=1.3
   $circle.TextFrame.MarginLeft=0;$circle.TextFrame.MarginRight=0;$circle.TextFrame.MarginTop=0;$circle.TextFrame.MarginBottom=0
   $circle.TextFrame.VerticalAnchor=3
   $circle.TextFrame.TextRange.Text=[string]$n
   $circle.TextFrame.TextRange.Font.Name='Tahoma'
   $circle.TextFrame.TextRange.Font.Size=10
   $circle.TextFrame.TextRange.Font.Bold=-1
   $circle.TextFrame.TextRange.Font.Color=$red
   $circle.TextFrame.TextRange.ParagraphFormat.Alignment=1
   $circle.TextFrame.TextRange.ParagraphFormat.SpaceBefore=0
   $circle.TextFrame.TextRange.ParagraphFormat.SpaceAfter=0
   $total++
  }
 }
 $arrowDoc.Repaginate()
 Write-Output ('Callouts: '+$total+' Pages: '+$arrowDoc.ComputeStatistics(2))
 $arrowDoc.Save()
 $arrowDoc.ExportAsFixedFormat((Join-Path (Get-Location) 'output\pdf\JUPITER_User_Manual.pdf'),17)
} finally {
 if($null -ne $arrowDoc) { $arrowDoc.Close(0);[void][Runtime.InteropServices.Marshal]::ReleaseComObject($arrowDoc) }
 $arrowWord.Quit();[void][Runtime.InteropServices.Marshal]::ReleaseComObject($arrowWord)
}
& 'C:\Users\TUF GAMING\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin\pdftoppm.exe' -r 100 -png output/pdf/JUPITER_User_Manual.pdf tmp/manual/annotated
