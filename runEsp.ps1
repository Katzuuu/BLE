param (
    [string]$Port = "COM3"
)

Push-Location -Path (Join-Path $PSScriptRoot 'esp32')

try {
    Write-Host "Uploading main.py to ESP32 on $Port..."

    # "resume" = skip the soft reset; with BLE active the soft reset can hang
    py -m mpremote connect $Port resume fs cp main.py :main.py

    if ($LASTEXITCODE -ne 0) {
        throw "Failed to upload main.py"
    }

    Write-Host "Restarting ESP32..."

    py -m mpremote connect $Port resume reset

    if ($LASTEXITCODE -ne 0) {
        throw "Failed to reset ESP32"
    }

    Write-Host "Connected to ESP32. Displaying logs..."
    Write-Host "Press Ctrl+C to exit."

    py -m mpremote connect $Port repl

    if ($LASTEXITCODE -ne 0) {
        throw "REPL connection failed"
    }
}
catch {
    Write-Error "An error occurred: $_"
    exit 1
}
finally {
    Pop-Location
}