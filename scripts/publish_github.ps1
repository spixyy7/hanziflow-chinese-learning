param(
    [string]$RepositoryName = 'hanziflow-chinese-learning'
)

$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Set-Location -LiteralPath $projectRoot

if ($RepositoryName -notmatch '^[A-Za-z0-9_.-]+$') {
    throw 'Use a simple GitHub repository name.'
}
foreach ($command in @('git', 'gh')) {
    if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
        throw "Install $command before publishing."
    }
}
$pythonExecutable = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExecutable)) {
    $pythonExecutable = (Get-Command python -ErrorAction Stop).Source
}

# Remove only empty scratch directories from failed test setup.
foreach ($directory in (Get-ChildItem -LiteralPath $projectRoot -Directory -Filter 'hanziflow-test-*')) {
    $target = [IO.Path]::GetFullPath($directory.FullName)
    if (-not $target.StartsWith($projectRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Unexpected scratch-directory location.'
    }
    if (@(Get-ChildItem -LiteralPath $target -Force).Count -eq 0) {
        Remove-Item -LiteralPath $target -Force
    }
}

& $pythonExecutable -B -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Regression checks failed.' }
& $pythonExecutable -B scripts/check_public.py
if ($LASTEXITCODE -ne 0) { throw 'Remove private/generated files before publishing.' }

gh auth status
if ($LASTEXITCODE -ne 0) { throw 'Run gh auth login in your terminal, then retry.' }
$githubLogin = (gh api user --jq '.login').Trim()
if ($LASTEXITCODE -ne 0 -or -not $githubLogin) { throw 'Could not verify the GitHub account.' }

if (-not (Test-Path -LiteralPath (Join-Path $projectRoot '.git'))) {
    git init -b main
    if ($LASTEXITCODE -ne 0) { throw 'Could not initialize Git.' }
}
$remotes = @(git remote)
if ($LASTEXITCODE -ne 0) { throw 'Could not inspect Git remotes.' }
if ($remotes.Count -gt 0) {
    throw 'This script creates a new repository. Review existing remotes before pushing.'
}

git add -- .env.example .env.template .gitignore LICENSE README.md ARCHITECTURE.md SECURITY.md main.py requirements.txt build_exe.py HanziFlow.spec main.spec diagnose_fp.py hanziflow scripts tests
if ($LASTEXITCODE -ne 0) { throw 'Could not stage the reviewed source.' }
git diff --cached --check
if ($LASTEXITCODE -ne 0) { throw 'Staged whitespace checks failed.' }
git -c "user.name=$githubLogin" -c "user.email=$githubLogin@users.noreply.github.com" commit -m 'Preserve discontinued HanziFlow Python/Tkinter prototype with sanitized source'
if ($LASTEXITCODE -ne 0) { throw 'Could not create the source commit.' }

gh repo create "$githubLogin/$RepositoryName" --public --source . --remote origin --push --description 'HanziFlow - Chinese Learning App built with Python and Tkinter. Discontinued desktop prototype with unresolved bugs; development moved to a web project.'
if ($LASTEXITCODE -ne 0) { throw 'GitHub creation or push failed. Inspect git remote -v before retrying.' }
gh repo view "$githubLogin/$RepositoryName" --json url --jq '.url'
if ($LASTEXITCODE -ne 0) { throw 'Push completed, but the repository URL could not be verified.' }
