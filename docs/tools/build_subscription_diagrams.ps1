$ErrorActionPreference = 'Stop'
$docs = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$folder = Join-Path $docs 'generated\subscription'
New-Item -ItemType Directory -Path $folder -Force | Out-Null
$target = Join-Path $folder 'PitWall-subscriptions.qeax'
Copy-Item -LiteralPath (Join-Path $docs 'generated\PitWall-Insights-thesis.qeax') -Destination $target -Force
$repo = New-Object -ComObject EA.Repository

function Diagram($name, $type) {
    $script:diagram = $package.Diagrams.AddNew($name, $type)
    [void]$diagram.Update()
}
function Node($name, $type, $x, $y, $fields = @()) {
    $element = $package.Elements.AddNew($name, $type)
    [void]$element.Update()
    foreach ($field in $fields) { [void]$element.Attributes.AddNew($field, '').Update() }
    $item = $diagram.DiagramObjects.AddNew("l=$x;r=$($x+170);t=$y;b=$($y-100);", '')
    $item.ElementID = $element.ElementID
    [void]$item.Update()
    return $element
}
function Edge($from, $to, $label = '', $kind = 'Dependency', $cardinality = '') {
    $edge = $from.Connectors.AddNew($label, $kind)
    $edge.SupplierID = $to.ElementID
    $edge.Direction = 'Source -> Destination'
    if ($cardinality) { $edge.ClientEnd.Cardinality = '1'; $edge.SupplierEnd.Cardinality = $cardinality }
    [void]$edge.Update()
}
function Export($file) {
    [void]$repo.ReloadDiagram($diagram.DiagramID)
    [void]$repo.GetProjectInterface().PutDiagramImageToFile($diagram.DiagramGUID, (Join-Path $folder "$file.png"), 1)
}

try {
    if (!$repo.OpenFile($target)) { throw 'Could not open diagram model' }
    $root = $repo.Models.GetAt(0)
    for ($i = $root.Packages.Count - 1; $i -ge 0; $i--) { $root.Packages.DeleteAt($i, $false) }
    $root.Packages.Refresh()
    $package = $root.Packages.AddNew('Subscriptions', 'Package')
    [void]$package.Update()

    Diagram 'Subscription system context' 'Component'
    $web = Node 'PitWall web' 'Component' 20 -50
    $api = Node 'PitWall API' 'Component' 255 -50
    $db = Node 'PostgreSQL' 'Component' 490 -50
    $google = Node 'Google Identity' 'Component' 20 -230
    $stripe = Node 'Stripe sandbox' 'Component' 255 -230
    Edge $web $api 'HTTPS / bearer'
    Edge $api $db 'entitlements'
    Edge $web $google 'sign in'
    Edge $api $stripe 'Checkout / events'
    Export 'system'

    Diagram 'Billing persistence' 'Logical'
    $user = Node 'users' 'Class' 20 -50 @('id (PK)', 'email')
    $billing = Node 'billing_accounts' 'Class' 255 -50 @('user_id (PK/FK)', 'stripe_customer_id', 'subscription_id', 'plan / status / period')
    $events = Node 'billing_webhook_events' 'Class' 490 -50 @('event_id (PK)', 'user_id (FK)', 'processed_at')
    $identity = Node 'google_identities' 'Class' 20 -230 @('subject (PK)', 'user_id (FK, unique)')
    $layout = Node 'user_dashboard_layouts' 'Class' 255 -230 @('id (PK)', 'owner_user_id (FK)', 'config_json')
    Edge $user $billing '' 'Association' '0..1'
    Edge $billing $events '' 'Association' '0..*'
    Edge $user $identity '' 'Association' '0..1'
    Edge $user $layout '' 'Association' '0..*'
    Export 'data'

    Diagram 'Checkout and cancellation messages' 'Component'
    $profile = Node 'Profile / Subscription' 'Component' 20 -50
    $service = Node 'Billing service' 'Component' 255 -50
    $provider = Node 'Stripe sandbox' 'Component' 490 -50
    $guard = Node 'Access policy' 'Component' 20 -230
    $projection = Node 'Billing projection' 'Component' 255 -230
    $webhook = Node 'Signed webhook' 'Component' 490 -230
    Edge $profile $service '1. checkout / cancel'
    Edge $service $provider '2. provider request'
    Edge $provider $webhook '3. event'
    Edge $webhook $projection '4. refresh + receipt'
    Edge $guard $projection '5. current tier'
    Export 'checkout'

    Diagram 'Google sign-in messages' 'Component'
    $page = Node 'Login / Profile' 'Component' 20 -50
    $gis = Node 'Google sign-in' 'Component' 255 -50
    $identity = Node 'Identity auth' 'Component' 20 -230
    $database = Node 'Identity and nonce rows' 'Component' 255 -230
    Edge $page $gis '2. challenge nonce'
    Edge $page $identity '1. challenge / 3. token'
    Edge $identity $database '4. consume / resolve'
    Export 'identity'
} finally {
    $repo.CloseFile()
    $repo.Exit()
}
