@echo off
REM Step 1: Remove venv folders from Git tracking
git rm -r --cached venv
git rm -r --cached venv310

REM Step 2: Create or update .gitignore
echo venv/>.gitignore
echo venv310/>>.gitignore
echo __pycache__/>>.gitignore
echo *.pyd>>.gitignore
echo *.dll>>.gitignore
echo *.log>>.gitignore

git add .gitignore
git commit -m "Clean .gitignore and remove venv folders from repo"

REM Step 3: Run BFG to clean history (you must have Java + bfg-1.14.0.jar)
java -jar bfg-1.14.0.jar --delete-folders venv,venv310 --no-blob-protection

REM Step 4: Force Git to clean and compress objects
git reflog expire --expire=now --all
git gc --prune=now --aggressive

REM Step 5: Push clean repo to GitHub
git push --force origin main

echo DONE: Repository cleaned and pushed!
pause
