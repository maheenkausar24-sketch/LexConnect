# Start LexConnect public site on port 8000
Set-Location $PSScriptRoot\..
& ".\.venv\Scripts\python.exe" manage.py runserver @args
