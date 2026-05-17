# Start LexConnect Django admin on port 9000
Set-Location $PSScriptRoot\..
& ".\.venv\Scripts\python.exe" manage.py runadminserver @args
