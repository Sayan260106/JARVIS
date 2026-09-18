param(
    [Parameter(Mandatory=$true)]
    [string]$ImagePath
)

try {
    [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime] | Out-Null
    [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics, ContentType = WindowsRuntime] | Out-Null
    [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime] | Out-Null
    Add-Type -AssemblyName System.Runtime.WindowsRuntime

    $fullPath = [System.IO.Path]::GetFullPath($ImagePath)
    if (-not (Test-Path $fullPath)) {
        Write-Error "Image file not found: $fullPath"
        exit 1
    }

    $asTaskGeneric = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and
        $_.GetParameters().Count -eq 1 -and
        $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
    }

    function Await-AsyncOp($asyncOp, $targetType) {
        $method = $asTaskGeneric.MakeGenericMethod($targetType)
        $task = $method.Invoke($null, @($asyncOp))
        $task.Wait()
        return $task.Result
    }

    $getFileOp = [Windows.Storage.StorageFile]::GetFileFromPathAsync($fullPath)
    $file = Await-AsyncOp $getFileOp ([Windows.Storage.StorageFile])

    $openOp = $file.OpenAsync([Windows.Storage.FileAccessMode]::Read)
    $stream = Await-AsyncOp $openOp ([Windows.Storage.Streams.IRandomAccessStream])

    $decoderOp = [Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)
    $decoder = Await-AsyncOp $decoderOp ([Windows.Graphics.Imaging.BitmapDecoder])

    $bitmapOp = $decoder.GetSoftwareBitmapAsync()
    $bitmap = Await-AsyncOp $bitmapOp ([Windows.Graphics.Imaging.SoftwareBitmap])

    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
    if ($engine -eq $null) {
        $lang = [Windows.Globalization.Language]::new("en-US")
        $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($lang)
    }

    $recognizeOp = $engine.RecognizeAsync($bitmap)
    $result = Await-AsyncOp $recognizeOp ([Windows.Media.Ocr.OcrResult])

    $linesList = @()
    foreach ($line in $result.Lines) {
        $wordsList = @()
        foreach ($w in $line.Words) {
            $wordsList += @{
                text = $w.Text
                x = [int]$w.BoundingRect.X
                y = [int]$w.BoundingRect.Y
                width = [int]$w.BoundingRect.Width
                height = [int]$w.BoundingRect.Height
            }
        }
        $linesList += @{
            text = $line.Text
            words = $wordsList
        }
    }

    $outputObj = @{
        success = $true
        text = $result.Text
        lines = $linesList
    }

    $stream.Dispose()
    ConvertTo-Json -InputObject $outputObj -Depth 5 -Compress
} catch {
    $errObj = @{
        success = $false
        error = $_.Exception.Message
    }
    ConvertTo-Json -InputObject $errObj -Compress
}
