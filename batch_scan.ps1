# Batch scan script for multiple cryptocurrencies
# Usage: .\batch_scan.ps1

param(
    [string]$ApiUrl = "http://127.0.0.1:8000",
    [int]$Limit = 10,
    [int]$Delay = 2
)

$tokens = @(
    @{ symbol = "BTC"; coingecko_id = "bitcoin"; contract_address = "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599"; narratives = @("Store of Value", "Digital Gold") },
    @{ symbol = "ETH"; coingecko_id = "ethereum"; contract_address = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"; narratives = @("Smart Contracts", "DeFi") },
    @{ symbol = "UNI"; coingecko_id = "uniswap"; contract_address = "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984"; narratives = @("DeFi", "DEX") },
    @{ symbol = "AAVE"; coingecko_id = "aave"; contract_address = "0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9"; narratives = @("DeFi", "Lending") },
    @{ symbol = "MKR"; coingecko_id = "maker"; contract_address = "0x9f8F72aA9304c8B593d555F12eF6589cC3A579A2"; narratives = @("DeFi", "Stablecoin") },
    @{ symbol = "COMP"; coingecko_id = "compound-governance-token"; contract_address = "0xc00e94Cb662C3520282E6f5717214004A7f26888"; narratives = @("DeFi", "Lending") },
    @{ symbol = "CRV"; coingecko_id = "curve-dao-token"; contract_address = "0xD533a949740bb3306d119CC777fa900bA034cd52"; narratives = @("DeFi", "DEX") },
    @{ symbol = "LINK"; coingecko_id = "chainlink"; contract_address = "0x514910771AF9Ca656af840dff83E8264EcF986CA"; narratives = @("Oracle", "Infrastructure") },
    @{ symbol = "GRT"; coingecko_id = "the-graph"; contract_address = "0xc944E90C64B2c07662A292be6244BDf05Cda44a7"; narratives = @("Indexing", "Web3") },
    @{ symbol = "MATIC"; coingecko_id = "matic-network"; contract_address = "0x7D1AfA7B718fb893dB30A3aBc0Cfc608AaCfeBB0"; narratives = @("Layer 2", "Scaling") },
    @{ symbol = "ARB"; coingecko_id = "arbitrum"; contract_address = "0x912CE59144191C1204E64559FE8253a0e49E6548"; narratives = @("Layer 2", "Rollup") },
    @{ symbol = "OP"; coingecko_id = "optimism"; contract_address = "0x4200000000000000000000000000000000000042"; narratives = @("Layer 2", "Optimistic Rollup") },
    @{ symbol = "LDO"; coingecko_id = "lido-dao"; contract_address = "0x5A98FcBEA516Cf06857215779Fd812CA3beF1B32"; narratives = @("Liquid Staking", "DeFi") },
    @{ symbol = "RPL"; coingecko_id = "rocket-pool"; contract_address = "0xD33526068D116cE69F19A9ee46F0bd304F21A51f"; narratives = @("Liquid Staking", "Decentralized") },
    @{ symbol = "PEPE"; coingecko_id = "pepe"; contract_address = "0x6982508145454Ce325dDbE47a25d4ec3d2311933"; narratives = @("Meme", "Community") }
)

$results = @()
$tokensToScan = $tokens[0..([Math]::Min($Limit, $tokens.Count) - 1)]

Write-Host "=" * 80
Write-Host "Starting Batch Scan: $($tokensToScan.Count) tokens"
Write-Host "=" * 80
Write-Host ""

$i = 0
foreach ($token in $tokensToScan) {
    $i++
    Write-Host "[$i/$($tokensToScan.Count)] Scanning $($token.symbol)... " -NoNewline
    
    $json = @{
        symbol = $token.symbol
        coingecko_id = $token.coingecko_id
        contract_address = $token.contract_address
        narratives = $token.narratives
        unlocks = @()
    } | ConvertTo-Json -Compress
    
    try {
        $startTime = Get-Date
        $response = Invoke-RestMethod -Uri "$ApiUrl/api/scan/run" -Method POST -Body $json -ContentType 'application/json' -ErrorAction Stop
        $duration = ((Get-Date) - $startTime).TotalSeconds
        
        $result = @{
            status = "success"
            symbol = $token.symbol
            gem_score = $response.gem_score
            confidence = $response.confidence
            flagged = $response.flagged
            liquidity_ok = $response.liquidity_ok
            duration = $duration
        }
        
        $flagEmoji = if ($response.flagged) { "🚩" } else { "" }
        Write-Host "✓ Score: $([Math]::Round($response.gem_score, 1)) (confidence: $([Math]::Round($response.confidence, 0))%) $flagEmoji" -ForegroundColor Green
        
        $results += $result
    }
    catch {
        Write-Host "✗ Error: $($_.Exception.Message)" -ForegroundColor Red
        $results += @{
            status = "error"
            symbol = $token.symbol
            error = $_.Exception.Message
        }
    }
    
    if ($i -lt $tokensToScan.Count) {
        Start-Sleep -Seconds $Delay
    }
}

Write-Host ""
Write-Host "=" * 80
Write-Host "Batch Scan Summary"
Write-Host "=" * 80

$successful = $results | Where-Object { $_.status -eq "success" }
$failed = $results | Where-Object { $_.status -eq "error" }

Write-Host "Total Tokens: $($results.Count)"
Write-Host "Successful: $($successful.Count) ($([Math]::Round($successful.Count / $results.Count * 100, 1))%)"
Write-Host "Failed: $($failed.Count) ($([Math]::Round($failed.Count / $results.Count * 100, 1))%)"
Write-Host ""

if ($successful.Count -gt 0) {
    $sorted = $successful | Sort-Object -Property gem_score -Descending
    
    Write-Host "Top Performers by Gem Score:"
    Write-Host "-" * 80
    Write-Host ("{0,-6} {1,-8} {2,-8} {3,-12} {4,-10} {5}" -f "Rank", "Symbol", "Score", "Confidence", "Flagged", "Liquidity")
    Write-Host "-" * 80
    
    $rank = 1
    foreach ($result in $sorted) {
        $flagged = if ($result.flagged) { "🚩 Yes" } else { "No" }
        $liquidity = if ($result.liquidity_ok) { "✓" } else { "✗" }
        Write-Host ("{0,-6} {1,-8} {2,-8} {3,-12} {4,-10} {5}" -f $rank, $result.symbol, [Math]::Round($result.gem_score, 1), [Math]::Round($result.confidence, 1), $flagged, $liquidity)
        $rank++
    }
    
    Write-Host ""
    Write-Host "Statistics:"
    Write-Host "-" * 80
    $avgScore = ($successful | Measure-Object -Property gem_score -Average).Average
    $maxScore = ($successful | Measure-Object -Property gem_score -Maximum).Maximum
    $minScore = ($successful | Measure-Object -Property gem_score -Minimum).Minimum
    $avgConfidence = ($successful | Measure-Object -Property confidence -Average).Average
    $avgDuration = ($successful | Measure-Object -Property duration -Average).Average
    $totalDuration = ($successful | Measure-Object -Property duration -Sum).Sum
    
    Write-Host "Average Gem Score: $([Math]::Round($avgScore, 2))"
    Write-Host "Max Gem Score: $([Math]::Round($maxScore, 2))"
    Write-Host "Min Gem Score: $([Math]::Round($minScore, 2))"
    Write-Host "Average Confidence: $([Math]::Round($avgConfidence, 2))%"
    Write-Host "Average Scan Duration: $([Math]::Round($avgDuration, 2))s"
    Write-Host "Total Scan Time: $([Math]::Round($totalDuration, 2))s"
}

if ($failed.Count -gt 0) {
    Write-Host ""
    Write-Host "Failed Scans:"
    Write-Host "-" * 80
    foreach ($result in $failed) {
        Write-Host "  $($result.symbol): $($result.error)"
    }
}

Write-Host "=" * 80
