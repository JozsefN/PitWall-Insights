$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$source = Join-Path $repoRoot 'docs\generated\PitWall-Insights-thesis.qeax'
$target = Join-Path $repoRoot 'docs\generated\PitWall-Insights-thesis-structure.qeax'
$folder = Join-Path $repoRoot 'docs\generated\szakdolgozat-abraterv'
Copy-Item -LiteralPath $source -Destination $target -Force
$repository = New-Object -ComObject EA.Repository
function Node($package, $diagram, $name, $type, $x, $y, $attributes, $methods, $stereotype='') {
    $element = $package.Elements.AddNew($name, $type)
    if ($stereotype) { $element.Stereotype = $stereotype }
    [void]$element.Update()
    foreach ($field in $attributes) {
        $attribute = $element.Attributes.AddNew($field, '')
        [void]$attribute.Update()
    }
    foreach ($methodName in $methods) {
        $method = $element.Methods.AddNew($methodName, '')
        [void]$method.Update()
    }
    $compact = $diagram.Name -eq 'Final OpenF1 data pipeline'
    $nodeHeight = if ($compact) { 65 } else { 115 }
    $nodeWidth = if ($type -eq 'Class') { 230 } else { 190 }
    if ($name -eq 'TelemetryMaterializationRepository') { $nodeWidth = 270 }
    $object = $diagram.DiagramObjects.AddNew("l=$x;r=$($x+$nodeWidth);t=$y;b=$($y-$nodeHeight);", '')
    $object.ElementID = $element.ElementID
    [void]$object.Update()
    $object.SetStyleEx('font', 'Arial')
    $object.SetStyleEx('fontsz', $(if ($type -eq 'Class') { '110' } else { '140' }))
    [void]$object.Update()
    return $element
}
function Link($a, $b, $type='Dependency', $many=$false, $label='') {
    $connector = $a.Connectors.AddNew($label, $type)
    $connector.SupplierID = $b.ElementID
    $connector.Direction = 'Source -> Destination'
    if ($many) { $connector.ClientEnd.Cardinality = '1'; $connector.SupplierEnd.Cardinality = '0..*' }
    [void]$connector.Update()
}
function Export($diagram, $name) {
    [void]$diagram.Update()
    [void]$repository.ReloadDiagram($diagram.DiagramID)
    [void]$repository.GetProjectInterface().PutDiagramImageToFile($diagram.DiagramGUID, (Join-Path $folder $name), 1)
}
try {
    [void]$repository.OpenFile($target)
    $modelRoot = $repository.Models.GetAt(0)
    # This is a disposable copy, not the user's source model. Keep only the
    # current loading workflow; inherited example/legacy provider packages
    # would otherwise leave FastF1 elements in the delivered thesis model.
    for ($packageIndex = $modelRoot.Packages.Count - 1; $packageIndex -ge 0; $packageIndex--) {
        if ($modelRoot.Packages.GetAt($packageIndex).Name -ne 'Thesis loading workflow') {
            $modelRoot.Packages.DeleteAt($packageIndex, $false)
        }
    }
    $modelRoot.Packages.Refresh()
    $package = $modelRoot.Packages.AddNew('Thesis structure', 'Package')
    [void]$package.Update()
    $diagram = $package.Diagrams.AddNew('Application architecture', 'Component')
    [void]$diagram.Update()
    $ui = Node $package $diagram 'PitWall web UI' 'Component' 20 -60 @() @()
    $api = Node $package $diagram 'PitWall API' 'Component' 270 -60 @() @()
    $db = Node $package $diagram 'PostgreSQL data and jobs' 'Component' 520 -60 @() @()
    $sourceApi = Node $package $diagram 'OpenF1 API' 'Component' 20 -290 @() @() 'external'
    $sourceProvider = Node $package $diagram 'OpenF1 data ingestion' 'Component' 270 -290 @() @()
    $worker = Node $package $diagram 'Data preparation worker' 'Component' 520 -290 @() @()
    Link $ui $api 'Dependency' $false 'HTTP'
    Link $api $db 'Dependency' $false 'queue / read'
    Link $api $sourceProvider 'Dependency' $false 'calendar'
    Link $worker $db 'Dependency' $false 'claim / save'
    Link $worker $sourceProvider 'Dependency' $false 'load'
    Link $sourceProvider $sourceApi 'Dependency' $false 'HTTP'
    Export $diagram 'rendszer-felepites.png'

    $diagram = $package.Diagrams.AddNew('OpenF1 access components', 'Logical')
    [void]$diagram.Update()
    $adapter = Node $package $diagram 'OpenF1Adapter' 'Class' 20 -60 @() @('load_session')
    $client = Node $package $diagram 'OpenF1Client' 'Class' 270 -60 @() @('get')
    $responseCache = Node $package $diagram 'OpenF1ResponseCache' 'Class' 520 -60 @() @('read','write')
    $catalog = Node $package $diagram 'OpenF1Catalog' 'Class' 20 -290 @() @('list_catalog')
    $limiter = Node $package $diagram 'OpenF1RequestLimiter' 'Class' 270 -290 @() @('wait')
    Link $adapter $client
    Link $adapter $catalog
    Link $catalog $client
    Link $client $responseCache
    Link $client $limiter
    Export $diagram 'openf1-komponensek.png'
    $diagram = $package.Diagrams.AddNew('Core race data model', 'Logical')
    [void]$diagram.Update()
    $event = Node $package $diagram 'event_sessions' 'Class' 20 -60 @('id','session_name') @() 'table'
    $entry = Node $package $diagram 'session_entries' 'Class' 270 -60 @('id','session_id','driver_id') @() 'table'
    $lap = Node $package $diagram 'entry_laps' 'Class' 520 -60 @('id','session_entry_id','lap_number') @() 'table'
    $pos = Node $package $diagram 'position_samples' 'Class' 20 -290 @('id','session_entry_id','session_time_ms') @() 'table'
    $car = Node $package $diagram 'car_telemetry_samples' 'Class' 270 -290 @('id','session_entry_id','session_time_ms') @() 'table'
    $stint = Node $package $diagram 'entry_stints' 'Class' 520 -290 @('id','session_entry_id','stint_number') @() 'table'
    Link $event $entry 'Association' $true
    Link $entry $lap 'Association' $true
    Link $entry $pos 'Association' $true
    Link $entry $car 'Association' $true
    Link $entry $stint 'Association' $true
    Export $diagram 'adatmodell.png'

    $diagram = $package.Diagrams.AddNew('Telemetry preparation services', 'Logical')
    [void]$diagram.Update()
    $service = Node $package $diagram 'TelemetryMaterializationService' 'Class' 270 -60 @() @('ensure_materialization','run_next_job')
    $ingestion = Node $package $diagram 'IngestionService' 'Class' 20 -290 @() @('load_session')
    $normalize = Node $package $diagram 'NormalizationService' 'Class' 270 -290 @() @('build_snapshot')
    $repo = Node $package $diagram 'TelemetryMaterializationRepository' 'Class' 520 -290 @() @('ensure_materialization','claim_next_job','materialize_snapshot')
    Link $service $ingestion
    Link $service $normalize
    Link $service $repo
    Export $diagram 'feldolgozas-osztalyok.png'
    $diagram = $package.Diagrams.AddNew('Final OpenF1 data pipeline', 'Component')
    [void]$diagram.Update()
    $sourceApi = Node $package $diagram 'OpenF1 API' 'Component' 20 -60 @() @()
    $sourceAdapter = Node $package $diagram 'OpenF1Adapter' 'Component' 270 -60 @() @()
    $normalization = Node $package $diagram 'Normalization' 'Component' 520 -60 @() @()
    $storage = Node $package $diagram 'PostgreSQL' 'Component' 520 -220 @() @()
    $calculation = Node $package $diagram 'Metrics and strategy' 'Component' 270 -220 @() @()
    $presentation = Node $package $diagram 'Replay and widgets' 'Component' 20 -220 @() @()
    Link $sourceApi $sourceAdapter 'InformationFlow'
    Link $sourceAdapter $normalization 'InformationFlow'
    Link $normalization $storage 'InformationFlow'
    Link $storage $calculation 'InformationFlow'
    Link $calculation $presentation 'InformationFlow'
    Export $diagram 'openf1-adatforras.png'
    Write-Output 'Exported current OpenF1 architecture, data model, processing services and data pipeline.'
} finally {
    if ($null -ne $repository) {
        $repository.CloseFile()
        $repository.Exit()
        [Runtime.InteropServices.Marshal]::ReleaseComObject($repository) | Out-Null
    }
}
