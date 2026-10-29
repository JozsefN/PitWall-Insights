param(
  [string]$SourceModel = "C:\Users\jozse\OneDrive\Dokumentumok\REMO HF\2026-use-case-huszarok\model.qeax",
  [string]$OutputModel = "docs\generated\PitWall-Insights-documentation.qeax",
  [string]$OutputDir = "docs\generated\ea-diagrams"
)

$ErrorActionPreference = "Stop"

function Resolve-RepoPath([string]$Path) {
  if ([System.IO.Path]::IsPathRooted($Path)) {
    return $Path
  }

  return Join-Path (Get-Location) $Path
}

function Add-Element($Package, [string]$Name, [string]$Type = "Component", [string]$Stereotype = "") {
  $element = $Package.Elements.AddNew($Name, $Type)
  if ($Stereotype) {
    $element.Stereotype = $Stereotype
  }
  [void]$element.Update()
  [void]$Package.Elements.Refresh()
  return $element
}

function Add-ObjectToDiagram($Diagram, $Element, [int]$Left, [int]$Top, [int]$Width, [int]$Height) {
  $diagramObject = $Diagram.DiagramObjects.AddNew(
    "l=$Left;r=$($Left + $Width);t=$Top;b=$($Top - $Height);",
    ""
  )
  $diagramObject.ElementID = $Element.ElementID
  [void]$diagramObject.Update()
  [void]$Diagram.DiagramObjects.Refresh()
  return $diagramObject
}

function Add-Connector($Source, $Target, [string]$Name, [string]$Type = "Dependency", [string]$Stereotype = "") {
  $connector = $Source.Connectors.AddNew($Name, $Type)
  $connector.SupplierID = $Target.ElementID
  $connector.Direction = "Source -> Destination"
  if ($Stereotype) {
    $connector.Stereotype = $Stereotype
  }
  [void]$connector.Update()
  [void]$Source.Connectors.Refresh()
  return $connector
}

function Add-Diagram($Package, [string]$Name) {
  $diagram = $Package.Diagrams.AddNew($Name, "Component")
  $diagram.Notes = "Generated for PitWall-Insights documentation. Layout uses sparse rows and left-to-right flows to avoid connectors crossing elements."
  [void]$diagram.Update()
  [void]$Package.Diagrams.Refresh()
  return $diagram
}

function New-Node($Package, [string]$Name, [int]$X, [int]$Y, [int]$W = 220, [int]$H = 76, [string]$Type = "Component", [string]$Stereotype = "") {
  return @{
    Element = Add-Element $Package $Name $Type $Stereotype
    X = $X
    Y = $Y
    W = $W
    H = $H
  }
}

function Put-Node($Diagram, $Node) {
  [void](Add-ObjectToDiagram $Diagram $Node.Element $Node.X $Node.Y $Node.W $Node.H)
}

function Add-Flow($SourceNode, $TargetNode, [string]$Label) {
  [void](Add-Connector $SourceNode.Element $TargetNode.Element $Label)
}

function Add-NodeSet($Diagram, [array]$Nodes) {
  foreach ($node in $Nodes) {
    Put-Node $Diagram $node
  }
}

function Export-Diagram($EaRepository, $Project, $Diagram, [string]$OutputPath) {
  [void]$EaRepository.OpenDiagram($Diagram.DiagramID)
  [void]$EaRepository.ReloadDiagram($Diagram.DiagramID)
  [void]$Project.PutDiagramImageToFile($Diagram.DiagramGUID, $OutputPath, 1)
  [void]$EaRepository.CloseDiagram($Diagram.DiagramID)
}

$sourceModelPath = Resolve-RepoPath $SourceModel
$outputModelPath = Resolve-RepoPath $OutputModel
$outputDirPath = Resolve-RepoPath $OutputDir
$outputModelParent = Split-Path -Parent $outputModelPath

New-Item -ItemType Directory -Force -Path $outputModelParent | Out-Null
New-Item -ItemType Directory -Force -Path $outputDirPath | Out-Null
Copy-Item -LiteralPath $sourceModelPath -Destination $outputModelPath -Force

$eaRepository = New-Object -ComObject EA.Repository

try {
  [void]$eaRepository.OpenFile($outputModelPath)
  $root = $eaRepository.Models.GetAt(0)
  $docPackage = $root.Packages.AddNew("PitWall-Insights Documentation", "Package")
  [void]$docPackage.Update()
  [void]$root.Packages.Refresh()
  $project = $eaRepository.GetProjectInterface()

  # PW-01: system context
  $context = Add-Diagram $docPackage "PW-01 System Context"
  $ctxUser = New-Node $docPackage "User" 20 -80 150 82 "Actor"
  $ctxFrontend = New-Node $docPackage "React SPA / Vite frontend" 230 -80 245 82
  $ctxApi = New-Node $docPackage "FastAPI delivery API" 545 -80 230 82
  $ctxDb = New-Node $docPackage "PostgreSQL session cache" 850 -80 245 82 "Component" "database"
  $ctxWorker = New-Node $docPackage "Import + telemetry worker" 545 -240 230 82
  $ctxFastf1 = New-Node $docPackage "FastF1 provider" 850 -240 245 82 "Component" "external"
  $ctxCache = New-Node $docPackage "FastF1 scratch cache" 850 -400 245 82 "Component" "cache"
  Add-NodeSet $context @($ctxUser, $ctxFrontend, $ctxApi, $ctxDb, $ctxWorker, $ctxFastf1, $ctxCache)
  Add-Flow $ctxUser $ctxFrontend "uses"
  Add-Flow $ctxFrontend $ctxApi "HTTPS / JSON API"
  Add-Flow $ctxApi $ctxDb "repositories"
  Add-Flow $ctxApi $ctxWorker "job queue"
  Add-Flow $ctxWorker $ctxFastf1 "source load"
  Add-Flow $ctxWorker $ctxDb "persist results"
  Add-Flow $ctxFastf1 $ctxCache "provider cache"

  # PW-02: backend module architecture
  $backend = Add-Diagram $docPackage "PW-02 Backend Module Architecture"
  $bAuthRoutes = New-Node $docPackage "Auth routes" 20 -50 190 62
  $bAuth = New-Node $docPackage "identity_auth" 260 -50 190 62
  $bUsers = New-Node $docPackage "users repository" 500 -50 205 62 "Component" "database"

  $bSessionRoutes = New-Node $docPackage "Session routes" 20 -140 190 62
  $bSession = New-Node $docPackage "session_domain" 260 -140 190 62
  $bIngestion = New-Node $docPackage "ingestion" 500 -140 190 62
  $bNormalization = New-Node $docPackage "normalization" 740 -140 190 62
  $bSessionStore = New-Node $docPackage "canonical session tables" 980 -140 225 62 "Component" "database"

  $bJobRoutes = New-Node $docPackage "Import job routes" 20 -230 190 62
  $bImport = New-Node $docPackage "session_import" 260 -230 190 62
  $bImportJobs = New-Node $docPackage "import_jobs table" 500 -230 205 62 "Component" "database"

  $bTelemetryRoutes = New-Node $docPackage "Telemetry routes" 20 -320 190 62
  $bMaterialization = New-Node $docPackage "telemetry_materialization" 260 -320 225 62
  $bTelemetryStore = New-Node $docPackage "telemetry cache tables" 535 -320 215 62 "Component" "database"

  $bMetricRoutes = New-Node $docPackage "Metric / decision routes" 20 -410 205 62
  $bMetrics = New-Node $docPackage "feature_metrics" 275 -410 190 62
  $bDecision = New-Node $docPackage "decision_engine" 515 -410 190 62
  $bMetricInputs = New-Node $docPackage "lap metric inputs" 755 -410 205 62 "Component" "database"

  $bLayoutRoutes = New-Node $docPackage "Layout routes" 20 -500 190 62
  $bLayouts = New-Node $docPackage "dashboard_layouts" 260 -500 190 62
  $bLayoutStore = New-Node $docPackage "user layout table" 500 -500 205 62 "Component" "database"

  $bStoryRoute = New-Node $docPackage "Story health route" 20 -590 190 62
  $bStory = New-Node $docPackage "story_feed (planned)" 260 -590 190 62

  Add-NodeSet $backend @(
    $bAuthRoutes, $bAuth, $bUsers,
    $bSessionRoutes, $bSession, $bIngestion, $bNormalization, $bSessionStore,
    $bJobRoutes, $bImport, $bImportJobs,
    $bTelemetryRoutes, $bMaterialization, $bTelemetryStore,
    $bMetricRoutes, $bMetrics, $bDecision, $bMetricInputs,
    $bLayoutRoutes, $bLayouts, $bLayoutStore,
    $bStoryRoute, $bStory
  )
  Add-Flow $bAuthRoutes $bAuth ""
  Add-Flow $bAuth $bUsers ""
  Add-Flow $bSessionRoutes $bSession ""
  Add-Flow $bSession $bIngestion ""
  Add-Flow $bIngestion $bNormalization ""
  Add-Flow $bNormalization $bSessionStore ""
  Add-Flow $bJobRoutes $bImport ""
  Add-Flow $bImport $bImportJobs ""
  Add-Flow $bTelemetryRoutes $bMaterialization ""
  Add-Flow $bMaterialization $bTelemetryStore ""
  Add-Flow $bMetricRoutes $bMetrics ""
  Add-Flow $bMetrics $bDecision ""
  Add-Flow $bDecision $bMetricInputs ""
  Add-Flow $bLayoutRoutes $bLayouts ""
  Add-Flow $bLayouts $bLayoutStore ""
  Add-Flow $bStoryRoute $bStory ""

  # PW-03: ports and adapters
  $ports = Add-Diagram $docPackage "PW-03 Ports and Adapters"
  $pRoutes = New-Node $docPackage "Delivery API routes" 20 -80 225 76
  $pSessionService = New-Node $docPackage "SessionService" 300 -80 220 76 "Class"
  $pSourcePort = New-Node $docPackage "SessionSourcePort" 580 -80 220 76 "Interface"
  $pFastAdapter = New-Node $docPackage "FastF1Adapter" 860 -80 220 76 "Class"
  $pNormalizer = New-Node $docPackage "NormalizationService" 300 -230 240 76 "Class"
  $pRepository = New-Node $docPackage "SessionRepository" 580 -230 230 76 "Class"
  $pMetrics = New-Node $docPackage "FeatureMetricInputProvider" 20 -380 250 76 "Class"
  $pRegistry = New-Node $docPackage "Metric calculator registry" 330 -380 250 76 "Class"
  Add-NodeSet $ports @($pRoutes, $pSessionService, $pSourcePort, $pFastAdapter, $pNormalizer, $pRepository, $pMetrics, $pRegistry)
  Add-Flow $pRoutes $pSessionService "use case"
  Add-Flow $pSessionService $pSourcePort "depends on port"
  Add-Flow $pFastAdapter $pSourcePort "realizes"
  Add-Flow $pSessionService $pNormalizer "snapshot"
  Add-Flow $pNormalizer $pRepository "persist canonical"
  Add-Flow $pMetrics $pRegistry "planned metric set"
  Add-Flow $pMetrics $pRepository "lap inputs"

  # PW-04: frontend architecture
  $frontendDiagram = Add-Diagram $docPackage "PW-04 Frontend Architecture"
  $fRouter = New-Node $docPackage "React Router route tree" 20 -70 210 68
  $fShell = New-Node $docPackage "AppLayout + navigation" 280 -70 215 68
  $fAuth = New-Node $docPackage "features/auth RequireAuth" 545 -70 230 68
  $fPages = New-Node $docPackage "session pages" 20 -205 210 68
  $fRenderer = New-Node $docPackage "DashboardRenderer" 280 -205 215 68
  $fRegistry = New-Node $docPackage "widget registry + layouts" 545 -205 230 68
  $fWidgets = New-Node $docPackage "telemetry / replay widgets" 825 -205 235 68
  $fData = New-Node $docPackage "data/api + query hooks" 20 -340 210 68
  Add-NodeSet $frontendDiagram @($fRouter, $fShell, $fAuth, $fPages, $fData, $fRenderer, $fRegistry, $fWidgets)
  Add-Flow $fRouter $fShell "mounts"
  Add-Flow $fShell $fAuth "protects routes"
  Add-Flow $fRouter $fPages "session routes"
  Add-Flow $fPages $fData "server state"
  Add-Flow $fPages $fRenderer "layout state"
  Add-Flow $fRenderer $fRegistry "WidgetId lookup"
  Add-Flow $fRegistry $fWidgets "registered widgets"

  # PW-05: protected sessions access
  $authFlow = Add-Diagram $docPackage "PW-05 Communication - Protected Sessions Access"
  $aUser = New-Node $docPackage "User" 20 -80 135 76 "Actor"
  $aGuard = New-Node $docPackage "RequireAuth" 205 -80 175 76
  $aSessionApi = New-Node $docPackage "Auth API: session" 430 -80 190 76
  $aFeatureCard = New-Node $docPackage "Feature card" 670 -80 175 76
  $aLogin = New-Node $docPackage "Login / Signup page" 895 -80 205 76
  $aLoginApi = New-Node $docPackage "Auth API: login/signup" 1150 -80 230 76
  $aSessions = New-Node $docPackage "Sessions route" 1430 -80 180 76
  Add-NodeSet $authFlow @($aUser, $aGuard, $aSessionApi, $aFeatureCard, $aLogin, $aLoginApi, $aSessions)
  Add-Flow $aUser $aGuard "1 open /sessions"
  Add-Flow $aGuard $aSessionApi "2 GET session"
  Add-Flow $aSessionApi $aFeatureCard "3 unauthenticated"
  Add-Flow $aFeatureCard $aLogin "4 sign in/up"
  Add-Flow $aLogin $aLoginApi "5 credentials"
  Add-Flow $aLoginApi $aSessions "6 redirect"

  # PW-06: core session import
  $importFlow = Add-Diagram $docPackage "PW-06 Communication - Core Session Import"
  $iExplorer = New-Node $docPackage "SessionsExplorerPage" 20 -80 210 76
  $iApi = New-Node $docPackage "Session API" 280 -80 175 76
  $iService = New-Node $docPackage "SessionService" 505 -80 190 76
  $iSource = New-Node $docPackage "Ingestion / FastF1" 745 -80 205 76
  $iNormalization = New-Node $docPackage "Normalization" 1000 -80 190 76
  $iRepository = New-Node $docPackage "SessionRepository" 1240 -80 210 76
  $iWorkspace = New-Node $docPackage "SessionWorkspacePage" 1500 -80 225 76
  Add-NodeSet $importFlow @($iExplorer, $iApi, $iService, $iSource, $iNormalization, $iRepository, $iWorkspace)
  Add-Flow $iExplorer $iApi "1 POST import(core)"
  Add-Flow $iApi $iService "2 import_session"
  Add-Flow $iService $iSource "3 load source"
  Add-Flow $iSource $iNormalization "4 source bundle"
  Add-Flow $iNormalization $iRepository "5 persist snapshot"
  Add-Flow $iRepository $iWorkspace "6 route with session id"

  # PW-07: telemetry materialization
  $telemetryFlow = Add-Diagram $docPackage "PW-07 Communication - Telemetry Materialization"
  $tWidget = New-Node $docPackage "Telemetry widget" 20 -80 180 76
  $tHook = New-Node $docPackage "session-data hook" 250 -80 190 76
  $tApi = New-Node $docPackage "Materialization API" 490 -80 215 76
  $tJob = New-Node $docPackage "Worker materialization job" 755 -80 245 76
  $tRepository = New-Node $docPackage "Telemetry tables" 1050 -80 190 76 "Component" "database"
  $tRead = New-Node $docPackage "Telemetry read endpoint" 1290 -80 225 76
  $tReady = New-Node $docPackage "Widget data ready" 1565 -80 190 76
  Add-NodeSet $telemetryFlow @($tWidget, $tHook, $tApi, $tJob, $tRepository, $tRead, $tReady)
  Add-Flow $tWidget $tHook "1 needs data"
  Add-Flow $tHook $tApi "2 POST ensure"
  Add-Flow $tApi $tJob "3 queue if missing"
  Add-Flow $tJob $tRepository "4 persist segment"
  Add-Flow $tRepository $tRead "5 samples"
  Add-Flow $tRead $tReady "6 dataByEntryId"

  $diagrams = @(
    @($context, "pw-01-system-context.png"),
    @($backend, "pw-02-backend-module-architecture.png"),
    @($ports, "pw-03-ports-and-adapters.png"),
    @($frontendDiagram, "pw-04-frontend-architecture.png"),
    @($authFlow, "pw-05-communication-protected-sessions-access.png"),
    @($importFlow, "pw-06-communication-core-session-import.png"),
    @($telemetryFlow, "pw-07-communication-telemetry-materialization.png")
  )

  foreach ($item in $diagrams) {
    Export-Diagram $eaRepository $project $item[0] (Join-Path $outputDirPath $item[1])
  }

  Write-Output "Generated EA model: $outputModelPath"
  Write-Output "Exported diagrams: $outputDirPath"
} finally {
  try { $eaRepository.CloseFile() } catch {}
  try { $eaRepository.Exit() } catch {}
}
