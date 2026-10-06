$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'

$PKG_BASE = 'c:\Users\liulingyi\Desktop\象棋\android\.buildozer\android\platform\build-arm64-v8a_armeabi-v7a\packages'

function Get-Urls($url) {
    if ($url -like 'https://github.com/*') {
        return @(
            "https://ghproxy.com/$url",
            "https://gh.api.99988866.xyz/$url",
            $url
        )
    }
    return @($url)
}

$recipes = @(
    @{ name='libffi'; url='https://github.com/libffi/libffi/archive/v3.4.2.tar.gz'; file='v3.4.2.tar.gz' },
    @{ name='openssl'; url='https://www.openssl.org/source/openssl-3.3.1.tar.gz'; file='openssl-3.3.1.tar.gz' },
    @{ name='png'; url='https://github.com/glennrp/libpng/archive/v1.6.37.zip'; file='v1.6.37.zip' },
    @{ name='sdl2_image'; url='https://github.com/libsdl-org/SDL_image/releases/download/release-2.8.2/SDL2_image-2.8.2.tar.gz'; file='SDL2_image-2.8.2.tar.gz' },
    @{ name='sdl2_mixer'; url='https://github.com/libsdl-org/SDL_mixer/releases/download/release-2.6.3/SDL2_mixer-2.6.3.tar.gz'; file='SDL2_mixer-2.6.3.tar.gz' },
    @{ name='sdl2_ttf'; url='https://github.com/libsdl-org/SDL_ttf/releases/download/release-2.22.0/SDL2_ttf-2.22.0.tar.gz'; file='SDL2_ttf-2.22.0.tar.gz' },
    @{ name='sdl2'; url='https://github.com/libsdl-org/SDL/releases/download/release-2.28.5/SDL2-2.28.5.tar.gz'; file='SDL2-2.28.5.tar.gz' }
)

foreach ($r in $recipes) {
    $dir = Join-Path $PKG_BASE $r.name
    $dst = Join-Path $dir $r.file
    New-Item -ItemType Directory -Force -Path $dir | Out-Null

    if (Test-Path $dst) {
        $sz = (Get-Item $dst).Length
        if ($sz -gt 1000000) {
            Write-Host "[SKIP] $($r.name) -> $sz bytes"
            continue
        }
    }

    Get-ChildItem $dir -Filter '.mark-*' -Force -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

    $urls = Get-Urls $r.url
    $success = $false
    foreach ($u in $urls) {
        Write-Host "[DL]   $($r.name) from $u"
        try {
            Invoke-WebRequest -Uri $u -OutFile $dst -UseBasicParsing -TimeoutSec 180
            $sz = (Get-Item $dst).Length
            if ($sz -gt 1000000) {
                Write-Host "       OK $sz bytes"
                $success = $true
                break
            } else {
                Write-Host "       too small $sz bytes"
                Remove-Item $dst -Force -ErrorAction SilentlyContinue
            }
        } catch {
            Write-Host "       FAIL: $($_.Exception.Message)"
            Remove-Item $dst -Force -ErrorAction SilentlyContinue
        }
    }
    if (-not $success) {
        Write-Host "[GIVE UP] $($r.name)"
    }
}

Write-Host ""
Write-Host "Final state:"
Get-ChildItem $PKG_BASE -Directory | ForEach-Object {
    $n = $_.Name
    $real = $_.GetFiles() | Where-Object { -not $_.Name.StartsWith('.mark-') }
    if ($real) {
        "{0,-15} {1,10} bytes  {2}" -f $n, $real[0].Length, $real[0].Name
    } else {
        "{0,-15} (no real file)" -f $n
    }
}
