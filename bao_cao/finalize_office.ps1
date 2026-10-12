# Update the table of contents in the report and export PDF previews with Microsoft Office.
# Usage (Windows, Office installed):  powershell -ExecutionPolicy Bypass -File bao_cao/finalize_office.ps1
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$docx = Join-Path $here "BaoCao_BTL_INT1422.docx"
$pptx = Join-Path $here "Slide_BTL_INT1422.pptx"

if (Test-Path $docx) {
  $word = New-Object -ComObject Word.Application
  $word.Visible = $false
  try {
    $doc = $word.Documents.Open($docx)
    foreach ($toc in $doc.TablesOfContents) { $toc.Update() }
    $doc.Fields.Update() | Out-Null
    $doc.Save()
    $pdf = [System.IO.Path]::ChangeExtension($docx, ".pdf")
    $doc.ExportAsFixedFormat($pdf, 17)   # wdExportFormatPDF
    "report pages: " + $doc.ComputeStatistics(2)  # wdStatisticPages
    $doc.Close()
  } finally { $word.Quit() }
}

if (Test-Path $pptx) {
  $pp = New-Object -ComObject PowerPoint.Application
  try {
    $pres = $pp.Presentations.Open($pptx, $true, $false, $false)
    $pdf = [System.IO.Path]::ChangeExtension($pptx, ".pdf")
    $pres.SaveAs($pdf, 32)   # ppSaveAsPDF
    "slides: " + $pres.Slides.Count
    $pres.Close()
  } finally { $pp.Quit() }
}
