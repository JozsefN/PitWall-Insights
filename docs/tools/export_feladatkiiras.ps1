param(
    [Parameter(Mandatory = $true)][string]$InputDocx,
    [Parameter(Mandatory = $true)][string]$TargetDocx,
    [Parameter(Mandatory = $true)][string]$OutputPdf,
    [Parameter(Mandatory = $true)][string]$SnapshotXml,
    [switch]$UpdateContents
)

$ErrorActionPreference = 'Stop'
$wordApp = $null
$stagedDoc = $null
$targetDoc = $null
$createdWord = $false
$keepTargetOpen = $false
try {
    try {
        $wordApp = [Runtime.InteropServices.Marshal]::GetActiveObject('Word.Application')
    } catch {
        $wordApp = New-Object -ComObject Word.Application
        $createdWord = $true
        $wordApp.Visible = $false
        $wordApp.DisplayAlerts = 0
        $wordApp.AutomationSecurity = 3
    }
    foreach ($candidate in @($wordApp.Documents)) {
        if ($candidate.Name -eq [IO.Path]::GetFileName($TargetDocx)) {
            $targetDoc = $candidate
            $keepTargetOpen = $true
            break
        }
    }
    $missing = [Type]::Missing
    $stagedDoc = $wordApp.Documents.Open(
        $InputDocx, $false, $true, $false, $missing, $missing,
        $false, $missing, $missing, $missing, $missing, $false
    )
    if ($null -ne $targetDoc) {
        if ($targetDoc.ReadOnly) { throw 'The target Word document is read-only.' }
        if ($UpdateContents) { $targetDoc.CopyStylesFromTemplate($InputDocx) }
        $targetDoc.Content.FormattedText = $stagedDoc.Content.FormattedText
        $targetDoc.Save()
    } else {
        $targetDoc = $stagedDoc
        $targetDoc.SaveAs2($TargetDocx, 16)
    }
    if ($UpdateContents) {
        for ($level = 0; $level -lt 2; $level++) {
            # Built-in style IDs avoid dependence on Word's display language.
            $tocStyle = $targetDoc.Styles.Item(-20 - $level)
            $tocStyle.Font.Name = 'Times New Roman'
            $tocStyle.Font.Size = 11 - $level
            $tocStyle.Font.Bold = [int]($level -eq 0)
            $tocStyle.ParagraphFormat.LineSpacingRule = 0
            $tocStyle.ParagraphFormat.SpaceBefore = 0
            $tocStyle.ParagraphFormat.SpaceAfter = 0
            $tocStyle.ParagraphFormat.KeepWithNext = 0
        }
        $targetDoc.Fields.Update() | Out-Null
        foreach ($contents in @($targetDoc.TablesOfContents)) {
            $contents.Update()
        }
    }
    $targetDoc.Repaginate()
    if ($UpdateContents) {
        foreach ($contents in @($targetDoc.TablesOfContents)) {
            $contents.UpdatePageNumbers()
        }
        $targetDoc.Save()
    }
    $targetDoc.ExportAsFixedFormat($OutputPdf, 17)
    [IO.File]::WriteAllText($SnapshotXml, $targetDoc.WordOpenXML, (New-Object Text.UTF8Encoding($false)))
    [pscustomobject]@{
        Document = $targetDoc.Name
        Saved = $targetDoc.Saved
        Pages = $targetDoc.ComputeStatistics(2)
        Pdf = $OutputPdf
    } | ConvertTo-Json
} finally {
    if ($null -ne $stagedDoc -and $stagedDoc -ne $targetDoc) {
        # Changes were already saved/exported. Word may dirty fields during
        # statistics/re-pagination; do not leave automation in a save dialog.
        $stagedDoc.Close(0)
    }
    if ($null -ne $targetDoc -and -not $keepTargetOpen) {
        $targetDoc.Close(0)
    }
    if ($null -ne $wordApp) {
        if ($createdWord) { $wordApp.Quit() }
        [Runtime.InteropServices.Marshal]::ReleaseComObject($wordApp) | Out-Null
    }
}
