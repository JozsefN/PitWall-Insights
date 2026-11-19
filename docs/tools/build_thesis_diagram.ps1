param()
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$source = Join-Path $repoRoot 'docs\generated\PitWall-Insights-documentation.qeax'
$target = Join-Path $repoRoot 'docs\generated\PitWall-Insights-thesis.qeax'
$folder = Join-Path $repoRoot 'docs\generated\szakdolgozat-abraterv'
New-Item -ItemType Directory -Force -Path $folder | Out-Null
Copy-Item -LiteralPath $source -Destination $target -Force
$repository = New-Object -ComObject EA.Repository
try {
    [void]$repository.OpenFile($target)
    $root = $repository.Models.GetAt(0)
    $package = $root.Packages.AddNew('Thesis loading workflow', 'Package')
    [void]$package.Update()
    $diagram = $package.Diagrams.AddNew('On-demand telemetry workflow', 'Component')
    [void]$diagram.Update()
    $specs = @(
        @('Widget request', 20, -70),
        @('Ensure API and cache', 240, -70),
        @('Job and worker', 460, -70),
        @('Selected source data', 460, -240),
        @('Normalize and COPY', 240, -240),
        @('Canonical PostgreSQL', 20, -240)
    )
    $elements = @()
    foreach ($spec in $specs) {
        $element = $package.Elements.AddNew($spec[0], 'Component')
        [void]$element.Update()
        $elements += $element
        $x = [int]$spec[1]; $y = [int]$spec[2]
        $object = $diagram.DiagramObjects.AddNew("l=$x;r=$($x+170);t=$y;b=$($y-70);", '')
        $object.ElementID = $element.ElementID
        [void]$object.Update()
    }
    foreach ($edge in @(@(0,1,'needs'), @(1,2,'if missing'), @(2,3,'load'), @(3,4,'prepare'), @(4,5,'persist'))) {
        $connector = $elements[$edge[0]].Connectors.AddNew($edge[2], 'Dependency')
        $connector.SupplierID = $elements[$edge[1]].ElementID
        $connector.Direction = 'Source -> Destination'
        [void]$connector.Update()
    }
    [void]$diagram.Update()
    [void]$repository.ReloadDiagram($diagram.DiagramID)
    $project = $repository.GetProjectInterface()
    $output = Join-Path $folder 'adatbetoltes.png'
    [void]$project.PutDiagramImageToFile($diagram.DiagramGUID, $output, 1)
    Write-Output $output
} finally {
    if ($null -ne $repository) {
        $repository.CloseFile()
        $repository.Exit()
        [Runtime.InteropServices.Marshal]::ReleaseComObject($repository) | Out-Null
    }
}
