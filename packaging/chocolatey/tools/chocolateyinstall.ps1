$ErrorActionPreference = 'Stop'

$toolsDir = Split-Path -Parent $MyInvocation.MyCommand.Definition

# The values below are substituted by the release workflow at
# package-build time, from that version's actual GitHub Release asset.
$url      = '__URL__'
$checksum = '__CHECKSUM__'

Install-ChocolateyZipPackage -PackageName 'quotabubble' `
  -Url $url `
  -UnzipLocation $toolsDir `
  -Checksum $checksum `
  -ChecksumType 'sha256'

Install-BinFile -Name 'quotabubble' -Path (Join-Path $toolsDir 'QuotaBubble.exe')
